from __future__ import annotations

import pytest
from connectrpc._compression import get_accept_encoding_compressions
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


def test_accept_encoding_only_includes_available_compressions():
    """Verify Accept-Encoding only advertises compressions that are actually available.

    When brotli and zstandard are not installed (as in the noextras environment),
    the Accept-Encoding header should not include 'br' or 'zstd'.
    """
    available = get_accept_encoding_compressions()
    assert "br" not in available, "brotli should not be advertised when not installed"
    assert "zstd" not in available, "zstd should not be advertised when not installed"
    assert "gzip" in available, "gzip should always be available"
    assert "identity" not in available, "identity should not be in Accept-Encoding"
