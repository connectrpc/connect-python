from __future__ import annotations

import argparse
import asyncio
import os
import re
import signal
import socket
import ssl
import sys
import time
from contextlib import ExitStack, closing
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Literal, TypeVar, get_args

from _util import create_standard_streams
from gen.connectrpc.conformance.v1.config_pb2 import Code as ConformanceCode
from gen.connectrpc.conformance.v1.server_compat_pb2 import (
    ServerCompatRequest,
    ServerCompatResponse,
)
from gen.connectrpc.conformance.v1.service_connect import (
    ConformanceService,
    ConformanceServiceASGIApplication,
    ConformanceServiceSync,
    ConformanceServiceWSGIApplication,
)
from gen.connectrpc.conformance.v1.service_pb2 import (
    BidiStreamRequest,
    BidiStreamResponse,
    ClientStreamRequest,
    ClientStreamResponse,
    ConformancePayload,
    IdempotentUnaryRequest,
    IdempotentUnaryResponse,
    ServerStreamRequest,
    ServerStreamResponse,
    StreamResponseDefinition,
    UnaryRequest,
    UnaryResponse,
    UnaryResponseDefinition,
)
from google.protobuf.any_pb2 import Any

from connectrpc.code import Code
from connectrpc.errors import ConnectError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from google.protobuf.message import Message

    from connectrpc.request import RequestContext


# TODO: Use google.protobuf.any.pack on upgrade to protobuf==6.
def pack(msg: Message) -> Any:
    any_msg = Any()
    any_msg.Pack(msg)
    return any_msg


def _convert_code(conformance_code: ConformanceCode) -> Code:
    match conformance_code:
        case ConformanceCode.CODE_CANCELED:
            return Code.CANCELED
        case ConformanceCode.CODE_UNKNOWN:
            return Code.UNKNOWN
        case ConformanceCode.CODE_INVALID_ARGUMENT:
            return Code.INVALID_ARGUMENT
        case ConformanceCode.CODE_DEADLINE_EXCEEDED:
            return Code.DEADLINE_EXCEEDED
        case ConformanceCode.CODE_NOT_FOUND:
            return Code.NOT_FOUND
        case ConformanceCode.CODE_ALREADY_EXISTS:
            return Code.ALREADY_EXISTS
        case ConformanceCode.CODE_PERMISSION_DENIED:
            return Code.PERMISSION_DENIED
        case ConformanceCode.CODE_RESOURCE_EXHAUSTED:
            return Code.RESOURCE_EXHAUSTED
        case ConformanceCode.CODE_FAILED_PRECONDITION:
            return Code.FAILED_PRECONDITION
        case ConformanceCode.CODE_ABORTED:
            return Code.ABORTED
        case ConformanceCode.CODE_OUT_OF_RANGE:
            return Code.OUT_OF_RANGE
        case ConformanceCode.CODE_UNIMPLEMENTED:
            return Code.UNIMPLEMENTED
        case ConformanceCode.CODE_INTERNAL:
            return Code.INTERNAL
        case ConformanceCode.CODE_UNAVAILABLE:
            return Code.UNAVAILABLE
        case ConformanceCode.CODE_DATA_LOSS:
            return Code.DATA_LOSS
        case ConformanceCode.CODE_UNAUTHENTICATED:
            return Code.UNAUTHENTICATED
    msg = f"Unknown ConformanceCode: {conformance_code}"
    raise ValueError(msg)


RES = TypeVar(
    "RES",
    bound=UnaryResponse
    | IdempotentUnaryResponse
    | ClientStreamResponse
    | ServerStreamResponse
    | BidiStreamResponse,
)


def _send_headers(
    ctx: RequestContext, definition: UnaryResponseDefinition | StreamResponseDefinition
) -> None:
    for header in definition.response_headers:
        for value in header.value:
            ctx.response_headers().add(header.name, value)
    for trailer in definition.response_trailers:
        for value in trailer.value:
            ctx.response_trailers().add(trailer.name, value)


def _create_request_info(
    ctx: RequestContext, reqs: list[Any]
) -> ConformancePayload.RequestInfo:
    request_info = ConformancePayload.RequestInfo(requests=reqs)
    timeout_ms = ctx.timeout_ms()
    if timeout_ms is not None:
        request_info.timeout_ms = int(timeout_ms)
    for key in ctx.request_headers():
        request_info.request_headers.add(
            name=key, value=ctx.request_headers().getall(key)
        )
    return request_info


async def _handle_unary_response(
    definition: UnaryResponseDefinition, reqs: list[Any], res: RES, ctx: RequestContext
) -> RES:
    _send_headers(ctx, definition)
    request_info = _create_request_info(ctx, reqs)

    if definition.WhichOneof("response") == "error":
        raise ConnectError(
            code=_convert_code(definition.error.code),
            message=definition.error.message,
            details=[*definition.error.details, request_info],
        )
    if definition.response_delay_ms:
        await asyncio.sleep(definition.response_delay_ms / 1000.0)

    res.payload.request_info.CopyFrom(request_info)
    res.payload.data = definition.response_data
    return res


class TestService(ConformanceService):
    async def unary(self, request: UnaryRequest, ctx: RequestContext) -> UnaryResponse:
        return await _handle_unary_response(
            request.response_definition, [pack(request)], UnaryResponse(), ctx
        )

    async def idempotent_unary(
        self, request: IdempotentUnaryRequest, ctx: RequestContext
    ) -> IdempotentUnaryResponse:
        return await _handle_unary_response(
            request.response_definition, [pack(request)], IdempotentUnaryResponse(), ctx
        )

    async def client_stream(
        self, request: AsyncIterator[ClientStreamRequest], ctx: RequestContext
    ) -> ClientStreamResponse:
        requests: list[Any] = []
        definition: UnaryResponseDefinition | None = None
        async for message in request:
            requests.append(pack(message))
            if not definition:
                definition = message.response_definition

        if not definition:
            msg = "ClientStream must have a response definition"
            raise ValueError(msg)
        return await _handle_unary_response(
            definition, requests, ClientStreamResponse(), ctx
        )

    async def server_stream(
        self, request: ServerStreamRequest, ctx: RequestContext
    ) -> AsyncIterator[ServerStreamResponse]:
        definition = request.response_definition
        _send_headers(ctx, definition)
        request_info = _create_request_info(ctx, [pack(request)])
        sent_message = False
        for res_data in definition.response_data:
            res = ServerStreamResponse()
            if not sent_message:
                res.payload.request_info.CopyFrom(request_info)
            res.payload.data = res_data
            if definition.response_delay_ms:
                await asyncio.sleep(definition.response_delay_ms / 1000.0)
            sent_message = True
            yield res

        if definition.HasField("error"):
            details: list[Message] = [*definition.error.details]
            if not sent_message:
                details.append(request_info)
            raise ConnectError(
                code=_convert_code(definition.error.code),
                message=definition.error.message,
                details=details,
            )

    async def bidi_stream(
        self, request: AsyncIterator[BidiStreamRequest], ctx: RequestContext
    ) -> AsyncIterator[BidiStreamResponse]:
        definition: StreamResponseDefinition | None = None
        full_duplex = False
        requests: list[Any] = []
        res_idx = 0
        async for message in request:
            if not definition:
                definition = message.response_definition
                _send_headers(ctx, definition)
                full_duplex = message.full_duplex
            requests.append(pack(message))
            if not full_duplex:
                continue
            if not definition or res_idx >= len(definition.response_data):
                break
            if definition.response_delay_ms:
                await asyncio.sleep(definition.response_delay_ms / 1000.0)
            res = BidiStreamResponse()
            res.payload.data = definition.response_data[res_idx]
            res.payload.request_info.CopyFrom(
                _create_request_info(ctx, [pack(message)])
            )
            yield res
            res_idx += 1
            requests = []

        if not definition:
            return

        request_info = _create_request_info(ctx, requests)
        for i in range(res_idx, len(definition.response_data)):
            if definition.response_delay_ms:
                await asyncio.sleep(definition.response_delay_ms / 1000.0)
            res = BidiStreamResponse()
            res.payload.data = definition.response_data[i]
            if i == 0:
                res.payload.request_info.CopyFrom(request_info)
            yield res

        if definition.HasField("error"):
            details: list[Message] = [*definition.error.details]
            if len(definition.response_data) == 0:
                details.append(request_info)
            raise ConnectError(
                code=_convert_code(definition.error.code),
                message=definition.error.message,
                details=details,
            )


def _handle_unary_response_sync(
    definition: UnaryResponseDefinition, reqs: list[Any], res: RES, ctx: RequestContext
) -> RES:
    _send_headers(ctx, definition)
    request_info = _create_request_info(ctx, reqs)

    if definition.WhichOneof("response") == "error":
        raise ConnectError(
            code=_convert_code(definition.error.code),
            message=definition.error.message,
            details=[*definition.error.details, request_info],
        )
    if definition.response_delay_ms:
        time.sleep(definition.response_delay_ms / 1000.0)

    res.payload.request_info.CopyFrom(request_info)
    res.payload.data = definition.response_data
    return res


class TestServiceSync(ConformanceServiceSync):
    def unary(self, request: UnaryRequest, ctx: RequestContext) -> UnaryResponse:
        return _handle_unary_response_sync(
            request.response_definition, [pack(request)], UnaryResponse(), ctx
        )

    def idempotent_unary(
        self, request: IdempotentUnaryRequest, ctx: RequestContext
    ) -> IdempotentUnaryResponse:
        return _handle_unary_response_sync(
            request.response_definition, [pack(request)], IdempotentUnaryResponse(), ctx
        )

    def client_stream(
        self, request: Iterator[ClientStreamRequest], ctx: RequestContext
    ) -> ClientStreamResponse:
        requests: list[Any] = []
        definition: UnaryResponseDefinition | None = None
        for message in request:
            requests.append(pack(message))
            if not definition:
                definition = message.response_definition

        if not definition:
            msg = "ClientStream must have a response definition"
            raise ValueError(msg)
        return _handle_unary_response_sync(
            definition, requests, ClientStreamResponse(), ctx
        )

    def server_stream(
        self, request: ServerStreamRequest, ctx: RequestContext
    ) -> Iterator[ServerStreamResponse]:
        definition = request.response_definition
        _send_headers(ctx, definition)
        request_info = _create_request_info(ctx, [pack(request)])
        sent_message = False
        for res_data in definition.response_data:
            res = ServerStreamResponse()
            if not sent_message:
                res.payload.request_info.CopyFrom(request_info)
            res.payload.data = res_data
            if definition.response_delay_ms:
                time.sleep(definition.response_delay_ms / 1000.0)
            sent_message = True
            yield res

        if definition.HasField("error"):
            details: list[Message] = [*definition.error.details]
            if not sent_message:
                details.append(request_info)
            raise ConnectError(
                code=_convert_code(definition.error.code),
                message=definition.error.message,
                details=details,
            )

    def bidi_stream(
        self, request: Iterator[BidiStreamRequest], ctx: RequestContext
    ) -> Iterator[BidiStreamResponse]:
        definition: StreamResponseDefinition | None = None
        full_duplex = False
        requests: list[Any] = []
        res_idx = 0
        for message in request:
            if not definition:
                definition = message.response_definition
                _send_headers(ctx, definition)
                full_duplex = message.full_duplex
            requests.append(pack(message))
            if not full_duplex:
                continue
            if not definition or res_idx >= len(definition.response_data):
                break
            if definition.response_delay_ms:
                time.sleep(definition.response_delay_ms / 1000.0)
            res = BidiStreamResponse()
            res.payload.data = definition.response_data[res_idx]
            res.payload.request_info.CopyFrom(
                _create_request_info(ctx, [pack(message)])
            )
            yield res
            res_idx += 1
            requests = []

        if not definition:
            return

        request_info = _create_request_info(ctx, requests)
        for i in range(res_idx, len(definition.response_data)):
            if definition.response_delay_ms:
                time.sleep(definition.response_delay_ms / 1000.0)
            res = BidiStreamResponse()
            res.payload.data = definition.response_data[i]
            if i == 0:
                res.payload.request_info.CopyFrom(request_info)
            yield res

        if definition.HasField("error"):
            details: list[Message] = [*definition.error.details]
            if len(definition.response_data) == 0:
                details.append(request_info)
            raise ConnectError(
                code=_convert_code(definition.error.code),
                message=definition.error.message,
                details=details,
            )


read_max_bytes = os.getenv("READ_MAX_BYTES")
if read_max_bytes is not None:
    read_max_bytes = int(read_max_bytes)

asgi_app = ConformanceServiceASGIApplication(
    TestService(), read_max_bytes=read_max_bytes
)
wsgi_app = ConformanceServiceWSGIApplication(
    TestServiceSync(), read_max_bytes=read_max_bytes
)


def _server_env(request: ServerCompatRequest) -> dict[str, str]:
    pythonpath = os.pathsep.join(sys.path)
    env = {
        **os.environ,
        "PYTHONPATH": pythonpath,
        "PYTHONHOME": f"{sys.prefix}:{sys.exec_prefix}",
    }
    if request.message_receive_limit:
        env["READ_MAX_BYTES"] = str(request.message_receive_limit)
    return env


_port_regex = re.compile(r".*://[^:]+:(\d+).*")


async def _tee_to_stderr(stream: asyncio.StreamReader) -> AsyncIterator[bytes]:
    while True:
        line = await stream.readline()
        if not line:
            break
        print(line.decode("utf-8"), end="", file=sys.stderr)  # noqa: T201
        yield line


async def _consume_log(stream: AsyncIterator[bytes]) -> None:
    async for _ in stream:
        pass


async def serve_daphne(
    request: ServerCompatRequest,
    certfile: str | None,
    keyfile: str | None,
    cafile: str | None,
    port_future: asyncio.Future[int],
):
    args = []
    ssl_endpoint_parts = []
    if certfile:
        ssl_endpoint_parts.append(f"certKey={certfile}")
    if keyfile:
        ssl_endpoint_parts.append(f"privateKey={keyfile}")
    if cafile:
        ssl_endpoint_parts.append(f"extraCertChain={cafile}")
    if ssl_endpoint_parts:
        args.append("-e")
        args.append(f"ssl:port=0:{':'.join(ssl_endpoint_parts)}")
    else:
        args.append("-p=0")

    args.append("server:asgi_app")

    proc = await asyncio.create_subprocess_exec(
        "daphne",
        *args,
        stderr=asyncio.subprocess.STDOUT,
        stdout=asyncio.subprocess.PIPE,
        env=_server_env(request),
    )
    stdout = proc.stdout
    assert stdout is not None
    stdout = _tee_to_stderr(stdout)
    try:
        async for line in stdout:
            if b"Listening on TCP address" in line:
                port = line.decode("utf-8").strip().rsplit(":", 1)[1]
                port_future.set_result(int(port))
                break
        await _consume_log(stdout)
    except asyncio.CancelledError:
        proc.terminate()
        await proc.wait()


async def serve_granian(
    request: ServerCompatRequest,
    mode: Literal["sync", "async"],
    certfile: str | None,
    keyfile: str | None,
    cafile: str | None,
    port_future: asyncio.Future[int],
):
    # Granian seems to have a bug that it prints out 0 rather than the resolved port,
    # so we need to determine it ourselves. If we see race conditions because of it,
    # we can set max-servers=1 in the runner.
    # ref: https://github.com/emmett-framework/granian/issues/711
    port = _find_free_port()
    args = [f"--port={port}", "--workers=8"]
    if certfile:
        args.append(f"--ssl-certificate={certfile}")
    if keyfile:
        args.append(f"--ssl-keyfile={keyfile}")
    if cafile:
        args.append(f"--ssl-ca={cafile}")
        args.append("--ssl-client-verify")

    if mode == "sync":
        args.append("--interface=wsgi")
        args.append("server:wsgi_app")
    else:
        args.append("--interface=asgi")
        args.append("server:asgi_app")

    proc = await asyncio.create_subprocess_exec(
        "granian",
        *args,
        stderr=asyncio.subprocess.STDOUT,
        stdout=asyncio.subprocess.PIPE,
        env=_server_env(request),
    )
    stdout = proc.stdout
    assert stdout is not None
    stdout = _tee_to_stderr(stdout)
    try:
        async for line in stdout:
            if b"Started worker-8 runtime-1" in line:
                break
        port_future.set_result(port)
        await _consume_log(stdout)
        await proc.wait()
    except asyncio.CancelledError:
        proc.terminate()
        await proc.wait()


async def serve_gunicorn(
    request: ServerCompatRequest,
    certfile: str | None,
    keyfile: str | None,
    cafile: str | None,
    port_future: asyncio.Future[int],
):
    args = [
        "--bind=127.0.0.1:0",
        "--workers=4",
        "--worker-class=gevent",
        "--reuse-port",
    ]
    if certfile:
        args.append(f"--certfile={certfile}")
    if keyfile:
        args.append(f"--keyfile={keyfile}")
    if cafile:
        args.append(f"--ca-certs={cafile}")
        args.append(f"--cert-reqs={ssl.CERT_REQUIRED}")

    args.append("server:wsgi_app")

    proc = await asyncio.create_subprocess_exec(
        "gunicorn",
        *args,
        stderr=asyncio.subprocess.STDOUT,
        stdout=asyncio.subprocess.PIPE,
        env=_server_env(request),
    )
    stdout = proc.stdout
    assert stdout is not None
    stdout = _tee_to_stderr(stdout)
    try:
        async for line in stdout:
            match = _port_regex.match(line.decode("utf-8"))
            if match:
                port_future.set_result(int(match.group(1)))
                break
        await _consume_log(stdout)
    except asyncio.CancelledError:
        proc.terminate()
        await proc.wait()


async def serve_hypercorn(
    request: ServerCompatRequest,
    mode: Literal["sync", "async"],
    certfile: str | None,
    keyfile: str | None,
    cafile: str | None,
    port_future: asyncio.Future[int],
):
    args = ["--bind=localhost:0"]
    if certfile:
        args.append(f"--certfile={certfile}")
    if keyfile:
        args.append(f"--keyfile={keyfile}")
    if cafile:
        args.append(f"--ca-certs={cafile}")
        args.append("--verify-mode=CERT_REQUIRED")

    if mode == "sync":
        args.append("server:wsgi_app")
    else:
        args.append("server:asgi_app")

    proc = await asyncio.create_subprocess_exec(
        "hypercorn",
        *args,
        stderr=asyncio.subprocess.STDOUT,
        stdout=asyncio.subprocess.PIPE,
        env=_server_env(request),
    )
    stdout = proc.stdout
    assert stdout is not None
    stdout = _tee_to_stderr(stdout)
    try:
        async for line in stdout:
            match = _port_regex.match(line.decode("utf-8"))
            if match:
                port_future.set_result(int(match.group(1)))
                break
        await _consume_log(stdout)
    except asyncio.CancelledError:
        proc.terminate()
        await proc.wait()


async def serve_pyvoy(
    request: ServerCompatRequest,
    mode: Literal["sync", "async"],
    certfile: str | None,
    keyfile: str | None,
    cafile: str | None,
    port_future: asyncio.Future[int],
):
    args = ["--port=0"]
    if certfile:
        args.append(f"--tls-cert={certfile}")
    if keyfile:
        args.append(f"--tls-key={keyfile}")
    if cafile:
        args.append(f"--tls-ca-cert={cafile}")

    if mode == "sync":
        args.append("--interface=wsgi")
        args.append("server:wsgi_app")
    else:
        args.append("server:asgi_app")

    proc = await asyncio.create_subprocess_exec(
        "pyvoy",
        *args,
        stderr=asyncio.subprocess.STDOUT,
        stdout=asyncio.subprocess.PIPE,
        env=_server_env(request),
    )
    stdout = proc.stdout
    assert stdout is not None
    stdout = _tee_to_stderr(stdout)
    try:
        async for line in stdout:
            if b"listening on" in line:
                port = int(line.strip().split(b"127.0.0.1:")[1])
                port_future.set_result(port)
                break
        await _consume_log(stdout)
    except asyncio.CancelledError:
        proc.terminate()
        await proc.wait()


async def serve_uvicorn(
    request: ServerCompatRequest,
    certfile: str | None,
    keyfile: str | None,
    cafile: str | None,
    port_future: asyncio.Future[int],
):
    args = ["--port=0", "--no-access-log"]
    if certfile:
        args.append(f"--ssl-certfile={certfile}")
    if keyfile:
        args.append(f"--ssl-keyfile={keyfile}")
    if cafile:
        args.append(f"--ssl-ca-certs={cafile}")
        args.append(f"--ssl-cert-reqs={ssl.CERT_REQUIRED}")

    args.append("server:asgi_app")

    proc = await asyncio.create_subprocess_exec(
        "uvicorn",
        *args,
        stderr=asyncio.subprocess.STDOUT,
        stdout=asyncio.subprocess.PIPE,
        env=_server_env(request),
    )
    stdout = proc.stdout
    assert stdout is not None
    stdout = _tee_to_stderr(stdout)
    try:
        async for line in stdout:
            match = _port_regex.match(line.decode("utf-8"))
            if match:
                port_future.set_result(int(match.group(1)))
                break
        await _consume_log(stdout)
    except asyncio.CancelledError:
        proc.terminate()
        await proc.wait()


def _find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


Mode = Literal["sync", "async"]
Server = Literal["daphne", "granian", "gunicorn", "hypercorn", "pyvoy", "uvicorn"]


class Args(argparse.Namespace):
    mode: Mode
    server: Server


async def main() -> None:
    parser = argparse.ArgumentParser(description="Conformance server")
    parser.add_argument("--mode", choices=get_args(Mode))
    parser.add_argument("--server", choices=get_args(Server))
    args = parser.parse_args(namespace=Args())

    stdin, stdout = await create_standard_streams()
    try:
        size_buf = await stdin.readexactly(4)
    except asyncio.IncompleteReadError:
        return
    size = int.from_bytes(size_buf, byteorder="big")
    # Allow to raise even on EOF since we always should have a message
    request_buf = await stdin.readexactly(size)
    request = ServerCompatRequest()
    request.ParseFromString(request_buf)

    cleanup = ExitStack()
    certfile = None
    keyfile = None
    cafile = None
    if request.use_tls:
        cert_file = cleanup.enter_context(NamedTemporaryFile())
        key_file = cleanup.enter_context(NamedTemporaryFile())
        cert_file.write(request.server_creds.cert)
        cert_file.flush()
        key_file.write(request.server_creds.key)
        key_file.flush()
        certfile = cert_file.name
        keyfile = key_file.name
        if request.client_tls_cert:
            ca_cert_file = cleanup.enter_context(NamedTemporaryFile())
            ca_cert_file.write(request.client_tls_cert)
            ca_cert_file.flush()
            cafile = ca_cert_file.name

    with cleanup:
        port_future: asyncio.Future[int] = asyncio.get_event_loop().create_future()
        match args.server:
            case "daphne":
                if args.mode == "sync":
                    msg = "daphne does not support sync mode"
                    raise ValueError(msg)
                serve_task = asyncio.create_task(
                    serve_daphne(request, certfile, keyfile, cafile, port_future)
                )
            case "granian":
                serve_task = asyncio.create_task(
                    serve_granian(
                        request, args.mode, certfile, keyfile, cafile, port_future
                    )
                )
            case "gunicorn":
                if args.mode == "async":
                    msg = "gunicorn does not support async mode"
                    raise ValueError(msg)
                serve_task = asyncio.create_task(
                    serve_gunicorn(request, certfile, keyfile, cafile, port_future)
                )
            case "hypercorn":
                serve_task = asyncio.create_task(
                    serve_hypercorn(
                        request, args.mode, certfile, keyfile, cafile, port_future
                    )
                )
            case "pyvoy":
                serve_task = asyncio.create_task(
                    serve_pyvoy(
                        request, args.mode, certfile, keyfile, cafile, port_future
                    )
                )
            case "uvicorn":
                if args.mode == "sync":
                    msg = "uvicorn does not support sync mode"
                    raise ValueError(msg)
                serve_task = asyncio.create_task(
                    serve_uvicorn(request, certfile, keyfile, cafile, port_future)
                )

        asyncio.get_event_loop().add_signal_handler(signal.SIGTERM, serve_task.cancel)

        port = await port_future
        response = ServerCompatResponse()
        response.host = "127.0.0.1"
        response.port = port
        if request.use_tls:
            response.pem_cert = request.server_creds.cert
        response_buf = response.SerializeToString()
        size_buf = len(response_buf).to_bytes(4, byteorder="big")
        stdout.write(size_buf)
        stdout.write(response_buf)
        await stdout.drain()
        await serve_task


if __name__ == "__main__":
    asyncio.run(main())
