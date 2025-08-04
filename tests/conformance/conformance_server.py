from __future__ import annotations

import socket
import sys
import time
from collections.abc import Iterable
from typing import TYPE_CHECKING
from typing import Any

from google.protobuf.any_pb2 import Any as ProtoAny
from gunicorn.app.base import BaseApplication  # type:ignore[ import-untyped]
from multidict import CIMultiDict

from conformance import multidict_to_proto
from conformance import proto_to_exception
from conformance import read_size_delimited_message
from conformance import write_size_delimited_message
from connectrpc.conformance.v1.server_compat_pb2 import ServerCompatRequest
from connectrpc.conformance.v1.server_compat_pb2 import ServerCompatResponse
from connectrpc.conformance.v1.service_pb2 import BidiStreamRequest
from connectrpc.conformance.v1.service_pb2 import BidiStreamResponse
from connectrpc.conformance.v1.service_pb2 import ClientStreamRequest
from connectrpc.conformance.v1.service_pb2 import ClientStreamResponse
from connectrpc.conformance.v1.service_pb2 import ConformancePayload
from connectrpc.conformance.v1.service_pb2 import IdempotentUnaryRequest
from connectrpc.conformance.v1.service_pb2 import IdempotentUnaryResponse
from connectrpc.conformance.v1.service_pb2 import ServerStreamRequest
from connectrpc.conformance.v1.service_pb2 import ServerStreamResponse
from connectrpc.conformance.v1.service_pb2 import StreamResponseDefinition
from connectrpc.conformance.v1.service_pb2 import UnaryRequest
from connectrpc.conformance.v1.service_pb2 import UnaryResponse
from connectrpc.conformance.v1.service_pb2 import UnaryResponseDefinition
from connectrpc.conformance.v1.service_pb2 import UnimplementedRequest
from connectrpc.conformance.v1.service_pb2 import UnimplementedResponse
from connectrpc.conformance.v1.service_pb2_connect import wsgi_conformance_service
from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode
from connectrpc.server import ClientRequest
from connectrpc.server import ClientStream
from connectrpc.server import ServerResponse
from connectrpc.server import ServerStream

if TYPE_CHECKING:
    # wsgiref.types was added in Python 3.11.
    if sys.version_info >= (3, 11):
        from wsgiref.types import WSGIApplication
    else:
        from _typeshed.wsgi import WSGIApplication


class Conformance:
    def unary(self, req: ClientRequest[UnaryRequest]) -> ServerResponse[UnaryResponse]:
        req_msg_any = ProtoAny()
        req_msg_any.Pack(req.msg)

        req_info = ConformancePayload.RequestInfo(
            request_headers=multidict_to_proto(req.headers),
            timeout_ms=req.timeout.timeout_ms,
            requests=[req_msg_any],
        )

        headers: CIMultiDict[str] = CIMultiDict()
        for h in req.msg.response_definition.response_headers:
            for value in h.value:
                headers.add(h.name, value)

        trailers: CIMultiDict[str] = CIMultiDict()
        for t in req.msg.response_definition.response_trailers:
            for value in t.value:
                trailers.add(t.name, value)

        delay = req.msg.response_definition.response_delay_ms
        if delay > 0:
            time.sleep(delay / 1000.0)
        if req.msg.response_definition.HasField("error"):
            err = proto_to_exception(req.msg.response_definition.error)
            err.add_detail(req_info, include_debug=True)
            return ServerResponse(err, headers, trailers)

        else:
            msg = UnaryResponse(
                payload=ConformancePayload(
                    request_info=req_info,
                    data=req.msg.response_definition.response_data,
                ),
            )
            return ServerResponse(msg, headers, trailers)

    def server_stream(
        self, req: ClientRequest[ServerStreamRequest]
    ) -> ServerStream[ServerStreamResponse]:
        # Capture the request
        req_msg_any = ProtoAny()
        req_msg_any.Pack(req.msg)
        req_info = ConformancePayload.RequestInfo(
            request_headers=multidict_to_proto(req.headers),
            timeout_ms=req.timeout.timeout_ms,
            requests=[req_msg_any],
        )

        response: ServerStream[ServerStreamResponse] = ServerStream(msgs=[])

        response_defn = req.msg.response_definition
        for h in response_defn.response_headers:
            for value in h.value:
                response.headers.add(h.name, value)
        for t in response_defn.response_trailers:
            for value in t.value:
                response.trailers.add(t.name, value)

        def message_iterator() -> Iterable[ServerStreamResponse | ConnectError]:
            n_sent = 0
            for resp_data in response_defn.response_data:
                output_msg = ServerStreamResponse(payload=ConformancePayload(data=resp_data))
                if n_sent == 0:
                    output_msg.payload.request_info.CopyFrom(req_info)

                time.sleep(response_defn.response_delay_ms / 1000.0)

                yield output_msg
                n_sent += 1

            if response_defn.HasField("error"):
                err_proto = response_defn.error
                err = proto_to_exception(err_proto)
                if n_sent == 0:
                    # If we sent no responses, but are supposed to
                    # send an error, then we need to stuff req_info
                    # into the error details of the error.
                    err.add_detail(req_info)
                yield err

        response.msgs = message_iterator()
        return response

    def client_stream(
        self, req: ClientStream[ClientStreamRequest]
    ) -> ServerResponse[ClientStreamResponse]:
        received: list[ProtoAny] = []

        response: ServerResponse[ClientStreamResponse] = ServerResponse.empty()

        response_defn: UnaryResponseDefinition | None = None
        first_msg = True
        for msg in req:
            msg_as_any = ProtoAny()
            msg_as_any.Pack(msg)
            received.append(msg_as_any)

            if first_msg:
                first_msg = False
                if msg.response_definition is not None:
                    response_defn = msg.response_definition
                    for h in response_defn.response_headers:
                        for value in h.value:
                            response.headers.add(h.name, value)
                    for t in response_defn.response_trailers:
                        for value in t.value:
                            response.trailers.add(t.name, value)

        req_info = ConformancePayload.RequestInfo(
            request_headers=multidict_to_proto(req.headers),
            timeout_ms=req.timeout.timeout_ms,
            requests=received,
        )
        assert response_defn is not None

        if response_defn.response_delay_ms > 0:
            time.sleep(response_defn.response_delay_ms / 1000.0)
        if response_defn.HasField("error"):
            assert response_defn.error is not None
            err_proto = response_defn.error
            err = proto_to_exception(err_proto)
            err.add_detail(req_info)
            response.error = err
            return response

        response.msg = ClientStreamResponse(
            payload=ConformancePayload(
                request_info=req_info,
                data=response_defn.response_data,
            ),
        )
        return response

    def bidi_stream(self, req: ClientStream[BidiStreamRequest]) -> ServerStream[BidiStreamResponse]:
        received: list[ProtoAny] = []

        response: ServerStream[BidiStreamResponse] = ServerStream(msgs=[])

        response_defn: StreamResponseDefinition | None = None
        first_msg = True
        for msg in req:
            msg_as_any = ProtoAny()
            msg_as_any.Pack(msg)
            received.append(msg_as_any)

            if first_msg:
                first_msg = False
                if msg.full_duplex:
                    raise ConnectError(
                        ConnectErrorCode.UNIMPLEMENTED, "this server is half duplex only"
                    )
                if msg.HasField("response_definition"):
                    response_defn = msg.response_definition
                    for h in response_defn.response_headers:
                        for value in h.value:
                            response.headers.add(h.name, value)
                    for t in response_defn.response_trailers:
                        for value in t.value:
                            response.trailers.add(t.name, value)

        req_info = ConformancePayload.RequestInfo(
            request_headers=multidict_to_proto(req.headers),
            timeout_ms=req.timeout.timeout_ms,
            requests=received,
        )

        def message_iterator() -> Iterable[BidiStreamResponse | ConnectError]:
            if response_defn is None:
                return

            n_sent = 0
            for resp_data in response_defn.response_data:
                output_msg = BidiStreamResponse(payload=ConformancePayload(data=resp_data))
                if n_sent == 0:
                    output_msg.payload.request_info.CopyFrom(req_info)
                time.sleep(response_defn.response_delay_ms / 1000.0)
                yield output_msg
                n_sent += 1

            if response_defn.HasField("error"):
                err_proto = response_defn.error
                err = proto_to_exception(err_proto)
                if n_sent == 0:
                    # If we sent no responses, but are supposed to
                    # send an error, then we need to stuff req_info
                    # into the error details of the error.
                    err.add_detail(req_info)
                yield err

        response.msgs = message_iterator()
        return response

    def unimplemented(
        self, req: ClientRequest[UnimplementedRequest]
    ) -> ServerResponse[UnimplementedResponse]:
        raise ConnectError(ConnectErrorCode.UNIMPLEMENTED, "not implemented")

    def idempotent_unary(
        self, req: ClientRequest[IdempotentUnaryRequest]
    ) -> ServerResponse[IdempotentUnaryResponse]:
        raise NotImplementedError


class SocketGunicornApp(BaseApplication):  # type:ignore[misc]
    """A barebones gunicorn WSGI server which runs a configured WSGI
    application on a pre-established socket.

    Using a pre-established socket lets us know the port that will be
    used *before* we call server.run().

    """

    def __init__(self, app: WSGIApplication, sock: socket.socket, extra_config: dict[str, Any]):
        self.app = app
        self.sock = sock
        self.extra_config = extra_config
        super().__init__()

    def load_config(self) -> None:
        # Tell Gunicorn to use our pre-bound socket
        self.cfg.set("bind", f"fd://{self.sock.fileno()}")
        self.cfg.set("preload_app", True)
        self.cfg.set("workers", 8)
        for k, v in self.extra_config.items():
            self.cfg.set(k, v)

    def load(self) -> WSGIApplication:
        return self.app


def create_bound_socket() -> tuple[socket.socket, int]:
    """Create and bind a socket, return socket and port"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 0))  # Let OS pick port
    sock.listen(128)  # Set listen backlog

    port = sock.getsockname()[1]
    return sock, port


def prepare_sync(sc_req: ServerCompatRequest) -> tuple[ServerCompatResponse, SocketGunicornApp]:
    """Create the WSGI application, wrap it in a server, set up a
    socket, and build the ServerCompatResponse we'll send back to the
    test runner, informing it of the port the server will be on.

    The server isn't actually started here because that is a blocking call.

    """
    app = Conformance()
    wsgi_app = wsgi_conformance_service(app)
    sock, port = create_bound_socket()

    server = SocketGunicornApp(wsgi_app, sock, {})

    response = ServerCompatResponse(host="127.0.0.1", port=port)
    return response, server


def main(mode: str) -> None:
    """Main loop that reads requests from stdin and writes responses to stdout."""
    if mode not in {"sync", "async"}:
        raise ValueError("mode must be sync or async")
    while True:
        try:
            message_bytes = read_size_delimited_message()
            if message_bytes is None:
                break  # EOF

            request = ServerCompatRequest()
            request.ParseFromString(message_bytes)

            if mode == "async":
                raise NotImplementedError
            elif mode == "sync":
                response, server = prepare_sync(request)
            else:
                raise NotImplementedError

            write_size_delimited_message(response.SerializeToString())
            server.run()
            return

        except Exception as e:
            sys.stderr.write(f"Error processing request: {e}\n")
            sys.stderr.flush()
            break


if __name__ == "__main__":
    main(sys.argv[1])
