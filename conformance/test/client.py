from __future__ import annotations

import argparse
import asyncio
import contextlib
import multiprocessing
import queue
import ssl
import sys
import time
import traceback
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Literal, TypeVar, get_args

import httpx
from _util import create_standard_streams
from gen.connectrpc.conformance.v1.client_compat_pb2 import (
    ClientCompatRequest,
    ClientCompatResponse,
)
from gen.connectrpc.conformance.v1.config_pb2 import Code as ConformanceCode
from gen.connectrpc.conformance.v1.config_pb2 import (
    Codec,
    Compression,
    HTTPVersion,
    Protocol,
    StreamType,
)
from gen.connectrpc.conformance.v1.service_connect import (
    ConformanceServiceClient,
    ConformanceServiceClientSync,
)
from gen.connectrpc.conformance.v1.service_pb2 import (
    BidiStreamRequest,
    ClientStreamRequest,
    ConformancePayload,
    IdempotentUnaryRequest,
    ServerStreamRequest,
    UnaryRequest,
    UnimplementedRequest,
)
from google.protobuf.message import Message
from pyqwest import HTTPTransport, SyncHTTPTransport
from pyqwest import HTTPVersion as PyQwestHTTPVersion
from pyqwest.httpx import AsyncPyqwestTransport, PyqwestTransport

from connectrpc.client import ResponseMetadata
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.request import Headers

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from google.protobuf.any_pb2 import Any


def _convert_code(error: Code) -> ConformanceCode:
    match error:
        case Code.CANCELED:
            return ConformanceCode.CODE_CANCELED
        case Code.UNKNOWN:
            return ConformanceCode.CODE_UNKNOWN
        case Code.INVALID_ARGUMENT:
            return ConformanceCode.CODE_INVALID_ARGUMENT
        case Code.DEADLINE_EXCEEDED:
            return ConformanceCode.CODE_DEADLINE_EXCEEDED
        case Code.NOT_FOUND:
            return ConformanceCode.CODE_NOT_FOUND
        case Code.ALREADY_EXISTS:
            return ConformanceCode.CODE_ALREADY_EXISTS
        case Code.PERMISSION_DENIED:
            return ConformanceCode.CODE_PERMISSION_DENIED
        case Code.RESOURCE_EXHAUSTED:
            return ConformanceCode.CODE_RESOURCE_EXHAUSTED
        case Code.FAILED_PRECONDITION:
            return ConformanceCode.CODE_FAILED_PRECONDITION
        case Code.ABORTED:
            return ConformanceCode.CODE_ABORTED
        case Code.OUT_OF_RANGE:
            return ConformanceCode.CODE_OUT_OF_RANGE
        case Code.UNIMPLEMENTED:
            return ConformanceCode.CODE_UNIMPLEMENTED
        case Code.INTERNAL:
            return ConformanceCode.CODE_INTERNAL
        case Code.UNAVAILABLE:
            return ConformanceCode.CODE_UNAVAILABLE
        case Code.DATA_LOSS:
            return ConformanceCode.CODE_DATA_LOSS
        case Code.UNAUTHENTICATED:
            return ConformanceCode.CODE_UNAUTHENTICATED


def _convert_compression(compression: Compression) -> str:
    match compression:
        case Compression.COMPRESSION_IDENTITY:
            return "identity"
        case Compression.COMPRESSION_GZIP:
            return "gzip"
        case Compression.COMPRESSION_BR:
            return "br"
        case Compression.COMPRESSION_ZSTD:
            return "zstd"
        case Compression.COMPRESSION_DEFLATE:
            return "deflate"
        case Compression.COMPRESSION_SNAPPY:
            return "snappy"
        case _:
            msg = f"Unsupported compression: {compression}"
            raise ValueError(msg)


T = TypeVar("T", bound=Message)


def _unpack_request(message: Any, request: T) -> T:
    message.Unpack(request)
    return request


async def httpx_client_kwargs(test_request: ClientCompatRequest) -> dict:
    kwargs = {}
    match test_request.http_version:
        case HTTPVersion.HTTP_VERSION_1:
            kwargs["http1"] = True
            kwargs["http2"] = False
        case HTTPVersion.HTTP_VERSION_2:
            kwargs["http1"] = False
            kwargs["http2"] = True
    if test_request.server_tls_cert:
        ctx = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH,
            cadata=test_request.server_tls_cert.decode(),
        )
        if test_request.HasField("client_tls_creds"):

            def load_certs() -> None:
                with (
                    NamedTemporaryFile() as cert_file,
                    NamedTemporaryFile() as key_file,
                ):
                    cert_file.write(test_request.client_tls_creds.cert)
                    cert_file.flush()
                    key_file.write(test_request.client_tls_creds.key)
                    key_file.flush()
                    ctx.load_cert_chain(certfile=cert_file.name, keyfile=key_file.name)

            await asyncio.to_thread(load_certs)
        kwargs["verify"] = ctx

    return kwargs


def pyqwest_client_kwargs(test_request: ClientCompatRequest) -> dict:
    kwargs: dict = {"enable_gzip": True, "enable_brotli": True, "enable_zstd": True}
    match test_request.http_version:
        case HTTPVersion.HTTP_VERSION_1:
            kwargs["http_version"] = PyQwestHTTPVersion.HTTP1
        case HTTPVersion.HTTP_VERSION_2:
            kwargs["http_version"] = PyQwestHTTPVersion.HTTP2
    if test_request.server_tls_cert:
        kwargs["tls_ca_cert"] = test_request.server_tls_cert
        if test_request.HasField("client_tls_creds"):
            kwargs["tls_key"] = test_request.client_tls_creds.key
            kwargs["tls_cert"] = test_request.client_tls_creds.cert

    return kwargs


@contextlib.asynccontextmanager
async def client_sync(
    test_request: ClientCompatRequest, client_type: Client
) -> AsyncIterator[ConformanceServiceClientSync]:
    read_max_bytes = None
    if test_request.message_receive_limit:
        read_max_bytes = test_request.message_receive_limit
    scheme = "https" if test_request.server_tls_cert else "http"
    cleanup = contextlib.ExitStack()
    match client_type:
        case "httpx":
            args = await httpx_client_kwargs(test_request)
            session = cleanup.enter_context(httpx.Client(**args))
        case "pyqwest":
            args = pyqwest_client_kwargs(test_request)
            http_transport = cleanup.enter_context(SyncHTTPTransport(**args))
            transport = cleanup.enter_context(PyqwestTransport(http_transport))
            session = cleanup.enter_context(httpx.Client(transport=transport))

    with (
        cleanup,
        ConformanceServiceClientSync(
            f"{scheme}://{test_request.host}:{test_request.port}",
            session=session,
            send_compression=_convert_compression(test_request.compression),
            proto_json=test_request.codec == Codec.CODEC_JSON,
            grpc=test_request.protocol == Protocol.PROTOCOL_GRPC,
            read_max_bytes=read_max_bytes,
        ) as client,
    ):
        yield client


@contextlib.asynccontextmanager
async def client_async(
    test_request: ClientCompatRequest, client_type: Client
) -> AsyncIterator[ConformanceServiceClient]:
    read_max_bytes = None
    if test_request.message_receive_limit:
        read_max_bytes = test_request.message_receive_limit
    scheme = "https" if test_request.server_tls_cert else "http"
    cleanup = contextlib.AsyncExitStack()
    match client_type:
        case "httpx":
            args = await httpx_client_kwargs(test_request)
            session = await cleanup.enter_async_context(httpx.AsyncClient(**args))
        case "pyqwest":
            args = pyqwest_client_kwargs(test_request)
            http_transport = await cleanup.enter_async_context(HTTPTransport(**args))
            transport = await cleanup.enter_async_context(
                AsyncPyqwestTransport(http_transport)
            )
            session = await cleanup.enter_async_context(
                httpx.AsyncClient(transport=transport)
            )

    async with (
        cleanup,
        ConformanceServiceClient(
            f"{scheme}://{test_request.host}:{test_request.port}",
            session=session,
            send_compression=_convert_compression(test_request.compression),
            proto_json=test_request.codec == Codec.CODEC_JSON,
            grpc=test_request.protocol == Protocol.PROTOCOL_GRPC,
            read_max_bytes=read_max_bytes,
        ) as client,
    ):
        yield client


async def _run_test(
    mode: Mode, test_request: ClientCompatRequest, client_type: Client
) -> ClientCompatResponse:
    test_response = ClientCompatResponse()
    test_response.test_name = test_request.test_name

    timeout_ms = None
    if test_request.timeout_ms:
        timeout_ms = test_request.timeout_ms

    request_headers = Headers()
    for header in test_request.request_headers:
        for value in header.value:
            request_headers.add(header.name, value)

    payloads: list[ConformancePayload] = []

    with ResponseMetadata() as meta:
        try:
            task: asyncio.Task
            request_closed = asyncio.Event()
            match mode:
                case "sync":
                    async with client_sync(test_request, client_type) as client:
                        match test_request.method:
                            case "BidiStream":
                                request_queue = queue.Queue()

                                def send_bidi_stream_request_sync(
                                    client: ConformanceServiceClientSync,
                                    request: Iterator[BidiStreamRequest],
                                ) -> None:
                                    responses = client.bidi_stream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    for message in test_request.request_messages:
                                        if test_request.request_delay_ms:
                                            time.sleep(
                                                test_request.request_delay_ms / 1000.0
                                            )
                                        request_queue.put(
                                            _unpack_request(
                                                message, BidiStreamRequest()
                                            )
                                        )

                                        if (
                                            test_request.stream_type
                                            != StreamType.STREAM_TYPE_FULL_DUPLEX_BIDI_STREAM
                                        ):
                                            continue

                                        response = next(responses, None)
                                        if response is not None:
                                            payloads.append(response.payload)
                                            if (
                                                num
                                                := test_request.cancel.after_num_responses
                                            ) and len(payloads) >= num:
                                                task.cancel()

                                    if test_request.cancel.HasField(
                                        "before_close_send"
                                    ):
                                        task.cancel()

                                    request_queue.put(None)

                                    request_closed.set()

                                    for response in responses:
                                        payloads.append(response.payload)
                                        if (
                                            num
                                            := test_request.cancel.after_num_responses
                                        ) and len(payloads) >= num:
                                            task.cancel()

                                def bidi_stream_request_sync():
                                    while True:
                                        request = request_queue.get()
                                        if request is None:
                                            return
                                        yield request

                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        send_bidi_stream_request_sync,
                                        client,
                                        bidi_stream_request_sync(),
                                    )
                                )

                            case "ClientStream":

                                def send_client_stream_request_sync(
                                    client: ConformanceServiceClientSync,
                                    request: Iterator[ClientStreamRequest],
                                ) -> None:
                                    res = client.client_stream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                def request_stream_sync():
                                    for message in test_request.request_messages:
                                        if test_request.request_delay_ms:
                                            time.sleep(
                                                test_request.request_delay_ms / 1000.0
                                            )
                                        yield _unpack_request(
                                            message, ClientStreamRequest()
                                        )
                                    if test_request.cancel.HasField(
                                        "before_close_send"
                                    ):
                                        task.cancel()
                                    request_closed.set()

                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        send_client_stream_request_sync,
                                        client,
                                        request_stream_sync(),
                                    )
                                )
                            case "IdempotentUnary":

                                def send_idempotent_unary_request_sync(
                                    client: ConformanceServiceClientSync,
                                    request: IdempotentUnaryRequest,
                                ) -> None:
                                    res = client.idempotent_unary(
                                        request,
                                        headers=request_headers,
                                        use_get=test_request.use_get_http_method,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        send_idempotent_unary_request_sync,
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            IdempotentUnaryRequest(),
                                        ),
                                    )
                                )
                                request_closed.set()
                            case "ServerStream":

                                def send_server_stream_request_sync(
                                    client: ConformanceServiceClientSync,
                                    request: ServerStreamRequest,
                                ) -> None:
                                    for message in client.server_stream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    ):
                                        payloads.append(message.payload)
                                        if (
                                            num
                                            := test_request.cancel.after_num_responses
                                        ) and len(payloads) >= num:
                                            task.cancel()

                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        send_server_stream_request_sync,
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            ServerStreamRequest(),
                                        ),
                                    )
                                )
                                request_closed.set()
                            case "Unary":

                                def send_unary_request_sync(
                                    client: ConformanceServiceClientSync,
                                    request: UnaryRequest,
                                ) -> None:
                                    res = client.unary(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        send_unary_request_sync,
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            UnaryRequest(),
                                        ),
                                    )
                                )
                                request_closed.set()
                            case "Unimplemented":
                                task = asyncio.create_task(
                                    asyncio.to_thread(
                                        client.unimplemented,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            UnimplementedRequest(),
                                        ),
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                )
                                request_closed.set()
                            case _:
                                msg = f"Unrecognized method: {test_request.method}"
                                raise ValueError(msg)
                        if test_request.cancel.after_close_send_ms:
                            await asyncio.sleep(
                                test_request.cancel.after_close_send_ms / 1000.0
                            )
                            task.cancel()
                        await task
                case "async":
                    async with client_async(test_request, client_type) as client:
                        match test_request.method:
                            case "BidiStream":
                                request_queue = asyncio.Queue()

                                async def send_bidi_stream_request(
                                    client: ConformanceServiceClient,
                                    request: AsyncIterator[BidiStreamRequest],
                                ) -> None:
                                    responses = client.bidi_stream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    for message in test_request.request_messages:
                                        if test_request.request_delay_ms:
                                            await asyncio.sleep(
                                                test_request.request_delay_ms / 1000.0
                                            )
                                        await request_queue.put(
                                            _unpack_request(
                                                message, BidiStreamRequest()
                                            )
                                        )

                                        if (
                                            test_request.stream_type
                                            != StreamType.STREAM_TYPE_FULL_DUPLEX_BIDI_STREAM
                                        ):
                                            continue

                                        response = await anext(responses, None)
                                        if response is not None:
                                            payloads.append(response.payload)
                                            if (
                                                num
                                                := test_request.cancel.after_num_responses
                                            ) and len(payloads) >= num:
                                                task.cancel()

                                    if test_request.cancel.HasField(
                                        "before_close_send"
                                    ):
                                        task.cancel()

                                    await request_queue.put(None)

                                    request_closed.set()

                                    async for response in responses:
                                        payloads.append(response.payload)
                                        if (
                                            num
                                            := test_request.cancel.after_num_responses
                                        ) and len(payloads) >= num:
                                            task.cancel()

                                async def bidi_stream_request():
                                    while True:
                                        request = await request_queue.get()
                                        if request is None:
                                            return
                                        yield request

                                task = asyncio.create_task(
                                    send_bidi_stream_request(
                                        client, bidi_stream_request()
                                    )
                                )

                            case "ClientStream":

                                async def send_client_stream_request(
                                    client: ConformanceServiceClient,
                                    request: AsyncIterator[ClientStreamRequest],
                                ) -> None:
                                    res = await client.client_stream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                async def client_stream_request():
                                    for message in test_request.request_messages:
                                        if test_request.request_delay_ms:
                                            await asyncio.sleep(
                                                test_request.request_delay_ms / 1000.0
                                            )
                                        yield _unpack_request(
                                            message, ClientStreamRequest()
                                        )
                                    if test_request.cancel.HasField(
                                        "before_close_send"
                                    ):
                                        task.cancel()
                                    request_closed.set()

                                task = asyncio.create_task(
                                    send_client_stream_request(
                                        client, client_stream_request()
                                    )
                                )
                            case "IdempotentUnary":

                                async def send_idempotent_unary_request(
                                    client: ConformanceServiceClient,
                                    request: IdempotentUnaryRequest,
                                ) -> None:
                                    res = await client.idempotent_unary(
                                        request,
                                        headers=request_headers,
                                        use_get=test_request.use_get_http_method,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                task = asyncio.create_task(
                                    send_idempotent_unary_request(
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            IdempotentUnaryRequest(),
                                        ),
                                    )
                                )
                                request_closed.set()
                            case "ServerStream":

                                async def send_server_stream_request(
                                    client: ConformanceServiceClient,
                                    request: ServerStreamRequest,
                                ) -> None:
                                    async for message in client.server_stream(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    ):
                                        payloads.append(message.payload)
                                        if (
                                            num
                                            := test_request.cancel.after_num_responses
                                        ) and len(payloads) >= num:
                                            task.cancel()

                                task = asyncio.create_task(
                                    send_server_stream_request(
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            ServerStreamRequest(),
                                        ),
                                    )
                                )
                                request_closed.set()
                            case "Unary":

                                async def send_unary_request(
                                    client: ConformanceServiceClient,
                                    request: UnaryRequest,
                                ) -> None:
                                    res = await client.unary(
                                        request,
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                    payloads.append(res.payload)

                                task = asyncio.create_task(
                                    send_unary_request(
                                        client,
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            UnaryRequest(),
                                        ),
                                    )
                                )
                                request_closed.set()
                            case "Unimplemented":
                                task = asyncio.create_task(
                                    client.unimplemented(
                                        _unpack_request(
                                            test_request.request_messages[0],
                                            UnimplementedRequest(),
                                        ),
                                        headers=request_headers,
                                        timeout_ms=timeout_ms,
                                    )
                                )
                                request_closed.set()
                            case _:
                                msg = f"Unrecognized method: {test_request.method}"
                                raise ValueError(msg)
                        if test_request.cancel.after_close_send_ms:
                            await request_closed.wait()
                            await asyncio.sleep(
                                test_request.cancel.after_close_send_ms / 1000.0
                            )
                            task.cancel()
                        await task
        except ConnectError as e:
            test_response.response.error.code = _convert_code(e.code)
            test_response.response.error.message = e.message
            test_response.response.error.details.extend(e.details)
        except (asyncio.CancelledError, Exception) as e:
            traceback.print_tb(e.__traceback__, file=sys.stderr)
            test_response.error.message = str(e)

        test_response.response.payloads.extend(payloads)

        for name in meta.headers():
            test_response.response.response_headers.add(
                name=name, value=meta.headers().getall(name)
            )
        for name in meta.trailers():
            test_response.response.response_trailers.add(
                name=name, value=meta.trailers().getall(name)
            )

    return test_response


Mode = Literal["sync", "async"]
Client = Literal["httpx", "pyqwest"]


class Args(argparse.Namespace):
    mode: Mode
    client: Client
    parallel: int


async def main() -> None:
    parser = argparse.ArgumentParser(description="Conformance client")
    parser.add_argument("--mode", choices=get_args(Mode))
    parser.add_argument("--parallel", type=int, default=multiprocessing.cpu_count() * 4)
    parser.add_argument("--client", choices=get_args(Client))
    args = parser.parse_args(namespace=Args())

    stdin, stdout = await create_standard_streams()
    sema = asyncio.Semaphore(args.parallel)
    tasks: list[asyncio.Task] = []
    try:
        while True:
            try:
                size_buf = await stdin.readexactly(4)
            except asyncio.IncompleteReadError:
                return
            size = int.from_bytes(size_buf, byteorder="big")
            # Allow to raise even on EOF since we always should have a message
            request_buf = await stdin.readexactly(size)
            request = ClientCompatRequest()
            request.ParseFromString(request_buf)

            async def task(request: ClientCompatRequest) -> None:
                async with sema:
                    response = await _run_test(args.mode, request, args.client)

                    response_buf = response.SerializeToString()
                    size_buf = len(response_buf).to_bytes(4, byteorder="big")
                    stdout.write(size_buf + response_buf)
                    await stdout.drain()

            tasks.append(asyncio.create_task(task(request)))
    finally:
        asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
