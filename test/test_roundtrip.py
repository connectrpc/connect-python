from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient, Client, WSGITransport

from connectrpc.code import Code
from connectrpc.errors import ConnectError

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
    from collections.abc import AsyncIterator, Iterator


@pytest.mark.parametrize("proto_json", [False, True])
@pytest.mark.parametrize("compression", ["gzip", "br", "zstd", "identity", None])
def test_roundtrip_sync(proto_json: bool, compression: str) -> None:
    class RoundtripHaberdasherSync(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    app = HaberdasherWSGIApplication(RoundtripHaberdasherSync())
    with HaberdasherClientSync(
        "http://localhost",
        session=Client(transport=WSGITransport(app=app)),
        proto_json=proto_json,
        send_compression=compression,
        accept_compression=[compression] if compression else None,
    ) as client:
        response = client.make_hat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"


@pytest.mark.parametrize("proto_json", [False, True])
@pytest.mark.parametrize("compression", ["gzip", "br", "zstd", "identity"])
@pytest.mark.asyncio
async def test_roundtrip_async(proto_json: bool, compression: str) -> None:
    class DetailsHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    app = HaberdasherASGIApplication(DetailsHaberdasher())
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    async with HaberdasherClient(
        "http://localhost",
        session=AsyncClient(transport=transport),
        proto_json=proto_json,
        send_compression=compression,
        accept_compression=[compression] if compression else None,
    ) as client:
        response = await client.make_hat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"


@pytest.mark.parametrize("proto_json", [False, True])
@pytest.mark.parametrize("compression", ["gzip", "br", "zstd", "identity"])
@pytest.mark.asyncio
async def test_roundtrip_response_stream_async(
    proto_json: bool, compression: str
) -> None:
    class StreamingHaberdasher(Haberdasher):
        async def make_similar_hats(self, request, ctx):
            yield Hat(size=request.inches, color="green")
            yield Hat(size=request.inches, color="red")
            yield Hat(size=request.inches, color="blue")
            raise ConnectError(Code.RESOURCE_EXHAUSTED, "No more hats available")

    app = HaberdasherASGIApplication(StreamingHaberdasher())
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete

    hats: list[Hat] = []
    async with HaberdasherClient(
        "http://localhost",
        session=AsyncClient(transport=transport),
        proto_json=proto_json,
        send_compression=compression,
        accept_compression=[compression] if compression else None,
    ) as client:
        with pytest.raises(ConnectError) as exc_info:
            async for h in client.make_similar_hats(request=Size(inches=10)):
                hats.append(h)
    assert hats[0].size == 10
    assert hats[0].color == "green"
    assert hats[1].size == 10
    assert hats[1].color == "red"
    assert hats[2].size == 10
    assert hats[2].color == "blue"

    assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
    assert exc_info.value.message == "No more hats available"


@pytest.mark.parametrize("client_bad", [False, True])
@pytest.mark.parametrize("compression", ["gzip", "br", "zstd", "identity"])
def test_message_limit_sync(client_bad: bool, compression: str) -> None:
    requests: list[Size] = []
    responses: list[Hat] = []

    good_size = Size(description="good")
    bad_size = Size(description="X" * 1000)
    good_hat = Hat(color="good")
    bad_hat = Hat(color="X" * 1000)

    class LargeHaberdasher(HaberdasherSync):
        def make_hat(self, request, ctx):
            requests.append(request)
            return good_hat if client_bad else bad_hat

        def make_various_hats(self, request: Iterator[Size], ctx) -> Iterator[Hat]:
            for size in request:
                requests.append(size)
            yield Hat(color="good")
            yield good_hat if client_bad else bad_hat

    app = HaberdasherWSGIApplication(LargeHaberdasher(), read_max_bytes=100)
    transport = WSGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    with HaberdasherClientSync(
        "http://localhost",
        session=Client(transport=transport),
        send_compression=compression,
        accept_compression=[compression] if compression else None,
        read_max_bytes=100,
    ) as client:
        with pytest.raises(ConnectError) as exc_info:
            client.make_hat(request=bad_size if client_bad else good_size)
        assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
        assert exc_info.value.message == "message is larger than configured max 100"
        if client_bad:
            assert len(requests) == 0
        else:
            assert len(requests) == 1
        assert len(responses) == 0

        requests = []
        responses = []

        with pytest.raises(ConnectError) as exc_info:

            def request_stream():
                yield good_size
                yield bad_size if client_bad else good_size

            for h in client.make_various_hats(request=request_stream()):
                responses.append(h)
        assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
        assert exc_info.value.message == "message is larger than configured max 100"
        if client_bad:
            assert len(requests) == 1
            assert len(responses) == 0
        else:
            assert len(requests) == 2
            assert len(responses) == 1


@pytest.mark.parametrize("client_bad", [False, True])
@pytest.mark.parametrize("compression", ["gzip", "br", "zstd", "identity"])
@pytest.mark.asyncio
async def test_message_limit_async(client_bad: bool, compression: str) -> None:
    requests: list[Size] = []
    responses: list[Hat] = []

    good_size = Size(description="good")
    bad_size = Size(description="X" * 1000)
    good_hat = Hat(color="good")
    bad_hat = Hat(color="X" * 1000)

    class LargeHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            requests.append(request)
            return good_hat if client_bad else bad_hat

        async def make_various_hats(
            self, request: AsyncIterator[Size], ctx
        ) -> AsyncIterator[Hat]:
            async for size in request:
                requests.append(size)
            yield Hat(color="good")
            yield good_hat if client_bad else bad_hat

    app = HaberdasherASGIApplication(LargeHaberdasher(), read_max_bytes=100)
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete
    async with HaberdasherClient(
        "http://localhost",
        session=AsyncClient(transport=transport),
        send_compression=compression,
        accept_compression=[compression] if compression else None,
        read_max_bytes=100,
    ) as client:
        with pytest.raises(ConnectError) as exc_info:
            await client.make_hat(request=bad_size if client_bad else good_size)
        assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
        assert exc_info.value.message == "message is larger than configured max 100"
        if client_bad:
            assert len(requests) == 0
        else:
            assert len(requests) == 1
        assert len(responses) == 0

        requests = []
        responses = []

        with pytest.raises(ConnectError) as exc_info:

            async def request_stream():
                yield good_size
                yield bad_size if client_bad else good_size

            async for h in client.make_various_hats(request=request_stream()):
                responses.append(h)
        assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
        assert exc_info.value.message == "message is larger than configured max 100"
        if client_bad:
            assert len(requests) == 1
            assert len(responses) == 0
        else:
            assert len(requests) == 2
            assert len(responses) == 1
