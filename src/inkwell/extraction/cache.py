"""Cache for extraction results.

Provides file-based caching with TTL to avoid redundant LLM API calls.
"""

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import aiofiles
import platformdirs


class ExtractionCache:
    """File-based cache for extraction results.

    Uses template version in cache key for automatic invalidation
    when templates change. Cache files stored in XDG cache directory.

    Example:
        >>> cache = ExtractionCache()
        >>> cache.set(template, transcript, "extracted content")
        >>> result = cache.get(template, transcript)
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

        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_days * 24 * 60 * 60

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def get(self, template_name: str, template_version: str, transcript: str) -> str | None:
        """Get cached extraction result (async).

        Args:
            template_name: Template name
            template_version: Template version (for invalidation)
            transcript: Transcript text

        Returns:
            Cached result or None if not found/expired
        """
        cache_key = self._make_key(template_name, template_version, transcript)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            # Async file read
            async with aiofiles.open(cache_file, "r") as f:
                content = await f.read()
                data = json.loads(content)

            # Check TTL
            if time.time() - data["timestamp"] > self.ttl_seconds:
                # Expired, delete file asynchronously
                await self._delete_file(cache_file)
                return None

            return data["result"]

        except (json.JSONDecodeError, KeyError, OSError):
            # Corrupted cache file, delete it
            await self._delete_file(cache_file)
            return None

    async def set(self, template_name: str, template_version: str, transcript: str, result: str) -> None:
        """Store extraction result in cache (async).

        Args:
            template_name: Template name
            template_version: Template version
            transcript: Transcript text
            result: Extraction result to cache
        """
        cache_key = self._make_key(template_name, template_version, transcript)
        cache_file = self.cache_dir / f"{cache_key}.json"

        data = {
            "timestamp": time.time(),
            "template_name": template_name,
            "template_version": template_version,
            "result": result,
        }

        # Async file write with atomic replace
        temp_file = cache_file.with_suffix(".tmp")

        try:
            # Write to temp file
            async with aiofiles.open(temp_file, "w") as f:
                await f.write(json.dumps(data))

            # Atomic rename (still sync, but fast)
            await asyncio.to_thread(temp_file.replace, cache_file)

        except OSError:
            # Failed to write cache, clean up temp file if exists
            if temp_file.exists():
                await self._delete_file(temp_file)

    async def clear(self) -> int:
        """Clear all cached extractions (async).

        Returns:
            Number of cache files deleted
        """
        cache_files = list(self.cache_dir.glob("*.json"))

        # Delete files in parallel
        results = await asyncio.gather(
            *[self._delete_file(f) for f in cache_files], return_exceptions=True
        )

        # Count successful deletions (None means success, Exception means failure)
        count = sum(1 for r in results if r is None)
        return count

    async def clear_expired(self) -> int:
        """Clear expired cache entries (async).

        Returns:
            Number of expired entries deleted
        """
        current_time = time.time()
        cache_files = list(self.cache_dir.glob("*.json"))

        async def check_and_delete(cache_file: Path) -> bool:
            """Check if file is expired and delete if so. Returns True if deleted."""
            try:
                async with aiofiles.open(cache_file, "r") as f:
                    content = await f.read()
                    data = json.loads(content)

                if current_time - data["timestamp"] > self.ttl_seconds:
                    await self._delete_file(cache_file)
                    return True

            except (json.JSONDecodeError, KeyError, OSError):
                # Corrupted file, delete it
                await self._delete_file(cache_file)
                return True

            return False

        # Check and delete expired files in parallel
        results = await asyncio.gather(*[check_and_delete(f) for f in cache_files])

        # Count deletions
        count = sum(1 for deleted in results if deleted)
        return count

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics (async).

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
        async def get_size(path: Path) -> int:
            stat_result = await asyncio.to_thread(path.stat)
            return stat_result.st_size

        sizes = await asyncio.gather(*[get_size(f) for f in cache_files])
        total_size = sum(sizes)
        total_size_mb = total_size / (1024 * 1024)

        # Find oldest entry in parallel
        async def get_timestamp(cache_file: Path) -> float:
            """Get timestamp from cache file, returns current time if error."""
            try:
                async with aiofiles.open(cache_file, "r") as f:
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

    async def _delete_file(self, path: Path) -> None:
        """Delete file asynchronously.

        Args:
            path: Path to file to delete
        """
        try:
            # aiofiles doesn't have unlink, use thread pool
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except Exception:
            # Ignore deletion errors
            pass

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
