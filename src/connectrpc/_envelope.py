from __future__ import annotations

import json
import struct
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from ._client_shared import handle_response_trailers
from ._compression import Compression, IdentityCompression
from ._protocol import ConnectWireError
from .code import Code
from .errors import ConnectError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ._codec import Codec
    from .request import Headers

_RES = TypeVar("_RES")
_T = TypeVar("_T")


class EnvelopeReader(Generic[_RES]):
    _next_message_length: int | None

    def __init__(
        self,
        message_class: type[_RES],
        codec: Codec,
        compression: Compression,
        read_max_bytes: int | None,
    ) -> None:
        self._buffer = bytearray()
        self._message_class = message_class
        self._codec = codec
        self._compression = compression
        self._read_max_bytes = read_max_bytes

        self._next_message_length = None

    def feed(self, data: bytes) -> Iterator[_RES]:
        self._buffer.extend(data)
        return self._read_messages()

    def _read_messages(self) -> Iterator[_RES]:
        while self._buffer:
            if self._next_message_length is not None:
                if len(self._buffer) < self._next_message_length + 5:
                    return

                compressed = self._buffer[0] & 0b01 != 0
                end_stream = self._buffer[0] & 0b10 != 0

                message_data = self._buffer[5 : 5 + self._next_message_length]
                self._buffer = self._buffer[5 + self._next_message_length :]
                self._next_message_length = None
                if compressed:
                    if isinstance(self._compression, IdentityCompression):
                        raise ConnectError(
                            Code.INTERNAL,
                            "protocol error: sent compressed message without compression support",
                        )
                    message_data = self._compression.decompress(message_data)

                if (
                    self._read_max_bytes is not None
                    and len(message_data) > self._read_max_bytes
                ):
                    raise ConnectError(
                        Code.RESOURCE_EXHAUSTED,
                        f"message is larger than configured max {self._read_max_bytes}",
                    )

                if end_stream:
                    end_stream_message: dict = json.loads(message_data)
                    metadata = end_stream_message.get("metadata")
                    if metadata:
                        handle_response_trailers(metadata)
                    error = end_stream_message.get("error")
                    if error:
                        # Most likely a bug in the protocol, handling of unknown code is different for unary
                        # and streaming.
                        raise ConnectWireError.from_dict(
                            error, 500, Code.UNKNOWN
                        ).to_exception()
                    return

                res = self._message_class()
                self._codec.decode(message_data, res)
                yield res

            if len(self._buffer) < 5:
                return

            self._next_message_length = int.from_bytes(self._buffer[1:5], "big")


class EnvelopeWriter(Generic[_T]):
    def __init__(self, codec: Codec[_T, Any], compression: Compression | None) -> None:
        self._codec = codec
        self._compression = compression
        self._prefix = (
            0 if not compression or isinstance(compression, IdentityCompression) else 1
        )

    def write(self, message: _T) -> bytes:
        data = self._codec.encode(message)
        if self._compression:
            data = self._compression.compress(data)
        # This copies data into the final envelope, but it is still better than issuing
        # I/O multiple times for small prefix / length elements.
        return struct.pack(">BI", self._prefix, len(data)) + data

    def end(self, trailers: Headers, error: ConnectWireError | None) -> bytes:
        end_message = {}
        if trailers:
            metadata: dict[str, list[str]] = {}
            for key, value in trailers.allitems():
                metadata.setdefault(key, []).append(value)
            end_message["metadata"] = metadata
        if error:
            end_message["error"] = error.to_dict()
        data = json.dumps(end_message).encode()
        if self._compression:
            data = self._compression.compress(data)
        return struct.pack(">BI", self._prefix | 0b10, len(data)) + data
