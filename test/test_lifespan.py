import asyncio
from collections import Counter
from io import StringIO

import pytest
import uvicorn
from uvicorn.config import LOGGING_CONFIG

from .haberdasher_connect import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherClient,
)
from .haberdasher_pb2 import Hat, Size


@pytest.mark.asyncio
async def test_lifespan() -> None:
    class CountingHaberdasher(Haberdasher):
        def __init__(self, counter: Counter) -> None:
            self._counter = counter

        async def make_hat(self, request, ctx):
            self._counter["requests"] += 1
            return Hat(size=request.inches, color="blue")

    final_count = None

    async def counting_haberdasher():
        counter = Counter()
        try:
            haberdasher = CountingHaberdasher(counter)
            yield haberdasher
        finally:
            nonlocal final_count
            final_count = counter["requests"]

    app = HaberdasherASGIApplication(counting_haberdasher())
    # Use uvicorn since it supports lifespan
    config = uvicorn.Config(
        app, port=0, log_level="critical", timeout_graceful_shutdown=0
    )
    server = uvicorn.Server(config)
    uvicorn_task = asyncio.create_task(server.serve())

    for _ in range(50):
        if server.started:
            break
        await asyncio.sleep(0.1)
    else:
        msg = "Server did not start"
        raise RuntimeError(msg)

    port = server.servers[0].sockets[0].getsockname()[1]

    async with HaberdasherClient(f"http://localhost:{port}") as client:
        for _ in range(5):
            hat = await client.make_hat(Size(inches=10))
            assert hat.size == 10
            assert hat.color == "blue"

    server.should_exit = True
    await uvicorn_task
    assert final_count == 5


@pytest.mark.asyncio
async def test_lifespan_startup_error() -> None:
    class CountingHaberdasher(Haberdasher):
        def __init__(self, counter: Counter) -> None:
            self._counter = counter

        async def make_hat(self, request, ctx):
            self._counter["requests"] += 1
            return Hat(size=request.inches, color="blue")

    final_count = None

    async def counting_haberdasher():
        counter = Counter()
        if True:
            msg = "Haberdasher failed to start"
            raise RuntimeError(msg)
        # Unreachable code below but keep it to make this an async generator
        try:
            haberdasher = CountingHaberdasher(counter)
            yield haberdasher
        finally:
            nonlocal final_count
            final_count = counter["requests"]

    app = HaberdasherASGIApplication(counting_haberdasher())
    # Use uvicorn since it supports lifespan
    logs = StringIO()
    log_config = LOGGING_CONFIG.copy()
    log_config["handlers"]["default"]["stream"] = logs
    config = uvicorn.Config(
        app,
        port=0,
        log_level="error",
        timeout_graceful_shutdown=0,
        log_config=log_config,
    )
    server = uvicorn.Server(config)
    await server.serve()

    assert "Haberdasher failed to start" in logs.getvalue()


@pytest.mark.asyncio
async def test_lifespan_shutdown_error() -> None:
    class CountingHaberdasher(Haberdasher):
        def __init__(self, counter: Counter) -> None:
            self._counter = counter

        async def make_hat(self, request, ctx):
            self._counter["requests"] += 1
            return Hat(size=request.inches, color="blue")

    async def counting_haberdasher():
        counter = Counter()
        try:
            haberdasher = CountingHaberdasher(counter)
            yield haberdasher
        finally:
            msg = "Haberdasher failed to shut down"
            raise RuntimeError(msg)

    app = HaberdasherASGIApplication(counting_haberdasher())
    # Use uvicorn since it supports lifespan
    logs = StringIO()
    log_config = LOGGING_CONFIG.copy()
    log_config["handlers"]["default"]["stream"] = logs
    config = uvicorn.Config(
        app,
        port=0,
        log_level="error",
        timeout_graceful_shutdown=0,
        log_config=log_config,
    )
    server = uvicorn.Server(config)
    uvicorn_task = asyncio.create_task(server.serve())

    for _ in range(50):
        if server.started:
            break
        await asyncio.sleep(0.1)
    else:
        msg = "Server did not start"
        raise RuntimeError(msg)

    port = server.servers[0].sockets[0].getsockname()[1]

    async with HaberdasherClient(f"http://localhost:{port}") as client:
        for _ in range(5):
            hat = await client.make_hat(Size(inches=10))
            assert hat.size == 10
            assert hat.color == "blue"

    server.should_exit = True
    await uvicorn_task
    assert "Haberdasher failed to shut down" in logs.getvalue()
