from __future__ import annotations

from typing import NoReturn

import pytest
from google.protobuf.any_pb2 import Any as AnyPb
from google.protobuf.duration_pb2 import Duration
from google.protobuf.struct_pb2 import Struct, Value
from pyqwest import Client, SyncClient
from pyqwest.testing import ASGITransport, WSGITransport

from connectrpc._protocol import ConnectWireError
from connectrpc.code import Code
from connectrpc.errors import ConnectError, pack_any

from .haberdasher_connect import (
    Haberdasher,
    HaberdasherASGIApplication,
    HaberdasherClient,
    HaberdasherClientSync,
    HaberdasherSync,
    HaberdasherWSGIApplication,
)
from .haberdasher_pb2 import Size


def test_details_sync() -> None:
    class DetailsHaberdasherSync(HaberdasherSync):
        def make_hat(self, request, ctx) -> NoReturn:
            raise ConnectError(
                Code.RESOURCE_EXHAUSTED,
                "Resource exhausted",
                details=[
                    Struct(fields={"animal": Value(string_value="bear")}),
                    pack_any(Struct(fields={"color": Value(string_value="red")})),
                ],
            )

    app = HaberdasherWSGIApplication(DetailsHaberdasherSync())
    with (
        HaberdasherClientSync(
            "http://localhost", http_client=SyncClient(transport=WSGITransport(app=app))
        ) as client,
        pytest.raises(ConnectError) as exc_info,
    ):
        client.make_hat(request=Size(inches=10))
    assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
    assert exc_info.value.message == "Resource exhausted"
    assert len(exc_info.value.details) == 2
    s0 = Struct()
    assert exc_info.value.details[0].Unpack(s0)
    assert s0.fields["animal"].string_value == "bear"
    s1 = Struct()
    assert exc_info.value.details[1].Unpack(s1)
    assert s1.fields["color"].string_value == "red"


@pytest.mark.asyncio
async def test_details_async() -> None:
    class DetailsHaberdasher(Haberdasher):
        async def make_hat(self, request, ctx) -> NoReturn:
            raise ConnectError(
                Code.RESOURCE_EXHAUSTED,
                "Resource exhausted",
                details=[
                    Struct(fields={"animal": Value(string_value="bear")}),
                    pack_any(Struct(fields={"color": Value(string_value="red")})),
                ],
            )

    app = HaberdasherASGIApplication(DetailsHaberdasher())
    transport = ASGITransport(app)
    async with HaberdasherClient(
        "http://localhost", http_client=Client(transport=transport)
    ) as client:
        with pytest.raises(ConnectError) as exc_info:
            await client.make_hat(request=Size(inches=10))
    assert exc_info.value.code == Code.RESOURCE_EXHAUSTED
    assert exc_info.value.message == "Resource exhausted"
    assert len(exc_info.value.details) == 2
    s0 = Struct()
    assert exc_info.value.details[0].Unpack(s0)
    assert s0.fields["animal"].string_value == "bear"
    s1 = Struct()
    assert exc_info.value.details[1].Unpack(s1)
    assert s1.fields["color"].string_value == "red"


def test_error_detail_debug_field() -> None:
    """Debug field is populated when proto descriptors are available."""
    wire_error = ConnectWireError.from_exception(
        ConnectError(
            Code.RESOURCE_EXHAUSTED,
            "Resource exhausted",
            details=[Struct(fields={"animal": Value(string_value="bear")})],
        )
    )
    data = wire_error.to_dict()
    assert len(data["details"]) == 1
    detail = data["details"][0]
    assert "debug" in detail
    # Struct uses proto-JSON well-known type mapping: becomes a plain JSON object
    assert detail["debug"] == {"animal": "bear"}


def test_error_detail_debug_field_well_known_type() -> None:
    """Debug field uses proto-JSON well-known type representation (e.g. Duration as string)."""
    wire_error = ConnectWireError.from_exception(
        ConnectError(
            Code.RESOURCE_EXHAUSTED, "Resource exhausted", details=[Duration(seconds=1)]
        )
    )
    data = wire_error.to_dict()
    assert len(data["details"]) == 1
    detail = data["details"][0]
    assert "debug" in detail
    # Duration uses proto-JSON well-known type mapping: serializes as "1s"
    assert detail["debug"] == "1s"


def test_error_detail_debug_field_absent_for_unknown_type() -> None:
    """Debug field is omitted when no descriptor is available for the type."""
    unknown_detail = AnyPb(
        type_url="type.googleapis.com/completely.Unknown.Message", value=b"\x08\x01"
    )
    wire_error = ConnectWireError(
        code=Code.INTERNAL, message="test", details=[unknown_detail]
    )
    data = wire_error.to_dict()
    assert len(data["details"]) == 1
    detail = data["details"][0]
    assert "debug" not in detail
