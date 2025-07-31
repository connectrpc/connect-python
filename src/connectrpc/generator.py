import protogen
import protogen._case

# Universal arguments on all RPC methods
common_params = [
    "extra_headers: HeaderInput | None=None",
    "timeout_seconds: float | None=None",
]

common_params_str = ", ".join(common_params)

common_args = [
    "extra_headers",
    "timeout_seconds",
]
common_args_str = ", ".join(common_args)


def rpc_url_str(f: protogen.File, s: protogen.Service, m: protogen.Method) -> str:
    route = f"{s.proto.name}/{m.proto.name}"
    if f.proto.package != "":
        route = f.proto.package + "." + route
    return f'"/{route}"'


def service_url_prefix(f: protogen.File, s: protogen.Service) -> str:
    route = s.proto.name
    if f.proto.package != "":
        route = f.proto.package + "." + route
    return f'"/{route}"'


def generate(gen: protogen.Plugin) -> None:
    for f in gen.files_to_generate:
        if len(f.services) == 0:
            continue

        g = gen.new_generated_file(
            f.proto.name.replace(".proto", "_pb2_connect.py"),
            import_path(f),
        )

        g.P("# Generated Connect client code")
        g.P()
        g.P("from __future__ import annotations")
        g.P("from collections.abc import AsyncIterator")
        g.P("from collections.abc import Iterator")
        g.P("from collections.abc import Iterable")
        g.P("import aiohttp")
        g.P("import urllib3")
        g.P("import typing")
        g.P("import sys")
        g.P()
        g.P("from connectrpc.client_async import AsyncConnectClient")
        g.P("from connectrpc.client_sync import ConnectClient")
        g.P("from connectrpc.client_protocol import ConnectProtocol")
        g.P("from connectrpc.client_connect import ConnectProtocolError")
        g.P("from connectrpc.headers import HeaderInput")
        g.P("from connectrpc.server import ClientRequest")
        g.P("from connectrpc.server import ClientStream")
        g.P("from connectrpc.server import ServerResponse")
        g.P("from connectrpc.server import ServerStream")
        g.P("from connectrpc.server_sync import ConnectWSGI")
        g.P("from connectrpc.streams import StreamInput")
        g.P("from connectrpc.streams import AsyncStreamOutput")
        g.P("from connectrpc.streams import StreamOutput")
        g.P("from connectrpc.unary import UnaryOutput")
        g.P("from connectrpc.unary import ClientStreamingOutput")
        g.P()
        g.P("if typing.TYPE_CHECKING:")
        g.P("    # wsgiref.types was added in Python 3.11.")
        g.P("    if sys.version_info >= (3, 11):")
        g.P("        from wsgiref.types import WSGIApplication")
        g.P("    else:")
        g.P("        from _typeshed.wsgi import WSGIApplication")
        g.P()
        g.print_import()
        g.P()

        for s in f.services:
            SyncClientGenerator(g, f, s).generate()
            g.P()
            AsyncClientGenerator(g, f, s).generate()
            g.P()
            WSGIServerGenerator(g, f, s).generate()
            g.P()


def docstring(g: protogen.GeneratedFile, *args: str) -> None:
    g.P('"""', *args, '"""')


def import_path(f: protogen.File) -> protogen.PyImportPath:
    return protogen.PyImportPath(f.py_import_path._path + "_connect")


class SyncClientGenerator:
    def __init__(self, g: protogen.GeneratedFile, f: protogen.File, s: protogen.Service):
        self.g = g
        self.f = f
        self.s = s

    def generate(self) -> None:
        self.generate_init()
        for m in self.s.methods:
            assert m.input is not None, f"Method {m.py_name} input should be resolved"
            assert m.output is not None, f"Method {m.py_name} output should be resolved"

            if not m.proto.client_streaming and not m.proto.server_streaming:
                self.generate_unary_rpc(m)
            elif not m.proto.client_streaming and m.proto.server_streaming:
                self.generate_server_streaming_rpc(m)
            elif m.proto.client_streaming and not m.proto.server_streaming:
                self.generate_client_streaming_rpc(m)
            elif m.proto.client_streaming and m.proto.server_streaming:
                self.generate_bidirectional_streaming_rpc(m)

    def generate_init(self) -> None:
        self.g.set_indent(0)
        self.g.P("class ", protogen.PyIdent(import_path(self.f), self.s.proto.name), "Client:")
        self.g.set_indent(4)
        self.g.P("def __init__(")
        self.g.P("    self,")
        self.g.P("    base_url: str,")
        self.g.P("    http_client: urllib3.PoolManager | None = None,")
        self.g.P("    protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,")
        self.g.P("):")
        self.g.P("    self.base_url = base_url")
        self.g.P("    self._connect_client = ConnectClient(http_client, protocol)")

    def generate_unary_rpc(self, m: protogen.Method) -> None:
        self.g.P("def call_", m.py_name, "(")
        self.g.P("    self, req: ", m.input.py_ident, ", ", common_params_str)
        self.g.P(") -> UnaryOutput[", m.output.py_ident, "]:")
        self.g.set_indent(8)
        docstring(
            self.g,
            "Low-level method to call ",
            m.proto.name,
            ", granting access to errors and metadata",
        )
        self.g.P("url = self.base_url + ", rpc_url_str(self.f, self.s, m))
        self.g.P(
            "return self._connect_client.call_unary(url, req, ",
            m.output.py_ident,
            ",",
            common_args_str,
            ")",
        )
        self.g.P()
        self.g.set_indent(4)
        self.g.P()
        self.g.P("def ", m.py_name, "(")
        self.g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
        self.g.P(") -> ", m.output.py_ident, ":")
        self.g.set_indent(8)
        self.g.P("response = self.call_", m.py_name, "(req, ", common_args_str, ")")
        self.g.P("err = response.error()")
        self.g.P("if err is not None:")
        self.g.P("    raise err")
        self.g.P("msg = response.message()")
        self.g.P("if msg is None:")
        self.g.P("    raise ConnectProtocolError('missing response message')")
        self.g.P("return msg")
        self.g.set_indent(4)
        self.g.P()

    def generate_server_streaming_rpc(self, m: protogen.Method) -> None:
        self.g.P("def ", m.py_name, "(")
        self.g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
        self.g.P(") -> Iterator[", m.output.py_ident, "]:")
        self.g.P("    return self._", m.py_name, "_iterator(req, ", common_args_str, ")")
        self.g.P()

        self.g.P("def _", m.py_name, "_iterator(")
        self.g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
        self.g.P(") -> Iterator[", m.output.py_ident, "]:")
        self.g.P("    stream_output = self.call_", m.py_name, "(req, extra_headers)")
        self.g.P("    err = stream_output.error()")
        self.g.P("    if err is not None:")
        self.g.P("        raise err")
        self.g.P("    yield from stream_output")
        self.g.P("    err = stream_output.error()")
        self.g.P("    if err is not None:")
        self.g.P("        raise err")

        self.g.P()

        self.g.P("def call_", m.py_name, "(")
        self.g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
        self.g.P(") -> StreamOutput[", m.output.py_ident, "]:")
        self.g.set_indent(8)
        docstring(
            self.g,
            "Low-level method to call ",
            m.proto.name,
            ", granting access to errors and metadata",
        )
        self.g.set_indent(4)
        self.g.P("    url = self.base_url + ", rpc_url_str(self.f, self.s, m))
        self.g.P("    return self._connect_client.call_server_streaming(")
        self.g.P("        url, req, ", m.output.py_ident, ", ", common_args_str)
        self.g.P("    )")
        self.g.P()

    def generate_client_streaming_rpc(self, m: protogen.Method) -> None:
        self.g.P("def call_", m.py_name, "(")
        self.g.P("    self, reqs: Iterable[", m.input.py_ident, "], ", common_params_str)
        self.g.P(") -> ClientStreamingOutput[", m.output.py_ident, "]:")
        self.g.set_indent(8)
        docstring(
            self.g,
            "Low-level method to call ",
            m.proto.name,
            ", granting access to errors and metadata",
        )
        self.g.set_indent(4)
        self.g.P("    url = self.base_url + ", rpc_url_str(self.f, self.s, m))
        self.g.P("    return self._connect_client.call_client_streaming(")
        self.g.P("        url, reqs, ", m.output.py_ident, ", ", common_args_str)
        self.g.P("    )")
        self.g.P()

        self.g.P("def ", m.py_name, "(")
        self.g.P("    self, reqs: Iterable[", m.input.py_ident, "], ", common_params_str)
        self.g.P(") -> ", m.output.py_ident, ":")
        self.g.P("    client_stream_output = self.call_", m.py_name, "(reqs, extra_headers)")
        self.g.P("    err = client_stream_output.error()")
        self.g.P("    if err is not None:")
        self.g.P("        raise err")
        self.g.P("    msg = client_stream_output.message()")
        self.g.P("    if msg is None:")
        self.g.P("        raise RuntimeError('ClientStreamOutput has empty error and message')")
        self.g.P("    return msg")
        self.g.P()

    def generate_bidirectional_streaming_rpc(self, m: protogen.Method) -> None:
        # Simple iterator method
        self.g.P("def ", m.py_name, "(")
        self.g.P("    self, reqs: Iterable[", m.input.py_ident, "], ", common_params_str)
        self.g.P(") -> Iterator[", m.output.py_ident, "]:")
        self.g.P("    return self._", m.py_name, "_iterator(reqs, ", common_args_str, ")")
        self.g.P()

        # Implementation helper
        self.g.P("def _", m.py_name, "_iterator(")
        self.g.P("    self, reqs: Iterable[", m.input.py_ident, "], ", common_params_str)
        self.g.P(") -> Iterator[", m.output.py_ident, "]:")
        self.g.P("    stream_output = self.call_", m.py_name, "(reqs, ", common_args_str, ")")
        self.g.P("    err = stream_output.error()")
        self.g.P("    if err is not None:")
        self.g.P("        raise err")
        self.g.P("    yield from stream_output")
        self.g.P("    err = stream_output.error()")
        self.g.P("    if err is not None:")
        self.g.P("        raise err")

        self.g.P()

        # Stream method for metadata access
        self.g.P("def call_", m.py_name, "(")
        self.g.P(
            "    self, reqs: Iterable[",
            m.input.py_ident,
            "], ",
            common_params_str,
        )
        self.g.P(") -> StreamOutput[", m.output.py_ident, "]:")
        self.g.set_indent(8)
        docstring(
            self.g,
            "Low-level method to call ",
            m.proto.name,
            ", granting access to errors and metadata",
        )
        self.g.set_indent(4)
        self.g.P("    url = self.base_url + ", rpc_url_str(self.f, self.s, m))
        self.g.P("    return self._connect_client.call_bidirectional_streaming(")
        self.g.P("        url, reqs, ", m.output.py_ident, ", ", common_args_str)
        self.g.P("    )")
        self.g.P()


class AsyncClientGenerator:
    def __init__(self, g: protogen.GeneratedFile, f: protogen.File, s: protogen.Service):
        self.g = g
        self.f = f
        self.s = s

    def import_path(self) -> protogen.PyImportPath:
        return protogen.PyImportPath(self.f.py_import_path._path + "_connect")

    def generate_init(self) -> None:
        self.g.set_indent(0)
        self.g.P("class Async", protogen.PyIdent(import_path(self.f), self.s.proto.name), "Client:")
        self.g.set_indent(4)
        self.g.P("def __init__(")
        self.g.P("    self,")
        self.g.P("    base_url: str,")
        self.g.P("    http_client: aiohttp.ClientSession,")
        self.g.P("    protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,")
        self.g.P("):")
        self.g.P("    self.base_url = base_url")
        self.g.P("    self._connect_client = AsyncConnectClient(http_client, protocol)")
        self.g.P()

    def generate(self) -> None:
        self.generate_init()

        for m in self.s.methods:
            assert m.input is not None, f"Method {m.py_name} input should be resolved"
            assert m.output is not None, f"Method {m.py_name} output should be resolved"

            if not m.proto.client_streaming and not m.proto.server_streaming:
                self.generate_unary_rpc(m)
            elif not m.proto.client_streaming and m.proto.server_streaming:
                self.generate_server_streaming_rpc(m)
            elif m.proto.client_streaming and not m.proto.server_streaming:
                self.generate_client_streaming_rpc(m)
            elif m.proto.client_streaming and m.proto.server_streaming:
                self.generate_bidirectional_streaming_rpc(m)

    def generate_unary_rpc(self, m: protogen.Method) -> None:
        """Generate a unary RPC method."""
        self.g.P("async def call_", m.py_name, "(")
        self.g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
        self.g.P(") -> UnaryOutput[", m.output.py_ident, "]:")
        self.g.set_indent(8)
        docstring(
            self.g,
            "Low-level method to call ",
            m.proto.name,
            ", granting access to errors and metadata",
        )
        self.g.P("url = self.base_url + ", rpc_url_str(self.f, self.s, m))
        self.g.P(
            "return await self._connect_client.call_unary(url, req, ",
            m.output.py_ident,
            ",",
            common_args_str,
            ")",
        )
        self.g.set_indent(4)
        self.g.P()
        self.g.P("async def ", m.py_name, "(")
        self.g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
        self.g.P(") -> ", m.output.py_ident, ":")
        self.g.set_indent(8)
        self.g.P("response = await self.call_", m.py_name, "(req, ", common_args_str, ")")
        self.g.P("err = response.error()")
        self.g.P("if err is not None:")
        self.g.P("    raise err")
        self.g.P("msg = response.message()")
        self.g.P("if msg is None:")
        self.g.P("    raise ConnectProtocolError('missing response message')")
        self.g.P("return msg")
        self.g.set_indent(4)
        self.g.P()

    def generate_server_streaming_rpc(self, m: protogen.Method) -> None:
        # Simple iterator method
        self.g.P("def ", m.py_name, "(")
        self.g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
        self.g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
        self.g.P("    return self._", m.py_name, "_iterator(req, ", common_args_str, ")")
        self.g.P()

        # Implementation helper
        self.g.P("async def _", m.py_name, "_iterator(")
        self.g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
        self.g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
        self.g.P("    stream_output = await self.call_", m.py_name, "(req, extra_headers)")
        self.g.P("    err = stream_output.error()")
        self.g.P("    if err is not None:")
        self.g.P("        raise err")
        self.g.P("    async with stream_output as stream:")
        self.g.P("        async for response in stream:")
        self.g.P("            yield response")
        self.g.P("        err = stream.error()")
        self.g.P("        if err is not None:")
        self.g.P("            raise err")
        self.g.P()

        self.g.P("async def call_", m.py_name, "(")
        self.g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
        self.g.P(") -> AsyncStreamOutput[", m.output.py_ident, "]:")
        self.g.set_indent(8)
        docstring(
            self.g,
            "Low-level method to call ",
            m.proto.name,
            ", granting access to errors and metadata",
        )
        self.g.set_indent(4)
        self.g.P("    url = self.base_url + ", rpc_url_str(self.f, self.s, m))
        self.g.P("    return await self._connect_client.call_server_streaming(")
        self.g.P("        url, req, ", m.output.py_ident, ", ", common_args_str)
        self.g.P("    )")
        self.g.P()

    def generate_client_streaming_rpc(self, m: protogen.Method) -> None:
        """Generate a client streaming RPC method."""
        self.g.P("async def call_", m.py_name, "(")
        self.g.P("    self, reqs: StreamInput[", m.input.py_ident, "], ", common_params_str)
        self.g.P(") -> ClientStreamingOutput[", m.output.py_ident, "]:")
        self.g.set_indent(8)
        docstring(
            self.g,
            "Low-level method to call ",
            m.proto.name,
            ", granting access to errors and metadata",
        )
        self.g.set_indent(4)
        self.g.P(
            '    url = self.base_url + "/',
            self.f.proto.package,
            ".",
            self.s.proto.name,
            "/",
            m.proto.name,
            '"',
        )
        self.g.P("    return await self._connect_client.call_client_streaming(")
        self.g.P("        url, reqs, ", m.output.py_ident, ", ", common_args_str)
        self.g.P("    )")
        self.g.P()

        self.g.P("async def ", m.py_name, "(")
        self.g.P("    self, reqs: StreamInput[", m.input.py_ident, "], ", common_params_str)
        self.g.P(") -> ", m.output.py_ident, ":")
        self.g.P("    client_stream_output = await self.call_", m.py_name, "(reqs, extra_headers)")
        self.g.P("    err = client_stream_output.error()")
        self.g.P("    if err is not None:")
        self.g.P("        raise err")
        self.g.P("    msg = client_stream_output.message()")
        self.g.P("    if msg is None:")
        self.g.P("        raise RuntimeError('ClientStreamOutput has empty error and message')")
        self.g.P("    return msg")
        self.g.P()

    def generate_bidirectional_streaming_rpc(self, m: protogen.Method) -> None:
        # Simple iterator method
        self.g.P("def ", m.py_name, "(")
        self.g.P("    self, reqs: StreamInput[", m.input.py_ident, "], ", common_params_str)
        self.g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
        self.g.P("    return self._", m.py_name, "_iterator(reqs, ", common_args_str, ")")
        self.g.P()

        # Implementation helper
        self.g.P("async def _", m.py_name, "_iterator(")
        self.g.P("    self, reqs: StreamInput[", m.input.py_ident, "], ", common_params_str)
        self.g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
        self.g.P("    stream_output = await self.call_", m.py_name, "(reqs, ", common_args_str, ")")
        self.g.P("    err = stream_output.error()")
        self.g.P("    if err is not None:")
        self.g.P("        raise err")
        self.g.P("    async with stream_output as stream:")
        self.g.P("        async for response in stream:")
        self.g.P("            yield response")
        self.g.P("        err = stream.error()")
        self.g.P("        if err is not None:")
        self.g.P("            raise err")

        self.g.P()

        # Stream method for metadata access
        self.g.P("async def call_", m.py_name, "(")
        self.g.P(
            "    self, reqs: StreamInput[",
            m.input.py_ident,
            "], ",
            common_params_str,
        )
        self.g.P(") -> AsyncStreamOutput[", m.output.py_ident, "]:")
        self.g.set_indent(8)
        docstring(
            self.g,
            "Low-level method to call ",
            m.proto.name,
            ", granting access to errors and metadata",
        )
        self.g.set_indent(4)
        self.g.P("    url = self.base_url + ", rpc_url_str(self.f, self.s, m))
        self.g.P("    return await self._connect_client.call_bidirectional_streaming(")
        self.g.P("        url, reqs, ", m.output.py_ident, ", ", common_args_str)
        self.g.P("    )")
        self.g.P()


class WSGIServerGenerator:
    def __init__(self, g: protogen.GeneratedFile, f: protogen.File, s: protogen.Service):
        self.g = g
        self.f = f
        self.s = s

    def generate(self) -> None:
        self.g.set_indent(0)
        self.generate_protocol()
        self.g.P()
        self.generate_path_prefix_const()
        self.g.P()
        self.generate_wsgi_constructor()

    def generate_wsgi_constructor(self) -> None:
        service_name = self.g.qualified_py_ident(
            protogen.PyIdent(import_path(self.f), self.s.proto.name)
        )
        service_name = protogen._case.snake_case(service_name)

        self.g.set_indent(0)
        self.g.P(
            "def wsgi_",
            service_name,
            "(implementation: ",
            self.protocol_name(),
            ") -> WSGIApplication:",
        )
        self.g.P("    app = ConnectWSGI()")
        for m in self.s.methods:
            assert m.input is not None, f"Method {m.py_name} input should be resolved"
            assert m.output is not None, f"Method {m.py_name} output should be resolved"

            if not m.proto.client_streaming and not m.proto.server_streaming:
                self.g.P(
                    f"    app.register_unary_rpc({rpc_url_str(self.f, self.s, m)}, implementation.{m.py_name}, ",
                    m.input.py_ident,
                    ")",
                )
            elif not m.proto.client_streaming and m.proto.server_streaming:
                self.g.P(
                    f"    app.register_server_streaming_rpc({rpc_url_str(self.f, self.s, m)}, implementation.{m.py_name}, ",
                    m.input.py_ident,
                    ")",
                )
            elif m.proto.client_streaming and not m.proto.server_streaming:
                self.g.P(
                    f"    app.register_client_streaming_rpc({rpc_url_str(self.f, self.s, m)}, implementation.{m.py_name}, ",
                    m.input.py_ident,
                    ")",
                )
            elif m.proto.client_streaming and m.proto.server_streaming:
                self.g.P(
                    f"    app.register_bidi_streaming_rpc({rpc_url_str(self.f, self.s, m)}, implementation.{m.py_name}, ",
                    m.input.py_ident,
                    ")",
                )

        self.g.P("    return app")

    def generate_path_prefix_const(self) -> None:
        self.g.set_indent(0)

        all_caps_name = protogen._case.snake_case(self.s.proto.name).upper()
        self.g.P(f"{all_caps_name}_PATH_PREFIX = {service_url_prefix(self.f, self.s)}")

    def protocol_name(self) -> str:
        return (
            self.g.qualified_py_ident(protogen.PyIdent(import_path(self.f), self.s.proto.name))
            + "Protocol"
        )

    def generate_protocol(self) -> None:
        self.g.P("@typing.runtime_checkable")
        self.g.P("class ", self.protocol_name(), "(typing.Protocol):")
        for m in self.s.methods:
            assert m.input is not None, f"Method {m.py_name} input should be resolved"
            assert m.output is not None, f"Method {m.py_name} output should be resolved"

            if not m.proto.client_streaming and not m.proto.server_streaming:
                self.generate_unary_protocol(m)
            elif not m.proto.client_streaming and m.proto.server_streaming:
                self.generate_server_streaming_protocol(m)
            elif m.proto.client_streaming and not m.proto.server_streaming:
                self.generate_client_streaming_protocol(m)
            elif m.proto.client_streaming and m.proto.server_streaming:
                self.generate_bidirectional_streaming_protocol(m)

    def generate_unary_protocol(self, m: protogen.Method) -> None:
        self.g.P(
            "    def ",
            m.py_name,
            "(self, req: ClientRequest[",
            m.input.py_ident,
            "]) -> ServerResponse[",
            m.output.py_ident,
            "]:",
        )
        self.g.P("        ...")

    def generate_server_streaming_protocol(self, m: protogen.Method) -> None:
        self.g.P(
            "    def ",
            m.py_name,
            "(self, req: ClientRequest[",
            m.input.py_ident,
            "]) -> ServerStream[",
            m.output.py_ident,
            "]:",
        )
        self.g.P("        ...")

    def generate_client_streaming_protocol(self, m: protogen.Method) -> None:
        self.g.P(
            "    def ",
            m.py_name,
            "(self, req: ClientStream[",
            m.input.py_ident,
            "]) -> ServerResponse[",
            m.output.py_ident,
            "]:",
        )
        self.g.P("        ...")

    def generate_bidirectional_streaming_protocol(self, m: protogen.Method) -> None:
        self.g.P(
            "    def ",
            m.py_name,
            "(self, req: ClientStream[",
            m.input.py_ident,
            "]) -> ServerStream[",
            m.output.py_ident,
            "]:",
        )
        self.g.P("        ...")


def gather_message_types(g: protogen.GeneratedFile, f: protogen.File) -> list[protogen.Message]:
    result: list[protogen.Message] = []
    for svc in f.services:
        for method in svc.methods:
            assert method.input is not None
            assert method.output is not None
            result.append(method.input)
            result.append(method.output)
    return result
