from gen.connectrpc.conformance.v1 import config_pb2 as _config_pb2
from google.protobuf import any_pb2 as _any_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class UnaryResponseDefinition(_message.Message):
    __slots__ = ("response_headers", "response_data", "error", "response_trailers", "response_delay_ms", "raw_response")
    RESPONSE_HEADERS_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_DATA_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_TRAILERS_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_DELAY_MS_FIELD_NUMBER: _ClassVar[int]
    RAW_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response_headers: _containers.RepeatedCompositeFieldContainer[Header]
    response_data: bytes
    error: Error
    response_trailers: _containers.RepeatedCompositeFieldContainer[Header]
    response_delay_ms: int
    raw_response: RawHTTPResponse
    def __init__(self, response_headers: _Optional[_Iterable[_Union[Header, _Mapping]]] = ..., response_data: _Optional[bytes] = ..., error: _Optional[_Union[Error, _Mapping]] = ..., response_trailers: _Optional[_Iterable[_Union[Header, _Mapping]]] = ..., response_delay_ms: _Optional[int] = ..., raw_response: _Optional[_Union[RawHTTPResponse, _Mapping]] = ...) -> None: ...

class StreamResponseDefinition(_message.Message):
    __slots__ = ("response_headers", "response_data", "response_delay_ms", "error", "response_trailers", "raw_response")
    RESPONSE_HEADERS_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_DATA_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_DELAY_MS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_TRAILERS_FIELD_NUMBER: _ClassVar[int]
    RAW_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response_headers: _containers.RepeatedCompositeFieldContainer[Header]
    response_data: _containers.RepeatedScalarFieldContainer[bytes]
    response_delay_ms: int
    error: Error
    response_trailers: _containers.RepeatedCompositeFieldContainer[Header]
    raw_response: RawHTTPResponse
    def __init__(self, response_headers: _Optional[_Iterable[_Union[Header, _Mapping]]] = ..., response_data: _Optional[_Iterable[bytes]] = ..., response_delay_ms: _Optional[int] = ..., error: _Optional[_Union[Error, _Mapping]] = ..., response_trailers: _Optional[_Iterable[_Union[Header, _Mapping]]] = ..., raw_response: _Optional[_Union[RawHTTPResponse, _Mapping]] = ...) -> None: ...

class UnaryRequest(_message.Message):
    __slots__ = ("response_definition", "request_data")
    RESPONSE_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    REQUEST_DATA_FIELD_NUMBER: _ClassVar[int]
    response_definition: UnaryResponseDefinition
    request_data: bytes
    def __init__(self, response_definition: _Optional[_Union[UnaryResponseDefinition, _Mapping]] = ..., request_data: _Optional[bytes] = ...) -> None: ...

class UnaryResponse(_message.Message):
    __slots__ = ("payload",)
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    payload: ConformancePayload
    def __init__(self, payload: _Optional[_Union[ConformancePayload, _Mapping]] = ...) -> None: ...

class IdempotentUnaryRequest(_message.Message):
    __slots__ = ("response_definition", "request_data")
    RESPONSE_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    REQUEST_DATA_FIELD_NUMBER: _ClassVar[int]
    response_definition: UnaryResponseDefinition
    request_data: bytes
    def __init__(self, response_definition: _Optional[_Union[UnaryResponseDefinition, _Mapping]] = ..., request_data: _Optional[bytes] = ...) -> None: ...

class IdempotentUnaryResponse(_message.Message):
    __slots__ = ("payload",)
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    payload: ConformancePayload
    def __init__(self, payload: _Optional[_Union[ConformancePayload, _Mapping]] = ...) -> None: ...

class ServerStreamRequest(_message.Message):
    __slots__ = ("response_definition", "request_data")
    RESPONSE_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    REQUEST_DATA_FIELD_NUMBER: _ClassVar[int]
    response_definition: StreamResponseDefinition
    request_data: bytes
    def __init__(self, response_definition: _Optional[_Union[StreamResponseDefinition, _Mapping]] = ..., request_data: _Optional[bytes] = ...) -> None: ...

class ServerStreamResponse(_message.Message):
    __slots__ = ("payload",)
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    payload: ConformancePayload
    def __init__(self, payload: _Optional[_Union[ConformancePayload, _Mapping]] = ...) -> None: ...

class ClientStreamRequest(_message.Message):
    __slots__ = ("response_definition", "request_data")
    RESPONSE_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    REQUEST_DATA_FIELD_NUMBER: _ClassVar[int]
    response_definition: UnaryResponseDefinition
    request_data: bytes
    def __init__(self, response_definition: _Optional[_Union[UnaryResponseDefinition, _Mapping]] = ..., request_data: _Optional[bytes] = ...) -> None: ...

class ClientStreamResponse(_message.Message):
    __slots__ = ("payload",)
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    payload: ConformancePayload
    def __init__(self, payload: _Optional[_Union[ConformancePayload, _Mapping]] = ...) -> None: ...

class BidiStreamRequest(_message.Message):
    __slots__ = ("response_definition", "full_duplex", "request_data")
    RESPONSE_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    FULL_DUPLEX_FIELD_NUMBER: _ClassVar[int]
    REQUEST_DATA_FIELD_NUMBER: _ClassVar[int]
    response_definition: StreamResponseDefinition
    full_duplex: bool
    request_data: bytes
    def __init__(self, response_definition: _Optional[_Union[StreamResponseDefinition, _Mapping]] = ..., full_duplex: bool = ..., request_data: _Optional[bytes] = ...) -> None: ...

class BidiStreamResponse(_message.Message):
    __slots__ = ("payload",)
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    payload: ConformancePayload
    def __init__(self, payload: _Optional[_Union[ConformancePayload, _Mapping]] = ...) -> None: ...

class UnimplementedRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UnimplementedResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ConformancePayload(_message.Message):
    __slots__ = ("data", "request_info")
    class RequestInfo(_message.Message):
        __slots__ = ("request_headers", "timeout_ms", "requests", "connect_get_info")
        REQUEST_HEADERS_FIELD_NUMBER: _ClassVar[int]
        TIMEOUT_MS_FIELD_NUMBER: _ClassVar[int]
        REQUESTS_FIELD_NUMBER: _ClassVar[int]
        CONNECT_GET_INFO_FIELD_NUMBER: _ClassVar[int]
        request_headers: _containers.RepeatedCompositeFieldContainer[Header]
        timeout_ms: int
        requests: _containers.RepeatedCompositeFieldContainer[_any_pb2.Any]
        connect_get_info: ConformancePayload.ConnectGetInfo
        def __init__(self, request_headers: _Optional[_Iterable[_Union[Header, _Mapping]]] = ..., timeout_ms: _Optional[int] = ..., requests: _Optional[_Iterable[_Union[_any_pb2.Any, _Mapping]]] = ..., connect_get_info: _Optional[_Union[ConformancePayload.ConnectGetInfo, _Mapping]] = ...) -> None: ...
    class ConnectGetInfo(_message.Message):
        __slots__ = ("query_params",)
        QUERY_PARAMS_FIELD_NUMBER: _ClassVar[int]
        query_params: _containers.RepeatedCompositeFieldContainer[Header]
        def __init__(self, query_params: _Optional[_Iterable[_Union[Header, _Mapping]]] = ...) -> None: ...
    DATA_FIELD_NUMBER: _ClassVar[int]
    REQUEST_INFO_FIELD_NUMBER: _ClassVar[int]
    data: bytes
    request_info: ConformancePayload.RequestInfo
    def __init__(self, data: _Optional[bytes] = ..., request_info: _Optional[_Union[ConformancePayload.RequestInfo, _Mapping]] = ...) -> None: ...

class Error(_message.Message):
    __slots__ = ("code", "message", "details")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    code: _config_pb2.Code
    message: str
    details: _containers.RepeatedCompositeFieldContainer[_any_pb2.Any]
    def __init__(self, code: _Optional[_Union[_config_pb2.Code, str]] = ..., message: _Optional[str] = ..., details: _Optional[_Iterable[_Union[_any_pb2.Any, _Mapping]]] = ...) -> None: ...

class Header(_message.Message):
    __slots__ = ("name", "value")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, name: _Optional[str] = ..., value: _Optional[_Iterable[str]] = ...) -> None: ...

class RawHTTPRequest(_message.Message):
    __slots__ = ("verb", "uri", "headers", "raw_query_params", "encoded_query_params", "unary", "stream")
    class EncodedQueryParam(_message.Message):
        __slots__ = ("name", "value", "base64_encode")
        NAME_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        BASE64_ENCODE_FIELD_NUMBER: _ClassVar[int]
        name: str
        value: MessageContents
        base64_encode: bool
        def __init__(self, name: _Optional[str] = ..., value: _Optional[_Union[MessageContents, _Mapping]] = ..., base64_encode: bool = ...) -> None: ...
    VERB_FIELD_NUMBER: _ClassVar[int]
    URI_FIELD_NUMBER: _ClassVar[int]
    HEADERS_FIELD_NUMBER: _ClassVar[int]
    RAW_QUERY_PARAMS_FIELD_NUMBER: _ClassVar[int]
    ENCODED_QUERY_PARAMS_FIELD_NUMBER: _ClassVar[int]
    UNARY_FIELD_NUMBER: _ClassVar[int]
    STREAM_FIELD_NUMBER: _ClassVar[int]
    verb: str
    uri: str
    headers: _containers.RepeatedCompositeFieldContainer[Header]
    raw_query_params: _containers.RepeatedCompositeFieldContainer[Header]
    encoded_query_params: _containers.RepeatedCompositeFieldContainer[RawHTTPRequest.EncodedQueryParam]
    unary: MessageContents
    stream: StreamContents
    def __init__(self, verb: _Optional[str] = ..., uri: _Optional[str] = ..., headers: _Optional[_Iterable[_Union[Header, _Mapping]]] = ..., raw_query_params: _Optional[_Iterable[_Union[Header, _Mapping]]] = ..., encoded_query_params: _Optional[_Iterable[_Union[RawHTTPRequest.EncodedQueryParam, _Mapping]]] = ..., unary: _Optional[_Union[MessageContents, _Mapping]] = ..., stream: _Optional[_Union[StreamContents, _Mapping]] = ...) -> None: ...

class MessageContents(_message.Message):
    __slots__ = ("binary", "text", "binary_message", "compression")
    BINARY_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    BINARY_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    COMPRESSION_FIELD_NUMBER: _ClassVar[int]
    binary: bytes
    text: str
    binary_message: _any_pb2.Any
    compression: _config_pb2.Compression
    def __init__(self, binary: _Optional[bytes] = ..., text: _Optional[str] = ..., binary_message: _Optional[_Union[_any_pb2.Any, _Mapping]] = ..., compression: _Optional[_Union[_config_pb2.Compression, str]] = ...) -> None: ...

class StreamContents(_message.Message):
    __slots__ = ("items",)
    class StreamItem(_message.Message):
        __slots__ = ("flags", "length", "payload")
        FLAGS_FIELD_NUMBER: _ClassVar[int]
        LENGTH_FIELD_NUMBER: _ClassVar[int]
        PAYLOAD_FIELD_NUMBER: _ClassVar[int]
        flags: int
        length: int
        payload: MessageContents
        def __init__(self, flags: _Optional[int] = ..., length: _Optional[int] = ..., payload: _Optional[_Union[MessageContents, _Mapping]] = ...) -> None: ...
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[StreamContents.StreamItem]
    def __init__(self, items: _Optional[_Iterable[_Union[StreamContents.StreamItem, _Mapping]]] = ...) -> None: ...

class RawHTTPResponse(_message.Message):
    __slots__ = ("status_code", "headers", "unary", "stream", "trailers")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    HEADERS_FIELD_NUMBER: _ClassVar[int]
    UNARY_FIELD_NUMBER: _ClassVar[int]
    STREAM_FIELD_NUMBER: _ClassVar[int]
    TRAILERS_FIELD_NUMBER: _ClassVar[int]
    status_code: int
    headers: _containers.RepeatedCompositeFieldContainer[Header]
    unary: MessageContents
    stream: StreamContents
    trailers: _containers.RepeatedCompositeFieldContainer[Header]
    def __init__(self, status_code: _Optional[int] = ..., headers: _Optional[_Iterable[_Union[Header, _Mapping]]] = ..., unary: _Optional[_Union[MessageContents, _Mapping]] = ..., stream: _Optional[_Union[StreamContents, _Mapping]] = ..., trailers: _Optional[_Iterable[_Union[Header, _Mapping]]] = ...) -> None: ...
