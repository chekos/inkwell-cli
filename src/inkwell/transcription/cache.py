"""Transcript caching layer."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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

    def get(self, episode_url: str) -> Transcript | None:
        """Get transcript from cache.

        Args:
            episode_url: Episode URL

        Returns:
            Transcript if found and not expired, None otherwise
        """
        cache_path = self._get_cache_path(episode_url)

        if not cache_path.exists():
            return None

        try:
            # Read cache file
            with cache_path.open("r") as f:
                data = json.load(f)

            # Check expiration
            cached_at = datetime.fromisoformat(data["cached_at"])
            if self._is_expired(cached_at):
                # Remove expired entry
                cache_path.unlink()
                return None

            # Deserialize transcript
            transcript = Transcript.model_validate(data["transcript"])

            # Mark as cached source
            transcript.source = "cached"

            return transcript

        except (json.JSONDecodeError, KeyError, ValueError):
            # Cache file is corrupted - remove it
            cache_path.unlink(missing_ok=True)
            return None

    def set(self, episode_url: str, transcript: Transcript) -> None:
        """Save transcript to cache.

        Args:
            episode_url: Episode URL
            transcript: Transcript to cache

        Raises:
            CacheError: If caching fails
        """
        cache_path = self._get_cache_path(episode_url)

        try:
            # Prepare cache data
            data = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "episode_url": episode_url,
                "transcript": transcript.model_dump(mode="json"),
            }

            # Write atomically (write to temp file, then rename)
            temp_path = cache_path.with_suffix(".tmp")
            with temp_path.open("w") as f:
                json.dump(data, f, indent=2)

            temp_path.rename(cache_path)

        except (OSError, TypeError) as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise CacheError(f"Failed to cache transcript: {e}") from e

    def delete(self, episode_url: str) -> bool:
        """Delete transcript from cache.

        Args:
            episode_url: Episode URL

        Returns:
            True if deleted, False if not found
        """
        cache_path = self._get_cache_path(episode_url)

        if cache_path.exists():
            cache_path.unlink()
            return True

        return False

    def clear(self) -> int:
        """Clear all cached transcripts.

        Returns:
            Number of cache entries deleted
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        return count

    def clear_expired(self) -> int:
        """Clear expired cache entries.

        Returns:
            Number of expired entries deleted
        """
        count = 0

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with cache_file.open("r") as f:
                    data = json.load(f)

                cached_at = datetime.fromisoformat(data["cached_at"])
                if self._is_expired(cached_at):
                    cache_file.unlink()
                    count += 1

            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                # Corrupted file - remove it
                cache_file.unlink(missing_ok=True)
                count += 1

        return count

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total = 0
        expired = 0
        sources: dict[str, int] = {}
        total_size = 0

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                total += 1
                total_size += cache_file.stat().st_size

                with cache_file.open("r") as f:
                    data = json.load(f)

                # Check expiration
                cached_at = datetime.fromisoformat(data["cached_at"])
                if self._is_expired(cached_at):
                    expired += 1

                # Count sources
                source = data["transcript"].get("source", "unknown")
                sources[source] = sources.get(source, 0) + 1

            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                # Skip corrupted files
                continue

        return {
            "total": total,
            "expired": expired,
            "valid": total - expired,
            "size_bytes": total_size,
            "sources": sources,
            "cache_dir": str(self.cache_dir),
        }
