from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HTTPVersion(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HTTP_VERSION_UNSPECIFIED: _ClassVar[HTTPVersion]
    HTTP_VERSION_1: _ClassVar[HTTPVersion]
    HTTP_VERSION_2: _ClassVar[HTTPVersion]
    HTTP_VERSION_3: _ClassVar[HTTPVersion]

class Protocol(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROTOCOL_UNSPECIFIED: _ClassVar[Protocol]
    PROTOCOL_CONNECT: _ClassVar[Protocol]
    PROTOCOL_GRPC: _ClassVar[Protocol]
    PROTOCOL_GRPC_WEB: _ClassVar[Protocol]

class Codec(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CODEC_UNSPECIFIED: _ClassVar[Codec]
    CODEC_PROTO: _ClassVar[Codec]
    CODEC_JSON: _ClassVar[Codec]
    CODEC_TEXT: _ClassVar[Codec]

class Compression(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    COMPRESSION_UNSPECIFIED: _ClassVar[Compression]
    COMPRESSION_IDENTITY: _ClassVar[Compression]
    COMPRESSION_GZIP: _ClassVar[Compression]
    COMPRESSION_BR: _ClassVar[Compression]
    COMPRESSION_ZSTD: _ClassVar[Compression]
    COMPRESSION_DEFLATE: _ClassVar[Compression]
    COMPRESSION_SNAPPY: _ClassVar[Compression]

class StreamType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STREAM_TYPE_UNSPECIFIED: _ClassVar[StreamType]
    STREAM_TYPE_UNARY: _ClassVar[StreamType]
    STREAM_TYPE_CLIENT_STREAM: _ClassVar[StreamType]
    STREAM_TYPE_SERVER_STREAM: _ClassVar[StreamType]
    STREAM_TYPE_HALF_DUPLEX_BIDI_STREAM: _ClassVar[StreamType]
    STREAM_TYPE_FULL_DUPLEX_BIDI_STREAM: _ClassVar[StreamType]

class Code(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CODE_UNSPECIFIED: _ClassVar[Code]
    CODE_CANCELED: _ClassVar[Code]
    CODE_UNKNOWN: _ClassVar[Code]
    CODE_INVALID_ARGUMENT: _ClassVar[Code]
    CODE_DEADLINE_EXCEEDED: _ClassVar[Code]
    CODE_NOT_FOUND: _ClassVar[Code]
    CODE_ALREADY_EXISTS: _ClassVar[Code]
    CODE_PERMISSION_DENIED: _ClassVar[Code]
    CODE_RESOURCE_EXHAUSTED: _ClassVar[Code]
    CODE_FAILED_PRECONDITION: _ClassVar[Code]
    CODE_ABORTED: _ClassVar[Code]
    CODE_OUT_OF_RANGE: _ClassVar[Code]
    CODE_UNIMPLEMENTED: _ClassVar[Code]
    CODE_INTERNAL: _ClassVar[Code]
    CODE_UNAVAILABLE: _ClassVar[Code]
    CODE_DATA_LOSS: _ClassVar[Code]
    CODE_UNAUTHENTICATED: _ClassVar[Code]
HTTP_VERSION_UNSPECIFIED: HTTPVersion
HTTP_VERSION_1: HTTPVersion
HTTP_VERSION_2: HTTPVersion
HTTP_VERSION_3: HTTPVersion
PROTOCOL_UNSPECIFIED: Protocol
PROTOCOL_CONNECT: Protocol
PROTOCOL_GRPC: Protocol
PROTOCOL_GRPC_WEB: Protocol
CODEC_UNSPECIFIED: Codec
CODEC_PROTO: Codec
CODEC_JSON: Codec
CODEC_TEXT: Codec
COMPRESSION_UNSPECIFIED: Compression
COMPRESSION_IDENTITY: Compression
COMPRESSION_GZIP: Compression
COMPRESSION_BR: Compression
COMPRESSION_ZSTD: Compression
COMPRESSION_DEFLATE: Compression
COMPRESSION_SNAPPY: Compression
STREAM_TYPE_UNSPECIFIED: StreamType
STREAM_TYPE_UNARY: StreamType
STREAM_TYPE_CLIENT_STREAM: StreamType
STREAM_TYPE_SERVER_STREAM: StreamType
STREAM_TYPE_HALF_DUPLEX_BIDI_STREAM: StreamType
STREAM_TYPE_FULL_DUPLEX_BIDI_STREAM: StreamType
CODE_UNSPECIFIED: Code
CODE_CANCELED: Code
CODE_UNKNOWN: Code
CODE_INVALID_ARGUMENT: Code
CODE_DEADLINE_EXCEEDED: Code
CODE_NOT_FOUND: Code
CODE_ALREADY_EXISTS: Code
CODE_PERMISSION_DENIED: Code
CODE_RESOURCE_EXHAUSTED: Code
CODE_FAILED_PRECONDITION: Code
CODE_ABORTED: Code
CODE_OUT_OF_RANGE: Code
CODE_UNIMPLEMENTED: Code
CODE_INTERNAL: Code
CODE_UNAVAILABLE: Code
CODE_DATA_LOSS: Code
CODE_UNAUTHENTICATED: Code

class Config(_message.Message):
    __slots__ = ("features", "include_cases", "exclude_cases")
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_CASES_FIELD_NUMBER: _ClassVar[int]
    EXCLUDE_CASES_FIELD_NUMBER: _ClassVar[int]
    features: Features
    include_cases: _containers.RepeatedCompositeFieldContainer[ConfigCase]
    exclude_cases: _containers.RepeatedCompositeFieldContainer[ConfigCase]
    def __init__(self, features: _Optional[_Union[Features, _Mapping]] = ..., include_cases: _Optional[_Iterable[_Union[ConfigCase, _Mapping]]] = ..., exclude_cases: _Optional[_Iterable[_Union[ConfigCase, _Mapping]]] = ...) -> None: ...

class Features(_message.Message):
    __slots__ = ("versions", "protocols", "codecs", "compressions", "stream_types", "supports_h2c", "supports_tls", "supports_tls_client_certs", "supports_trailers", "supports_half_duplex_bidi_over_http1", "supports_connect_get", "supports_message_receive_limit")
    VERSIONS_FIELD_NUMBER: _ClassVar[int]
    PROTOCOLS_FIELD_NUMBER: _ClassVar[int]
    CODECS_FIELD_NUMBER: _ClassVar[int]
    COMPRESSIONS_FIELD_NUMBER: _ClassVar[int]
    STREAM_TYPES_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_H2C_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_TLS_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_TLS_CLIENT_CERTS_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_TRAILERS_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_HALF_DUPLEX_BIDI_OVER_HTTP1_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_CONNECT_GET_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_MESSAGE_RECEIVE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    versions: _containers.RepeatedScalarFieldContainer[HTTPVersion]
    protocols: _containers.RepeatedScalarFieldContainer[Protocol]
    codecs: _containers.RepeatedScalarFieldContainer[Codec]
    compressions: _containers.RepeatedScalarFieldContainer[Compression]
    stream_types: _containers.RepeatedScalarFieldContainer[StreamType]
    supports_h2c: bool
    supports_tls: bool
    supports_tls_client_certs: bool
    supports_trailers: bool
    supports_half_duplex_bidi_over_http1: bool
    supports_connect_get: bool
    supports_message_receive_limit: bool
    def __init__(self, versions: _Optional[_Iterable[_Union[HTTPVersion, str]]] = ..., protocols: _Optional[_Iterable[_Union[Protocol, str]]] = ..., codecs: _Optional[_Iterable[_Union[Codec, str]]] = ..., compressions: _Optional[_Iterable[_Union[Compression, str]]] = ..., stream_types: _Optional[_Iterable[_Union[StreamType, str]]] = ..., supports_h2c: bool = ..., supports_tls: bool = ..., supports_tls_client_certs: bool = ..., supports_trailers: bool = ..., supports_half_duplex_bidi_over_http1: bool = ..., supports_connect_get: bool = ..., supports_message_receive_limit: bool = ...) -> None: ...

class ConfigCase(_message.Message):
    __slots__ = ("version", "protocol", "codec", "compression", "stream_type", "use_tls", "use_tls_client_certs", "use_message_receive_limit")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    CODEC_FIELD_NUMBER: _ClassVar[int]
    COMPRESSION_FIELD_NUMBER: _ClassVar[int]
    STREAM_TYPE_FIELD_NUMBER: _ClassVar[int]
    USE_TLS_FIELD_NUMBER: _ClassVar[int]
    USE_TLS_CLIENT_CERTS_FIELD_NUMBER: _ClassVar[int]
    USE_MESSAGE_RECEIVE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    version: HTTPVersion
    protocol: Protocol
    codec: Codec
    compression: Compression
    stream_type: StreamType
    use_tls: bool
    use_tls_client_certs: bool
    use_message_receive_limit: bool
    def __init__(self, version: _Optional[_Union[HTTPVersion, str]] = ..., protocol: _Optional[_Union[Protocol, str]] = ..., codec: _Optional[_Union[Codec, str]] = ..., compression: _Optional[_Union[Compression, str]] = ..., stream_type: _Optional[_Union[StreamType, str]] = ..., use_tls: bool = ..., use_tls_client_certs: bool = ..., use_message_receive_limit: bool = ...) -> None: ...

class TLSCreds(_message.Message):
    __slots__ = ("cert", "key")
    CERT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    cert: bytes
    key: bytes
    def __init__(self, cert: _Optional[bytes] = ..., key: _Optional[bytes] = ...) -> None: ...
