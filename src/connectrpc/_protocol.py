from __future__ import annotations

import json
from base64 import b64decode, b64encode
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, cast

from google.protobuf.any_pb2 import Any

from .code import Code
from .errors import ConnectError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import httpx

CONNECT_HEADER_PROTOCOL_VERSION = "connect-protocol-version"
CONNECT_PROTOCOL_VERSION = "1"
CONNECT_UNARY_CONTENT_TYPE_PREFIX = "application/"
CONNECT_STREAMING_CONTENT_TYPE_PREFIX = "application/connect+"

CONNECT_UNARY_HEADER_COMPRESSION = "content-encoding"
CONNECT_UNARY_HEADER_ACCEPT_COMPRESSION = "accept-encoding"
CONNECT_STREAMING_HEADER_COMPRESSION = "connect-content-encoding"
CONNECT_STREAMING_HEADER_ACCEPT_COMPRESSION = "connect-accept-encoding"

CONNECT_HEADER_TIMEOUT = "connect-timeout-ms"


# Define a custom class for HTTP Status to allow adding 499 status code
@dataclass(frozen=True)
class ExtendedHTTPStatus:
    code: int
    reason: str

    @staticmethod
    def from_http_status(status: HTTPStatus) -> ExtendedHTTPStatus:
        return ExtendedHTTPStatus(code=status.value, reason=status.phrase)


# Dedupe statuses that are mapped multiple times
_BAD_REQUEST = ExtendedHTTPStatus.from_http_status(HTTPStatus.BAD_REQUEST)
_CONFLICT = ExtendedHTTPStatus.from_http_status(HTTPStatus.CONFLICT)
_INTERNAL_SERVER_ERROR = ExtendedHTTPStatus.from_http_status(
    HTTPStatus.INTERNAL_SERVER_ERROR
)

_error_to_http_status = {
    Code.CANCELED: ExtendedHTTPStatus(499, "Client Closed Request"),
    Code.UNKNOWN: _INTERNAL_SERVER_ERROR,
    Code.INVALID_ARGUMENT: _BAD_REQUEST,
    Code.DEADLINE_EXCEEDED: ExtendedHTTPStatus.from_http_status(
        HTTPStatus.GATEWAY_TIMEOUT
    ),
    Code.NOT_FOUND: ExtendedHTTPStatus.from_http_status(HTTPStatus.NOT_FOUND),
    Code.ALREADY_EXISTS: _CONFLICT,
    Code.PERMISSION_DENIED: ExtendedHTTPStatus.from_http_status(HTTPStatus.FORBIDDEN),
    Code.RESOURCE_EXHAUSTED: ExtendedHTTPStatus.from_http_status(
        HTTPStatus.TOO_MANY_REQUESTS
    ),
    Code.FAILED_PRECONDITION: _BAD_REQUEST,
    Code.ABORTED: _CONFLICT,
    Code.OUT_OF_RANGE: _BAD_REQUEST,
    Code.UNIMPLEMENTED: ExtendedHTTPStatus.from_http_status(HTTPStatus.NOT_IMPLEMENTED),
    Code.INTERNAL: _INTERNAL_SERVER_ERROR,
    Code.UNAVAILABLE: ExtendedHTTPStatus.from_http_status(
        HTTPStatus.SERVICE_UNAVAILABLE
    ),
    Code.DATA_LOSS: _INTERNAL_SERVER_ERROR,
    Code.UNAUTHENTICATED: ExtendedHTTPStatus.from_http_status(HTTPStatus.UNAUTHORIZED),
}


_http_status_code_to_error = {
    400: Code.INTERNAL,
    401: Code.UNAUTHENTICATED,
    403: Code.PERMISSION_DENIED,
    404: Code.UNIMPLEMENTED,
    429: Code.UNAVAILABLE,
    502: Code.UNAVAILABLE,
    503: Code.UNAVAILABLE,
    504: Code.UNAVAILABLE,
}


@dataclass(frozen=True)
class ConnectWireError:
    code: Code
    message: str
    details: Sequence[Any]

    @staticmethod
    def from_exception(exc: Exception) -> ConnectWireError:
        if isinstance(exc, ConnectError):
            return ConnectWireError(exc.code, exc.message, exc.details)
        return ConnectWireError(Code.UNKNOWN, str(exc), details=())

    @staticmethod
    def from_response(response: httpx.Response) -> ConnectWireError:
        try:
            data = response.json()
        except Exception:
            data = None
        if isinstance(data, dict):
            return ConnectWireError.from_dict(
                data, response.status_code, Code.UNAVAILABLE
            )
        return ConnectWireError.from_http_status(response.status_code)

    @staticmethod
    def from_dict(
        data: dict, http_status: int, unexpected_code: Code
    ) -> ConnectWireError:
        code_str = data.get("code")
        if code_str:
            try:
                code = Code(code_str)
            except ValueError:
                code = unexpected_code
        else:
            code = _http_status_code_to_error.get(http_status, Code.UNKNOWN)
        message = data.get("message", "")
        details: Sequence[Any] = ()
        details_json = cast("list[dict[str, str]] | None", data.get("details"))
        if details_json:
            details = []
            for detail in details_json:
                detail_type = detail.get("type")
                detail_value = detail.get("value")
                if detail_type is None or detail_value is None:
                    # Ignore malformed details
                    continue
                details.append(
                    Any(
                        type_url="type.googleapis.com/" + detail_type,
                        value=b64decode(detail_value + "==="),
                    )
                )
        return ConnectWireError(code, message, details)

    @staticmethod
    def from_http_status(status_code: int) -> ConnectWireError:
        code = _http_status_code_to_error.get(status_code, Code.UNKNOWN)
        try:
            http_status = HTTPStatus(status_code)
            message = http_status.phrase
        except ValueError:
            message = "Client Closed Request" if status_code == 499 else ""
        return ConnectWireError(code, message, details=())

    def to_exception(self) -> ConnectError:
        return ConnectError(self.code, self.message, details=self.details)

    def to_http_status(self) -> ExtendedHTTPStatus:
        return _error_to_http_status.get(self.code, _INTERNAL_SERVER_ERROR)

    def to_dict(self) -> dict:
        data: dict = {"code": self.code.value, "message": self.message}
        if self.details:
            details: list[dict[str, str]] = []
            for detail in self.details:
                if detail.type_url.startswith("type.googleapis.com/"):
                    detail_type = detail.type_url[len("type.googleapis.com/") :]
                else:
                    detail_type = detail.type_url
                details.append(
                    {
                        "type": detail_type,
                        # Connect requires unpadded base64
                        "value": b64encode(detail.value).decode("utf-8").rstrip("="),
                    }
                )
            data["details"] = details
        return data

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict()).encode("utf-8")


class HTTPException(Exception):
    """An HTTP exception returned directly before starting the connect protocol."""

    def __init__(self, status: HTTPStatus, headers: list[tuple[str, str]]) -> None:
        self.status = status
        self.headers = headers


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
