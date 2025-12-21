"""Transcript caching layer."""

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import aiofiles
from platformdirs import user_cache_dir

from inkwell.transcription.models import Transcript
from inkwell.utils.cache import CacheError, FileCache

__all__ = ["TranscriptCache", "CacheError"]


class TranscriptCache(FileCache[Transcript]):
    """File-based cache for transcripts.

    Uses SHA256 hashes of episode URLs as cache keys.
    Stores transcripts as JSON files with metadata.
    Implements TTL-based expiration (default: 30 days).

    Inherits from FileCache[Transcript] for all core cache operations.
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

        super().__init__(
            cache_dir=cache_dir,
            ttl_days=ttl_days,
            serializer=self._serialize_transcript,
            deserializer=self._deserialize_transcript,
            key_generator=self._make_cache_key,
        )

    def _make_cache_key(self, episode_url: str) -> str:
        """Generate cache key from episode URL.

        Args:
            episode_url: Episode URL

        Returns:
            SHA256 hash of URL as hex string
        """
        return hashlib.sha256(episode_url.encode("utf-8")).hexdigest()

    def _serialize_transcript(self, transcript: Transcript) -> dict:
        """Serialize transcript to dict for JSON storage.

        Args:
            transcript: Transcript to serialize

        Returns:
            Dictionary with transcript data and metadata
        """
        return {
            "transcript": transcript.model_dump(mode="json"),
            "episode_url": transcript.episode_url,
        }

    def _deserialize_transcript(self, data: dict) -> Transcript:
        """Deserialize transcript from stored data.

        Args:
            data: Dictionary with transcript data

        Returns:
            Transcript instance
        """
        transcript = Transcript.model_validate(data["transcript"])
        # Mark as cached source
        transcript.source = "cached"
        return transcript

    # Convenience methods that match the original API
    async def get(self, episode_url: str) -> Transcript | None:
        """Get transcript from cache.

        Args:
            episode_url: Episode URL

        Returns:
            Transcript if found and not expired, None otherwise
        """
        return await super().get(episode_url)

    async def set(self, episode_url: str, transcript: Transcript) -> None:
        """Save transcript to cache.

        Args:
            episode_url: Episode URL
            transcript: Transcript to cache

        Raises:
            CacheError: If caching fails
        """
        await super().set(episode_url, value=transcript)

    async def delete(self, episode_url: str) -> bool:
        """Delete transcript from cache.

        Args:
            episode_url: Episode URL

        Returns:
            True if deleted, False if not found
        """
        return await super().delete(episode_url)

    # Helper methods for compatibility with original implementation
    def _get_cache_key(self, episode_url: str) -> str:
        """Generate cache key from episode URL (compatibility method).

        Args:
            episode_url: Episode URL

        Returns:
            SHA256 hash of URL as hex string
        """
        return self._make_cache_key(episode_url)

    def _get_cache_path(self, episode_url: str) -> Path:
        """Get cache file path for episode URL (compatibility method).

        Args:
            episode_url: Episode URL

        Returns:
            Path to cache file
        """
        cache_key = self._make_cache_key(episode_url)
        return self.cache_dir / f"{cache_key}.json"

    def _is_expired(self, cached_at) -> bool:
        """Check if cache entry is expired (compatibility method).

        Args:
            cached_at: When entry was cached

        Returns:
            True if expired, False otherwise
        """
        return super()._is_expired(cached_at)

    async def _delete_file(self, path: Path) -> None:
        """Delete file asynchronously (compatibility method).

        Args:
            path: Path to file to delete
        """
        await super()._delete_file(path)

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics (with transcript-specific source tracking).

        Returns:
            Dictionary with cache stats including sources information
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
                async with aiofiles.open(cache_file) as f:
                    content = await f.read()
                    data = json.loads(content)

                # Check expiration
                from datetime import datetime

                cached_at = datetime.fromisoformat(data["cached_at"])
                is_expired = self._is_expired(cached_at)

                # Get source from transcript data
                # Handle old format (data["transcript"]) and new format
                # (data["value"]["transcript"])
                value_data = data.get("value", data)  # Fallback for old format
                source = value_data.get("transcript", {}).get("source", "unknown")

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
