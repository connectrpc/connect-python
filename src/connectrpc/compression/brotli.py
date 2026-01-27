from __future__ import annotations

__all__ = ["BrotliCompression"]

import brotli

from . import Compression


class BrotliCompression(Compression):
    """Compression implementation using Brotli."""

    def __init__(self, quality: int = 3) -> None:
        """Creates a new BrotliCompression.

        Args:
            quality: Compression quality to use.
        """
        self._quality = quality

    def name(self) -> str:
        return "br"

    def compress(self, data: bytes | bytearray | memoryview) -> bytes:
        return brotli.compress(data, quality=self._quality)

    def decompress(self, data: bytes | bytearray | memoryview) -> bytes:
        return brotli.decompress(data)
