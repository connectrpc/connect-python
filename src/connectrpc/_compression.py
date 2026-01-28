from __future__ import annotations

from typing import TYPE_CHECKING

from connectrpc.compression.gzip import GzipCompression

from .compression import Compression

if TYPE_CHECKING:
    from collections.abc import Sequence


class IdentityCompression(Compression):
    def name(self) -> str:
        return "identity"

    def compress(self, data: bytes | bytearray | memoryview) -> bytes:
        """Return data as-is without compression."""
        return bytes(data)

    def decompress(self, data: bytes | bytearray | memoryview) -> bytes:
        """Return data as-is without decompression."""
        return bytes(data)


_identity = IdentityCompression()

_gzip = GzipCompression()
_default_compressions = {"gzip": _gzip, "identity": _identity}


def resolve_compressions(
    compressions: Sequence[Compression] | None,
) -> dict[str, Compression]:
    if compressions is None:
        return _default_compressions
    res = {comp.name(): comp for comp in compressions}
    # identity is always supported
    res["identity"] = _identity
    return res


def negotiate_compression(
    accept_encoding: str, compressions: dict[str, Compression]
) -> Compression:
    for accept in accept_encoding.split(","):
        compression = compressions.get(accept.strip())
        if compression:
            return compression
    return _identity
