from __future__ import annotations

__all__ = ["Headers", "RequestContext"]


import time
from typing import TYPE_CHECKING, Generic, TypeVar

from ._headers import Headers

if TYPE_CHECKING:
    from .method import MethodInfo

REQ = TypeVar("REQ")
RES = TypeVar("RES")


class RequestContext(Generic[REQ, RES]):
    """Additional context for an RPC request message."""

    _method: MethodInfo[REQ, RES]
    _http_method: str
    _request_headers: Headers
    _response_headers: Headers | None
    _response_trailers: Headers | None

    def __init__(
        self,
        *,
        method: MethodInfo[REQ, RES],
        http_method: str,
        request_headers: Headers,
        timeout_ms: int | None = None,
    ) -> None:
        """
        Initialize a Context object.
        """
        self._method = method
        self._http_method = http_method
        self._request_headers = request_headers
        self._response_headers = None
        self._response_trailers = None

        if timeout_ms is None:
            self._end_time = None
        else:
            self._end_time = time.monotonic() + (timeout_ms / 1000.0)

    def method(self) -> MethodInfo[REQ, RES]:
        """Returns information about the RPC method being invoked."""
        return self._method

    def http_method(self) -> str:
        """Returns the HTTP method for this request.

        This is nearly always POST, but side-effect-free unary RPCs could be made
        via GET.
        """
        return self._http_method

    def request_headers(self) -> Headers:
        """
        Returns the request headers associated with the context.

        :return: A mapping of header keys to lists of header values.
        """
        return self._request_headers

    def response_headers(self) -> Headers:
        """
        Returns the response headers that will be sent before the response.
        """
        if self._response_headers is None:
            self._response_headers = Headers()
        return self._response_headers

    def response_trailers(self) -> Headers:
        """
        Returns the response trailers that will be sent after the response.
        """
        if self._response_trailers is None:
            self._response_trailers = Headers()
        return self._response_trailers

    def timeout_ms(self) -> float | None:
        """
        Returns the remaining time until the timeout.

        Returns:
            float | None: The remaining time in milliseconds, or None if no timeout is set.
        """
        if self._end_time is None:
            return None
        return (self._end_time - time.monotonic()) * 1000.0
