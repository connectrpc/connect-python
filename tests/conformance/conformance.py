import asyncio
import struct
import sys
import traceback

# Imported for their side effects of loading protobuf registry
import google.protobuf.descriptor_pb2  # noqa: F401
import urllib3
import urllib3.exceptions
from google.protobuf.any_pb2 import Any as ProtoAny
from google.protobuf.symbol_database import Default as DefaultSymbolDatabase
from multidict import MultiDict

from connectrpc.client_connect import UnexpectedContentType
from connectrpc.conformance.v1.config_pb2 import Code
from connectrpc.conformance.v1.service_pb2 import Error
from connectrpc.conformance.v1.service_pb2 import Header
from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode


def proto_to_exception(proto_error: Error) -> ConnectError:
    code = {
        Code.CODE_CANCELED: ConnectErrorCode.CANCELED,
        Code.CODE_UNKNOWN: ConnectErrorCode.UNKNOWN,
        Code.CODE_INVALID_ARGUMENT: ConnectErrorCode.INVALID_ARGUMENT,
        Code.CODE_DEADLINE_EXCEEDED: ConnectErrorCode.DEADLINE_EXCEEDED,
        Code.CODE_NOT_FOUND: ConnectErrorCode.NOT_FOUND,
        Code.CODE_ALREADY_EXISTS: ConnectErrorCode.ALREADY_EXISTS,
        Code.CODE_PERMISSION_DENIED: ConnectErrorCode.PERMISSION_DENIED,
        Code.CODE_RESOURCE_EXHAUSTED: ConnectErrorCode.RESOURCE_EXHAUSTED,
        Code.CODE_FAILED_PRECONDITION: ConnectErrorCode.FAILED_PRECONDITION,
        Code.CODE_ABORTED: ConnectErrorCode.ABORTED,
        Code.CODE_OUT_OF_RANGE: ConnectErrorCode.OUT_OF_RANGE,
        Code.CODE_UNIMPLEMENTED: ConnectErrorCode.UNIMPLEMENTED,
        Code.CODE_INTERNAL: ConnectErrorCode.INTERNAL,
        Code.CODE_UNAVAILABLE: ConnectErrorCode.UNAVAILABLE,
        Code.CODE_DATA_LOSS: ConnectErrorCode.DATA_LOSS,
        Code.CODE_UNAUTHENTICATED: ConnectErrorCode.UNAUTHENTICATED,
    }[proto_error.code]
    connect_err = ConnectError(code, proto_error.message)
    for d in proto_error.details:
        d_type = DefaultSymbolDatabase().GetSymbol(d.type_url)
        d_value = d_type()
        d.Unpack(d_value)
        connect_err.add_detail(d_value)
    return connect_err


def exception_to_proto(error: Exception) -> Error:
    if isinstance(error, TimeoutError):
        error = ConnectError(ConnectErrorCode.DEADLINE_EXCEEDED, str(error))
    if isinstance(error, urllib3.exceptions.TimeoutError):
        error = ConnectError(ConnectErrorCode.DEADLINE_EXCEEDED, str(error))
    if isinstance(error, asyncio.TimeoutError):
        error = ConnectError(ConnectErrorCode.DEADLINE_EXCEEDED, str(error))

    if isinstance(error, UnexpectedContentType):
        if error.content_type_received.startswith("application"):
            # Fairly silly, but the test suite treats this differently
            error = ConnectError(ConnectErrorCode.INTERNAL, str(error))
        else:
            error = ConnectError(ConnectErrorCode.UNKNOWN, str(error))

    if not isinstance(error, ConnectError):
        tb = traceback.format_tb(error.__traceback__)
        error = ConnectError(ConnectErrorCode.INTERNAL, str(tb))

    details: list[ProtoAny] = []
    if isinstance(error.details, list):
        for d in error.details:
            v = ProtoAny()
            v.Pack(d.message())
            details.append(v)

    code = {
        ConnectErrorCode.CANCELED: Code.CODE_CANCELED,
        ConnectErrorCode.UNKNOWN: Code.CODE_UNKNOWN,
        ConnectErrorCode.INVALID_ARGUMENT: Code.CODE_INVALID_ARGUMENT,
        ConnectErrorCode.DEADLINE_EXCEEDED: Code.CODE_DEADLINE_EXCEEDED,
        ConnectErrorCode.NOT_FOUND: Code.CODE_NOT_FOUND,
        ConnectErrorCode.ALREADY_EXISTS: Code.CODE_ALREADY_EXISTS,
        ConnectErrorCode.PERMISSION_DENIED: Code.CODE_PERMISSION_DENIED,
        ConnectErrorCode.RESOURCE_EXHAUSTED: Code.CODE_RESOURCE_EXHAUSTED,
        ConnectErrorCode.FAILED_PRECONDITION: Code.CODE_FAILED_PRECONDITION,
        ConnectErrorCode.ABORTED: Code.CODE_ABORTED,
        ConnectErrorCode.OUT_OF_RANGE: Code.CODE_OUT_OF_RANGE,
        ConnectErrorCode.UNIMPLEMENTED: Code.CODE_UNIMPLEMENTED,
        ConnectErrorCode.INTERNAL: Code.CODE_INTERNAL,
        ConnectErrorCode.UNAVAILABLE: Code.CODE_UNAVAILABLE,
        ConnectErrorCode.DATA_LOSS: Code.CODE_DATA_LOSS,
        ConnectErrorCode.UNAUTHENTICATED: Code.CODE_UNAUTHENTICATED,
    }[error.code]

    return Error(code=code, message=error.message, details=details)


def read_size_delimited_message() -> bytes | None:
    """Read a size-delimited protobuf message from stdin."""
    # Read 4-byte big-endian length prefix
    length_bytes = sys.stdin.buffer.read(4)
    if len(length_bytes) < 4:
        return None  # EOF

    # Unpack big-endian 32-bit integer
    message_length = struct.unpack(">I", length_bytes)[0]

    # Read the actual message
    message_bytes = sys.stdin.buffer.read(message_length)
    if len(message_bytes) < message_length:
        raise ValueError("Incomplete message")

    return message_bytes


def write_size_delimited_message(message_bytes: bytes) -> None:
    """Write a size-delimited protobuf message to stdout."""
    # Write 4-byte big-endian length prefix
    length = len(message_bytes)
    sys.stdout.buffer.write(struct.pack(">I", length))

    # Write the actual message
    sys.stdout.buffer.write(message_bytes)
    sys.stdout.buffer.flush()


def multidict_to_proto(headers: MultiDict[str]) -> list[Header]:
    result = []
    for k in headers:
        result.append(Header(name=k, value=headers.getall(k)))
    return result
