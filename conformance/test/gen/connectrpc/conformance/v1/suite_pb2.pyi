from gen.connectrpc.conformance.v1 import client_compat_pb2 as _client_compat_pb2
from gen.connectrpc.conformance.v1 import config_pb2 as _config_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TestSuite(_message.Message):
    __slots__ = ("name", "mode", "test_cases", "relevant_protocols", "relevant_http_versions", "relevant_codecs", "relevant_compressions", "connect_version_mode", "relies_on_tls", "relies_on_tls_client_certs", "relies_on_connect_get", "relies_on_message_receive_limit")
    class TestMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TEST_MODE_UNSPECIFIED: _ClassVar[TestSuite.TestMode]
        TEST_MODE_CLIENT: _ClassVar[TestSuite.TestMode]
        TEST_MODE_SERVER: _ClassVar[TestSuite.TestMode]
    TEST_MODE_UNSPECIFIED: TestSuite.TestMode
    TEST_MODE_CLIENT: TestSuite.TestMode
    TEST_MODE_SERVER: TestSuite.TestMode
    class ConnectVersionMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        CONNECT_VERSION_MODE_UNSPECIFIED: _ClassVar[TestSuite.ConnectVersionMode]
        CONNECT_VERSION_MODE_REQUIRE: _ClassVar[TestSuite.ConnectVersionMode]
        CONNECT_VERSION_MODE_IGNORE: _ClassVar[TestSuite.ConnectVersionMode]
    CONNECT_VERSION_MODE_UNSPECIFIED: TestSuite.ConnectVersionMode
    CONNECT_VERSION_MODE_REQUIRE: TestSuite.ConnectVersionMode
    CONNECT_VERSION_MODE_IGNORE: TestSuite.ConnectVersionMode
    NAME_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    TEST_CASES_FIELD_NUMBER: _ClassVar[int]
    RELEVANT_PROTOCOLS_FIELD_NUMBER: _ClassVar[int]
    RELEVANT_HTTP_VERSIONS_FIELD_NUMBER: _ClassVar[int]
    RELEVANT_CODECS_FIELD_NUMBER: _ClassVar[int]
    RELEVANT_COMPRESSIONS_FIELD_NUMBER: _ClassVar[int]
    CONNECT_VERSION_MODE_FIELD_NUMBER: _ClassVar[int]
    RELIES_ON_TLS_FIELD_NUMBER: _ClassVar[int]
    RELIES_ON_TLS_CLIENT_CERTS_FIELD_NUMBER: _ClassVar[int]
    RELIES_ON_CONNECT_GET_FIELD_NUMBER: _ClassVar[int]
    RELIES_ON_MESSAGE_RECEIVE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    name: str
    mode: TestSuite.TestMode
    test_cases: _containers.RepeatedCompositeFieldContainer[TestCase]
    relevant_protocols: _containers.RepeatedScalarFieldContainer[_config_pb2.Protocol]
    relevant_http_versions: _containers.RepeatedScalarFieldContainer[_config_pb2.HTTPVersion]
    relevant_codecs: _containers.RepeatedScalarFieldContainer[_config_pb2.Codec]
    relevant_compressions: _containers.RepeatedScalarFieldContainer[_config_pb2.Compression]
    connect_version_mode: TestSuite.ConnectVersionMode
    relies_on_tls: bool
    relies_on_tls_client_certs: bool
    relies_on_connect_get: bool
    relies_on_message_receive_limit: bool
    def __init__(self, name: _Optional[str] = ..., mode: _Optional[_Union[TestSuite.TestMode, str]] = ..., test_cases: _Optional[_Iterable[_Union[TestCase, _Mapping]]] = ..., relevant_protocols: _Optional[_Iterable[_Union[_config_pb2.Protocol, str]]] = ..., relevant_http_versions: _Optional[_Iterable[_Union[_config_pb2.HTTPVersion, str]]] = ..., relevant_codecs: _Optional[_Iterable[_Union[_config_pb2.Codec, str]]] = ..., relevant_compressions: _Optional[_Iterable[_Union[_config_pb2.Compression, str]]] = ..., connect_version_mode: _Optional[_Union[TestSuite.ConnectVersionMode, str]] = ..., relies_on_tls: bool = ..., relies_on_tls_client_certs: bool = ..., relies_on_connect_get: bool = ..., relies_on_message_receive_limit: bool = ...) -> None: ...

class TestCase(_message.Message):
    __slots__ = ("request", "expand_requests", "expected_response", "other_allowed_error_codes")
    class ExpandedSize(_message.Message):
        __slots__ = ("size_relative_to_limit",)
        SIZE_RELATIVE_TO_LIMIT_FIELD_NUMBER: _ClassVar[int]
        size_relative_to_limit: int
        def __init__(self, size_relative_to_limit: _Optional[int] = ...) -> None: ...
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    EXPAND_REQUESTS_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    OTHER_ALLOWED_ERROR_CODES_FIELD_NUMBER: _ClassVar[int]
    request: _client_compat_pb2.ClientCompatRequest
    expand_requests: _containers.RepeatedCompositeFieldContainer[TestCase.ExpandedSize]
    expected_response: _client_compat_pb2.ClientResponseResult
    other_allowed_error_codes: _containers.RepeatedScalarFieldContainer[_config_pb2.Code]
    def __init__(self, request: _Optional[_Union[_client_compat_pb2.ClientCompatRequest, _Mapping]] = ..., expand_requests: _Optional[_Iterable[_Union[TestCase.ExpandedSize, _Mapping]]] = ..., expected_response: _Optional[_Union[_client_compat_pb2.ClientResponseResult, _Mapping]] = ..., other_allowed_error_codes: _Optional[_Iterable[_Union[_config_pb2.Code, str]]] = ...) -> None: ...
