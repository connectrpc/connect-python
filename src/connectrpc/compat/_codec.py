from __future__ import annotations

from typing import TypeVar

from google.protobuf.json_format import MessageToJson
from google.protobuf.json_format import Parse as MessageFromJson
from google.protobuf.message import Message

from connectrpc.codec import Codec

CODEC_NAME_PROTO = "proto"
CODEC_NAME_JSON = "json"


T_contra = TypeVar("T_contra", contravariant=True)
U = TypeVar("U")
V = TypeVar("V", bound=Message)


class ProtoBinaryCodec(Codec[Message, V]):
    """Codec for Protocol bytes | bytearrays binary format."""

    def name(self) -> str:
        return "proto"

    def encode(self, message: Message) -> bytes:
        return message.SerializeToString()

    def decode(self, data: bytes | bytearray, message: V) -> V:
        message.ParseFromString(data)  # ty:ignore[invalid-argument-type] type is incorrect
        return message


class ProtoJSONCodec(Codec[Message, V]):
    """Codec for Protocol bytes | bytearrays JSON format."""

    def __init__(self, name: str = "json") -> None:
        self._name = name

    def name(self) -> str:
        return self._name

    def encode(self, message: Message) -> bytes:
        return MessageToJson(message).encode()

    def decode(self, data: bytes | bytearray, message: V) -> V:
        MessageFromJson(data, message)  # ty:ignore[invalid-argument-type] type is incorrect
        return message


_proto_binary_codec = ProtoBinaryCodec()
_proto_json_codec = ProtoJSONCodec()
_default_codecs: list[Codec] = [_proto_binary_codec, _proto_json_codec]


def google_protobuf_codecs() -> list[Codec]:
    """Returns the codecs for marshaling Protocol Buffers using google.protobuf."""
    return _default_codecs


def google_protobuf_binary_codec() -> Codec:
    """Returns the Protocol Buffers binary codec using google.protobuf."""
    return _proto_binary_codec


def google_protobuf_json_codec() -> Codec:
    """Returns the Protocol Buffers JSON codec using google.protobuf."""
    return _proto_json_codec
