"""Cache for extraction results.

Provides file-based caching with TTL to avoid redundant LLM API calls.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any

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

    def get(self, template_name: str, template_version: str, transcript: str) -> str | None:
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

        if not cache_file.exists():
            return None

        try:
            with cache_file.open("r") as f:
                data = json.load(f)

            # Check TTL
            if time.time() - data["timestamp"] > self.ttl_seconds:
                # Expired, delete file
                cache_file.unlink()
                return None

            return data["result"]

        except (json.JSONDecodeError, KeyError, OSError):
            # Corrupted cache file, delete it
            cache_file.unlink(missing_ok=True)
            return None

    def set(self, template_name: str, template_version: str, transcript: str, result: str) -> None:
        """Store extraction result in cache.

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

        try:
            with cache_file.open("w") as f:
                json.dump(data, f)
        except OSError:
            # Failed to write cache, just continue
            pass

    def clear(self) -> int:
        """Clear all cached extractions.

        Returns:
            Number of cache files deleted
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except OSError:
                pass
        return count

    def clear_expired(self) -> int:
        """Clear expired cache entries.

        Returns:
            Number of expired entries deleted
        """
        count = 0
        current_time = time.time()

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with cache_file.open("r") as f:
                    data = json.load(f)

                if current_time - data["timestamp"] > self.ttl_seconds:
                    cache_file.unlink()
                    count += 1

            except (json.JSONDecodeError, KeyError, OSError):
                # Corrupted file, delete it
                cache_file.unlink(missing_ok=True)
                count += 1

        return count

    def get_stats(self) -> dict[str, Any]:
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

        # Calculate total size
        total_size = sum(f.stat().st_size for f in cache_files)
        total_size_mb = total_size / (1024 * 1024)

        # Find oldest entry
        oldest_timestamp = time.time()
        for cache_file in cache_files:
            try:
                with cache_file.open("r") as f:
                    data = json.load(f)
                    if data["timestamp"] < oldest_timestamp:
                        oldest_timestamp = data["timestamp"]
            except (json.JSONDecodeError, KeyError, OSError):
                pass

        oldest_age_days = (time.time() - oldest_timestamp) / (24 * 60 * 60)

        return {
            "total_entries": total_entries,
            "total_size_mb": round(total_size_mb, 2),
            "oldest_entry_age_days": round(oldest_age_days, 1),
        }

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
