from __future__ import annotations

import gzip

from . import Compression


class GzipCompression(Compression):
    """Compression implementation using GZip."""

    def __init__(self, level: int = 6) -> None:
        """Creates a new GzipCompression.
        Args:
            level: Compression level to use.
        """
        self._level = level

    def name(self) -> str:
        return "gzip"

    def compress(self, data: bytes | bytearray | memoryview) -> bytes:
        return gzip.compress(data, compresslevel=self._level)

    def decompress(self, data: bytes | bytearray | memoryview) -> bytes:
        return gzip.decompress(data)
