from __future__ import annotations

import asyncio
import functools
from asyncio import CancelledError, sleep, wait_for
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

import httpx
from httpx import USE_CLIENT_DEFAULT, Timeout

from . import _client_shared
from ._asyncio_timeout import timeout as asyncio_timeout
from ._codec import Codec, get_proto_binary_codec, get_proto_json_codec
from ._interceptor_async import (
    BidiStreamInterceptor,
    ClientStreamInterceptor,
    Interceptor,
    ServerStreamInterceptor,
    UnaryInterceptor,
    resolve_interceptors,
)
from ._protocol import ConnectWireError
from ._protocol_connect import ConnectClientProtocol, ConnectEnvelopeWriter
from ._protocol_grpc import GRPCClientProtocol
from ._response_metadata import handle_response_headers
from .code import Code
from .errors import ConnectError

try:
    from asyncio import (
        timeout as asyncio_timeout,  # pyright: ignore[reportAttributeAccessIssue]
    )
except ImportError:
    from ._asyncio_timeout import timeout as asyncio_timeout

if TYPE_CHECKING:
    import sys
    from collections.abc import AsyncIterator, Iterable, Mapping
    from types import TracebackType

    from ._compression import Compression
    from ._envelope import EnvelopeReader
    from .method import MethodInfo
    from .request import Headers, RequestContext

    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self
else:
    Self = "Self"

REQ = TypeVar("REQ")
RES = TypeVar("RES")


class _ExecuteUnary(Protocol[REQ, RES]):
    async def __call__(self, request: REQ, ctx: RequestContext[REQ, RES]) -> RES: ...


class _ExecuteClientStream(Protocol[REQ, RES]):
    async def __call__(
        self, request: AsyncIterator[REQ], ctx: RequestContext[REQ, RES]
    ) -> RES: ...


class _ExecuteServerStream(Protocol[REQ, RES]):
    def __call__(
        self, request: REQ, ctx: RequestContext[REQ, RES]
    ) -> AsyncIterator[RES]: ...


class _ExecuteBidiStream(Protocol[REQ, RES]):
    def __call__(
        self, request: AsyncIterator[REQ], ctx: RequestContext[REQ, RES]
    ) -> AsyncIterator[RES]: ...


class ConnectClient:
    """An asynchronous client for the Connect protocol."""

    _execute_unary: _ExecuteUnary
    _execute_client_stream: _ExecuteClientStream
    _execute_server_stream: _ExecuteServerStream
    _execute_bidi_stream: _ExecuteBidiStream

    def __init__(
        self,
        address: str,
        *,
        proto_json: bool = False,
        grpc: bool = False,
        accept_compression: Iterable[str] | None = None,
        send_compression: str | None = None,
        timeout_ms: int | None = None,
        read_max_bytes: int | None = None,
        interceptors: Iterable[Interceptor] = (),
        session: httpx.AsyncClient | None = None,
    ) -> None:
        """Creates a new asynchronous Connect client.

        Args:
            address: The address of the server to connect to, including scheme.
            proto_json: Whether to use JSON for the protocol
            accept_compression: A list of compression algorithms to accept from the server
            send_compression: The compression algorithm to use for sending requests
            timeout_ms: The timeout for requests in milliseconds
            read_max_bytes: The maximum number of bytes to read from the response
            interceptors: A list of interceptors to apply to requests
            session: An httpx Client to use for requests
        """
        self._address = address
        self._codec = get_proto_json_codec() if proto_json else get_proto_binary_codec()
        self._accept_compression = accept_compression
        self._send_compression = _client_shared.resolve_send_compression(
            send_compression
        )
        self._timeout_ms = timeout_ms
        self._read_max_bytes = read_max_bytes
        if session:
            self._session = session
            self._close_client = False
        else:
            self._session = httpx.AsyncClient(
                timeout=_convert_connect_timeout(timeout_ms)
            )
            self._close_client = True
        self._closed = False

        if grpc:
            self._protocol = GRPCClientProtocol()
        else:
            self._protocol = ConnectClientProtocol()

        interceptors = resolve_interceptors(interceptors)
        execute_unary = self._send_request_unary
        for interceptor in (
            i for i in reversed(interceptors) if isinstance(i, UnaryInterceptor)
        ):
            execute_unary = functools.partial(
                interceptor.intercept_unary, execute_unary
            )
        self._execute_unary = execute_unary

        execute_client_stream = self._send_request_client_stream
        for interceptor in (
            i for i in reversed(interceptors) if isinstance(i, ClientStreamInterceptor)
        ):
            execute_client_stream = functools.partial(
                interceptor.intercept_client_stream, execute_client_stream
            )
        self._execute_client_stream = execute_client_stream

        execute_server_stream: _ExecuteServerStream = self._send_request_server_stream
        for interceptor in (
            i for i in reversed(interceptors) if isinstance(i, ServerStreamInterceptor)
        ):
            execute_server_stream = functools.partial(
                interceptor.intercept_server_stream, execute_server_stream
            )
        self._execute_server_stream = execute_server_stream

        execute_bidi_stream = self._send_request_bidi_stream
        for interceptor in (
            i for i in reversed(interceptors) if isinstance(i, BidiStreamInterceptor)
        ):
            execute_bidi_stream = functools.partial(
                interceptor.intercept_bidi_stream, execute_bidi_stream
            )
        self._execute_bidi_stream = execute_bidi_stream

    async def close(self) -> None:
        """Close the HTTP client. After closing, the client cannot be used to make requests."""
        if not self._closed:
            self._closed = True
            if self._close_client:
                await self._session.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def execute_unary(
        self,
        *,
        request: REQ,
        method: MethodInfo[REQ, RES],
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
        use_get: bool = False,
    ) -> RES:
        ctx = self._protocol.create_request_context(
            method=method,
            http_method="GET" if use_get else "POST",
            user_headers=headers,
            timeout_ms=timeout_ms or self._timeout_ms,
            codec=self._codec,
            stream=False,
            accept_compression=self._accept_compression,
            send_compression=self._send_compression,
        )
        return await self._execute_unary(request, ctx)

    async def execute_client_stream(
        self,
        *,
        request: AsyncIterator[REQ],
        method: MethodInfo[REQ, RES],
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> RES:
        ctx = self._protocol.create_request_context(
            method=method,
            http_method="POST",
            user_headers=headers,
            timeout_ms=timeout_ms or self._timeout_ms,
            codec=self._codec,
            stream=True,
            accept_compression=self._accept_compression,
            send_compression=self._send_compression,
        )
        return await self._execute_client_stream(request, ctx)

    def execute_server_stream(
        self,
        *,
        request: REQ,
        method: MethodInfo[REQ, RES],
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> AsyncIterator[RES]:
        ctx = self._protocol.create_request_context(
            method=method,
            http_method="POST",
            user_headers=headers,
            timeout_ms=timeout_ms or self._timeout_ms,
            codec=self._codec,
            stream=True,
            accept_compression=self._accept_compression,
            send_compression=self._send_compression,
        )
        return self._execute_server_stream(request, ctx)

    def execute_bidi_stream(
        self,
        *,
        request: AsyncIterator[REQ],
        method: MethodInfo[REQ, RES],
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> AsyncIterator[RES]:
        ctx = self._protocol.create_request_context(
            method=method,
            http_method="POST",
            user_headers=headers,
            timeout_ms=timeout_ms or self._timeout_ms,
            codec=self._codec,
            stream=True,
            accept_compression=self._accept_compression,
            send_compression=self._send_compression,
        )
        return self._execute_bidi_stream(request, ctx)

    async def _send_request_unary(
        self, request: REQ, ctx: RequestContext[REQ, RES]
    ) -> RES:
        if isinstance(self._protocol, GRPCClientProtocol):
            return await _consume_single_response(
                self._send_request_bidi_stream(_yield_single_message(request), ctx)
            )

        request_headers = httpx.Headers(list(ctx.request_headers().allitems()))
        url = f"{self._address}/{ctx.method().service_name}/{ctx.method().name}"
        if (timeout_ms := ctx.timeout_ms()) is not None:
            timeout_s = timeout_ms / 1000.0
            timeout = _convert_connect_timeout(timeout_ms)
        else:
            timeout_s = None
            timeout = USE_CLIENT_DEFAULT

        try:
            request_data = self._codec.encode(request)
            if self._send_compression:
                request_data = self._send_compression.compress(request_data)

            if ctx.http_method() == "GET":
                params = _client_shared.prepare_get_params(
                    self._codec, request_data, request_headers
                )
                request_headers.pop("content-type", None)
                resp = await wait_for(
                    self._session.get(
                        url=url, headers=request_headers, params=params, timeout=timeout
                    ),
                    timeout_s,
                )
            else:
                resp = await wait_for(
                    self._session.post(
                        url=url,
                        headers=request_headers,
                        content=request_data,
                        timeout=timeout,
                    ),
                    timeout_s,
                )

            self._protocol.validate_response(
                self._codec.name(),
                resp.status_code,
                resp.headers.get("content-type", ""),
            )
            # Decompression itself is handled by httpx, but we validate it
            # by resolving it.
            self._protocol.handle_response_compression(resp.headers, stream=False)
            handle_response_headers(resp.headers)

            if resp.status_code == 200:
                if (
                    self._read_max_bytes is not None
                    and len(resp.content) > self._read_max_bytes
                ):
                    raise ConnectError(
                        Code.RESOURCE_EXHAUSTED,
                        f"message is larger than configured max {self._read_max_bytes}",
                    )

                response = ctx.method().output()
                self._codec.decode(resp.content, response)
                return response
            raise ConnectWireError.from_response(resp).to_exception()
        except (httpx.TimeoutException, TimeoutError, asyncio.TimeoutError) as e:
            raise ConnectError(Code.DEADLINE_EXCEEDED, "Request timed out") from e
        except ConnectError:
            raise
        except CancelledError as e:
            raise ConnectError(Code.CANCELED, "Request was cancelled") from e
        except Exception as e:
            raise ConnectError(Code.UNAVAILABLE, str(e)) from e

    async def _send_request_client_stream(
        self, request: AsyncIterator[REQ], ctx: RequestContext[REQ, RES]
    ) -> RES:
        return await _consume_single_response(
            self._send_request_bidi_stream(request, ctx)
        )

    def _send_request_server_stream(
        self, request: REQ, ctx: RequestContext[REQ, RES]
    ) -> AsyncIterator[RES]:
        return self._send_request_bidi_stream(_yield_single_message(request), ctx)

    async def _send_request_bidi_stream(
        self, request: AsyncIterator[REQ], ctx: RequestContext[REQ, RES]
    ) -> AsyncIterator[RES]:
        request_headers = httpx.Headers(list(ctx.request_headers().allitems()))
        url = f"{self._address}/{ctx.method().service_name}/{ctx.method().name}"
        if (timeout_ms := ctx.timeout_ms()) is not None:
            timeout_s = timeout_ms / 1000.0
            timeout = _convert_connect_timeout(timeout_ms)
        else:
            timeout_s = None
            timeout = USE_CLIENT_DEFAULT

        reader: EnvelopeReader | None = None
        resp: httpx.Response | None = None
        try:
            request_data = _streaming_request_content(
                request, self._codec, self._send_compression
            )

            async with asyncio_timeout(timeout_s):
                httpx_req = self._session.build_request(
                    method="POST",
                    url=url,
                    headers=request_headers,
                    content=request_data,
                    timeout=timeout,
                )
                resp = await self._session.send(httpx_req, stream=True)
                try:
                    handle_response_headers(resp.headers)
                    if resp.status_code == 200:
                        self._protocol.validate_stream_response(
                            self._codec.name(), resp.headers.get("content-type", "")
                        )
                        compression = self._protocol.handle_response_compression(
                            resp.headers, stream=True
                        )
                        reader = self._protocol.create_envelope_reader(
                            ctx.method().output,
                            self._codec,
                            compression,
                            self._read_max_bytes,
                        )
                        async for chunk in resp.aiter_bytes():
                            for message in reader.feed(chunk):
                                yield message
                                # Check for cancellation each message. While this seems heavyweight,
                                # conformance tests require it.
                                await sleep(0)
                        reader.handle_response_complete(resp)
                    else:
                        raise ConnectWireError.from_response(resp).to_exception()
                finally:
                    await asyncio.shield(resp.aclose())
        except (httpx.TimeoutException, TimeoutError, asyncio.TimeoutError) as e:
            raise ConnectError(Code.DEADLINE_EXCEEDED, "Request timed out") from e
        except ConnectError:
            raise
        except CancelledError as e:
            raise ConnectError(Code.CANCELED, "Request was cancelled") from e
        except Exception as e:
            if rst_err := _client_shared.maybe_map_stream_reset(e, ctx):
                # It is possible for a reset to come with trailers which should
                # be used.
                if reader and resp:
                    reader.handle_response_complete(resp, rst_err)
                raise rst_err from e
            raise ConnectError(Code.UNAVAILABLE, str(e)) from e


def _convert_connect_timeout(timeout_ms: float | None) -> Timeout:
    if timeout_ms is None:
        # If no timeout provided, match connect-go's default behavior of a 30s connect timeout
        # and no read/write timeouts.
        return Timeout(None, connect=30.0)
    # We apply the timeout to the entire operation per connect's semantics so don't need
    # HTTP timeout
    return Timeout(None)


async def _streaming_request_content(
    msgs: AsyncIterator[Any], codec: Codec, compression: Compression | None
) -> AsyncIterator[bytes]:
    writer = ConnectEnvelopeWriter(codec, compression)
    async for msg in msgs:
        yield writer.write(msg)


async def _yield_single_message(message: REQ) -> AsyncIterator[REQ]:
    yield message


async def _consume_single_response(stream: AsyncIterator[RES]) -> RES:
    res = None
    async for message in stream:
        if res is not None:
            raise ConnectError(
                Code.UNIMPLEMENTED, "unary response has multiple messages"
            )
        res = message
    if res is None:
        raise ConnectError(Code.UNIMPLEMENTED, "unary response has zero messages")
    return res
