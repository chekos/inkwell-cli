"""Cache for extraction results.

Provides file-based caching with TTL to avoid redundant LLM API calls.
"""

import hashlib
import logging
import time
from pathlib import Path
from typing import Any

import platformdirs

from inkwell.utils.cache import FileCache

logger = logging.getLogger(__name__)

__all__ = ["ExtractionCache"]


class ExtractionCache(FileCache[str]):
    """File-based cache for extraction results.

    Uses template version in cache key for automatic invalidation
    when templates change. Cache files stored in XDG cache directory.

    Inherits from FileCache[str] for all core cache operations.

    Example:
        >>> cache = ExtractionCache()
        >>> await cache.set(template, transcript, "extracted content")
        >>> result = await cache.get(template, transcript)
        'extracted content'
    """

    DEFAULT_TTL_DAYS = 30

    def __init__(self, cache_dir: Path | None = None, ttl_days: int = DEFAULT_TTL_DAYS) -> None:
        """Initialize cache.

        Args:
            cache_dir: Cache directory (defaults to XDG cache dir)
            ttl_days: Time-to-live in days (default: 30)
        """
        if cache_dir is None:
            cache_dir = Path(platformdirs.user_cache_dir("inkwell")) / "extractions"

        super().__init__(
            cache_dir=cache_dir,
            ttl_days=ttl_days,
            serializer=self._serialize_result,
            deserializer=self._deserialize_result,
            key_generator=self._make_key,
        )

        # Store ttl_seconds for compatibility with existing code
        self.ttl_seconds = ttl_days * 24 * 60 * 60

    def _make_key(self, template_name: str, template_version: str, transcript: str) -> str:
        """Generate cache key from template and transcript.

        Includes template version so cache is invalidated when template changes.

        Args:
            template_name: Template name
            template_version: Template version
            transcript: Transcript text

        Returns:
            Cache key (hex string)
        """
        # Include template name, version, and transcript hash
        # This ensures cache invalidation when template changes
        content = f"{template_name}:{template_version}:{transcript}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _serialize_result(self, result: str) -> dict[str, Any]:
        """Serialize extraction result to dict for JSON storage.

        Args:
            result: Extraction result string

        Returns:
            Dictionary with result and timestamp
        """
        return {
            "result": result,
            "timestamp": time.time(),
        }

    def _deserialize_result(self, data: dict[str, Any]) -> str:
        """Deserialize extraction result from stored data.

        Args:
            data: Dictionary with result data

        Returns:
            Extraction result string
        """
        return data["result"]

    # Convenience methods that match the original API
    async def get(self, template_name: str, template_version: str, transcript: str) -> str | None:
        """Get cached extraction result.

        Args:
            template_name: Template name
            template_version: Template version (for invalidation)
            transcript: Transcript text

        Returns:
            Cached result or None if not found/expired
        """
        cache_key = self._make_key(template_name, template_version, transcript)
        cache_file = self.cache_dir / f"{cache_key}.json"

        # Check for temp file existence (indicates active write)
        temp_file = cache_file.with_suffix(".tmp")
        if temp_file.exists():
            # Another process is writing, treat as cache miss
            logger.debug(f"Cache file {cache_file.name} is being written, treating as miss")
            return None

        # Additional validation for partial writes (ExtractionCache-specific)
        if cache_file.exists():
            try:
                import aiofiles

                async with aiofiles.open(cache_file) as f:
                    content = await f.read()

                # Verify JSON is complete (simple sanity check)
                if not content.strip().endswith("}"):
                    # Partial write detected, remove corrupt file
                    logger.warning(
                        f"Detected partial write in cache file {cache_file.name}, removing"
                    )
                    await self._delete_file(cache_file)
                    return None

            except OSError:
                # File system error
                return None

        return await super().get(template_name, template_version, transcript)

    async def set(
        self, template_name: str, template_version: str, transcript: str, result: str
    ) -> None:
        """Store extraction result in cache.

        Args:
            template_name: Template name
            template_version: Template version
            transcript: Transcript text
            result: Extraction result to cache
        """
        # Override serializer temporarily to include template metadata
        original_serializer = self.serializer

        def extended_serializer(result: str) -> dict[str, Any]:
            base_data = original_serializer(result)
            base_data.update(
                {
                    "template_name": template_name,
                    "template_version": template_version,
                }
            )
            return base_data

        self.serializer = extended_serializer

        try:
            await super().set(template_name, template_version, transcript, value=result)
        finally:
            # Restore original serializer
            self.serializer = original_serializer

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache stats (total_entries, total_size_mb, oldest_entry_age_days)
        """
        cache_files = list(self.cache_dir.glob("*.json"))
        total_entries = len(cache_files)

        if total_entries == 0:
            return {
                "total_entries": 0,
                "total_size_mb": 0.0,
                "oldest_entry_age_days": 0,
            }

        # Calculate total size in parallel
        import asyncio

        async def get_size(path: Path) -> int:
            stat_result = await asyncio.to_thread(path.stat)
            return stat_result.st_size

        sizes = await asyncio.gather(*[get_size(f) for f in cache_files])
        total_size = sum(sizes)
        total_size_mb = total_size / (1024 * 1024)

        # Find oldest entry in parallel
        import json

        import aiofiles

        async def get_timestamp(cache_file: Path) -> float:
            """Get timestamp from cache file, returns current time if error."""
            try:
                async with aiofiles.open(cache_file) as f:
                    content = await f.read()
                    data = json.loads(content)
                    return data["timestamp"]
            except (json.JSONDecodeError, KeyError, OSError):
                return time.time()

        timestamps = await asyncio.gather(*[get_timestamp(f) for f in cache_files])
        oldest_timestamp = min(timestamps) if timestamps else time.time()

        oldest_age_days = (time.time() - oldest_timestamp) / (24 * 60 * 60)

        return {
            "total_entries": total_entries,
            "total_size_mb": round(total_size_mb, 2),
            "oldest_entry_age_days": round(oldest_age_days, 1),
        }
