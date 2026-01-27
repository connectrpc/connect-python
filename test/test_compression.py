from __future__ import annotations

import pytest
from pyqwest import Client, SyncClient
from pyqwest.testing import ASGITransport, WSGITransport

from connectrpc.client import ResponseMetadata

from .haberdasher_connect import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherClient,
    HaberdasherClientSync,
    HaberdasherSync,
    HaberdasherWSGIApplication,
)
from .haberdasher_pb2 import Hat, Size


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("compressions", "encoding"),
    [
        pytest.param((), "identity", id="none"),
        pytest.param(("gzip",), "gzip", id="gzip"),
        pytest.param(("zstd",), "zstd", id="zstd"),
        pytest.param(("br",), "br", id="br"),
        pytest.param(("gzip", "br", "zstd"), "zstd", id="all"),
    ],
)
async def test_server_compressions_async(
    compressions: tuple[str], encoding: str
) -> None:
    class SimpleHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat(size=10, color="blue")

    app = HaberdasherASGIApplication(SimpleHaberdasher(), compressions=compressions)
    with ResponseMetadata() as meta:
        client = HaberdasherClient(
            "http://localhost",
            http_client=Client(ASGITransport(app)),
            accept_compression=["zstd", "gzip", "br"],
        )
        res = await client.make_hat(Size(inches=10))
    assert res.size == 10
    assert res.color == "blue"
    assert meta.headers().get("content-encoding") == encoding


@pytest.mark.parametrize(
    ("compressions", "encoding"),
    [
        pytest.param((), "identity", id="none"),
        pytest.param(("gzip",), "gzip", id="gzip"),
        pytest.param(("zstd",), "zstd", id="zstd"),
        pytest.param(("br",), "br", id="br"),
        pytest.param(("gzip", "br", "zstd"), "zstd", id="all"),
    ],
)
def test_server_compressions_sync(compressions: tuple[str], encoding: str) -> None:
    class SimpleHaberdasher(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat(size=10, color="blue")

    app = HaberdasherWSGIApplication(SimpleHaberdasher(), compressions=compressions)
    client = HaberdasherClientSync(
        "http://localhost",
        http_client=SyncClient(WSGITransport(app)),
        accept_compression=["zstd", "gzip", "br"],
    )
    with ResponseMetadata() as meta:
        res = client.make_hat(Size(inches=10))
    assert res.size == 10
    assert res.color == "blue"
    assert meta.headers().get("content-encoding") == encoding


def test_server_unsupported_compression_async() -> None:
    class SimpleHaberdasher(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat(size=10, color="blue")

    with pytest.raises(ValueError, match="unknown compression"):
        HaberdasherWSGIApplication(SimpleHaberdasher(), compressions=("unknown",))


def test_server_unsupported_compression_sync() -> None:
    class SimpleHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat(size=10, color="blue")

    with pytest.raises(ValueError, match="unknown compression"):
        HaberdasherASGIApplication(SimpleHaberdasher(), compressions=("unknown",))
