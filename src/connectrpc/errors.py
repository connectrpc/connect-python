from __future__ import annotations

__all__ = ["ConnectError", "ErrorDetail"]


from typing import TYPE_CHECKING, TypeVar, overload

from google.protobuf import symbol_database
from google.protobuf.any_pb2 import Any
from google.protobuf.message import Message

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from .code import Code

T = TypeVar("T", bound=Message)


class ErrorDetail:
    """A self-describing Protobuf message attached to a [ConnectError][].

    Error details are sent over the network to clients, which can then work with
    strongly-typed data rather than trying to parse a complex error message. For
    example, you might use details to send a localized error message or retry
    parameters to a client.
    """

    def __init__(self, message: Message) -> None:
        if isinstance(message, Any):
            self._message = None
            self._any = message
            return
        self._message = message
        self._any = pack_any(message)

    @property
    def type_name(self) -> str:
        """The fully-qualified name of the details Protobuf message (for example, acme.foo.v1.FooDetail)."""
        return self._any.type_url.removeprefix("type.googleapis.com/")

    @property
    def message_bytes(self) -> bytes:
        """The Protobuf message serialized as bytes."""
        return self._any.value

    @overload
    def value(self) -> Message | None: ...

    @overload
    def value(self, typ: type[T], /) -> T | None: ...

    def value(self, desc: type[Message] | None = None) -> Message | None:
        """The details message as a Protobuf message, or None if it cannot be deserialized."""
        if self._message:
            return self._message
        if isinstance(desc, type):
            msg = desc()
            if self._any.Unpack(msg):
                return msg
            return None
        try:
            detail_type = self._any.type_url.removeprefix("type.googleapis.com/")
            msg_instance = symbol_database.Default().GetSymbol(detail_type)()
            if self._any.Unpack(msg_instance):
                return msg_instance
            return None
        except Exception:
            return None


class ConnectError(Exception):
    """An exception in a Connect RPC.

    If a server raises a ConnectError, the same exception content will be
    raised on the client as well. Errors surfacing on the client side such as
    timeouts will also be raised as a ConnectError with an appropriate
    [Code][].
    """

    def __init__(
        self, code: Code, message: str, details: Iterable[Message | ErrorDetail] = ()
    ) -> None:
        """
        Creates a new Connect error.

        Args:
            code: The error code.
            message: The error message.
            details: Additional details about the error.
        """
        super().__init__(message)
        self._code = code
        self._message = message

        self._details = (
            [m if isinstance(m, ErrorDetail) else ErrorDetail(m) for m in details]
            if details
            else ()
        )

    @property
    def code(self) -> Code:
        return self._code

    @property
    def message(self) -> str:
        return self._message

    @property
    def details(self) -> Sequence[ErrorDetail]:
        return self._details


def pack_any(msg: Message) -> Any:
    any_msg = Any()
    any_msg.Pack(msg=msg, type_url_prefix="type.googleapis.com/")
    return any_msg
