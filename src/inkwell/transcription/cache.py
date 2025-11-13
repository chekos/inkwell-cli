"""Transcript caching layer."""

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiofiles
from platformdirs import user_cache_dir

from inkwell.transcription.models import Transcript


class CacheError(Exception):
    """Raised when cache operations fail."""

    pass


class TranscriptCache:
    """File-based cache for transcripts.

    Uses SHA256 hashes of episode URLs as cache keys.
    Stores transcripts as JSON files with metadata.
    Implements TTL-based expiration (default: 30 days).
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        ttl_days: int = 30,
    ):
        """Initialize transcript cache.

        Args:
            cache_dir: Directory for cache storage (default: XDG cache dir)
            ttl_days: Time-to-live in days (default: 30)
        """
        if cache_dir is None:
            cache_dir = Path(user_cache_dir("inkwell", "inkwell")) / "transcripts"

        self.cache_dir = cache_dir
        self.ttl_days = ttl_days

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, episode_url: str) -> str:
        """Generate cache key from episode URL.

        Args:
            episode_url: Episode URL

        Returns:
            SHA256 hash of URL as hex string
        """
        return hashlib.sha256(episode_url.encode("utf-8")).hexdigest()

    def _get_cache_path(self, episode_url: str) -> Path:
        """Get cache file path for episode URL.

        Args:
            episode_url: Episode URL

        Returns:
            Path to cache file
        """
        cache_key = self._get_cache_key(episode_url)
        return self.cache_dir / f"{cache_key}.json"

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

    async def get(self, episode_url: str) -> Transcript | None:
        """Get transcript from cache (async).

        Args:
            episode_url: Episode URL

        Returns:
            Transcript if found and not expired, None otherwise
        """
        cache_path = self._get_cache_path(episode_url)

        if not cache_path.exists():
            return None

        try:
            # Read cache file asynchronously
            async with aiofiles.open(cache_path, "r") as f:
                content = await f.read()
                data = json.loads(content)

            # Check expiration
            cached_at = datetime.fromisoformat(data["cached_at"])
            if self._is_expired(cached_at):
                # Remove expired entry asynchronously
                await self._delete_file(cache_path)
                return None

            # Deserialize transcript
            transcript = Transcript.model_validate(data["transcript"])

            # Mark as cached source
            transcript.source = "cached"

            return transcript

        except (json.JSONDecodeError, KeyError, ValueError):
            # Cache file is corrupted - remove it
            await self._delete_file(cache_path)
            return None

    async def set(self, episode_url: str, transcript: Transcript) -> None:
        """Save transcript to cache (async).

        Args:
            episode_url: Episode URL
            transcript: Transcript to cache

        Raises:
            CacheError: If caching fails
        """
        cache_path = self._get_cache_path(episode_url)
        temp_path = cache_path.with_suffix(".tmp")

        try:
            # Prepare cache data
            data = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "episode_url": episode_url,
                "transcript": transcript.model_dump(mode="json"),
            }

            # Write atomically (write to temp file, then rename)
            async with aiofiles.open(temp_path, "w") as f:
                await f.write(json.dumps(data, indent=2))

            # Atomic rename (still sync, but fast)
            await asyncio.to_thread(temp_path.rename, cache_path)

        except (OSError, TypeError) as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                await self._delete_file(temp_path)
            raise CacheError(f"Failed to cache transcript: {e}") from e

    async def delete(self, episode_url: str) -> bool:
        """Delete transcript from cache (async).

        Args:
            episode_url: Episode URL

        Returns:
            True if deleted, False if not found
        """
        cache_path = self._get_cache_path(episode_url)

        if cache_path.exists():
            await self._delete_file(cache_path)
            return True

        return False

    async def clear(self) -> int:
        """Clear all cached transcripts (async).

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
        """Clear expired cache entries (async).

        Returns:
            Number of expired entries deleted
        """
        cache_files = list(self.cache_dir.glob("*.json"))

        async def check_and_delete(cache_file: Path) -> bool:
            """Check if file is expired and delete if so. Returns True if deleted."""
            try:
                async with aiofiles.open(cache_file, "r") as f:
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
        """Get cache statistics (async).

        Returns:
            Dictionary with cache stats
        """
        cache_files = list(self.cache_dir.glob("*.json"))

        if not cache_files:
            return {
                "total": 0,
                "expired": 0,
                "valid": 0,
                "size_bytes": 0,
                "sources": {},
                "cache_dir": str(self.cache_dir),
            }

        async def analyze_file(cache_file: Path) -> dict[str, Any] | None:
            """Analyze a single cache file. Returns stats dict or None if error."""
            try:
                # Get size
                stat = await asyncio.to_thread(cache_file.stat)
                file_size = stat.st_size

                # Read content
                async with aiofiles.open(cache_file, "r") as f:
                    content = await f.read()
                    data = json.loads(content)

                # Check expiration
                cached_at = datetime.fromisoformat(data["cached_at"])
                is_expired = self._is_expired(cached_at)

                # Get source
                source = data["transcript"].get("source", "unknown")

                return {
                    "size": file_size,
                    "expired": is_expired,
                    "source": source,
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
        sources: dict[str, int] = {}

        for result in results:
            if result:
                total_size += result["size"]
                if result["expired"]:
                    expired += 1
                source = result["source"]
                sources[source] = sources.get(source, 0) + 1

        return {
            "total": total,
            "expired": expired,
            "valid": total - expired,
            "size_bytes": total_size,
            "sources": sources,
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
