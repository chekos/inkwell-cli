"""Generic file-based cache with TTL and async operations.

Provides a reusable cache implementation that can be specialized for different data types.
"""

import asyncio
import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generic, TypeVar

import aiofiles

T = TypeVar("T")


class CacheError(Exception):
    """Raised when cache operations fail."""

    pass


class FileCache(Generic[T]):
    """Generic file-based cache with TTL and async operations.

    Type parameter T is the cached value type.

    This cache provides:
    - File-based persistence with atomic writes
    - TTL-based expiration
    - Async file operations for performance
    - Automatic cleanup of expired/corrupted entries
    - Cache statistics

    Example:
        >>> cache = FileCache[str](
        ...     cache_dir=Path("~/.cache/myapp"),
        ...     ttl_days=30,
        ...     serializer=lambda x: {"value": x},
        ...     deserializer=lambda d: d["value"],
        ... )
        >>> await cache.set("key1", value="test")
        >>> result = await cache.get("key1")
        >>> assert result == "test"

    Args:
        cache_dir: Directory to store cache files
        ttl_days: Time-to-live in days (default: 30)
        serializer: Function to serialize T to dict (for JSON storage)
        deserializer: Function to deserialize dict to T (from JSON storage)
        key_generator: Function to generate cache key from arguments
    """

    DEFAULT_TTL_DAYS = 30

    def __init__(
        self,
        cache_dir: Path,
        ttl_days: int = DEFAULT_TTL_DAYS,
        serializer: Callable[[T], dict[str, Any]] | None = None,
        deserializer: Callable[[dict[str, Any]], T] | None = None,
        key_generator: Callable[..., str] | None = None,
    ):
        """Initialize file cache.

        Args:
            cache_dir: Directory for cache storage
            ttl_days: Time-to-live in days (default: 30)
            serializer: Function to serialize T to dict (default: identity)
            deserializer: Function to deserialize dict to T (default: identity)
            key_generator: Function to generate cache key (default: SHA256 hash)
        """
        self.cache_dir = cache_dir
        self.ttl_days = ttl_days
        self.serializer = serializer or (lambda x: x if isinstance(x, dict) else {"value": x})
        self.deserializer = deserializer or (lambda d: d)
        self.key_generator = key_generator or self._default_key_generator

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _default_key_generator(self, *args: Any) -> str:
        """Generate SHA256 hash from arguments.

        Args:
            *args: Arguments to hash

        Returns:
            SHA256 hex digest
        """
        content = ":".join(str(arg) for arg in args)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _is_expired(self, cached_at: datetime) -> bool:
        """Check if cache entry is expired.

        Args:
            cached_at: When entry was cached

        Returns:
            True if expired, False otherwise
        """
        now = datetime.now(timezone.utc)
        age = now - cached_at
        return age > timedelta(days=self.ttl_days)

    async def get(self, *key_args: Any) -> T | None:
        """Get value from cache using provided key arguments.

        Args:
            *key_args: Arguments to generate cache key

        Returns:
            Cached value or None if not found/expired
        """
        key = self.key_generator(*key_args)
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            return None

        try:
            # Read cache file asynchronously
            async with aiofiles.open(cache_file) as f:
                content = await f.read()
                data = json.loads(content)

            # Check expiration
            cached_at = datetime.fromisoformat(data["cached_at"])
            if self._is_expired(cached_at):
                # Remove expired entry asynchronously
                await self._delete_file(cache_file)
                return None

            # Deserialize value
            value = self.deserializer(data["value"])
            return value

        except (json.JSONDecodeError, KeyError, ValueError):
            # Cache file is corrupted - remove it
            await self._delete_file(cache_file)
            return None

    async def set(self, *key_args: Any, value: T) -> None:
        """Save value to cache.

        Args:
            *key_args: Arguments to generate cache key
            value: Value to cache

        Raises:
            CacheError: If caching fails
        """
        key = self.key_generator(*key_args)
        cache_file = self.cache_dir / f"{key}.json"
        temp_file = cache_file.with_suffix(".tmp")

        try:
            # Prepare cache data
            data = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "value": self.serializer(value),
            }

            # Write atomically (write to temp file, then rename)
            async with aiofiles.open(temp_file, "w") as f:
                await f.write(json.dumps(data, indent=2))

            # Atomic rename (still sync, but fast)
            await asyncio.to_thread(temp_file.replace, cache_file)

        except (OSError, TypeError) as e:
            # Clean up temp file if it exists
            if temp_file.exists():
                await self._delete_file(temp_file)
            raise CacheError(f"Failed to cache value: {e}") from e

    async def delete(self, *key_args: Any) -> bool:
        """Delete value from cache.

        Args:
            *key_args: Arguments to generate cache key

        Returns:
            True if deleted, False if not found
        """
        key = self.key_generator(*key_args)
        cache_file = self.cache_dir / f"{key}.json"

        if cache_file.exists():
            await self._delete_file(cache_file)
            return True

        return False

    async def clear(self) -> int:
        """Clear all cached values.

        Returns:
            Number of cache entries deleted
        """
        cache_files = list(self.cache_dir.glob("*.json"))

        # Delete files in parallel
        results = await asyncio.gather(
            *[self._delete_file(f) for f in cache_files], return_exceptions=True
        )

        # Count successful deletions
        count = sum(1 for r in results if r is None)
        return count

    async def clear_expired(self) -> int:
        """Clear expired cache entries.

        Returns:
            Number of expired entries deleted
        """
        cache_files = list(self.cache_dir.glob("*.json"))

        async def check_and_delete(cache_file: Path) -> bool:
            """Check if file is expired and delete if so. Returns True if deleted."""
            try:
                async with aiofiles.open(cache_file) as f:
                    content = await f.read()
                    data = json.loads(content)

                cached_at = datetime.fromisoformat(data["cached_at"])
                if self._is_expired(cached_at):
                    await self._delete_file(cache_file)
                    return True

            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                # Corrupted file - remove it
                await self._delete_file(cache_file)
                return True

            return False

        # Check and delete expired files in parallel
        results = await asyncio.gather(*[check_and_delete(f) for f in cache_files])

        # Count deletions
        count = sum(1 for deleted in results if deleted)
        return count

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats (total, expired, valid, size_bytes, cache_dir)
        """
        cache_files = list(self.cache_dir.glob("*.json"))

        if not cache_files:
            return {
                "total": 0,
                "expired": 0,
                "valid": 0,
                "size_bytes": 0,
                "cache_dir": str(self.cache_dir),
            }

        async def analyze_file(cache_file: Path) -> dict[str, Any] | None:
            """Analyze a single cache file. Returns stats dict or None if error."""
            try:
                # Get size
                stat = await asyncio.to_thread(cache_file.stat)
                file_size = stat.st_size

                # Read content
                async with aiofiles.open(cache_file) as f:
                    content = await f.read()
                    data = json.loads(content)

                # Check expiration
                cached_at = datetime.fromisoformat(data["cached_at"])
                is_expired = self._is_expired(cached_at)

                return {
                    "size": file_size,
                    "expired": is_expired,
                }

            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                # Corrupted file
                return None

        # Analyze all files in parallel
        results = await asyncio.gather(*[analyze_file(f) for f in cache_files])

        # Aggregate results
        total = len(cache_files)
        expired = 0
        total_size = 0

        for result in results:
            if result:
                total_size += result["size"]
                if result["expired"]:
                    expired += 1

        return {
            "total": total,
            "expired": expired,
            "valid": total - expired,
            "size_bytes": total_size,
            "cache_dir": str(self.cache_dir),
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
