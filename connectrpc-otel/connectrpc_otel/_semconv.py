# Vendored in OpenTelemetry semantic conventions for connect-python to avoid
# unstable imports. We don't copy docstrings since for us they are implementation
# details and should be obvious enough.

# https://github.com/open-telemetry/opentelemetry-python/blob/main/opentelemetry-semantic-conventions/src/opentelemetry/semconv/_incubating/attributes/rpc_attributes.py
from __future__ import annotations

from enum import Enum
from typing import Final

CLIENT_ADDRESS: Final = "client.address"
CLIENT_PORT: Final = "client.port"
ERROR_TYPE: Final = "error.type"
RPC_METHOD: Final = "rpc.method"
RPC_RESPONSE_STATUS_CODE: Final = "rpc.response.status_code"
RPC_SYSTEM_NAME: Final = "rpc.system.name"
SERVER_ADDRESS: Final = "server.address"
SERVER_PORT: Final = "server.port"


class RpcSystemNameValues(Enum):
    CONNECTRPC = "connectrpc"
