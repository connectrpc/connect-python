from __future__ import annotations

__all__ = ["ZstdCompression"]

import zstandard

from . import Compression


class ZstdCompression(Compression):
    """Compression implementation using Zstandard."""

    def __init__(self, level: int = 3) -> None:
        """Creates a new ZstdCompression.

        Args:
            level: Compression level to use.
        """
        self._level = level

    def name(self) -> str:
        return "zstd"

    def compress(self, data: bytes | bytearray | memoryview) -> bytes:
        return zstandard.ZstdCompressor(level=self._level).compress(data)

    def decompress(self, data: bytes | bytearray | memoryview) -> bytes:
        # Support clients sending frames without length by using
        # stream API.
        with zstandard.ZstdDecompressor().stream_reader(data) as reader:
            return reader.read()
