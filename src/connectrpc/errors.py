from __future__ import annotations

__all__ = ["ConnectError"]


from typing import TYPE_CHECKING

from google.protobuf.any_pb2 import Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from google.protobuf.message import Message

    from .code import Code


class ConnectError(Exception):
    """An exception in a Connect RPC.

    If a server raises a ConnectError, the same exception content will be
    raised on the client as well. Errors surfacing on the client side such as
    timeouts will also be raised as a ConnectError with an appropriate
    code.
    """

    def __init__(
        self, code: Code, message: str, details: Iterable[Message] = ()
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
            [m if isinstance(m, Any) else pack_any(m) for m in details]
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
    def details(self) -> Sequence[Any]:
        return self._details


def pack_any(msg: Message) -> Any:
    any_msg = Any()
    any_msg.Pack(msg=msg, type_url_prefix="type.googleapis.com/")
    return any_msg
