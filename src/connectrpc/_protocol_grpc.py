from __future__ import annotations

import sys
import urllib.parse
from base64 import b64decode, b64encode
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, TypeVar

from ._compression import (
    IdentityCompression,
    get_accept_encoding,
    get_available_compressions,
    get_compression,
    negotiate_compression,
)
from ._envelope import EnvelopeReader, EnvelopeWriter
from ._gen.status_pb2 import Status
from ._protocol import ConnectWireError, HTTPException
from ._response_metadata import handle_response_trailers
from ._version import __version__
from .code import Code
from .errors import ConnectError
from .request import Headers, RequestContext

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    import httpx

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

_DEFAULT_GRPC_USER_AGENT = f"grpc-python-connect/{__version__} ({sys.version})"


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


class GRPCClientProtocol:
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
        headers["te"] = "trailers"
        if "user-agent" not in headers:
            headers["user-agent"] = _DEFAULT_GRPC_USER_AGENT

        if accept_compression is not None:
            headers[GRPC_HEADER_ACCEPT_COMPRESSION] = ",".join(accept_compression)
        else:
            headers[GRPC_HEADER_ACCEPT_COMPRESSION] = get_accept_encoding()
        if send_compression is not None:
            headers[GRPC_HEADER_COMPRESSION] = send_compression.name()
        else:
            headers.pop(GRPC_HEADER_COMPRESSION, None)
        headers["content-type"] = f"{GRPC_CONTENT_TYPE_PREFIX}{codec.name()}"
        if timeout_ms is not None:
            headers[GRPC_HEADER_TIMEOUT] = _serialize_timeout(timeout_ms)

        return RequestContext(
            method=method,
            http_method=http_method,
            request_headers=headers,
            timeout_ms=timeout_ms,
        )

    def validate_response(
        self, request_codec_name: str, status_code: int, response_content_type: str
    ) -> None:
        raise NotImplementedError

    def validate_stream_response(
        self, request_codec_name: str, response_content_type: str
    ) -> None:
        if not (
            response_content_type == GRPC_CONTENT_TYPE_DEFAULT
            or response_content_type.startswith(GRPC_CONTENT_TYPE_PREFIX)
        ):
            raise ConnectError(
                Code.UNKNOWN,
                f"invalid content-type: '{response_content_type}'; expecting '{GRPC_CONTENT_TYPE_PREFIX}{request_codec_name}'",
            )
        if response_content_type.startswith(GRPC_CONTENT_TYPE_PREFIX):
            response_codec_name = response_content_type[len(GRPC_CONTENT_TYPE_PREFIX) :]
        else:
            response_codec_name = "proto"
        if response_codec_name != request_codec_name:
            raise ConnectError(
                Code.INTERNAL,
                f"invalid content-type: '{response_content_type}'; expecting '{GRPC_CONTENT_TYPE_PREFIX}{request_codec_name}'",
            )

    def handle_response_compression(
        self, headers: httpx.Headers, *, stream: bool
    ) -> Compression:
        encoding = headers.get(GRPC_HEADER_COMPRESSION)
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
        return GRPCEnvelopeReader(message_class, codec, compression, read_max_bytes)


class GRPCEnvelopeReader(EnvelopeReader[RES]):
    def __init__(
        self,
        message_class: type[RES],
        codec: Codec,
        compression: Compression,
        read_max_bytes: int | None,
    ) -> None:
        super().__init__(message_class, codec, compression, read_max_bytes)
        self._read_message = False

    def handle_end_message(
        self, prefix_byte: int, message_data: bytes | bytearray
    ) -> bool:
        # It's coincidence that this method is called when there is a body and not
        # when there isn't. Somewhat hacky, but easiest way to handle the case
        # where there is a body and no trailers, which conformance tests verify.
        self._read_message = True
        return False

    def handle_response_complete(
        self, response: httpx.Response, e: ConnectError | None = None
    ) -> None:
        get_trailers = response.extensions.get("get_trailers")
        if not get_trailers:
            msg = "gRPC client support requires using an HTTPX-compatible client that supports trailers"
            raise RuntimeError(msg)
        # Go ahead and feed HTTP trailers regardless of gRPC semantics.
        trailers: httpx.Headers = get_trailers()
        handle_response_trailers({k: trailers.get_list(k) for k in trailers})

        # Now handle gRPC trailers. They are either the HTTP trailers if there was body present
        # or HTTP headers if there was no body.
        grpc_status = trailers.get("grpc-status")
        if grpc_status is None:
            # If there was a body message, we do not read response headers
            if self._read_message:
                raise e or ConnectError(Code.INTERNAL, "missing grpc-status trailer")
            trailers = response.headers

        grpc_status = trailers.get("grpc-status")
        if grpc_status is None:
            raise e or ConnectError(Code.INTERNAL, "missing grpc-status trailer")

        # e is present for RST_STREAM. We prioritize its code while reading message and details
        # from trailers when available.
        code = e.code if e else None
        if grpc_status != "0":
            message = trailers.get("grpc-message", "")
            if grpc_status_details := trailers.get("grpc-status-details-bin"):
                status = Status()
                status.ParseFromString(b64decode(grpc_status_details + "==="))
                connect_code = code or _grpc_status_to_connect.get(
                    str(status.code), Code.UNKNOWN
                )
                raise ConnectError(connect_code, status.message, details=status.details)
            connect_code = code or _grpc_status_to_connect.get(
                grpc_status, Code.UNKNOWN
            )
            raise ConnectError(connect_code, urllib.parse.unquote(message))


_GRPC_TIMEOUT_MAX_VALUE = 1e8


def _serialize_timeout(timeout_ms: int) -> str:
    if timeout_ms <= 0:
        return "0n"

    # The gRPC protocol limits timeouts to 8 characters (not counting the unit),
    # so timeouts must be strictly less than 1e8 of the appropriate unit.

    if timeout_ms < _GRPC_TIMEOUT_MAX_VALUE:
        size, unit = 1, "m"
    elif timeout_ms < _GRPC_TIMEOUT_MAX_VALUE * 1000:
        size, unit = 1 * 1000, "S"
    elif timeout_ms < _GRPC_TIMEOUT_MAX_VALUE * 60 * 1000:
        size, unit = 60 * 1000, "M"
    else:
        size, unit = 60 * 60 * 1000, "H"

    return f"{timeout_ms // size}{unit}"


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

_grpc_status_to_connect = {v: k for k, v in _connect_status_to_grpc.items()}
