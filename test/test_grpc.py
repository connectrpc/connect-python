from __future__ import annotations

import grpc
import pytest
import pytest_asyncio
from example.eliza_pb2 import SayRequest, SayResponse
from example.eliza_pb2_grpc import ElizaServiceStub
from pyvoy import Interface, PyvoyServer

from connectrpc._protocol_grpc import _parse_timeout


@pytest_asyncio.fixture(scope="module")
async def url_asgi():
    async with PyvoyServer("example.eliza_service") as server:
        yield f"localhost:{server.listener_port}"


@pytest_asyncio.fixture(scope="module")
async def url_wsgi():
    async with PyvoyServer("example.eliza_service_sync", interface="wsgi") as server:
        yield f"localhost:{server.listener_port}"


@pytest.fixture(params=["asgi", "wsgi"])
def interface(request: pytest.FixtureRequest) -> Interface:
    return request.param


@pytest.fixture
def url(interface: Interface, url_asgi: str, url_wsgi: str) -> str:
    match interface:
        case "asgi":
            return url_asgi
        case "wsgi":
            return url_wsgi


@pytest.mark.asyncio
async def test_grpc_unary(url: str) -> None:
    async with grpc.aio.insecure_channel(url) as channel:
        client = ElizaServiceStub(channel)
        response: SayResponse = await client.Say(SayRequest(sentence="Hello"))
        assert len(response.sentence) > 0


def test_parse_timeout() -> None:
    assert _parse_timeout("1H") == 3600 * 1000
    assert _parse_timeout("2M") == 2 * 60 * 1000
    assert _parse_timeout("3S") == 3 * 1000
    assert _parse_timeout("4m") == 4
    # We parse gRPC timeouts with connect conventions, which means integer milliseconds
    # The below parse to 0ms.
    assert _parse_timeout("5u") == 0
    assert _parse_timeout("6n") == 0
    with pytest.raises(ValueError, match="protocol error") as excinfo:
        _parse_timeout("100X")
    assert "protocol error: timeout has invalid unit 'X'" in str(excinfo.value)
