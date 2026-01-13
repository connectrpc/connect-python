from __future__ import annotations

import json
import struct
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, TypeVar

from ._codec import CODEC_NAME_JSON, CODEC_NAME_JSON_CHARSET_UTF8, Codec
from ._compression import (
    IdentityCompression,
    get_accept_encoding,
    get_available_compressions,
    get_compression,
    negotiate_compression,
)
from ._envelope import EnvelopeReader, EnvelopeWriter
from ._protocol import ConnectWireError, HTTPException
from ._response_metadata import handle_response_trailers
from ._version import __version__
from .code import Code
from .errors import ConnectError
from .method import IdempotencyLevel, MethodInfo
from .request import Headers, RequestContext

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    import httpx

    from ._codec import Codec
    from ._compression import Compression

REQ = TypeVar("REQ")
RES = TypeVar("RES")

CONNECT_HEADER_PROTOCOL_VERSION = "connect-protocol-version"
CONNECT_PROTOCOL_VERSION = "1"
CONNECT_HEADER_TIMEOUT = "connect-timeout-ms"
CONNECT_UNARY_CONTENT_TYPE_PREFIX = "application/"
CONNECT_STREAMING_CONTENT_TYPE_PREFIX = "application/connect+"
CONNECT_UNARY_HEADER_COMPRESSION = "content-encoding"
CONNECT_UNARY_HEADER_ACCEPT_COMPRESSION = "accept-encoding"
CONNECT_STREAMING_HEADER_COMPRESSION = "connect-content-encoding"
CONNECT_STREAMING_HEADER_ACCEPT_COMPRESSION = "connect-accept-encoding"


_DEFAULT_CONNECT_USER_AGENT = f"connectrpc/{__version__}"


def codec_name_from_content_type(content_type: str, *, stream: bool) -> str:
    prefix = (
        CONNECT_STREAMING_CONTENT_TYPE_PREFIX
        if stream
        else CONNECT_UNARY_CONTENT_TYPE_PREFIX
    )
    if content_type.startswith(prefix):
        return content_type[len(prefix) :]
    # Follow connect-go behavior for malformed content type. If the content type misses the prefix,
    # it will still be coincidentally handled.
    return content_type


class ConnectServerProtocol:
    def create_request_context(
        self, method: MethodInfo[REQ, RES], http_method: str, headers: Headers
    ) -> RequestContext[REQ, RES]:
        if method.idempotency_level == IdempotencyLevel.NO_SIDE_EFFECTS:
            if http_method not in ("GET", "POST"):
                raise HTTPException(
                    HTTPStatus.METHOD_NOT_ALLOWED, [("allow", "GET, POST")]
                )
        elif http_method != "POST":
            raise HTTPException(HTTPStatus.METHOD_NOT_ALLOWED, [("allow", "POST")])

        # We don't require connect-protocol-version header. connect-go provides an option
        # to require it but it's almost never used in practice.
        connect_protocol_version = headers.get(
            CONNECT_HEADER_PROTOCOL_VERSION, CONNECT_PROTOCOL_VERSION
        )
        if connect_protocol_version != CONNECT_PROTOCOL_VERSION:
            raise ConnectError(
                Code.INVALID_ARGUMENT,
                f"connect-protocol-version must be '1': got '{connect_protocol_version}'",
            )

        timeout_header = headers.get(CONNECT_HEADER_TIMEOUT)
        if timeout_header:
            if len(timeout_header) > 10:
                raise ConnectError(
                    Code.INVALID_ARGUMENT,
                    f"Invalid timeout header: '{timeout_header} has >10 digits",
                )
            try:
                timeout_ms = int(timeout_header)
            except ValueError as e:
                raise ConnectError(
                    Code.INVALID_ARGUMENT, f"Invalid timeout header: '{timeout_header}'"
                ) from e
        else:
            timeout_ms = None
        return RequestContext(
            method=method,
            http_method=http_method,
            request_headers=headers,
            timeout_ms=timeout_ms,
        )

    def create_envelope_writer(
        self, codec: Codec[RES, Any], compression: Compression | None
    ) -> EnvelopeWriter[RES]:
        return ConnectEnvelopeWriter(codec, compression)

    def uses_trailers(self) -> bool:
        return False

    def content_type(self, codec: Codec) -> str:
        return f"{CONNECT_STREAMING_CONTENT_TYPE_PREFIX}{codec.name()}"

    def compression_header_name(self) -> str:
        return CONNECT_STREAMING_HEADER_COMPRESSION

    def codec_name_from_content_type(self, content_type: str, *, stream: bool) -> str:
        return codec_name_from_content_type(content_type, stream=stream)

    def negotiate_stream_compression(
        self, headers: Headers
    ) -> tuple[Compression, Compression]:
        req_compression_name = headers.get(
            CONNECT_STREAMING_HEADER_COMPRESSION, "identity"
        )
        req_compression = get_compression(req_compression_name) or IdentityCompression()
        accept_compression = headers.get(
            CONNECT_STREAMING_HEADER_ACCEPT_COMPRESSION, ""
        )
        resp_compression = negotiate_compression(accept_compression)
        return req_compression, resp_compression


class ConnectEnvelopeWriter(EnvelopeWriter):
    def end(self, user_trailers: Headers, error: ConnectWireError | None) -> bytes:
        end_message = {}
        if user_trailers:
            metadata: dict[str, list[str]] = {}
            for key, value in user_trailers.allitems():
                metadata.setdefault(key, []).append(value)
            end_message["metadata"] = metadata
        if error:
            end_message["error"] = error.to_dict()
        data = json.dumps(end_message).encode()
        if self._compression:
            data = self._compression.compress(data)
        return struct.pack(">BI", self._prefix | 0b10, len(data)) + data


class ConnectClientProtocol:
    def create_request_context(
        self,
        *,
        method: MethodInfo[REQ, RES],
        http_method: str,
        user_headers: Headers | Mapping[str, str] | None,
        timeout_ms: int | None,
        codec: Codec,
        stream: bool,
        accept_compression: Iterable[str] | None,
        send_compression: Compression | None,
    ) -> RequestContext[REQ, RES]:
        match user_headers:
            case Headers():
                # Copy to prevent modification if user keeps reference
                # TODO: Optimize
                headers = Headers(tuple(user_headers.allitems()))
            case None:
                headers = Headers()
            case _:
                headers = Headers(user_headers)

        if "user-agent" not in headers:
            headers["user-agent"] = _DEFAULT_CONNECT_USER_AGENT
        headers["connect-protocol-version"] = CONNECT_PROTOCOL_VERSION

        compression_header = (
            CONNECT_STREAMING_HEADER_COMPRESSION
            if stream
            else CONNECT_UNARY_HEADER_COMPRESSION
        )
        accept_compression_header = (
            CONNECT_STREAMING_HEADER_ACCEPT_COMPRESSION
            if stream
            else CONNECT_UNARY_HEADER_ACCEPT_COMPRESSION
        )

        if accept_compression is not None:
            headers[accept_compression_header] = ", ".join(accept_compression)
        else:
            headers[accept_compression_header] = get_accept_encoding()
        if send_compression is not None:
            headers[compression_header] = send_compression.name()
        else:
            headers.pop(compression_header, None)
        headers["content-type"] = (
            f"{CONNECT_STREAMING_CONTENT_TYPE_PREFIX if stream else CONNECT_UNARY_CONTENT_TYPE_PREFIX}{codec.name()}"
        )
        if timeout_ms is not None:
            headers["connect-timeout-ms"] = str(timeout_ms)

        return RequestContext(
            method=method,
            http_method=http_method,
            request_headers=headers,
            timeout_ms=timeout_ms,
        )

    def validate_response(
        self, request_codec_name: str, status_code: int, response_content_type: str
    ) -> None:
        if status_code != HTTPStatus.OK:
            # Error responses must be JSON-encoded
            if response_content_type in (
                f"{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{CODEC_NAME_JSON}",
                f"{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{CODEC_NAME_JSON_CHARSET_UTF8}",
            ):
                return
            raise ConnectWireError.from_http_status(status_code).to_exception()

        if not response_content_type.startswith(CONNECT_UNARY_CONTENT_TYPE_PREFIX):
            raise ConnectError(
                Code.UNKNOWN,
                f"invalid content-type: '{response_content_type}'; expecting '{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{request_codec_name}'",
            )

        response_codec_name = codec_name_from_content_type(
            response_content_type, stream=False
        )
        if response_codec_name == request_codec_name:
            return

        if (
            response_codec_name == CODEC_NAME_JSON
            and request_codec_name == CODEC_NAME_JSON_CHARSET_UTF8
        ) or (
            response_codec_name == CODEC_NAME_JSON_CHARSET_UTF8
            and request_codec_name == CODEC_NAME_JSON
        ):
            # Both are JSON
            return

        raise ConnectError(
            Code.INTERNAL,
            f"invalid content-type: '{response_content_type}'; expecting '{CONNECT_UNARY_CONTENT_TYPE_PREFIX}{request_codec_name}'",
        )

    def validate_stream_response(
        self, request_codec_name: str, response_content_type: str
    ) -> None:
        if not response_content_type.startswith(CONNECT_STREAMING_CONTENT_TYPE_PREFIX):
            raise ConnectError(
                Code.UNKNOWN,
                f"invalid content-type: '{response_content_type}'; expecting '{CONNECT_STREAMING_CONTENT_TYPE_PREFIX}{request_codec_name}'",
            )

        response_codec_name = response_content_type[
            len(CONNECT_STREAMING_CONTENT_TYPE_PREFIX) :
        ]
        if response_codec_name != request_codec_name:
            raise ConnectError(
                Code.INTERNAL,
                f"invalid content-type: '{response_content_type}'; expecting '{CONNECT_STREAMING_CONTENT_TYPE_PREFIX}{request_codec_name}'",
            )

    def handle_response_compression(
        self, headers: httpx.Headers, *, stream: bool
    ) -> Compression:
        compression_header = (
            CONNECT_STREAMING_HEADER_COMPRESSION
            if stream
            else CONNECT_UNARY_HEADER_COMPRESSION
        )
        encoding = headers.get(compression_header)
        if not encoding:
            return IdentityCompression()
        res = get_compression(encoding)
        if not res:
            raise ConnectError(
                Code.INTERNAL,
                f"unknown encoding '{encoding}'; accepted encodings are {', '.join(get_available_compressions())}",
            )
        return res

    def create_envelope_reader(
        self,
        message_class: type[RES],
        codec: Codec,
        compression: Compression,
        read_max_bytes: int | None,
    ) -> EnvelopeReader[RES]:
        return ConnectEnvelopeReader(message_class, codec, compression, read_max_bytes)


class ConnectEnvelopeReader(EnvelopeReader[RES]):
    def handle_end_message(
        self, prefix_byte: int, message_data: bytes | bytearray
    ) -> bool:
        end_stream = prefix_byte & 0b10 != 0
        if not end_stream:
            return False
        end_stream_message: dict = json.loads(message_data)
        metadata = end_stream_message.get("metadata")
        if metadata:
            handle_response_trailers(metadata)
        error = end_stream_message.get("error")
        if error:
            # Most likely a bug in the protocol, handling of unknown code is different for unary
            # and streaming.
            raise ConnectWireError.from_dict(error, 500, Code.UNKNOWN).to_exception()
        return True
