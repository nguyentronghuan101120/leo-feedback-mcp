#!/usr/bin/env python3
"""Gzip compression config and static file cache strategy for Web UI."""

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompressionConfig:
    """Compression configuration."""

    minimum_size: int = 1000
    compression_level: int = 6

    static_cache_max_age: int = 0
    api_cache_max_age: int = 0

    compressible_types: list[str] = field(default_factory=list)
    exclude_paths: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Post-init setup."""
        if not self.compressible_types:
            self.compressible_types = [
                "text/html",
                "text/css",
                "text/javascript",
                "text/plain",
                "application/json",
                "application/javascript",
                "application/xml",
                "application/rss+xml",
                "application/atom+xml",
                "image/svg+xml",
            ]

        if not self.exclude_paths:
            self.exclude_paths = ["/ws", "/api/ws", "/health"]

    @classmethod
    def from_env(cls) -> "CompressionConfig":
        """Create config from environment variables."""
        return cls(
            minimum_size=int(os.getenv("MCP_GZIP_MIN_SIZE", "1000")),
            compression_level=int(os.getenv("MCP_GZIP_LEVEL", "6")),
            static_cache_max_age=int(os.getenv("MCP_STATIC_CACHE_AGE", "3600")),
            api_cache_max_age=int(os.getenv("MCP_API_CACHE_AGE", "0")),
        )

    def should_compress(self, content_type: str, content_length: int) -> bool:
        """Check if content should be compressed."""
        if content_length < self.minimum_size:
            return False

        if not content_type:
            return False

        for mime_type in self.compressible_types:
            if content_type.startswith(mime_type):
                return True

        return False

    def should_exclude_path(self, path: str) -> bool:
        """Check if path should be excluded from compression."""
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return True
        return False

    def get_cache_headers(self, path: str) -> dict[str, str]:
        """Get cache headers for path."""
        headers = {}

        if path.startswith("/static/"):
            headers["Cache-Control"] = f"public, max-age={self.static_cache_max_age}"
            headers["Expires"] = self._get_expires_header(self.static_cache_max_age)
        elif path.startswith("/api/") and self.api_cache_max_age > 0:
            headers["Cache-Control"] = f"public, max-age={self.api_cache_max_age}"
            headers["Expires"] = self._get_expires_header(self.api_cache_max_age)
        else:
            headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            headers["Pragma"] = "no-cache"
            headers["Expires"] = "0"

        return headers

    def _get_expires_header(self, max_age: int) -> str:
        """Generate Expires header."""
        from datetime import datetime, timedelta

        expires_time = datetime.utcnow() + timedelta(seconds=max_age)
        return expires_time.strftime("%a, %d %b %Y %H:%M:%S GMT")

    def get_compression_stats(self) -> dict[str, Any]:
        """Get compression stats."""
        return {
            "minimum_size": self.minimum_size,
            "compression_level": self.compression_level,
            "static_cache_max_age": self.static_cache_max_age,
            "compressible_types_count": len(self.compressible_types),
            "exclude_paths_count": len(self.exclude_paths),
            "compressible_types": self.compressible_types,
            "exclude_paths": self.exclude_paths,
        }


class CompressionManager:
    """Compression manager."""

    def __init__(self, config: CompressionConfig | None = None):
        self.config = config or CompressionConfig.from_env()
        self._stats = {
            "requests_total": 0,
            "requests_compressed": 0,
            "bytes_original": 0,
            "bytes_compressed": 0,
            "compression_ratio": 0.0,
        }

    def update_stats(
        self, original_size: int, compressed_size: int, was_compressed: bool
    ):
        """Update compression stats."""
        self._stats["requests_total"] += 1
        self._stats["bytes_original"] += original_size

        if was_compressed:
            self._stats["requests_compressed"] += 1
            self._stats["bytes_compressed"] += compressed_size
        else:
            self._stats["bytes_compressed"] += original_size

        if self._stats["bytes_original"] > 0:
            self._stats["compression_ratio"] = (
                1 - self._stats["bytes_compressed"] / self._stats["bytes_original"]
            ) * 100

    def get_stats(self) -> dict[str, Any]:
        """Get compression stats."""
        stats = self._stats.copy()
        stats["compression_percentage"] = (
            self._stats["requests_compressed"]
            / max(self._stats["requests_total"], 1)
            * 100
        )
        return stats

    def reset_stats(self):
        """Reset stats."""
        self._stats = {
            "requests_total": 0,
            "requests_compressed": 0,
            "bytes_original": 0,
            "bytes_compressed": 0,
            "compression_ratio": 0.0,
        }


_compression_manager: CompressionManager | None = None


def get_compression_manager() -> CompressionManager:
    """Get global compression manager instance."""
    global _compression_manager
    if _compression_manager is None:
        _compression_manager = CompressionManager()
    return _compression_manager
