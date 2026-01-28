from __future__ import annotations

from typing import TYPE_CHECKING

from connectrpc._compression import IdentityCompression
from connectrpc.compression.brotli import BrotliCompression
from connectrpc.compression.gzip import GzipCompression
from connectrpc.compression.zstd import ZstdCompression

if TYPE_CHECKING:
    from connectrpc.compression import Compression


def resolve_compression(encoding: str) -> Compression:
    match encoding:
        case "gzip":
            return GzipCompression()
        case "br":
            return BrotliCompression()
        case "zstd":
            return ZstdCompression()
        case "identity":
            return IdentityCompression()
        case _:
            msg = f"unknown encoding '{encoding}'"
            raise ValueError(msg)
