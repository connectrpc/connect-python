from __future__ import annotations

import asyncio
import io
import json
import struct
from typing import TYPE_CHECKING

import pytest
from pyqwest import Client, SyncClient
from pyqwest.testing import ASGITransport, WSGITransport

from connectrpc import ProtoJSONCodec
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

    from asgiref.typing import HTTPDisconnectEvent, HTTPRequestEvent, HTTPScope


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


@pytest.mark.asyncio
async def test_server_stream_client_disconnect() -> None:
    """Server streaming generator should be closed when the client disconnects.

    Regression test for https://github.com/connectrpc/connect-python/issues/174.
    """
    generator_closed = asyncio.Event()

    class InfiniteHaberdasher(Haberdasher):
        async def make_similar_hats(self, request, ctx):
            try:
                while True:
                    yield Hat(size=request.inches, color="green")
                    await asyncio.sleep(0)  # yield control to event loop
            finally:
                generator_closed.set()

    app = HaberdasherASGIApplication(InfiniteHaberdasher())

    # Encode a Connect protocol (application/connect+proto) request for Size(inches=10).
    request_bytes = Size(inches=10).SerializeToString()
    request_body = struct.pack(">BI", 0, len(request_bytes)) + request_bytes

    # We invoke the ASGI app directly rather than using a real client with a
    # short timeout because a real client could trigger the disconnect before the
    # request body has been fully read, which would be a different code path.
    disconnect_trigger = asyncio.Event()
    response_count = 0
    call_count = 0

    async def receive() -> HTTPRequestEvent | HTTPDisconnectEvent:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"type": "http.request", "body": request_body, "more_body": False}
        # Block until the test is ready to simulate a disconnect.
        await disconnect_trigger.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal response_count
        if message.get("type") == "http.response.body" and message.get(
            "more_body", False
        ):
            response_count += 1
            if response_count >= 3:
                disconnect_trigger.set()

    scope: HTTPScope = {
        "type": "http",
        "asgi": {"spec_version": "2.0", "version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/connectrpc.example.Haberdasher/MakeSimilarHats",
        "raw_path": b"/connectrpc.example.Haberdasher/MakeSimilarHats",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/connect+proto")],
        "client": None,
        "server": None,
        "extensions": None,
    }

    # Without the fix the app hangs forever (generator never stopped), causing a
    # TimeoutError here.  With the fix it terminates promptly after the disconnect.
    await asyncio.wait_for(app(scope, receive, send), timeout=5.0)

    assert generator_closed.is_set(), (
        "generator should be closed after client disconnect"
    )


_json_codec = ProtoJSONCodec(
    marshal_options={"always_print_fields_with_no_presence": True}
)


def test_json_codec_server_sync() -> None:
    """WSGI server with custom json_codec includes empty repeated in JSON wire body."""

    class SyncHaberdasher(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    app = HaberdasherWSGIApplication(SyncHaberdasher(), json_codec=_json_codec)
    with HaberdasherClientSync(
        "http://localhost",
        http_client=SyncClient(WSGITransport(app=app)),
        proto_json=True,
        send_compression=None,
        accept_compression=[],
    ) as client:
        response = client.make_hat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"


def test_json_codec_server_sync_wire_body() -> None:
    """Verify the wire JSON body from WSGI server contains empty repeated field."""

    class SyncHaberdasher(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    app = HaberdasherWSGIApplication(SyncHaberdasher(), json_codec=_json_codec)
    http_client = SyncClient(WSGITransport(app=app))
    resp = http_client.post(
        "http://localhost/connectrpc.example.Haberdasher/MakeHat",
        content=b'{"inches": 10}',
        headers={"content-type": "application/json"},
    )
    body = json.loads(resp.content)
    assert "tags" in body
    assert body["tags"] == []


def test_json_codec_server_sync_proto_unaffected() -> None:
    """Proto binary requests still work when json_codec is overridden on WSGI server."""

    class SyncHaberdasher(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="blue")

    app = HaberdasherWSGIApplication(SyncHaberdasher(), json_codec=_json_codec)
    with HaberdasherClientSync(
        "http://localhost",
        http_client=SyncClient(WSGITransport(app=app)),
        proto_json=False,
        send_compression=None,
        accept_compression=[],
    ) as client:
        response = client.make_hat(request=Size(inches=5))
    assert response.size == 5
    assert response.color == "blue"


@pytest.mark.asyncio
async def test_json_codec_server_async() -> None:
    """ASGI server with custom json_codec includes empty repeated in JSON wire body."""

    class AsyncHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    app = HaberdasherASGIApplication(AsyncHaberdasher(), json_codec=_json_codec)
    transport = ASGITransport(app)
    async with HaberdasherClient(
        "http://localhost",
        http_client=Client(transport),
        proto_json=True,
        send_compression=None,
        accept_compression=[],
    ) as client:
        response = await client.make_hat(request=Size(inches=10))
    assert response.size == 10
    assert response.color == "green"


@pytest.mark.asyncio
async def test_json_codec_server_async_wire_body() -> None:
    """Verify the wire JSON body from ASGI server contains empty repeated field."""

    class AsyncHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    app = HaberdasherASGIApplication(AsyncHaberdasher(), json_codec=_json_codec)
    transport = ASGITransport(app)
    http_client = Client(transport)
    resp = await http_client.post(
        "http://localhost/connectrpc.example.Haberdasher/MakeHat",
        content=b'{"inches": 10}',
        headers={"content-type": "application/json"},
    )
    body = json.loads(resp.content)
    assert "tags" in body
    assert body["tags"] == []


@pytest.mark.asyncio
async def test_json_codec_server_async_proto_unaffected() -> None:
    """Proto binary requests still work when json_codec is overridden on ASGI server."""

    class AsyncHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="blue")

    app = HaberdasherASGIApplication(AsyncHaberdasher(), json_codec=_json_codec)
    transport = ASGITransport(app)
    async with HaberdasherClient(
        "http://localhost",
        http_client=Client(transport),
        proto_json=False,
        send_compression=None,
        accept_compression=[],
    ) as client:
        response = await client.make_hat(request=Size(inches=5))
    assert response.size == 5
    assert response.color == "blue"


def test_json_codec_client_sync() -> None:
    """Sync client with custom json_codec encodes request with marshal options."""
    captured_bodies: list[bytes] = []

    class SyncHaberdasher(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    inner_app = HaberdasherWSGIApplication(SyncHaberdasher())

    def capturing_app(environ, start_response):
        body = environ["wsgi.input"].read()
        captured_bodies.append(body)
        environ["wsgi.input"] = io.BytesIO(body)
        return inner_app(environ, start_response)

    with HaberdasherClientSync(
        "http://localhost",
        http_client=SyncClient(WSGITransport(app=capturing_app)),
        proto_json=True,
        json_codec=_json_codec,
        send_compression=None,
        accept_compression=[],
    ) as client:
        client.make_hat(request=Size(inches=7))

    assert len(captured_bodies) == 1
    request_body = json.loads(captured_bodies[0])
    # always_print_fields_with_no_presence causes the default-valued
    # "description" field to appear in the wire JSON.
    assert "description" in request_body
    assert request_body["description"] == ""


@pytest.mark.asyncio
async def test_json_codec_client_async() -> None:
    """Async client with custom json_codec encodes request with marshal options."""
    captured_bodies: list[bytes] = []

    class AsyncHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat(size=request.inches, color="green")

    inner_app = HaberdasherASGIApplication(AsyncHaberdasher())

    async def capturing_app(scope, receive, send):
        if scope["type"] == "http":
            original_receive = receive

            async def capturing_receive():
                message = await original_receive()
                body = message.get("body", b"")
                if message.get("type") == "http.request" and body:
                    captured_bodies.append(body)
                return message

            await inner_app(scope, capturing_receive, send)
        else:
            await inner_app(scope, receive, send)

    async with HaberdasherClient(
        "http://localhost",
        http_client=Client(ASGITransport(capturing_app)),
        proto_json=True,
        json_codec=_json_codec,
        send_compression=None,
        accept_compression=[],
    ) as client:
        await client.make_hat(request=Size(inches=7))

    assert len(captured_bodies) == 1
    request_body = json.loads(captured_bodies[0])
    assert "description" in request_body
    assert request_body["description"] == ""


def test_json_codec_client_requires_proto_json_sync() -> None:
    """Sync client raises ValueError if json_codec is set without proto_json=True."""
    with pytest.raises(ValueError, match="json_codec requires proto_json=True"):
        HaberdasherClientSync("http://localhost", json_codec=_json_codec)


@pytest.mark.asyncio
async def test_json_codec_client_requires_proto_json_async() -> None:
    """Async client raises ValueError if json_codec is set without proto_json=True."""
    with pytest.raises(ValueError, match="json_codec requires proto_json=True"):
        HaberdasherClient("http://localhost", json_codec=_json_codec)
