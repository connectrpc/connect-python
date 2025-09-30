import argparse
import asyncio
import signal
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import ExitStack
from ssl import VerifyMode
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Literal, TypeVar

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
from hypercorn.asyncio import serve as hypercorn_serve
from hypercorn.config import Config as HypercornConfig
from hypercorn.logging import Logger

from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.request import RequestContext

if TYPE_CHECKING:
    from google.protobuf.message import Message


# TODO: Use google.protobuf.any.pack on upgrade to protobuf==6.
def pack(msg: "Message") -> Any:
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


class PortCapturingLogger(Logger):
    """In-memory logger for Hypercorn, useful for testing."""

    port = -1

    def __init__(self, conf: HypercornConfig) -> None:
        super().__init__(conf)

    async def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        if "Running on" in message:
            _, _, rest = message.partition("//127.0.0.1:")
            port, _, _ = rest.partition(" ")
            self.port = int(port)
        await super().info(message, *args, **kwargs)


async def serve(
    request: ServerCompatRequest, mode: Literal["sync", "async"]
) -> tuple[asyncio.Task, int]:
    read_max_bytes = request.message_receive_limit or None
    match mode:
        case "async":
            app = ConformanceServiceASGIApplication(
                TestService(), read_max_bytes=read_max_bytes
            )
        case "sync":
            app = ConformanceServiceWSGIApplication(
                TestServiceSync(), read_max_bytes=read_max_bytes
            )

    conf = HypercornConfig()
    conf.bind = ["127.0.0.1:0"]

    cleanup = ExitStack()
    if request.use_tls:
        cert_file = cleanup.enter_context(NamedTemporaryFile())
        key_file = cleanup.enter_context(NamedTemporaryFile())
        cert_file.write(request.server_creds.cert)
        cert_file.flush()
        key_file.write(request.server_creds.key)
        key_file.flush()
        conf.certfile = cert_file.name
        conf.keyfile = key_file.name
        if request.client_tls_cert:
            ca_cert_file = cleanup.enter_context(NamedTemporaryFile())
            ca_cert_file.write(request.client_tls_cert)
            ca_cert_file.flush()
            conf.ca_certs = ca_cert_file.name
            conf.verify_mode = VerifyMode.CERT_REQUIRED

    conf._log = PortCapturingLogger(conf)

    shutdown_event = asyncio.Event()

    def _signal_handler(*_) -> None:
        cleanup.close()
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGTERM, _signal_handler)
    loop.add_signal_handler(signal.SIGINT, _signal_handler)

    serve_task = loop.create_task(
        hypercorn_serve(
            app,  # pyright:ignore[reportArgumentType] - some incompatibility in type
            conf,
            shutdown_trigger=shutdown_event.wait,
            mode="asgi" if mode == "async" else "wsgi",
        )
    )
    port = -1
    for _ in range(100):
        port = conf._log.port
        if port != -1:
            break
        await asyncio.sleep(0.01)
    return serve_task, port


class Args(argparse.Namespace):
    mode: Literal["sync", "async"]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Conformance client")
    parser.add_argument("--mode", choices=["sync", "async"])
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

    serve_task, port = await serve(request, args.mode)
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
    # Runner will send sigterm which is handled by serve
    await serve_task


if __name__ == "__main__":
    asyncio.run(main())
