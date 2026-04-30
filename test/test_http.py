from __future__ import annotations

import pytest
from pyqwest import Client, SyncClient
from pyqwest.testing import ASGITransport, WSGITransport

from .haberdasher_connect import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherSync,
    HaberdasherWSGIApplication,
)
from .haberdasher_pb2 import Hat

_charset_content_type_cases = [
    "application/json",
    "application/json; charset=utf-8",
    "application/json; charset=UTF-8",
    "application/json;charset=utf-8",
    "application/json;    charset=utf-8",
    "application/json; charset=utf-8; version=1",
    "application/JSON",
]


@pytest.mark.parametrize("header", _charset_content_type_cases)
def test_json_charset_content_type(header: str) -> None:
    class HeadersHaberdasherSync(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat(size=2)

    transport = WSGITransport(HaberdasherWSGIApplication(HeadersHaberdasherSync()))

    client = SyncClient(transport=transport)

    res = client.post(
        "http://localhost/connectrpc.example.Haberdasher/MakeHat",
        content=b"{}",
        headers={"content-type": header},
    )
    assert res.status == 200
    assert res.json() == {"size": 2}


@pytest.mark.asyncio
@pytest.mark.parametrize("header", _charset_content_type_cases)
async def test_json_charset_content_type_async(header: str) -> None:
    class HeadersHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat(size=2)

    transport = ASGITransport(HaberdasherASGIApplication(HeadersHaberdasher()))

    client = Client(transport=transport)

    res = await client.post(
        "http://localhost/connectrpc.example.Haberdasher/MakeHat",
        content=b"{}",
        headers={"content-type": header},
    )
    assert res.status == 200
    assert res.json() == {"size": 2}
