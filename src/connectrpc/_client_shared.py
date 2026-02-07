from __future__ import annotations

import base64
import re
from http import HTTPStatus
from typing import TYPE_CHECKING, TypeVar

from pyqwest import Headers as HTTPHeaders
from pyqwest import StreamError, StreamErrorCode

from ._codec import CODEC_NAME_JSON, CODEC_NAME_JSON_CHARSET_UTF8, Codec
from ._protocol import ConnectWireError
from ._protocol_connect import (
    CONNECT_PROTOCOL_VERSION,
    CONNECT_STREAMING_CONTENT_TYPE_PREFIX,
    CONNECT_UNARY_CONTENT_TYPE_PREFIX,
    codec_name_from_content_type,
)
from .code import Code
from .errors import ConnectError

if TYPE_CHECKING:
    from .request import RequestContext


REQ = TypeVar("REQ")
RES = TypeVar("RES")


def prepare_get_params(
    codec: Codec, request_data: bytes, headers: HTTPHeaders
) -> dict[str, str]:
    params = {
        "connect": f"v{CONNECT_PROTOCOL_VERSION}",
        "message": base64.urlsafe_b64encode(request_data).decode("ascii"),
        "base64": "1",
        "encoding": codec.name(),
    }
    if "content-encoding" in headers:
        params["compression"] = headers.pop("content-encoding")
    return params


def validate_unary_response(
    request_codec_name: str, status_code: int, response_content_type: str
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


def validate_stream_response_content_type(
    request_codec_name: str, response_content_type: str
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


_stream_error_code_regex = re.compile(
    r".*<StreamReset .*, error_code:(\d+), .*remote_reset:True>.*"
)


# https://github.com/connectrpc/connect-go/blob/59cc6973156cd9164d6bea493b1d106ed894f2df/error.go#L393
def maybe_map_stream_reset(
    e: Exception, ctx: RequestContext[REQ, RES]
) -> ConnectError | None:
    if not isinstance(e, StreamError):
        return None

    msg = str(e)
    match e.code:
        case (
            StreamErrorCode.NO_ERROR
            | StreamErrorCode.PROTOCOL_ERROR
            | StreamErrorCode.INTERNAL_ERROR
            | StreamErrorCode.FLOW_CONTROL_ERROR
            | StreamErrorCode.SETTINGS_TIMEOUT
            | StreamErrorCode.FRAME_SIZE_ERROR
            | StreamErrorCode.COMPRESSION_ERROR
            | StreamErrorCode.CONNECT_ERROR
        ):
            return ConnectError(Code.INTERNAL, msg)
        case StreamErrorCode.REFUSED_STREAM:
            return ConnectError(Code.UNAVAILABLE, msg)
        case StreamErrorCode.CANCEL:
            # Some servers use CANCEL when deadline expires. We can't differentiate
            # that from normal cancel without checking our own deadline.
            if (t := ctx.timeout_ms()) is not None and t <= 0:
                return ConnectError(Code.DEADLINE_EXCEEDED, msg)
            return ConnectError(Code.CANCELED, msg)
        case StreamErrorCode.ENHANCE_YOUR_CALM:
            return ConnectError(Code.RESOURCE_EXHAUSTED, f"Bandwidth exhausted: {msg}")
        case StreamErrorCode.INADEQUATE_SECURITY:
            return ConnectError(
                Code.PERMISSION_DENIED, f"Transport protocol insecure: {msg}"
            )

    return None
