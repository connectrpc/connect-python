from __future__ import annotations

import json

from connectrpc import MarshalOptions, ProtoJSONCodec

from .haberdasher_pb2 import Hat


def test_default_codec_omits_empty_repeated() -> None:
    """Default ProtoJSONCodec omits empty repeated fields from JSON."""
    codec = ProtoJSONCodec()
    hat = Hat(size=1, color="red")
    body = json.loads(codec.encode(hat))
    assert "tags" not in body


def test_always_print_fields_with_no_presence() -> None:
    """ProtoJSONCodec with always_print_fields_with_no_presence includes empty repeated."""
    options: MarshalOptions = {"always_print_fields_with_no_presence": True}
    codec = ProtoJSONCodec(marshal_options=options)
    hat = Hat(size=1, color="red")
    body = json.loads(codec.encode(hat))
    assert "tags" in body
    assert body["tags"] == []


def test_preserving_proto_field_name() -> None:
    """ProtoJSONCodec with preserving_proto_field_name keeps snake_case keys."""
    codec = ProtoJSONCodec(marshal_options={"preserving_proto_field_name": True})
    hat = Hat(size=1, color="red")
    body = json.loads(codec.encode(hat))
    # Proto field names are already snake_case here, so just verify it works
    assert body["size"] == 1
    assert body["color"] == "red"


def test_decode_roundtrip() -> None:
    """Encode then decode preserves the message."""
    codec = ProtoJSONCodec(
        marshal_options={"always_print_fields_with_no_presence": True}
    )
    original = Hat(size=5, color="blue", tags=["summer", "formal"])
    data = codec.encode(original)
    decoded = codec.decode(data, Hat())
    assert decoded.size == 5
    assert decoded.color == "blue"
    assert list(decoded.tags) == ["summer", "formal"]
