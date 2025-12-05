from __future__ import annotations

import pytest
from example.eliza_connect import (
    ElizaService,
    ElizaServiceASGIApplication,
    ElizaServiceClient,
    ElizaServiceClientSync,
    ElizaServiceSync,
    ElizaServiceWSGIApplication,
)
from example.eliza_pb2 import SayRequest, SayResponse
from httpx import ASGITransport, AsyncClient, Client, WSGITransport


@pytest.mark.parametrize("compression", ["gzip", "identity", None])
def test_roundtrip_sync(compression: str) -> None:
    class RoundtripElizaServiceSync(ElizaServiceSync):
        def say(self, request, ctx):
            return SayResponse(sentence=request.sentence)

    app = ElizaServiceWSGIApplication(RoundtripElizaServiceSync())
    with ElizaServiceClientSync(
        "http://localhost",
        session=Client(transport=WSGITransport(app=app)),
        send_compression=compression,
        accept_compression=[compression] if compression else None,
    ) as client:
        response = client.say(SayRequest(sentence="Hello"))
    assert response.sentence == "Hello"


@pytest.mark.parametrize("compression", ["gzip", "identity"])
@pytest.mark.asyncio
async def test_roundtrip_async(compression: str) -> None:
    class DetailsElizaService(ElizaService):
        async def say(self, request, ctx):
            return SayResponse(sentence=request.sentence)

    app = ElizaServiceASGIApplication(DetailsElizaService())
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    async with ElizaServiceClient(
        "http://localhost",
        session=AsyncClient(transport=transport),
        send_compression=compression,
        accept_compression=[compression] if compression else None,
    ) as client:
        response = await client.say(SayRequest(sentence="Hello"))
    assert response.sentence == "Hello"


@pytest.mark.parametrize("compression", ["br", "zstd"])
def test_invalid_compression_sync(compression: str) -> None:
    class RoundtripElizaServiceSync(ElizaServiceSync):
        def say(self, request, ctx):
            return SayResponse(sentence=request.sentence)

    app = ElizaServiceWSGIApplication(RoundtripElizaServiceSync())

    with pytest.raises(
        ValueError, match=r"Unsupported compression method: .*"
    ) as exc_info:
        ElizaServiceClientSync(
            "http://localhost",
            session=Client(transport=WSGITransport(app=app)),
            send_compression=compression,
            accept_compression=[compression] if compression else None,
        )
    assert (
        str(exc_info.value)
        == f"Unsupported compression method: {compression}. Available methods: gzip, identity"
    )


@pytest.mark.parametrize("compression", ["br", "zstd"])
@pytest.mark.asyncio
async def test_invalid_compression_async(compression: str) -> None:
    class DetailsElizaService(ElizaService):
        async def say(self, request, ctx):
            return SayResponse(sentence=request.sentence)

    app = ElizaServiceASGIApplication(DetailsElizaService())
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    with pytest.raises(
        ValueError, match=r"Unsupported compression method: .*"
    ) as exc_info:
        ElizaServiceClient(
            "http://localhost",
            session=AsyncClient(transport=transport),
            send_compression=compression,
            accept_compression=[compression] if compression else None,
        )
    assert (
        str(exc_info.value)
        == f"Unsupported compression method: {compression}. Available methods: gzip, identity"
    )
