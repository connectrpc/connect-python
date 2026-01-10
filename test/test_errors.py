from __future__ import annotations

import threading
import time
from http import HTTPStatus
from typing import NoReturn

import pytest
import uvicorn
from httpx import (
    ASGITransport,
    AsyncClient,
    Client,
    MockTransport,
    Request,
    Response,
    Timeout,
    WSGITransport,
)

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

_errors = [
    (Code.CANCELED, "Operation was cancelled", 499),
    (Code.UNKNOWN, "An unknown error occurred", 500),
    (Code.INVALID_ARGUMENT, "That's not right", 400),
    (Code.DEADLINE_EXCEEDED, "Deadline exceeded", 504),
    (Code.NOT_FOUND, "Resource not found", 404),
    (Code.ALREADY_EXISTS, "Resource already exists", 409),
    (Code.PERMISSION_DENIED, "Permission denied", 403),
    (Code.RESOURCE_EXHAUSTED, "Resource exhausted", 429),
    (Code.FAILED_PRECONDITION, "Failed precondition", 400),
    (Code.ABORTED, "Operation aborted", 409),
    (Code.OUT_OF_RANGE, "Out of range", 400),
    (Code.UNIMPLEMENTED, "Method not implemented", 501),
    (Code.INTERNAL, "Internal server error", 500),
    (Code.UNAVAILABLE, "Service unavailable", 503),
    (Code.DATA_LOSS, "Data loss occurred", 500),
    (Code.UNAUTHENTICATED, "Unauthenticated access", 401),
]


@pytest.mark.parametrize(("code", "message", "http_status"), _errors)
def test_sync_errors(code: Code, message: str, http_status: int) -> None:
    class ErrorHaberdasherSync(HaberdasherSync):
        def __init__(self, exception: ConnectError) -> None:
            self._exception = exception

        def make_hat(self, request, ctx) -> NoReturn:
            raise self._exception

    haberdasher = ErrorHaberdasherSync(ConnectError(code, message))
    app = HaberdasherWSGIApplication(haberdasher)
    transport = WSGITransport(app)

    recorded_response: Response | None = None

    def record_response(response) -> None:
        nonlocal recorded_response
        recorded_response = response

    session = Client(transport=transport, event_hooks={"response": [record_response]})

    with (
        HaberdasherClientSync("http://localhost", session=session) as client,
        pytest.raises(ConnectError) as exc_info,
    ):
        client.make_hat(request=Size(inches=10))

    assert exc_info.value.code == code
    assert exc_info.value.message == message
    assert recorded_response is not None
    assert recorded_response.status_code == http_status


@pytest.mark.asyncio
@pytest.mark.parametrize(("code", "message", "http_status"), _errors)
async def test_async_errors(code: Code, message: str, http_status: int) -> None:
    class ErrorHaberdasher(Haberdasher):
        def __init__(self, exception: ConnectError) -> None:
            self._exception = exception

        async def make_hat(self, request, ctx) -> NoReturn:
            raise self._exception

    haberdasher = ErrorHaberdasher(ConnectError(code, message))
    app = HaberdasherASGIApplication(haberdasher)
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete

    recorded_response: Response | None = None

    async def record_response(response) -> None:
        nonlocal recorded_response
        recorded_response = response

    async with (
        AsyncClient(
            transport=transport, event_hooks={"response": [record_response]}
        ) as session,
        HaberdasherClient("http://localhost", session=session) as client,
    ):
        with pytest.raises(ConnectError) as exc_info:
            await client.make_hat(request=Size(inches=10))

    assert exc_info.value.code == code
    assert exc_info.value.message == message
    assert recorded_response is not None
    assert recorded_response.status_code == http_status


_http_errors = [
    pytest.param(400, {}, Code.INTERNAL, "Bad Request", id="400"),
    pytest.param(401, {}, Code.UNAUTHENTICATED, "Unauthorized", id="401"),
    pytest.param(403, {}, Code.PERMISSION_DENIED, "Forbidden", id="403"),
    pytest.param(404, {}, Code.UNIMPLEMENTED, "Not Found", id="404"),
    pytest.param(429, {}, Code.UNAVAILABLE, "Too Many Requests", id="429"),
    pytest.param(499, {}, Code.UNKNOWN, "Client Closed Request", id="499"),
    pytest.param(502, {}, Code.UNAVAILABLE, "Bad Gateway", id="502"),
    pytest.param(503, {}, Code.UNAVAILABLE, "Service Unavailable", id="503"),
    pytest.param(504, {}, Code.UNAVAILABLE, "Gateway Timeout", id="504"),
    pytest.param(
        400,
        {"json": {"code": "invalid_argument", "message": "Bad parameter"}},
        Code.INVALID_ARGUMENT,
        "Bad parameter",
        id="connect error",
    ),
    pytest.param(
        400,
        {"json": {"message": "Bad parameter"}},
        Code.INTERNAL,
        "Bad parameter",
        id="connect error without code",
    ),
    pytest.param(
        404,
        {"json": {"code": "not_found"}},
        Code.NOT_FOUND,
        "",
        id="connect error without message",
    ),
    pytest.param(
        502, {"text": '"{bad_json'}, Code.UNAVAILABLE, "Bad Gateway", id="bad json"
    ),
    pytest.param(
        200,
        {
            "text": "weird encoding",
            "headers": {
                "content-type": "application/proto",
                "content-encoding": "weird",
            },
        },
        Code.INTERNAL,
        "unknown encoding 'weird'; accepted encodings are gzip, br, zstd, identity",
        id="bad encoding",
    ),
]


@pytest.mark.parametrize(
    ("response_status", "response_kwargs", "code", "message"), _http_errors
)
def test_sync_http_errors(response_status, response_kwargs, code, message) -> None:
    transport = MockTransport(lambda _: Response(response_status, **response_kwargs))
    with (
        HaberdasherClientSync(
            "http://localhost", session=Client(transport=transport)
        ) as client,
        pytest.raises(ConnectError) as exc_info,
    ):
        client.make_hat(request=Size(inches=10))
    assert exc_info.value.code == code
    assert exc_info.value.message == message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response_status", "response_kwargs", "code", "message"), _http_errors
)
async def test_async_http_errors(
    response_status, response_kwargs, code, message
) -> None:
    transport = MockTransport(lambda _: Response(response_status, **response_kwargs))
    async with HaberdasherClient(
        "http://localhost", session=AsyncClient(transport=transport)
    ) as client:
        with pytest.raises(ConnectError) as exc_info:
            await client.make_hat(request=Size(inches=10))
    assert exc_info.value.code == code
    assert exc_info.value.message == message


_client_errors = [
    pytest.param(
        "PUT",
        "/connectrpc.example.Haberdasher/MakeHat",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.METHOD_NOT_ALLOWED,
        {"Allow": "GET, POST"},
        id="bad method",
    ),
    pytest.param(
        "POST",
        "/notservicemethod",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.NOT_FOUND,
        {},
        id="not found",
    ),
    pytest.param(
        "POST",
        "/notservice/method",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.NOT_FOUND,
        {},
        id="not present service",
    ),
    pytest.param(
        "POST",
        "/connectrpc.example.Haberdasher/notmethod",
        {"Content-Type": "application/proto"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.NOT_FOUND,
        {},
        id="not present method",
    ),
    pytest.param(
        "POST",
        "/connectrpc.example.Haberdasher/MakeHat",
        {"Content-Type": "text/html"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        {"Accept-Post": "application/json, application/proto"},
        id="bad content type",
    ),
    pytest.param(
        "POST",
        "/connectrpc.example.Haberdasher/MakeHat",
        {"Content-Type": "application/proto", "connect-protocol-version": "2"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.BAD_REQUEST,
        {"content-type": "application/json"},
        id="bad connect protocol version",
    ),
    pytest.param(
        "POST",
        "/connectrpc.example.Haberdasher/MakeHat",
        {"Content-Type": "application/proto", "connect-timeout-ms": "10000000000"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.BAD_REQUEST,
        {"content-type": "application/json"},
        id="connect timeout header too long",
    ),
    pytest.param(
        "POST",
        "/connectrpc.example.Haberdasher/MakeHat",
        {"Content-Type": "application/proto", "connect-timeout-ms": "goodbeer"},
        Size(inches=10).SerializeToString(),
        HTTPStatus.BAD_REQUEST,
        {"content-type": "application/json"},
        id="connect timeout header invalid",
    ),
]


@pytest.mark.parametrize(
    ("method", "path", "headers", "body", "response_status", "response_headers"),
    _client_errors,
)
def test_sync_client_errors(
    method, path, headers, body, response_status, response_headers
) -> None:
    class ValidHaberdasherSync(HaberdasherSync):
        def make_hat(self, request, ctx):
            return Hat()

    app = HaberdasherWSGIApplication(ValidHaberdasherSync())
    transport = WSGITransport(app)

    client = Client(transport=transport)
    response = client.request(
        method=method, url=f"http://localhost{path}", content=body, headers=headers
    )

    assert response.status_code == response_status
    assert response.headers == response_headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "headers", "body", "response_status", "response_headers"),
    _client_errors,
)
async def test_async_client_errors(
    method, path, headers, body, response_status, response_headers
) -> None:
    class ValidHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx):
            return Hat()

    haberdasher = ValidHaberdasher()
    app = HaberdasherASGIApplication(haberdasher)
    transport = ASGITransport(app)  # pyright:ignore[reportArgumentType] - httpx type is not complete

    client = AsyncClient(transport=transport)
    response = await client.request(
        method=method, url=f"http://localhost{path}", content=body, headers=headers
    )

    assert response.status_code == response_status
    assert response.headers == response_headers


# To exercise timeouts, can't use mock transports
@pytest.fixture(scope="module")
def timeout_server():
    class SleepingHaberdasher(Haberdasher):
        def make_hat(self, request, ctx) -> NoReturn:
            time.sleep(10)
            raise AssertionError("Should be timedout already")

    app = HaberdasherASGIApplication(SleepingHaberdasher())
    config = uvicorn.Config(
        app, port=0, log_level="critical", timeout_graceful_shutdown=0
    )
    server = uvicorn.Server(config)
    # Since we want to target the server from sync clients as well as async,
    # it's best to use a sync fixture with the server on a background thread.
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()

    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started

    port = server.servers[0].sockets[0].getsockname()[1]

    yield f"http://localhost:{port}"

    server.should_exit = True


@pytest.mark.parametrize(
    ("client_timeout_ms", "call_timeout_ms"), [(200, None), (None, 200)]
)
def test_sync_client_timeout(
    client_timeout_ms, call_timeout_ms, timeout_server: str
) -> None:
    recorded_timeout_header = ""

    def modify_timeout_header(request: Request) -> None:
        nonlocal recorded_timeout_header
        recorded_timeout_header = request.headers.get("connect-timeout-ms")
        # Make sure server doesn't timeout since we are verifying client timeout
        request.headers["connect-timeout-ms"] = "10000"

    with (
        Client(
            timeout=Timeout(
                None,
                read=client_timeout_ms / 1000.0
                if client_timeout_ms is not None
                else None,
            ),
            event_hooks={"request": [modify_timeout_header]},
        ) as session,
        HaberdasherClientSync(
            timeout_server, timeout_ms=client_timeout_ms, session=session
        ) as client,
        pytest.raises(ConnectError) as exc_info,
    ):
        client.make_hat(request=Size(inches=10), timeout_ms=call_timeout_ms)

    assert exc_info.value.code == Code.DEADLINE_EXCEEDED
    assert exc_info.value.message == "Request timed out"
    assert recorded_timeout_header == "200"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("client_timeout_ms", "call_timeout_ms"), [(200, None), (None, 200)]
)
async def test_async_client_timeout(
    client_timeout_ms, call_timeout_ms, timeout_server: str
) -> None:
    recorded_timeout_header = ""

    async def modify_timeout_header(request: Request) -> None:
        nonlocal recorded_timeout_header
        recorded_timeout_header = request.headers.get("connect-timeout-ms")
        # Make sure server doesn't timeout since we are verifying client timeout
        request.headers["connect-timeout-ms"] = "10000"

    async with (
        AsyncClient(
            timeout=Timeout(None), event_hooks={"request": [modify_timeout_header]}
        ) as session,
        HaberdasherClient(
            timeout_server, timeout_ms=client_timeout_ms, session=session
        ) as client,
    ):
        with pytest.raises(ConnectError) as exc_info:
            await client.make_hat(request=Size(inches=10), timeout_ms=call_timeout_ms)

    assert exc_info.value.code == Code.DEADLINE_EXCEEDED
    assert exc_info.value.message == "Request timed out"
    assert recorded_timeout_header == "200"
