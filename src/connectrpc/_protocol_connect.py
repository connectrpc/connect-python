from __future__ import annotations

import json
import struct
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, TypeVar

from ._compression import IdentityCompression, get_compression, negotiate_compression
from ._envelope import EnvelopeWriter
from ._protocol import ConnectWireError, HTTPException
from .code import Code
from .errors import ConnectError
from .method import IdempotencyLevel, MethodInfo
from .request import Headers, RequestContext

if TYPE_CHECKING:
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
