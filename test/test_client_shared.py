from __future__ import annotations

from urllib.parse import urlencode

from pyqwest import Headers as HTTPHeaders

from connectrpc._client_shared import prepare_get_params
from connectrpc.codec import proto_binary_codec


def test_prepare_get_params_order() -> None:
    headers = HTTPHeaders([("content-encoding", "gzip")])
    params = prepare_get_params(proto_binary_codec(), b"hello", headers)
    assert list(params.keys()) == [
        "connect",
        "base64",
        "compression",
        "encoding",
        "message",
    ]
    assert "content-encoding" not in headers
    query = urlencode(params)
    expected_prefix = "connect=v1&base64=1&compression=gzip&encoding=proto&message="
    assert query.startswith(expected_prefix)


def test_prepare_get_params_order_without_compression() -> None:
    params = prepare_get_params(proto_binary_codec(), b"hello", HTTPHeaders([]))
    assert list(params.keys()) == ["connect", "base64", "encoding", "message"]
