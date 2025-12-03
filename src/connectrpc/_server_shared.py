from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Generic, TypeVar

from ._protocol import (
    CONNECT_HEADER_PROTOCOL_VERSION,
    CONNECT_HEADER_TIMEOUT,
    CONNECT_PROTOCOL_VERSION,
    HTTPException,
)
from .code import Code
from .errors import ConnectError
from .method import IdempotencyLevel, MethodInfo
from .request import Headers, RequestContext

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

REQ = TypeVar("REQ")
RES = TypeVar("RES")
T = TypeVar("T")
U = TypeVar("U")


@dataclass(kw_only=True, frozen=True, slots=True)
class Endpoint(Generic[REQ, RES]):
    """
    Represents an endpoint in a service.

    Attributes:
        method: The method to map the the RPC function.
    """

    method: MethodInfo[REQ, RES]

    @staticmethod
    def unary(
        method: MethodInfo[T, U],
        function: Callable[[T, RequestContext[T, U]], Awaitable[U]],
    ) -> EndpointUnary[T, U]:
        return EndpointUnary(method=method, function=function)

    @staticmethod
    def client_stream(
        method: MethodInfo[T, U],
        function: Callable[[AsyncIterator[T], RequestContext[T, U]], Awaitable[U]],
    ) -> EndpointClientStream[T, U]:
        return EndpointClientStream(method=method, function=function)

    @staticmethod
    def server_stream(
        method: MethodInfo[T, U],
        function: Callable[[T, RequestContext[T, U]], AsyncIterator[U]],
    ) -> EndpointServerStream[T, U]:
        return EndpointServerStream(method=method, function=function)

    @staticmethod
    def bidi_stream(
        method: MethodInfo[T, U],
        function: Callable[[AsyncIterator[T], RequestContext[T, U]], AsyncIterator[U]],
    ) -> EndpointBidiStream[T, U]:
        return EndpointBidiStream(method=method, function=function)


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointUnary(Endpoint[REQ, RES]):
    function: Callable[[REQ, RequestContext[REQ, RES]], Awaitable[RES]]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointClientStream(Endpoint[REQ, RES]):
    function: Callable[[AsyncIterator[REQ], RequestContext[REQ, RES]], Awaitable[RES]]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointServerStream(Endpoint[REQ, RES]):
    function: Callable[[REQ, RequestContext[REQ, RES]], AsyncIterator[RES]]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointBidiStream(Endpoint[REQ, RES]):
    function: Callable[
        [AsyncIterator[REQ], RequestContext[REQ, RES]], AsyncIterator[RES]
    ]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointSync(Generic[REQ, RES]):
    """
    Represents a sync endpoint in a service.

    Attributes:
        method: The method to map the RPC function.
    """

    method: MethodInfo[REQ, RES]

    @staticmethod
    def unary(
        *, method: MethodInfo[T, U], function: Callable[[T, RequestContext[T, U]], U]
    ) -> EndpointUnarySync[T, U]:
        return EndpointUnarySync(method=method, function=function)

    @staticmethod
    def client_stream(
        *,
        method: MethodInfo[T, U],
        function: Callable[[Iterator[T], RequestContext[T, U]], U],
    ) -> EndpointClientStreamSync[T, U]:
        return EndpointClientStreamSync(method=method, function=function)

    @staticmethod
    def server_stream(
        *,
        method: MethodInfo[T, U],
        function: Callable[[T, RequestContext[T, U]], Iterator[U]],
    ) -> EndpointServerStreamSync[T, U]:
        return EndpointServerStreamSync(method=method, function=function)

    @staticmethod
    def bidi_stream(
        method: MethodInfo[T, U],
        function: Callable[[Iterator[T], RequestContext[T, U]], Iterator[U]],
    ) -> EndpointBidiStreamSync[T, U]:
        return EndpointBidiStreamSync(method=method, function=function)


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointUnarySync(EndpointSync[REQ, RES]):
    function: Callable[[REQ, RequestContext[REQ, RES]], RES]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointClientStreamSync(EndpointSync[REQ, RES]):
    function: Callable[[Iterator[REQ], RequestContext[REQ, RES]], RES]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointServerStreamSync(EndpointSync[REQ, RES]):
    function: Callable[[REQ, RequestContext[REQ, RES]], Iterator[RES]]


@dataclass(kw_only=True, frozen=True, slots=True)
class EndpointBidiStreamSync(EndpointSync[REQ, RES]):
    function: Callable[[Iterator[REQ], RequestContext[REQ, RES]], Iterator[RES]]


def create_request_context(
    method: MethodInfo[REQ, RES], http_method: str, headers: Headers
) -> RequestContext[REQ, RES]:
    if method.idempotency_level == IdempotencyLevel.NO_SIDE_EFFECTS:
        if http_method not in ("GET", "POST"):
            raise HTTPException(HTTPStatus.METHOD_NOT_ALLOWED, [("allow", "GET, POST")])
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
