from __future__ import annotations

import urllib.parse
from base64 import b64encode
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, TypeVar

from ._compression import get_compression, negotiate_compression
from ._envelope import EnvelopeWriter
from ._gen.status_pb2 import Status
from ._protocol import ConnectWireError, HTTPException
from .code import Code
from .request import Headers, RequestContext

if TYPE_CHECKING:
    from ._codec import Codec
    from ._compression import Compression
    from .method import MethodInfo

REQ = TypeVar("REQ")
RES = TypeVar("RES")

GRPC_CONTENT_TYPE_DEFAULT = "application/grpc"
GRPC_CONTENT_TYPE_PREFIX = f"{GRPC_CONTENT_TYPE_DEFAULT}+"

GRPC_HEADER_TIMEOUT = "grpc-timeout"
GRPC_HEADER_COMPRESSION = "grpc-encoding"
GRPC_HEADER_ACCEPT_COMPRESSION = "grpc-accept-encoding"


class GRPCServerProtocol:
    def create_request_context(
        self, method: MethodInfo[REQ, RES], http_method: str, headers: Headers
    ) -> RequestContext[REQ, RES]:
        if http_method != "POST":
            raise HTTPException(HTTPStatus.METHOD_NOT_ALLOWED, [("allow", "POST")])

        timeout_header = headers.get(GRPC_HEADER_TIMEOUT)
        timeout_ms = _parse_timeout(timeout_header) if timeout_header else None

        return RequestContext(
            method=method,
            http_method=http_method,
            request_headers=headers,
            timeout_ms=timeout_ms,
        )

    def create_envelope_writer(
        self, codec: Codec[RES, Any], compression: Compression | None
    ) -> EnvelopeWriter[RES]:
        return GRPCEnvelopeWriter(codec, compression)

    def uses_trailers(self) -> bool:
        return True

    def content_type(self, codec: Codec) -> str:
        return f"{GRPC_CONTENT_TYPE_PREFIX}{codec.name()}"

    def compression_header_name(self) -> str:
        return GRPC_HEADER_COMPRESSION

    def codec_name_from_content_type(self, content_type: str, *, stream: bool) -> str:
        if content_type.startswith(GRPC_CONTENT_TYPE_PREFIX):
            return content_type[len(GRPC_CONTENT_TYPE_PREFIX) :]
        return "proto"

    def negotiate_stream_compression(
        self, headers: Headers
    ) -> tuple[Compression | None, Compression]:
        req_compression_name = headers.get(GRPC_HEADER_COMPRESSION, "identity")
        req_compression = get_compression(req_compression_name)
        accept_compression = headers.get(GRPC_HEADER_ACCEPT_COMPRESSION, "")
        resp_compression = negotiate_compression(accept_compression)
        return req_compression, resp_compression


def _parse_timeout(timeout: str) -> int:
    # We normalize to int milliseconds matching connect's timeout header.
    value_to_ms = _lookup_timeout_unit(timeout[-1])
    try:
        value = int(timeout[:-1])
    except ValueError as e:
        msg = f"protocol error: invalid timeout '{timeout}'"
        raise ValueError(msg) from e

    # timeout must be ASCII string of at most 8 digits
    if value > 99999999:
        msg = f"protocol error: timeout '{timeout}' is too long"
        raise ValueError(msg)

    return int(value * value_to_ms)


def _lookup_timeout_unit(unit: str) -> float:
    match unit:
        case "H":
            return 60 * 60 * 1000
        case "M":
            return 60 * 1000
        case "S":
            return 1 * 1000
        case "m":
            return 1
        case "u":
            return 1 / 1000
        case "n":
            return 1 / 1000 / 1000
        case _:
            msg = f"protocol error: timeout has invalid unit '{unit}'"
            raise ValueError(msg)


class GRPCEnvelopeWriter(EnvelopeWriter):
    def end(self, user_trailers: Headers, error: ConnectWireError | None) -> Headers:
        trailers = Headers(list(user_trailers.allitems()))
        if error:
            status = _connect_status_to_grpc[error.code]
            trailers["grpc-status"] = status
            message = error.message
            if message:
                message = urllib.parse.quote(message, safe="")
                trailers["grpc-message"] = message
            if error.details:
                grpc_status = Status(
                    code=int(status), message=error.message, details=error.details
                )
                grpc_status_bin = (
                    b64encode(grpc_status.SerializeToString()).decode().rstrip("=")
                )
                trailers["grpc-status-details-bin"] = grpc_status_bin
        else:
            trailers["grpc-status"] = "0"
        return trailers


_connect_status_to_grpc = {
    Code.CANCELED: "1",
    Code.UNKNOWN: "2",
    Code.INVALID_ARGUMENT: "3",
    Code.DEADLINE_EXCEEDED: "4",
    Code.NOT_FOUND: "5",
    Code.ALREADY_EXISTS: "6",
    Code.PERMISSION_DENIED: "7",
    Code.RESOURCE_EXHAUSTED: "8",
    Code.FAILED_PRECONDITION: "9",
    Code.ABORTED: "10",
    Code.OUT_OF_RANGE: "11",
    Code.UNIMPLEMENTED: "12",
    Code.INTERNAL: "13",
    Code.UNAVAILABLE: "14",
    Code.DATA_LOSS: "15",
    Code.UNAUTHENTICATED: "16",
}
