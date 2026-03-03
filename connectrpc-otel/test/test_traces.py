from __future__ import annotations

import asyncio
import contextvars
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING, cast

import pytest
from connectrpc_otel import OpenTelemetryInterceptor
from example.eliza_connect import (
    ElizaService,
    ElizaServiceASGIApplication,
    ElizaServiceClient,
    ElizaServiceClientSync,
    ElizaServiceSync,
    ElizaServiceWSGIApplication,
)
from example.eliza_pb2 import SayRequest, SayResponse
from opentelemetry.instrumentation.asgi import (
    OpenTelemetryMiddleware as ASGIOpenTelemetryMiddleware,
)
from opentelemetry.instrumentation.wsgi import (
    OpenTelemetryMiddleware as WSGIOpenTelemetryMiddleware,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from pyqwest import Client, SyncClient
from pyqwest.testing import ASGITransport, WSGITransport

from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.interceptor import MetadataInterceptor, MetadataInterceptorSync

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from asgiref.typing import ASGIApplication

    from connectrpc.request import RequestContext


class ElizaServiceTest(ElizaService):
    async def say(self, request: SayRequest, ctx: RequestContext) -> SayResponse:
        if request.sentence == "connect error":
            raise ConnectError(Code.FAILED_PRECONDITION, "connect error")
        if request.sentence == "unknown error":
            raise ValueError("unknown error")
        return SayResponse(sentence="Hello")


class ElizaServiceTestSync(ElizaServiceSync):
    def say(self, request: SayRequest, ctx: RequestContext) -> SayResponse:
        if request.sentence == "connect error":
            raise ConnectError(Code.FAILED_PRECONDITION, "connect error")
        if request.sentence == "unknown error":
            raise ValueError("unknown error")
        return SayResponse(sentence="Hello")


# Work around testing transports not filling host header like a normal one does.
# https://github.com/curioswitch/pyqwest/pull/117
class HostInterceptor(MetadataInterceptorSync, MetadataInterceptor):
    def __init__(self, host: str) -> None:
        self._host = host

    async def on_start(self, ctx: RequestContext) -> None:
        ctx.request_headers()["host"] = self._host

    def on_start_sync(self, ctx: RequestContext) -> None:
        ctx.request_headers()["host"] = self._host


# Work around testing WSGI transport doesn't copy context by default.
# https://github.com/curioswitch/pyqwest/pull/118
class ContextCopyingExecutor(ThreadPoolExecutor):
    def submit(
        self, fn: Callable[..., object], *args: object, **kwargs: object
    ) -> Future:
        ctx = contextvars.copy_context()
        return super().submit(lambda: ctx.run(fn, *args, **kwargs))


@pytest.fixture(scope="module")
def executor() -> Iterator[ContextCopyingExecutor]:
    with ContextCopyingExecutor() as executor:
        yield executor


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def tracer_provider(span_exporter: InMemorySpanExporter) -> TracerProvider:
    tp = TracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(span_exporter))
    return tp


@pytest.fixture
def app_async(tracer_provider: TracerProvider) -> ElizaServiceASGIApplication:
    return ElizaServiceASGIApplication(
        ElizaServiceTest(),
        interceptors=[
            HostInterceptor("localhost"),
            OpenTelemetryInterceptor(tracer_provider=tracer_provider),
        ],
    )


@pytest.fixture
def client_async(
    app_async: ElizaServiceASGIApplication, tracer_provider: TracerProvider
) -> ElizaServiceClient:
    transport = ASGITransport(app_async, client=("123.456.7.89", 143))
    return ElizaServiceClient(
        "http://localhost",
        http_client=Client(transport=transport),
        interceptors=[
            HostInterceptor("localhost"),
            OpenTelemetryInterceptor(tracer_provider=tracer_provider, client=True),
        ],
    )


@pytest.fixture
def app_sync(tracer_provider: TracerProvider) -> ElizaServiceWSGIApplication:
    return ElizaServiceWSGIApplication(
        ElizaServiceTestSync(),
        interceptors=[
            HostInterceptor("localhost"),
            OpenTelemetryInterceptor(tracer_provider=tracer_provider),
        ],
    )


@pytest.fixture
def client_sync(
    app_sync: ElizaServiceWSGIApplication,
    tracer_provider: TracerProvider,
    executor: ContextCopyingExecutor,
) -> ElizaServiceClientSync:
    transport = WSGITransport(app_sync, executor=executor)
    return ElizaServiceClientSync(
        "http://localhost",
        http_client=SyncClient(transport=transport),
        interceptors=[
            HostInterceptor("localhost"),
            OpenTelemetryInterceptor(tracer_provider=tracer_provider, client=True),
        ],
    )


@pytest.fixture(params=["async", "sync"])
def client(
    request: pytest.FixtureRequest,
    client_async: ElizaServiceClient,
    client_sync: ElizaServiceClientSync,
) -> ElizaServiceClient | ElizaServiceClientSync:
    match request.param:
        case "async":
            return client_async
        case "sync":
            return client_sync
        case _:
            raise ValueError(f"invalid client type {request.param}")


@pytest.fixture(params=["async", "sync"])
def app(
    request: pytest.FixtureRequest,
    app_async: ElizaServiceASGIApplication,
    app_sync: ElizaServiceWSGIApplication,
) -> ElizaServiceASGIApplication | ElizaServiceWSGIApplication:
    match request.param:
        case "async":
            return app_async
        case "sync":
            return app_sync
        case _:
            raise ValueError(f"invalid app type {request.param}")


@pytest.mark.asyncio
async def test_basic(
    client: ElizaServiceClient | ElizaServiceClientSync,
    span_exporter: InMemorySpanExporter,
) -> None:
    if isinstance(client, ElizaServiceClient):
        await client.say(SayRequest(sentence="Hi"))
    else:
        await asyncio.to_thread(client.say, SayRequest(sentence="Hi"))

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 2
    assert spans[0].kind == SpanKind.SERVER
    assert spans[1].kind == SpanKind.CLIENT
    server_trace_context = spans[0].get_span_context()
    assert server_trace_context is not None
    server_parent_context = spans[0].parent
    assert server_parent_context is not None
    client_trace_context = spans[1].get_span_context()
    assert client_trace_context is not None
    assert client_trace_context.trace_id == server_trace_context.trace_id
    assert server_parent_context.span_id == client_trace_context.span_id

    for span in spans:
        assert span.status.is_unset
        attrs = span.attributes
        assert attrs is not None
        assert attrs["rpc.system.name"] == "connectrpc"
        assert attrs["rpc.method"] == "connectrpc.eliza.v1.ElizaService/Say"
        assert "rpc.response.status_code" not in attrs
        assert "error.type" not in attrs
        assert attrs["server.address"] == "localhost"
        assert attrs["server.port"] == 80

    # TODO: Remove guard when WSGITransport supports setting client addr
    # https://github.com/curioswitch/pyqwest/pull/117
    if isinstance(client, ElizaServiceClient):
        server_attrs = spans[0].attributes
        assert server_attrs is not None
        assert server_attrs["client.address"] == "123.456.7.89"
        assert server_attrs["client.port"] == 143


@pytest.mark.asyncio
async def test_connect_error(
    client: ElizaServiceClient | ElizaServiceClientSync,
    span_exporter: InMemorySpanExporter,
) -> None:
    with pytest.raises(ConnectError):
        if isinstance(client, ElizaServiceClient):
            await client.say(SayRequest(sentence="connect error"))
        else:
            await asyncio.to_thread(client.say, SayRequest(sentence="connect error"))

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 2
    assert spans[0].kind == SpanKind.SERVER
    assert spans[1].kind == SpanKind.CLIENT
    server_trace_context = spans[0].get_span_context()
    assert server_trace_context is not None
    server_parent_context = spans[0].parent
    assert server_parent_context is not None
    client_trace_context = spans[1].get_span_context()
    assert client_trace_context is not None
    assert client_trace_context.trace_id == server_trace_context.trace_id
    assert server_parent_context.span_id == client_trace_context.span_id

    for span in spans:
        assert span.status.status_code == StatusCode.ERROR
        attrs = span.attributes
        assert attrs is not None
        assert attrs["rpc.system.name"] == "connectrpc"
        assert attrs["rpc.method"] == "connectrpc.eliza.v1.ElizaService/Say"
        assert attrs["rpc.response.status_code"] == "failed_precondition"
        assert "error.type" not in attrs
        assert attrs["server.address"] == "localhost"
        assert attrs["server.port"] == 80

    # TODO: Remove guard when WSGITransport supports setting client addr
    # https://github.com/curioswitch/pyqwest/pull/117
    if isinstance(client, ElizaServiceClient):
        server_attrs = spans[0].attributes
        assert server_attrs is not None
        assert server_attrs["client.address"] == "123.456.7.89"
        assert server_attrs["client.port"] == 143


@pytest.mark.asyncio
async def test_unknown_error(
    client: ElizaServiceClient | ElizaServiceClientSync,
    span_exporter: InMemorySpanExporter,
) -> None:
    with pytest.raises(ConnectError):
        if isinstance(client, ElizaServiceClient):
            await client.say(SayRequest(sentence="unknown error"))
        else:
            await asyncio.to_thread(client.say, SayRequest(sentence="unknown error"))

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 2
    assert spans[0].kind == SpanKind.SERVER
    assert spans[1].kind == SpanKind.CLIENT
    server_trace_context = spans[0].get_span_context()
    assert server_trace_context is not None
    server_parent_context = spans[0].parent
    assert server_parent_context is not None
    client_trace_context = spans[1].get_span_context()
    assert client_trace_context is not None
    assert client_trace_context.trace_id == server_trace_context.trace_id
    assert server_parent_context.span_id == client_trace_context.span_id

    for span in spans:
        assert span.status.status_code == StatusCode.ERROR
        attrs = span.attributes
        assert attrs is not None
        assert attrs["rpc.system.name"] == "connectrpc"
        assert attrs["rpc.method"] == "connectrpc.eliza.v1.ElizaService/Say"
        assert attrs["rpc.response.status_code"] == "unknown"
        assert attrs["server.address"] == "localhost"
        assert attrs["server.port"] == 80

    server_attrs = spans[0].attributes
    assert server_attrs is not None
    # Server sees the ValueError itself
    assert server_attrs["error.type"] == "ValueError"
    # TODO: Remove guard when WSGITransport supports setting client addr
    # https://github.com/curioswitch/pyqwest/pull/117
    if isinstance(client, ElizaServiceClient):
        assert server_attrs["client.address"] == "123.456.7.89"
        assert server_attrs["client.port"] == 143

    client_attrs = spans[1].attributes
    assert client_attrs is not None
    # Client just sees a ConnectError
    assert "error.type" not in client_attrs


@pytest.mark.asyncio
async def test_http_server_parent(
    app: ElizaServiceASGIApplication | ElizaServiceWSGIApplication,
    tracer_provider: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    if isinstance(app, ElizaServiceASGIApplication):
        transport = ASGITransport(
            cast(
                "ASGIApplication",
                ASGIOpenTelemetryMiddleware(app, tracer_provider=tracer_provider),
            ),
            client=("123.456.7.89", 143),
        )
        client = ElizaServiceClient(
            "http://localhost",
            http_client=Client(transport=transport),
            interceptors=[
                HostInterceptor("localhost"),
                OpenTelemetryInterceptor(tracer_provider=tracer_provider, client=True),
            ],
        )
        await client.say(SayRequest(sentence="Hi"))
    else:
        transport = WSGITransport(
            WSGIOpenTelemetryMiddleware(app, tracer_provider=tracer_provider),
            executor=ContextCopyingExecutor(),
        )
        client = ElizaServiceClientSync(
            "http://localhost",
            http_client=SyncClient(transport=transport),
            interceptors=[
                HostInterceptor("localhost"),
                OpenTelemetryInterceptor(tracer_provider=tracer_provider, client=True),
            ],
        )
        await asyncio.to_thread(client.say, SayRequest(sentence="Hi"))

    spans = [
        s
        for s in span_exporter.get_finished_spans()
        if s.instrumentation_scope and s.instrumentation_scope.name == "connectrpc-otel"
    ]
    assert len(spans) == 2
    assert spans[0].kind == SpanKind.SERVER
    assert spans[1].kind == SpanKind.CLIENT
    server_trace_context = spans[0].get_span_context()
    assert server_trace_context is not None
    server_parent_context = spans[0].parent
    assert server_parent_context is not None
    client_trace_context = spans[1].get_span_context()
    assert client_trace_context is not None
    assert client_trace_context.trace_id == server_trace_context.trace_id
    # Parent is the server middleware span, not client span.
    assert server_parent_context.span_id != client_trace_context.span_id

    for span in spans:
        assert span.status.is_unset
        attrs = span.attributes
        assert attrs is not None
        assert attrs["rpc.system.name"] == "connectrpc"
        assert attrs["rpc.method"] == "connectrpc.eliza.v1.ElizaService/Say"
        assert "rpc.response.status_code" not in attrs
        assert "error.type" not in attrs
        assert attrs["server.address"] == "localhost"
        assert attrs["server.port"] == 80

    # TODO: Remove guard when WSGITransport supports setting client addr
    # https://github.com/curioswitch/pyqwest/pull/117
    if isinstance(client, ElizaServiceClient):
        server_attrs = spans[0].attributes
        assert server_attrs is not None
        assert server_attrs["client.address"] == "123.456.7.89"
        assert server_attrs["client.port"] == 143


@pytest.mark.asyncio
async def test_non_standard_port(
    app: ElizaServiceASGIApplication | ElizaServiceWSGIApplication,
    tracer_provider: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    if isinstance(app, ElizaServiceASGIApplication):
        transport = ASGITransport(app, client=("123.456.7.89", 143))
        client = ElizaServiceClient(
            "http://localhost:9123",
            http_client=Client(transport=transport),
            interceptors=[
                HostInterceptor("localhost:9123"),
                OpenTelemetryInterceptor(tracer_provider=tracer_provider, client=True),
            ],
        )
        await client.say(SayRequest(sentence="Hi"))
    else:
        transport = WSGITransport(app, executor=ContextCopyingExecutor())
        client = ElizaServiceClientSync(
            "http://localhost:9123",
            http_client=SyncClient(transport=transport),
            interceptors=[
                HostInterceptor("localhost:9123"),
                OpenTelemetryInterceptor(tracer_provider=tracer_provider, client=True),
            ],
        )
        await asyncio.to_thread(client.say, SayRequest(sentence="Hi"))

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 2
    assert spans[0].kind == SpanKind.SERVER
    assert spans[1].kind == SpanKind.CLIENT
    server_trace_context = spans[0].get_span_context()
    assert server_trace_context is not None
    server_parent_context = spans[0].parent
    assert server_parent_context is not None
    client_trace_context = spans[1].get_span_context()
    assert client_trace_context is not None
    assert client_trace_context.trace_id == server_trace_context.trace_id
    assert server_parent_context.span_id == client_trace_context.span_id

    for span in spans:
        assert span.status.is_unset
        attrs = span.attributes
        assert attrs is not None
        assert attrs["rpc.system.name"] == "connectrpc"
        assert attrs["rpc.method"] == "connectrpc.eliza.v1.ElizaService/Say"
        assert "rpc.response.status_code" not in attrs
        assert "error.type" not in attrs
        assert attrs["server.address"] == "localhost"
        assert attrs["server.port"] == 9123

    # TODO: Remove guard when WSGITransport supports setting client addr
    # https://github.com/curioswitch/pyqwest/pull/117
    if isinstance(client, ElizaServiceClient):
        server_attrs = spans[0].attributes
        assert server_attrs is not None
        assert server_attrs["client.address"] == "123.456.7.89"
        assert server_attrs["client.port"] == 143
