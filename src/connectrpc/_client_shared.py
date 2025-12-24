from __future__ import annotations

import base64
from http import HTTPStatus
from typing import TYPE_CHECKING, TypeVar

from . import _compression
from ._codec import CODEC_NAME_JSON, CODEC_NAME_JSON_CHARSET_UTF8, Codec
from ._compression import (
    Compression,
    get_accept_encoding,
    get_available_compressions,
    get_compression,
)
from ._protocol import ConnectWireError
from ._protocol_connect import (
    CONNECT_PROTOCOL_VERSION,
    CONNECT_STREAMING_CONTENT_TYPE_PREFIX,
    CONNECT_STREAMING_HEADER_ACCEPT_COMPRESSION,
    CONNECT_STREAMING_HEADER_COMPRESSION,
    CONNECT_UNARY_CONTENT_TYPE_PREFIX,
    CONNECT_UNARY_HEADER_ACCEPT_COMPRESSION,
    CONNECT_UNARY_HEADER_COMPRESSION,
    codec_name_from_content_type,
)
from ._version import __version__
from .code import Code
from .errors import ConnectError
from .request import Headers, RequestContext

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from httpx import Headers as HttpxHeaders

    from .method import MethodInfo

_DEFAULT_CONNECT_USER_AGENT = f"connectrpc/{__version__}"

REQ = TypeVar("REQ")
RES = TypeVar("RES")


def resolve_send_compression(compression_name: str | None) -> Compression | None:
    if compression_name is None:
        return None
    compression = get_compression(compression_name)
    if compression is None:
        msg = (
            f"Unsupported compression method: {compression_name}. "
            f"Available methods: {', '.join(get_available_compressions())}"
        )
        raise ValueError(msg)
    return compression


def create_request_context(
    *,
    method: MethodInfo[REQ, RES],
    http_method: str,
    user_headers: Headers | Mapping[str, str] | None,
    timeout_ms: int | None,
    codec: Codec,
    stream: bool,
    accept_compression: Iterable[str] | None,
    send_compression: Compression | None,
) -> RequestContext:
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


def prepare_get_params(
    codec: Codec, request_data: bytes, headers: HttpxHeaders
) -> dict[str, str]:
    params = {"connect": f"v{CONNECT_PROTOCOL_VERSION}"}
    if request_data:
        params["message"] = base64.urlsafe_b64encode(request_data).decode("ascii")
        params["base64"] = "1"
        params["encoding"] = codec.name()
    if "content-encoding" in headers:
        params["compression"] = headers.pop("content-encoding")
    return params


def validate_response_content_encoding(
    encoding: str | None,
) -> _compression.Compression:
    if not encoding:
        return _compression.IdentityCompression()
    res = _compression.get_compression(encoding.lower())
    if not res:
        raise ConnectError(
            Code.INTERNAL,
            f"unknown encoding '{encoding}'; accepted encodings are {', '.join(_compression.get_available_compressions())}",
        )
    return res


def validate_response_content_type(
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
