from gen.connectrpc.conformance.v1 import config_pb2 as _config_pb2
from gen.connectrpc.conformance.v1 import service_pb2 as _service_pb2
from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ClientCompatRequest(_message.Message):
    __slots__ = ("test_name", "http_version", "protocol", "codec", "compression", "host", "port", "server_tls_cert", "client_tls_creds", "message_receive_limit", "service", "method", "stream_type", "use_get_http_method", "request_headers", "request_messages", "timeout_ms", "request_delay_ms", "cancel", "raw_request")
    class Cancel(_message.Message):
        __slots__ = ("before_close_send", "after_close_send_ms", "after_num_responses")
        BEFORE_CLOSE_SEND_FIELD_NUMBER: _ClassVar[int]
        AFTER_CLOSE_SEND_MS_FIELD_NUMBER: _ClassVar[int]
        AFTER_NUM_RESPONSES_FIELD_NUMBER: _ClassVar[int]
        before_close_send: _empty_pb2.Empty
        after_close_send_ms: int
        after_num_responses: int
        def __init__(self, before_close_send: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ..., after_close_send_ms: _Optional[int] = ..., after_num_responses: _Optional[int] = ...) -> None: ...
    TEST_NAME_FIELD_NUMBER: _ClassVar[int]
    HTTP_VERSION_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    CODEC_FIELD_NUMBER: _ClassVar[int]
    COMPRESSION_FIELD_NUMBER: _ClassVar[int]
    HOST_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    SERVER_TLS_CERT_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TLS_CREDS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_RECEIVE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    METHOD_FIELD_NUMBER: _ClassVar[int]
    STREAM_TYPE_FIELD_NUMBER: _ClassVar[int]
    USE_GET_HTTP_METHOD_FIELD_NUMBER: _ClassVar[int]
    REQUEST_HEADERS_FIELD_NUMBER: _ClassVar[int]
    REQUEST_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_MS_FIELD_NUMBER: _ClassVar[int]
    REQUEST_DELAY_MS_FIELD_NUMBER: _ClassVar[int]
    CANCEL_FIELD_NUMBER: _ClassVar[int]
    RAW_REQUEST_FIELD_NUMBER: _ClassVar[int]
    test_name: str
    http_version: _config_pb2.HTTPVersion
    protocol: _config_pb2.Protocol
    codec: _config_pb2.Codec
    compression: _config_pb2.Compression
    host: str
    port: int
    server_tls_cert: bytes
    client_tls_creds: _config_pb2.TLSCreds
    message_receive_limit: int
    service: str
    method: str
    stream_type: _config_pb2.StreamType
    use_get_http_method: bool
    request_headers: _containers.RepeatedCompositeFieldContainer[_service_pb2.Header]
    request_messages: _containers.RepeatedCompositeFieldContainer[_any_pb2.Any]
    timeout_ms: int
    request_delay_ms: int
    cancel: ClientCompatRequest.Cancel
    raw_request: _service_pb2.RawHTTPRequest
    def __init__(self, test_name: _Optional[str] = ..., http_version: _Optional[_Union[_config_pb2.HTTPVersion, str]] = ..., protocol: _Optional[_Union[_config_pb2.Protocol, str]] = ..., codec: _Optional[_Union[_config_pb2.Codec, str]] = ..., compression: _Optional[_Union[_config_pb2.Compression, str]] = ..., host: _Optional[str] = ..., port: _Optional[int] = ..., server_tls_cert: _Optional[bytes] = ..., client_tls_creds: _Optional[_Union[_config_pb2.TLSCreds, _Mapping]] = ..., message_receive_limit: _Optional[int] = ..., service: _Optional[str] = ..., method: _Optional[str] = ..., stream_type: _Optional[_Union[_config_pb2.StreamType, str]] = ..., use_get_http_method: bool = ..., request_headers: _Optional[_Iterable[_Union[_service_pb2.Header, _Mapping]]] = ..., request_messages: _Optional[_Iterable[_Union[_any_pb2.Any, _Mapping]]] = ..., timeout_ms: _Optional[int] = ..., request_delay_ms: _Optional[int] = ..., cancel: _Optional[_Union[ClientCompatRequest.Cancel, _Mapping]] = ..., raw_request: _Optional[_Union[_service_pb2.RawHTTPRequest, _Mapping]] = ...) -> None: ...

class ClientCompatResponse(_message.Message):
    __slots__ = ("test_name", "response", "error")
    TEST_NAME_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    test_name: str
    response: ClientResponseResult
    error: ClientErrorResult
    def __init__(self, test_name: _Optional[str] = ..., response: _Optional[_Union[ClientResponseResult, _Mapping]] = ..., error: _Optional[_Union[ClientErrorResult, _Mapping]] = ...) -> None: ...

class ClientResponseResult(_message.Message):
    __slots__ = ("response_headers", "payloads", "error", "response_trailers", "num_unsent_requests", "http_status_code", "feedback")
    RESPONSE_HEADERS_FIELD_NUMBER: _ClassVar[int]
    PAYLOADS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_TRAILERS_FIELD_NUMBER: _ClassVar[int]
    NUM_UNSENT_REQUESTS_FIELD_NUMBER: _ClassVar[int]
    HTTP_STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    FEEDBACK_FIELD_NUMBER: _ClassVar[int]
    response_headers: _containers.RepeatedCompositeFieldContainer[_service_pb2.Header]
    payloads: _containers.RepeatedCompositeFieldContainer[_service_pb2.ConformancePayload]
    error: _service_pb2.Error
    response_trailers: _containers.RepeatedCompositeFieldContainer[_service_pb2.Header]
    num_unsent_requests: int
    http_status_code: int
    feedback: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, response_headers: _Optional[_Iterable[_Union[_service_pb2.Header, _Mapping]]] = ..., payloads: _Optional[_Iterable[_Union[_service_pb2.ConformancePayload, _Mapping]]] = ..., error: _Optional[_Union[_service_pb2.Error, _Mapping]] = ..., response_trailers: _Optional[_Iterable[_Union[_service_pb2.Header, _Mapping]]] = ..., num_unsent_requests: _Optional[int] = ..., http_status_code: _Optional[int] = ..., feedback: _Optional[_Iterable[str]] = ...) -> None: ...

class ClientErrorResult(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class WireDetails(_message.Message):
    __slots__ = ("actual_status_code", "connect_error_raw", "actual_http_trailers", "actual_grpcweb_trailers")
    ACTUAL_STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    CONNECT_ERROR_RAW_FIELD_NUMBER: _ClassVar[int]
    ACTUAL_HTTP_TRAILERS_FIELD_NUMBER: _ClassVar[int]
    ACTUAL_GRPCWEB_TRAILERS_FIELD_NUMBER: _ClassVar[int]
    actual_status_code: int
    connect_error_raw: _struct_pb2.Struct
    actual_http_trailers: _containers.RepeatedCompositeFieldContainer[_service_pb2.Header]
    actual_grpcweb_trailers: str
    def __init__(self, actual_status_code: _Optional[int] = ..., connect_error_raw: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., actual_http_trailers: _Optional[_Iterable[_Union[_service_pb2.Header, _Mapping]]] = ..., actual_grpcweb_trailers: _Optional[str] = ...) -> None: ...
