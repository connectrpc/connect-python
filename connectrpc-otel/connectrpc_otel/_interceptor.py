from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, TypeVar, cast

from opentelemetry.propagate import get_global_textmap
from opentelemetry.propagators.textmap import Setter, TextMapPropagator, default_setter
from opentelemetry.trace import (
    Span,
    SpanKind,
    TracerProvider,
    get_current_span,
    get_tracer_provider,
)

from connectrpc.errors import ConnectError

from ._semconv import (
    CLIENT_ADDRESS,
    CLIENT_PORT,
    ERROR_TYPE,
    RPC_METHOD,
    RPC_RESPONSE_STATUS_CODE,
    RPC_SYSTEM_NAME,
    SERVER_ADDRESS,
    SERVER_PORT,
    RpcSystemNameValues,
)
from ._version import __version__

if TYPE_CHECKING:
    from collections.abc import (
        AsyncIterator,
        Awaitable,
        Callable,
        Iterator,
        MutableMapping,
    )

    from opentelemetry.util.types import AttributeValue

    from connectrpc.request import RequestContext

REQ = TypeVar("REQ")
RES = TypeVar("RES")

# Workaround bad typing
_DEFAULT_TEXTMAP_SETTER = cast("Setter[MutableMapping[str, str]]", default_setter)


class OpenTelemetryInterceptor:
    """Interceptor to generate telemetry for RPC server and client requests."""

    def __init__(
        self,
        *,
        propagator: TextMapPropagator | None = None,
        tracer_provider: TracerProvider | None = None,
        client: bool = False,
    ) -> None:
        """Creates a new OpenTelemetry interceptor.

        Args:
            propagator: The OpenTelemetry TextMapPropagator to use. If not
                provided, the global default will be used.
            tracer_provider: The OpenTelemetry TracerProvider to use. If not
                provided, the global default will be used.
            client: Whether this interceptor is for a client or server.
        """
        self._client = client
        tracer_provider = tracer_provider or get_tracer_provider()
        self._tracer = tracer_provider.get_tracer("connectrpc-otel", __version__)
        self._propagator = propagator or get_global_textmap()

    async def intercept_unary(
        self,
        call_next: Callable[[REQ, RequestContext], Awaitable[RES]],
        request: REQ,
        ctx: RequestContext,
    ) -> RES:
        error: Exception | None = None
        with self._start_span(ctx) as span:
            try:
                return await call_next(request, ctx)
            except Exception as e:
                error = e
                raise
            finally:
                self._finish_span(span, error)

    async def intercept_client_stream(
        self,
        call_next: Callable[[AsyncIterator[REQ], RequestContext], Awaitable[RES]],
        request: AsyncIterator[REQ],
        ctx: RequestContext,
    ) -> RES:
        error: Exception | None = None
        with self._start_span(ctx) as span:
            try:
                return await call_next(request, ctx)
            except Exception as e:
                error = e
                raise
            finally:
                self._finish_span(span, error)

    async def intercept_server_stream(
        self,
        call_next: Callable[[REQ, RequestContext], AsyncIterator[RES]],
        request: REQ,
        ctx: RequestContext,
    ) -> AsyncIterator[RES]:
        error: Exception | None = None
        with self._start_span(ctx) as span:
            try:
                async for response in call_next(request, ctx):
                    yield response
            except Exception as e:
                error = e
                raise
            finally:
                self._finish_span(span, error)

    async def intercept_bidi_stream(
        self,
        call_next: Callable[[AsyncIterator[REQ], RequestContext], AsyncIterator[RES]],
        request: AsyncIterator[REQ],
        ctx: RequestContext,
    ) -> AsyncIterator[RES]:
        error: Exception | None = None
        with self._start_span(ctx) as span:
            try:
                async for response in call_next(request, ctx):
                    yield response
            except Exception as e:
                error = e
                raise
            finally:
                self._finish_span(span, error)

    def intercept_unary_sync(
        self,
        call_next: Callable[[REQ, RequestContext], RES],
        request: REQ,
        ctx: RequestContext,
    ) -> RES:
        error: Exception | None = None
        with self._start_span(ctx) as span:
            try:
                return call_next(request, ctx)
            except Exception as e:
                error = e
                raise
            finally:
                self._finish_span(span, error)

    def intercept_client_stream_sync(
        self,
        call_next: Callable[[Iterator[REQ], RequestContext], RES],
        request: Iterator[REQ],
        ctx: RequestContext,
    ) -> RES:
        error: Exception | None = None
        with self._start_span(ctx) as span:
            try:
                return call_next(request, ctx)
            except Exception as e:
                error = e
                raise
            finally:
                self._finish_span(span, error)

    def intercept_server_stream_sync(
        self,
        call_next: Callable[[REQ, RequestContext], Iterator[RES]],
        request: REQ,
        ctx: RequestContext,
    ) -> Iterator[RES]:
        error: Exception | None = None
        with self._start_span(ctx) as span:
            try:
                yield from call_next(request, ctx)
            except Exception as e:
                error = e
                raise
            finally:
                self._finish_span(span, error)

    def intercept_bidi_stream_sync(
        self,
        call_next: Callable[[Iterator[REQ], RequestContext], Iterator[RES]],
        request: Iterator[REQ],
        ctx: RequestContext,
    ) -> Iterator[RES]:
        error: Exception | None = None
        with self._start_span(ctx) as span:
            try:
                yield from call_next(request, ctx)
            except Exception as e:
                error = e
                raise
            finally:
                self._finish_span(span, error)

    @contextmanager
    def _start_span(self, ctx: RequestContext) -> Iterator[Span]:
        parent_otel_ctx = None
        if self._client:
            span_kind = SpanKind.CLIENT
            carrier = ctx.request_headers()
            self._propagator.inject(carrier, setter=_DEFAULT_TEXTMAP_SETTER)
        else:
            span_kind = SpanKind.SERVER
            parent_span = get_current_span()
            if not parent_span.get_span_context().is_valid:
                carrier = ctx.request_headers()
                parent_otel_ctx = self._propagator.extract(carrier)

        span_kind = SpanKind.CLIENT if self._client else SpanKind.SERVER

        rpc_method = f"{ctx.method().service_name}/{ctx.method().name}"

        attrs: MutableMapping[str, AttributeValue] = {
            RPC_SYSTEM_NAME: RpcSystemNameValues.CONNECTRPC.value,
            RPC_METHOD: rpc_method,
        }
        if sa := ctx.server_address():
            addr, port = sa.rsplit(":", 1)
            attrs[SERVER_ADDRESS] = addr
            attrs[SERVER_PORT] = int(port)
        if ca := ctx.client_address():
            addr, port = ca.rsplit(":", 1)
            attrs[CLIENT_ADDRESS] = addr
            attrs[CLIENT_PORT] = int(port)

        with self._tracer.start_as_current_span(
            rpc_method, kind=span_kind, attributes=attrs, context=parent_otel_ctx
        ) as span:
            yield span

    def _finish_span(self, span: Span, error: Exception | None) -> None:
        if error:
            if isinstance(error, ConnectError):
                span.set_attribute(RPC_RESPONSE_STATUS_CODE, error.code.value)
            else:
                span.set_attribute(RPC_RESPONSE_STATUS_CODE, "unknown")
                span.set_attribute(ERROR_TYPE, type(error).__qualname__)
