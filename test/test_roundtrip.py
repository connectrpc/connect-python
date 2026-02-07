from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pyqwest import Client, SyncClient
from pyqwest.testing import ASGITransport, WSGITransport

from connectrpc.code import Code
from connectrpc.errors import ConnectError

from ._util import resolve_compression
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
@pytest.mark.parametrize("compression_name", ["gzip", "br", "zstd", "identity"])
def test_roundtrip_sync(proto_json: bool, compression_name: str) -> None:
    class RoundtripHaberdasherSync(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    compression = resolve_compression(compression_name)
    app = HaberdasherWSGIApplication(
        RoundtripHaberdasherSync(), compressions=[compression]
    )
    with HaberdasherClientSync(
        "http://localhost",
        http_client=SyncClient(WSGITransport(app=app)),
        proto_json=proto_json,
        send_compression=compression,
        accept_compression=[compression],
    ) as client:
        response = client.make_hat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"


@pytest.mark.parametrize("proto_json", [False, True])
@pytest.mark.parametrize("compression_name", ["gzip", "br", "zstd", "identity"])
@pytest.mark.asyncio
async def test_roundtrip_async(proto_json: bool, compression_name: str) -> None:
    class DetailsHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    compression = resolve_compression(compression_name)
    app = HaberdasherASGIApplication(DetailsHaberdasher(), compressions=[compression])
    transport = ASGITransport(app)
    async with HaberdasherClient(
        "http://localhost",
        http_client=Client(transport),
        proto_json=proto_json,
        send_compression=compression,
        accept_compression=[compression],
    ) as client:
        response = await client.make_hat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"


def test_roundtrip_sync_connect_get_empty_request() -> None:
    class RoundtripHaberdasherSync(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    compression = resolve_compression("identity")
    app = HaberdasherWSGIApplication(
        RoundtripHaberdasherSync(), compressions=[compression]
    )
    with HaberdasherClientSync(
        "http://localhost",
        http_client=SyncClient(WSGITransport(app=app)),
        send_compression=compression,
        accept_compression=[compression],
    ) as client:
        response = client.make_hat(request=Size(), use_get=True)
    assert response.size == 0
    assert response.color == "green"


@pytest.mark.asyncio
async def test_roundtrip_async_connect_get_empty_request() -> None:
    class RoundtripHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    compression = resolve_compression("identity")
    app = HaberdasherASGIApplication(RoundtripHaberdasher(), compressions=[compression])
    transport = ASGITransport(app)
    async with HaberdasherClient(
        "http://localhost",
        http_client=Client(transport=transport),
        send_compression=compression,
        accept_compression=[compression],
    ) as client:
        response = await client.make_hat(request=Size(), use_get=True)
    assert response.size == 0
    assert response.color == "green"


@pytest.mark.parametrize("proto_json", [False, True])
@pytest.mark.parametrize("compression_name", ["gzip", "br", "zstd", "identity"])
@pytest.mark.asyncio
async def test_roundtrip_response_stream_async(
    proto_json: bool, compression_name: str
) -> None:
    class StreamingHaberdasher(Haberdasher):
        async def make_similar_hats(self, request, ctx):
            yield Hat(size=request.inches, color="green")
            yield Hat(size=request.inches, color="red")
            yield Hat(size=request.inches, color="blue")
            raise ConnectError(Code.RESOURCE_EXHAUSTED, "No more hats available")

    compression = resolve_compression(compression_name)
    app = HaberdasherASGIApplication(StreamingHaberdasher(), compressions=[compression])
    transport = ASGITransport(app)

    hats: list[Hat] = []
    async with HaberdasherClient(
        "http://localhost",
        http_client=Client(transport=transport),
        proto_json=proto_json,
        send_compression=compression,
        accept_compression=[compression],
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
@pytest.mark.parametrize("compression_name", ["gzip", "br", "zstd", "identity"])
def test_message_limit_sync(client_bad: bool, compression_name: str) -> None:
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

    compression = resolve_compression(compression_name)
    app = HaberdasherWSGIApplication(
        LargeHaberdasher(), read_max_bytes=100, compressions=[compression]
    )
    transport = WSGITransport(app)
    with HaberdasherClientSync(
        "http://localhost",
        http_client=SyncClient(transport),
        send_compression=compression,
        accept_compression=[compression],
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
@pytest.mark.parametrize("compression_name", ["gzip", "br", "zstd", "identity"])
@pytest.mark.asyncio
async def test_message_limit_async(client_bad: bool, compression_name: str) -> None:
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

    compression = resolve_compression(compression_name)
    app = HaberdasherASGIApplication(
        LargeHaberdasher(), read_max_bytes=100, compressions=[compression]
    )
    transport = ASGITransport(app)
    async with HaberdasherClient(
        "http://localhost",
        http_client=Client(transport=transport),
        send_compression=compression,
        accept_compression=[compression],
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
