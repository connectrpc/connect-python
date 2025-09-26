from gen.connectrpc.conformance.v1 import config_pb2 as _config_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ServerCompatRequest(_message.Message):
    __slots__ = ("protocol", "http_version", "use_tls", "client_tls_cert", "message_receive_limit", "server_creds")
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    HTTP_VERSION_FIELD_NUMBER: _ClassVar[int]
    USE_TLS_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TLS_CERT_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_RECEIVE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    SERVER_CREDS_FIELD_NUMBER: _ClassVar[int]
    protocol: _config_pb2.Protocol
    http_version: _config_pb2.HTTPVersion
    use_tls: bool
    client_tls_cert: bytes
    message_receive_limit: int
    server_creds: _config_pb2.TLSCreds
    def __init__(self, protocol: _Optional[_Union[_config_pb2.Protocol, str]] = ..., http_version: _Optional[_Union[_config_pb2.HTTPVersion, str]] = ..., use_tls: bool = ..., client_tls_cert: _Optional[bytes] = ..., message_receive_limit: _Optional[int] = ..., server_creds: _Optional[_Union[_config_pb2.TLSCreds, _Mapping]] = ...) -> None: ...

class ServerCompatResponse(_message.Message):
    __slots__ = ("host", "port", "pem_cert")
    HOST_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    PEM_CERT_FIELD_NUMBER: _ClassVar[int]
    host: str
    port: int
    pem_cert: bytes
    def __init__(self, host: _Optional[str] = ..., port: _Optional[int] = ..., pem_cert: _Optional[bytes] = ...) -> None: ...
