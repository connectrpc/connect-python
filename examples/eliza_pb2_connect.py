# Generated Connect client code

from __future__ import annotations
from collections.abc import AsyncIterator
from collections.abc import Iterator
from collections.abc import Iterable
import aiohttp
import urllib3
import typing
import sys

from connectrpc.client_async import AsyncConnectClient
from connectrpc.client_sync import ConnectClient
from connectrpc.client_protocol import ConnectProtocol
from connectrpc.client_connect import ConnectProtocolError
from connectrpc.headers import HeaderInput
from connectrpc.server import ClientRequest
from connectrpc.server import ClientStream
from connectrpc.server import ServerResponse
from connectrpc.server import ServerStream
from connectrpc.server_sync import ConnectWSGI
from connectrpc.streams import StreamInput
from connectrpc.streams import AsyncStreamOutput
from connectrpc.streams import StreamOutput
from connectrpc.unary import UnaryOutput
from connectrpc.unary import ClientStreamingOutput

if typing.TYPE_CHECKING:
    # wsgiref.types was added in Python 3.11.
    if sys.version_info >= (3, 11):
        from wsgiref.types import WSGIApplication
    else:
        from _typeshed.wsgi import WSGIApplication

import eliza_pb2

class ElizaServiceClient:
    def __init__(
        self,
        base_url: str,
        http_client: urllib3.PoolManager | None = None,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = ConnectClient(http_client, protocol)
    def call_say(
        self, req: eliza_pb2.SayRequest, extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> UnaryOutput[eliza_pb2.SayResponse]:
        """Low-level method to call Say, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Say"
        return self._connect_client.call_unary(url, req, eliza_pb2.SayResponse,extra_headers, timeout_seconds)


    def say(
        self, req: eliza_pb2.SayRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> eliza_pb2.SayResponse:
        response = self.call_say(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError('missing response message')
        return msg

    def converse(
        self, reqs: Iterable[eliza_pb2.ConverseRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> Iterator[eliza_pb2.ConverseResponse]:
        return self._converse_iterator(reqs, extra_headers, timeout_seconds)

    def _converse_iterator(
        self, reqs: Iterable[eliza_pb2.ConverseRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> Iterator[eliza_pb2.ConverseResponse]:
        stream_output = self.call_converse(reqs, extra_headers, timeout_seconds)
        err = stream_output.error()
        if err is not None:
            raise err
        yield from stream_output
        err = stream_output.error()
        if err is not None:
            raise err

    def call_converse(
        self, reqs: Iterable[eliza_pb2.ConverseRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> StreamOutput[eliza_pb2.ConverseResponse]:
        """Low-level method to call Converse, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Converse"
        return self._connect_client.call_bidirectional_streaming(
            url, reqs, eliza_pb2.ConverseResponse, extra_headers, timeout_seconds
        )

    def introduce(
        self, req: eliza_pb2.IntroduceRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> Iterator[eliza_pb2.IntroduceResponse]:
        return self._introduce_iterator(req, extra_headers, timeout_seconds)

    def _introduce_iterator(
        self, req: eliza_pb2.IntroduceRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> Iterator[eliza_pb2.IntroduceResponse]:
        stream_output = self.call_introduce(req, extra_headers)
        err = stream_output.error()
        if err is not None:
            raise err
        yield from stream_output
        err = stream_output.error()
        if err is not None:
            raise err

    def call_introduce(
        self, req: eliza_pb2.IntroduceRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> StreamOutput[eliza_pb2.IntroduceResponse]:
        """Low-level method to call Introduce, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Introduce"
        return self._connect_client.call_server_streaming(
            url, req, eliza_pb2.IntroduceResponse, extra_headers, timeout_seconds
        )


class AsyncElizaServiceClient:
    def __init__(
        self,
        base_url: str,
        http_client: aiohttp.ClientSession,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = AsyncConnectClient(http_client, protocol)

    async def call_say(
        self, req: eliza_pb2.SayRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> UnaryOutput[eliza_pb2.SayResponse]:
        """Low-level method to call Say, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Say"
        return await self._connect_client.call_unary(url, req, eliza_pb2.SayResponse,extra_headers, timeout_seconds)

    async def say(
        self, req: eliza_pb2.SayRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> eliza_pb2.SayResponse:
        response = await self.call_say(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError('missing response message')
        return msg

    def converse(
        self, reqs: StreamInput[eliza_pb2.ConverseRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[eliza_pb2.ConverseResponse]:
        return self._converse_iterator(reqs, extra_headers, timeout_seconds)

    async def _converse_iterator(
        self, reqs: StreamInput[eliza_pb2.ConverseRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[eliza_pb2.ConverseResponse]:
        stream_output = await self.call_converse(reqs, extra_headers, timeout_seconds)
        err = stream_output.error()
        if err is not None:
            raise err
        async with stream_output as stream:
            async for response in stream:
                yield response
            err = stream.error()
            if err is not None:
                raise err

    async def call_converse(
        self, reqs: StreamInput[eliza_pb2.ConverseRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncStreamOutput[eliza_pb2.ConverseResponse]:
        """Low-level method to call Converse, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Converse"
        return await self._connect_client.call_bidirectional_streaming(
            url, reqs, eliza_pb2.ConverseResponse, extra_headers, timeout_seconds
        )

    def introduce(
        self, req: eliza_pb2.IntroduceRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[eliza_pb2.IntroduceResponse]:
        return self._introduce_iterator(req, extra_headers, timeout_seconds)

    async def _introduce_iterator(
        self, req: eliza_pb2.IntroduceRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[eliza_pb2.IntroduceResponse]:
        stream_output = await self.call_introduce(req, extra_headers)
        err = stream_output.error()
        if err is not None:
            raise err
        async with stream_output as stream:
            async for response in stream:
                yield response
            err = stream.error()
            if err is not None:
                raise err

    async def call_introduce(
        self, req: eliza_pb2.IntroduceRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncStreamOutput[eliza_pb2.IntroduceResponse]:
        """Low-level method to call Introduce, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Introduce"
        return await self._connect_client.call_server_streaming(
            url, req, eliza_pb2.IntroduceResponse, extra_headers, timeout_seconds
        )


@typing.runtime_checkable
class ElizaServiceProtocol(typing.Protocol):
    def say(self, req: ClientRequest[eliza_pb2.SayRequest]) -> ServerResponse[eliza_pb2.SayResponse]:
        ...
    def converse(self, req: ClientStream[eliza_pb2.ConverseRequest]) -> ServerStream[eliza_pb2.ConverseResponse]:
        ...
    def introduce(self, req: ClientRequest[eliza_pb2.IntroduceRequest]) -> ServerStream[eliza_pb2.IntroduceResponse]:
        ...

ELIZA_SERVICE_PATH_PREFIX = "/connectrpc.eliza.v1.ElizaService"

def wsgi_eliza_service(implementation: ElizaServiceProtocol) -> WSGIApplication:
    app = ConnectWSGI()
    app.register_unary_rpc("/connectrpc.eliza.v1.ElizaService/Say", implementation.say, eliza_pb2.SayRequest)
    app.register_bidi_streaming_rpc("/connectrpc.eliza.v1.ElizaService/Converse", implementation.converse, eliza_pb2.ConverseRequest)
    app.register_server_streaming_rpc("/connectrpc.eliza.v1.ElizaService/Introduce", implementation.introduce, eliza_pb2.IntroduceRequest)
    return app
