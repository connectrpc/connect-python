from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from pyqwest import Client, SyncClient
from pyqwest.testing import ASGITransport, WSGITransport

from .haberdasher_connect import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherClient,
    HaberdasherClientSync,
    HaberdasherSync,
    HaberdasherWSGIApplication,
)
from .haberdasher_pb2 import Hat, Size

if TYPE_CHECKING:
    from connectrpc.request import RequestContext


class RequestInterceptor:
    def __init__(self) -> None:
        self.result = []

    async def on_start(self, ctx: RequestContext):
        return self.on_start_sync(ctx)

    async def on_end(self, token: str, ctx: RequestContext) -> None:
        self.on_end_sync(token, ctx)

    def on_start_sync(self, ctx: RequestContext) -> str:
        return f"Hello {ctx.method().name}"

    def on_end_sync(self, token: str, ctx: RequestContext) -> None:
        self.result.append(f"{token} and goodbye")


@pytest.fixture
def interceptor():
    return RequestInterceptor()


@pytest_asyncio.fixture
async def client_async(interceptor: RequestInterceptor):
    class SimpleHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

        async def make_flexible_hat(self, request, ctx):
            size = 0
            async for s in request:
                size += s.inches
            return Hat(size=size, color="red")

        async def make_similar_hats(self, request, ctx):
            yield Hat(size=request.inches, color="orange")
            yield Hat(size=request.inches, color="blue")

        async def make_various_hats(self, request, ctx):
            colors = itertools.cycle(("black", "white", "gold"))
            async for s in request:
                yield Hat(size=s.inches, color=next(colors))

    app = HaberdasherASGIApplication(SimpleHaberdasher(), interceptors=(interceptor,))
    transport = ASGITransport(app)
    async with HaberdasherClient(
        "http://localhost",
        interceptors=(interceptor,),
        http_client=Client(transport=transport),
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_intercept_unary_async(
    client_async: HaberdasherClient, interceptor: RequestInterceptor
) -> None:
    result = await client_async.make_hat(Size(inches=10))
    assert result == Hat(size=10, color="green")
    assert interceptor.result == ["Hello MakeHat and goodbye"] * 2


@pytest.mark.asyncio
async def test_intercept_client_stream_async(
    client_async: HaberdasherClient, interceptor: RequestInterceptor
) -> None:
    async def requests():
        yield Size(inches=10)
        yield Size(inches=20)

    result = await client_async.make_flexible_hat(requests())
    assert result == Hat(size=30, color="red")
    assert interceptor.result == ["Hello MakeFlexibleHat and goodbye"] * 2


@pytest.mark.asyncio
async def test_intercept_server_stream_async(
    client_async: HaberdasherClient, interceptor: RequestInterceptor
) -> None:
    result = [r async for r in client_async.make_similar_hats(Size(inches=15))]

    assert result == [Hat(size=15, color="orange"), Hat(size=15, color="blue")]
    assert interceptor.result == ["Hello MakeSimilarHats and goodbye"] * 2


@pytest.mark.asyncio
async def test_intercept_bidi_stream_async(
    client_async: HaberdasherClient, interceptor: RequestInterceptor
) -> None:
    async def requests():
        yield Size(inches=25)
        yield Size(inches=35)
        yield Size(inches=45)

    result = [r async for r in client_async.make_various_hats(requests())]

    assert result == [
        Hat(size=25, color="black"),
        Hat(size=35, color="white"),
        Hat(size=45, color="gold"),
    ]
    assert interceptor.result == ["Hello MakeVariousHats and goodbye"] * 2


@pytest.fixture
def client_sync(interceptor: RequestInterceptor):
    class SimpleHaberdasherSync(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

        def make_flexible_hat(self, request, ctx):
            size = 0
            for s in request:
                size += s.inches
            return Hat(size=size, color="red")

        def make_similar_hats(self, request, ctx):
            yield Hat(size=request.inches, color="orange")
            yield Hat(size=request.inches, color="blue")

        def make_various_hats(self, request, ctx):
            colors = itertools.cycle(("black", "white", "gold"))
            requests = [*request]
            for s in requests:
                yield Hat(size=s.inches, color=next(colors))

    app = HaberdasherWSGIApplication(
        SimpleHaberdasherSync(), interceptors=(interceptor,)
    )
    transport = WSGITransport(app)
    with HaberdasherClientSync(
        "http://localhost",
        interceptors=(interceptor,),
        http_client=SyncClient(transport),
    ) as client:
        yield client


def test_intercept_unary_sync(
    client_sync: HaberdasherClientSync, interceptor: RequestInterceptor
) -> None:
    result = client_sync.make_hat(Size(inches=10))
    assert result == Hat(size=10, color="green")
    assert interceptor.result == ["Hello MakeHat and goodbye"] * 2


def test_intercept_client_stream_sync(
    client_sync: HaberdasherClientSync, interceptor: RequestInterceptor
) -> None:
    def requests():
        yield Size(inches=10)
        yield Size(inches=20)

    result = client_sync.make_flexible_hat(requests())
    assert result == Hat(size=30, color="red")
    assert interceptor.result == ["Hello MakeFlexibleHat and goodbye"] * 2


def test_intercept_server_stream_sync(
    client_sync: HaberdasherClientSync, interceptor: RequestInterceptor
) -> None:
    result = list(client_sync.make_similar_hats(Size(inches=15)))

    assert result == [Hat(size=15, color="orange"), Hat(size=15, color="blue")]
    assert interceptor.result == ["Hello MakeSimilarHats and goodbye"] * 2


def test_intercept_bidi_stream_sync(
    client_sync: HaberdasherClientSync, interceptor: RequestInterceptor
) -> None:
    def requests():
        yield Size(inches=25)
        yield Size(inches=35)
        yield Size(inches=45)

    result = list(client_sync.make_various_hats(requests()))

    assert result == [
        Hat(size=25, color="black"),
        Hat(size=35, color="white"),
        Hat(size=45, color="gold"),
    ]
    assert interceptor.result == ["Hello MakeVariousHats and goodbye"] * 2
