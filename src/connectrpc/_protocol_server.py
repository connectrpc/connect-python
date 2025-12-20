from __future__ import annotations

from typing import TYPE_CHECKING

from ._protocol_connect import ConnectServerProtocol
from ._protocol_grpc import (
    GRPC_CONTENT_TYPE_DEFAULT,
    GRPC_CONTENT_TYPE_PREFIX,
    GRPCServerProtocol,
)

if TYPE_CHECKING:
    from ._protocol import ServerProtocol


def negotiate_server_protocol(content_type: str) -> ServerProtocol:
    if content_type == GRPC_CONTENT_TYPE_DEFAULT or content_type.startswith(
        GRPC_CONTENT_TYPE_PREFIX
    ):
        return GRPCServerProtocol()
    return ConnectServerProtocol()
