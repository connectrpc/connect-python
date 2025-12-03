from __future__ import annotations

import base64
import functools
import inspect
from abc import ABC, abstractmethod
from asyncio import CancelledError, sleep
from dataclasses import replace
from http import HTTPStatus
from typing import TYPE_CHECKING, Generic, TypeVar, cast
from urllib.parse import parse_qs

from . import _compression, _server_shared
from ._codec import Codec, get_codec
from ._envelope import EnvelopeReader, EnvelopeWriter
from ._interceptor_async import (
    BidiStreamInterceptor,
    ClientStreamInterceptor,
    Interceptor,
    ServerStreamInterceptor,
    UnaryInterceptor,
    resolve_interceptors,
)
from ._protocol import (
    CONNECT_STREAMING_CONTENT_TYPE_PREFIX,
    CONNECT_STREAMING_HEADER_ACCEPT_COMPRESSION,
    CONNECT_STREAMING_HEADER_COMPRESSION,
    CONNECT_UNARY_CONTENT_TYPE_PREFIX,
    ConnectWireError,
    HTTPException,
    codec_name_from_content_type,
)
from ._server_shared import (
    EndpointBidiStream,
    EndpointClientStream,
    EndpointServerStream,
    EndpointUnary,
)
from .code import Code
from .errors import ConnectError
from .request import Headers, RequestContext

if TYPE_CHECKING:
    # We don't use asgiref code so only import from it for type checking
    from collections.abc import (
        AsyncGenerator,
        AsyncIterator,
        Callable,
        Iterable,
        Mapping,
        Sequence,
    )

    from asgiref.typing import ASGIReceiveCallable, ASGISendCallable, HTTPScope, Scope
else:
    ASGIReceiveCallable = "asgiref.typing.ASGIReceiveCallable"
    ASGISendCallable = "asgiref.typing.ASGISendCallable"
    HTTPScope = "asgiref.typing.HTTPScope"
    Scope = "asgiref.typing.Scope"


_SVC = TypeVar("_SVC")
_REQ = TypeVar("_REQ")
_RES = TypeVar("_RES")

# We don't mutate query params so use a singleton for when they're not set.
_UNSET_QUERY_PARAMS: dict[str, list[str]] = {}

# While _server_shared.Endpoint is a closed type, we can't indicate that to Python so define
# a more precise type here.
Endpoint = (
    EndpointBidiStream[_REQ, _RES]
    | EndpointClientStream[_REQ, _RES]
    | EndpointServerStream[_REQ, _RES]
    | EndpointUnary[_REQ, _RES]
)


class ConnectASGIApplication(ABC, Generic[_SVC]):
    """An ASGI application for the Connect protocol."""

    _resolved_endpoints: Mapping[str, Endpoint] | None

    @property
    @abstractmethod
    def path(self) -> str: ...

    def __init__(
        self,
        *,
        service: _SVC | AsyncGenerator[_SVC],
        endpoints: Callable[[_SVC], Mapping[str, Endpoint]],
        interceptors: Iterable[Interceptor] = (),
        read_max_bytes: int | None = None,
    ) -> None:
        """Initialize the ASGI application."""
        super().__init__()
        self._service = service
        self._endpoints = endpoints
        self._interceptors = interceptors
        self._resolved_endpoints = None
        self._read_max_bytes = read_max_bytes

    async def __call__(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        if scope["type"] == "websocket":
            msg = "connect does not support websockets"
            raise RuntimeError(msg)

        if scope["type"] == "lifespan":
            service_iter = None
            while True:
                msg = await receive()
                match msg["type"]:
                    case "lifespan.startup":
                        # Need to cast since type checking doesn't seem to narrow well with isasyncgen
                        if inspect.isasyncgen(self._service):
                            service_iter = cast(
                                "AsyncGenerator[_SVC, None]", self._service
                            )
                            try:
                                service = await anext(service_iter)
                            except Exception as e:
                                await send(
                                    {
                                        "type": "lifespan.startup.failed",
                                        "message": str(e),
                                    }
                                )
                                return None
                        else:
                            service = cast("_SVC", self._service)
                        self._resolved_endpoints = self._resolve_endpoints(service)
                        await send({"type": "lifespan.startup.complete"})
                    case "lifespan.shutdown":
                        if service_iter is not None:
                            try:
                                await service_iter.aclose()
                            except Exception as e:
                                await send(
                                    {
                                        "type": "lifespan.shutdown.failed",
                                        "message": str(e),
                                    }
                                )
                                return None
                        await send({"type": "lifespan.shutdown.complete"})
                        return None

        if not self._resolved_endpoints:
            if inspect.isasyncgen(self._service):
                msg = "ASGI server does not support lifespan but async generator passed for service. Enable lifespan support."
                raise RuntimeError(msg)

            self._resolved_endpoints = self._resolve_endpoints(
                cast("_SVC", self._service)
            )
        endpoints = self._resolved_endpoints

        ctx: RequestContext | None = None
        try:
            path = scope["path"]
            endpoint = endpoints.get(path)
            if not endpoint and scope["root_path"]:
                # The application was mounted at some root so try stripping the prefix.
                path = path.removeprefix(scope["root_path"])
                endpoint = endpoints.get(path)
            if not endpoint:
                raise HTTPException(HTTPStatus.NOT_FOUND, [])

            http_method = scope["method"]
            headers = _process_headers(scope.get("headers", ()))

            ctx = _server_shared.create_request_context(
                endpoint.method, http_method, headers
            )

            is_unary = isinstance(endpoint, EndpointUnary)

            if http_method == "GET":
                query_string = scope.get("query_string", b"").decode("utf-8")
                query_params = parse_qs(query_string)
                codec_name = query_params.get("encoding", ("",))[0]
            else:
                query_params = _UNSET_QUERY_PARAMS
                codec_name = codec_name_from_content_type(
                    headers.get("content-type", ""), stream=not is_unary
                )
            codec = get_codec(codec_name.lower())
            if not codec:
                raise HTTPException(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    [("Accept-Post", "application/json, application/proto")],
                )

            if is_unary:
                return await self._handle_unary(
                    http_method,
                    headers,
                    codec,
                    query_params,
                    endpoint,
                    receive,
                    send,
                    ctx,
                )
        except Exception as e:
            return await self._handle_error(e, ctx, send)

        # Streams have their own error handling so move out of the try block.
        return await self._handle_stream(receive, send, endpoint, codec, headers, ctx)

    async def _handle_unary(
        self,
        http_method: str,
        headers: Headers,
        codec: Codec,
        query_params: dict[str, list[str]],
        endpoint: EndpointUnary[_REQ, _RES],
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
        ctx: RequestContext,
    ) -> None:
        accept_encoding = headers.get("accept-encoding", "")
        compression = _compression.negotiate_compression(accept_encoding)

        if http_method == "GET":
            request = await self._read_get_request(endpoint, codec, query_params)
        else:
            request = await self._read_post_request(endpoint, receive, codec, headers)

        response_data = await endpoint.function(request, ctx)

        res_bytes = codec.encode(response_data)
        response_headers: list[tuple[bytes, bytes]] = [
            (
                b"content-type",
                f"{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{codec.name()}".encode(),
            )
        ]
        res_bytes = compression.compress(res_bytes)
        response_headers.append((b"content-encoding", compression.name().encode()))
        response_headers.append((b"vary", b"Accept-Encoding"))

        _add_context_headers(response_headers, ctx)

        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": response_headers,
                "trailers": False,
            }
        )
        await send(
            {"type": "http.response.body", "body": res_bytes, "more_body": False}
        )

    async def _read_get_request(
        self,
        endpoint: EndpointUnary[_REQ, _RES],
        codec: Codec,
        params: dict[str, list[str]],
    ) -> _REQ:
        """Handle GET request with query parameters."""
        # Validation
        if "message" not in params:
            raise ConnectError(
                Code.INVALID_ARGUMENT,
                "'message' parameter is required for GET requests",
            )

        # Get and decode message
        message = params["message"][0]
        is_base64 = "base64" in params and params["base64"][0] == "1"

        if is_base64:
            try:
                message = base64.urlsafe_b64decode(message + "===")
            except Exception as e:
                raise ConnectError(
                    Code.INVALID_ARGUMENT, "Invalid base64 encoding"
                ) from e
        else:
            message = message.encode("utf-8")

        # Handle compression
        compression_name = params.get("compression", ["identity"])[0]
        compression = _compression.get_compression(compression_name)
        if not compression:
            raise ConnectError(
                Code.UNIMPLEMENTED,
                f"unknown compression: '{compression_name}': supported encodings are {', '.join(_compression.get_available_compressions())}",
            )

        # Decompress and decode message
        if message:  # Don't decompress empty messages
            message = compression.decompress(message)

        # Get the appropriate decoder for the endpoint
        return codec.decode(message, endpoint.method.input())

    async def _read_post_request(
        self,
        endpoint: Endpoint[_REQ, _RES],
        receive: ASGIReceiveCallable,
        codec: Codec,
        headers: Headers,
    ) -> _REQ:
        """Handle POST request with body."""

        # Get request body
        chunks: list[bytes] = [chunk async for chunk in _read_body(receive)]
        req_body = b"".join(chunks)

        # Handle compression if specified
        compression_name = headers.get("content-encoding", "identity").lower()
        compression = _compression.get_compression(compression_name)
        if not compression:
            raise ConnectError(
                Code.UNIMPLEMENTED,
                f"unknown compression: '{compression_name}': supported encodings are {', '.join(_compression.get_available_compressions())}",
            )

        if req_body:  # Don't decompress empty body
            req_body = compression.decompress(req_body)

        if self._read_max_bytes is not None and len(req_body) > self._read_max_bytes:
            raise ConnectError(
                Code.RESOURCE_EXHAUSTED,
                f"message is larger than configured max {self._read_max_bytes}",
            )

        return codec.decode(req_body, endpoint.method.input())

    async def _handle_stream(
        self,
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
        endpoint: EndpointBidiStream[_REQ, _RES]
        | EndpointClientStream[_REQ, _RES]
        | EndpointServerStream[_REQ, _RES],
        codec: Codec,
        headers: Headers,
        ctx: _server_shared.RequestContext,
    ) -> None:
        req_compression_name = headers.get(
            CONNECT_STREAMING_HEADER_COMPRESSION, "identity"
        )
        req_compression = (
            _compression.get_compression(req_compression_name)
            or _compression.IdentityCompression()
        )
        accept_compression = headers.get(
            CONNECT_STREAMING_HEADER_ACCEPT_COMPRESSION, ""
        )
        response_compression = _compression.negotiate_compression(accept_compression)

        writer = EnvelopeWriter(codec, response_compression)

        error: Exception | None = None
        sent_headers = False
        try:
            request_stream = _request_stream(
                receive,
                endpoint.method.input,
                codec,
                req_compression,
                self._read_max_bytes,
            )

            match endpoint:
                case EndpointClientStream():
                    response = await endpoint.function(request_stream, ctx)
                    response_stream = _yield_single_response(response)
                case EndpointServerStream():
                    request = await _consume_single_request(request_stream)
                    response_stream = endpoint.function(request, ctx)
                case EndpointBidiStream():
                    response_stream = endpoint.function(request_stream, ctx)

            async for message in response_stream:
                # Don't send headers until the first message to allow logic a chance to add
                # response headers.
                if not sent_headers:
                    await _send_stream_response_headers(
                        send, codec, response_compression.name(), ctx
                    )
                    sent_headers = True

                body = writer.write(message)
                await send(
                    {"type": "http.response.body", "body": body, "more_body": True}
                )
        except CancelledError as e:
            raise ConnectError(Code.CANCELED, "Request was cancelled") from e
        except Exception as e:
            error = e
        finally:
            if not sent_headers:
                # Exception before any response message is returned
                await _send_stream_response_headers(
                    send, codec, response_compression.name(), ctx
                )
            await send(
                {
                    "type": "http.response.body",
                    "body": writer.end(
                        ctx.response_trailers(),
                        ConnectWireError.from_exception(error) if error else None,
                    ),
                    "more_body": False,
                }
            )

    async def _handle_error(
        self, exc: Exception, ctx: RequestContext | None, send: ASGISendCallable
    ) -> None:
        """Handle errors that occur during request processing."""
        headers: list[tuple[bytes, bytes]]
        body: bytes
        status: int
        if isinstance(exc, HTTPException):
            status = exc.status.value
            headers = [(k.encode("utf-8"), v.encode("utf-8")) for k, v in exc.headers]
            body = b""
        else:
            wire_error = ConnectWireError.from_exception(exc)
            status = wire_error.to_http_status().code
            headers = [(b"content-type", b"application/json")]
            body = wire_error.to_json_bytes()

        if ctx:
            _add_context_headers(headers, ctx)

        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
                "trailers": False,
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})

    def _resolve_endpoints(self, service: _SVC) -> Mapping[str, Endpoint]:
        resolved_endpoints = self._endpoints(service)
        if self._interceptors:
            resolved_endpoints = {
                path: _apply_interceptors(
                    endpoint, resolve_interceptors(self._interceptors)
                )
                for path, endpoint in resolved_endpoints.items()
            }
        return resolved_endpoints


async def _send_stream_response_headers(
    send: ASGISendCallable, codec: Codec, compression_name: str, ctx: RequestContext
) -> None:
    response_headers = [
        (
            b"content-type",
            f"{CONNECT_STREAMING_CONTENT_TYPE_PREFIX}{codec.name()}".encode(),
        ),
        (CONNECT_STREAMING_HEADER_COMPRESSION.encode(), compression_name.encode()),
    ]
    response_headers.extend(
        (key.encode(), value.encode())
        for key, value in ctx.response_headers().allitems()
    )
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": response_headers,
            "trailers": False,
        }
    )


async def _request_stream(
    receive: ASGIReceiveCallable,
    request_class: type[_REQ],
    codec: Codec,
    compression: _compression.Compression,
    read_max_bytes: int | None = None,
) -> AsyncIterator[_REQ]:
    reader = EnvelopeReader(request_class, codec, compression, read_max_bytes)
    try:
        async for chunk in _read_body(receive):
            for message in reader.feed(chunk):
                yield message
                # Check for cancellation each message. While this seems heavyweight,
                # conformance tests require it.
                await sleep(0)
    except CancelledError as e:
        raise ConnectError(Code.CANCELED, "Request was cancelled") from e


async def _read_body(receive: ASGIReceiveCallable) -> AsyncIterator[bytes]:
    """Read the body of the request."""
    while True:
        message = await receive()
        match message["type"]:
            case "http.request":
                body = message.get("body", b"")
                yield body
                if not message.get("more_body", False):
                    return
            case "http.disconnect":
                raise ConnectError(
                    Code.CANCELED, "Client disconnected before request completion"
                )
            case _:
                raise ConnectError(Code.UNKNOWN, "Unexpected message type")


async def _consume_single_request(stream: AsyncIterator[_REQ]) -> _REQ:
    req = None
    async for message in stream:
        if req is not None:
            raise ConnectError(
                Code.UNIMPLEMENTED, "unary request has multiple messages"
            )
        req = message
    if req is None:
        raise ConnectError(Code.UNIMPLEMENTED, "unary request has zero messages")
    return req


async def _yield_single_response(response: _RES) -> AsyncIterator[_RES]:
    yield response


def _process_headers(iterable: Iterable[tuple[bytes, bytes]]) -> Headers:
    result = Headers()
    for key, value in iterable:
        result.add(key.decode(), value.decode())
    return result


def _add_context_headers(
    headers: list[tuple[bytes, bytes]], ctx: RequestContext
) -> None:
    headers.extend(
        (key.encode(), value.encode())
        for key, value in ctx.response_headers().allitems()
    )
    headers.extend(
        (f"trailer-{key}".encode(), value.encode())
        for key, value in ctx.response_trailers().allitems()
    )


def _apply_interceptors(
    endpoint: Endpoint[_REQ, _RES], interceptors: Sequence[Interceptor]
) -> Endpoint[_REQ, _RES]:
    match endpoint:
        case EndpointUnary():
            func = endpoint.function
            for interceptor in reversed(interceptors):
                if not isinstance(interceptor, UnaryInterceptor):
                    continue
                func = functools.partial(interceptor.intercept_unary, func)
            return replace(endpoint, function=func)
        case EndpointClientStream():
            func = endpoint.function
            for interceptor in reversed(interceptors):
                if not isinstance(interceptor, ClientStreamInterceptor):
                    continue
                func = functools.partial(interceptor.intercept_client_stream, func)
            return replace(endpoint, function=func)
        case EndpointServerStream():
            func = endpoint.function
            for interceptor in reversed(interceptors):
                if not isinstance(interceptor, ServerStreamInterceptor):
                    continue
                func = functools.partial(interceptor.intercept_server_stream, func)
            return replace(endpoint, function=func)
        case EndpointBidiStream():
            func = endpoint.function
            for interceptor in reversed(interceptors):
                if not isinstance(interceptor, BidiStreamInterceptor):
                    continue
                func = functools.partial(interceptor.intercept_bidi_stream, func)
            return replace(endpoint, function=func)
