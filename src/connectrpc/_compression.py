from __future__ import annotations

import gzip
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import KeysView


class Compression(Protocol):
    def name(self) -> str:
        """Returns the name of the compression method."""
        ...

    def compress(self, data: bytes | bytearray) -> bytes:
        """Compress the given data."""
        ...

    def decompress(self, data: bytes | bytearray) -> bytes:
        """Decompress the given data."""
        ...


_compressions: dict[str, Compression] = {}


class GZipCompression(Compression):
    def name(self) -> str:
        return "gzip"

    def compress(self, data: bytes | bytearray) -> bytes:
        return gzip.compress(data)

    def decompress(self, data: bytes | bytearray) -> bytes:
        return gzip.decompress(data)


_compressions["gzip"] = GZipCompression()

try:
    import brotli

    class BrotliCompression(Compression):
        def name(self) -> str:
            return "br"

        def compress(self, data: bytes | bytearray) -> bytes:
            return brotli.compress(data)

        def decompress(self, data: bytes | bytearray) -> bytes:
            return brotli.decompress(data)

    _compressions["br"] = BrotliCompression()
except ImportError:
    pass

try:
    import zstandard

    class ZstdCompression(Compression):
        def name(self) -> str:
            return "zstd"

        def compress(self, data: bytes | bytearray) -> bytes:
            return zstandard.ZstdCompressor().compress(data)

        def decompress(self, data: bytes | bytearray) -> bytes:
            # Support clients sending frames without length by using
            # stream API.
            with zstandard.ZstdDecompressor().stream_reader(data) as reader:
                return reader.read()

    _compressions["zstd"] = ZstdCompression()
except ImportError:
    pass


class IdentityCompression(Compression):
    def name(self) -> str:
        return "identity"

    def compress(self, data: bytes | bytearray) -> bytes:
        """Return data as-is without compression."""
        return bytes(data)

    def decompress(self, data: bytes | bytearray) -> bytes:
        """Return data as-is without decompression."""
        return bytes(data)


_identity = IdentityCompression()
_compressions["identity"] = _identity


def get_compression(name: str) -> Compression | None:
    return _compressions.get(name.lower())


def get_available_compressions() -> KeysView:
    """Returns a list of available compression names."""
    return _compressions.keys()


def negotiate_compression(accept_encoding: str) -> Compression:
    for accept in accept_encoding.split(","):
        compression = _compressions.get(accept.strip())
        if compression:
            return compression
    return _identity
