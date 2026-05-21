"""Cache for extraction results.

Provides file-based caching with TTL to avoid redundant LLM API calls.
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, cast

import aiofiles
import platformdirs

from inkwell.utils.cache import FileCache

logger = logging.getLogger(__name__)

EXTRACTION_CACHE_FORMAT_VERSION = 2
EXTRACTION_OUTPUT_SCHEMA_VERSION = "extraction-result:v1"
UNKNOWN_CACHE_KEY_PART = "unknown"

__all__ = [
    "EXTRACTION_CACHE_FORMAT_VERSION",
    "EXTRACTION_OUTPUT_SCHEMA_VERSION",
    "ExtractionCache",
]


class ExtractionCache:
    """File-based cache for extraction results.

    Uses template version in cache key for automatic invalidation
    when templates change. Cache files stored in XDG cache directory.

    Uses composition with FileCache[str] for core cache operations,
    providing a clean domain-specific API.

    Example:
        >>> cache = ExtractionCache()
        >>> await cache.set("summary", "v1.0", transcript, "extracted content")
        >>> result = await cache.get("summary", "v1.0", transcript)
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

        self._cache = FileCache[str](
            cache_dir=cache_dir,
            ttl_days=ttl_days,
            serializer=self._serialize_result,
            deserializer=self._deserialize_result,
            key_generator=self._make_key,
        )

        # Expose cache_dir for compatibility
        self.cache_dir = cache_dir

        self.ttl_seconds = ttl_days * 24 * 60 * 60

    @staticmethod
    def _hash_text(value: str) -> str:
        """Hash text content for cache-key metadata."""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _canonical_json(data: dict[str, Any]) -> str:
        """Serialize cache-key metadata deterministically."""
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    def _key_components(
        self,
        template_name: str,
        template_version: str,
        transcript: str,
        provider: str | None = None,
        model: str | None = None,
        prompt_hash: str | None = None,
        output_schema_version: str | None = None,
    ) -> dict[str, Any]:
        """Build explicit extraction cache-key inputs."""
        return {
            "cache_format_version": EXTRACTION_CACHE_FORMAT_VERSION,
            "transcript_hash": self._hash_text(transcript),
            "template_name": template_name,
            "template_version": template_version,
            "provider": provider or UNKNOWN_CACHE_KEY_PART,
            "model": model or UNKNOWN_CACHE_KEY_PART,
            "prompt_hash": prompt_hash or UNKNOWN_CACHE_KEY_PART,
            "output_schema_version": output_schema_version or EXTRACTION_OUTPUT_SCHEMA_VERSION,
        }

    def _make_key(
        self,
        template_name: str,
        template_version: str,
        transcript: str,
        provider: str | None = None,
        model: str | None = None,
        prompt_hash: str | None = None,
        output_schema_version: str | None = None,
    ) -> str:
        """Generate cache key from template and transcript.

        Includes explicit versioned key inputs so cache entries are invalidated
        when template prompts, provider/model routing, transcript content, or
        output schema expectations change.

        Args:
            template_name: Template name
            template_version: Template version
            transcript: Transcript text
            provider: LLM provider used or selected
            model: Provider model used or selected
            prompt_hash: Hash of prompt/template content
            output_schema_version: Output schema identifier

        Returns:
            Cache key (hex string)
        """
        payload = self._key_components(
            template_name,
            template_version,
            transcript,
            provider,
            model,
            prompt_hash,
            output_schema_version,
        )
        return self._hash_text(self._canonical_json(payload))

    def _serialize_result(self, result: str) -> dict[str, Any]:
        """Serialize extraction result to dict for JSON storage.

        Args:
            result: Extraction result string

        Returns:
            Dictionary with result and timestamp
        """
        return {
            "cache_format_version": EXTRACTION_CACHE_FORMAT_VERSION,
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
        return str(data["result"])

    async def get(
        self,
        template_name: str,
        template_version: str,
        transcript: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        prompt_hash: str | None = None,
        output_schema_version: str | None = None,
    ) -> str | None:
        """Get cached extraction result.

        Args:
            template_name: Template name
            template_version: Template version (for invalidation)
            transcript: Transcript text
            provider: LLM provider used or selected
            model: Provider model used or selected
            prompt_hash: Hash of prompt/template content
            output_schema_version: Output schema identifier

        Returns:
            Cached result or None if not found/expired
        """
        cache_key = self._make_key(
            template_name,
            template_version,
            transcript,
            provider,
            model,
            prompt_hash,
            output_schema_version,
        )
        cache_file = self.cache_dir / f"{cache_key}.json"

        temp_file = cache_file.with_suffix(".tmp")
        if temp_file.exists():
            # Another process is writing, treat as cache miss
            logger.debug(f"Cache file {cache_file.name} is being written, treating as miss")
            return None

        # Additional validation for partial writes (ExtractionCache-specific)
        if cache_file.exists():
            try:
                async with aiofiles.open(cache_file) as f:
                    content = await f.read()

                # Verify JSON is complete (simple sanity check)
                if not content.strip().endswith("}"):
                    # Partial write detected, remove corrupt file
                    logger.warning(
                        f"Detected partial write in cache file {cache_file.name}, removing"
                    )
                    await self._cache._delete_file(cache_file)
                    return None

            except OSError:
                # File system error
                return None

        return await self._cache.get(
            template_name,
            template_version,
            transcript,
            provider,
            model,
            prompt_hash,
            output_schema_version,
        )

    async def set(
        self,
        template_name: str,
        template_version: str,
        transcript: str,
        result: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        prompt_hash: str | None = None,
        output_schema_version: str | None = None,
    ) -> None:
        """Store extraction result in cache.

        Args:
            template_name: Template name
            template_version: Template version
            transcript: Transcript text
            result: Extraction result to cache
            provider: LLM provider used or selected
            model: Provider model used or selected
            prompt_hash: Hash of prompt/template content
            output_schema_version: Output schema identifier
        """
        key_components = self._key_components(
            template_name,
            template_version,
            transcript,
            provider,
            model,
            prompt_hash,
            output_schema_version,
        )

        # Override serializer temporarily to include template metadata
        original_serializer = self._cache.serializer

        def extended_serializer(result: str) -> dict[str, Any]:
            base_data = cast(dict[str, Any], original_serializer(result))
            base_data.update(
                {
                    "template_name": template_name,
                    "template_version": template_version,
                    "provider": provider or UNKNOWN_CACHE_KEY_PART,
                    "model": model or UNKNOWN_CACHE_KEY_PART,
                    "prompt_hash": prompt_hash or UNKNOWN_CACHE_KEY_PART,
                    "output_schema_version": (
                        output_schema_version or EXTRACTION_OUTPUT_SCHEMA_VERSION
                    ),
                    "transcript_hash": key_components["transcript_hash"],
                    "key_components": key_components,
                }
            )
            return base_data

        self._cache.serializer = extended_serializer

        try:
            await self._cache.set(
                template_name,
                template_version,
                transcript,
                provider,
                model,
                prompt_hash,
                output_schema_version,
                value=result,
            )
        finally:
            self._cache.serializer = original_serializer

    async def delete(
        self,
        template_name: str,
        template_version: str,
        transcript: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        prompt_hash: str | None = None,
        output_schema_version: str | None = None,
    ) -> bool:
        """Delete cached extraction result.

        Args:
            template_name: Template name
            template_version: Template version
            transcript: Transcript text
            provider: LLM provider used or selected
            model: Provider model used or selected
            prompt_hash: Hash of prompt/template content
            output_schema_version: Output schema identifier

        Returns:
            True if deleted, False if not found
        """
        return await self._cache.delete(
            template_name,
            template_version,
            transcript,
            provider,
            model,
            prompt_hash,
            output_schema_version,
        )

    async def clear(self) -> int:
        """Clear all cached values.

        Returns:
            Number of cache entries deleted
        """
        return await self._cache.clear()

    async def clear_expired(self) -> int:
        """Clear expired cache entries.

        Returns:
            Number of expired entries deleted
        """
        return await self._cache.clear_expired()

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache stats and extraction-specific metadata summaries.
        """
        cache_files = list(self.cache_dir.glob("*.json"))
        total_entries = len(cache_files)

        if total_entries == 0:
            return {
                "total_entries": 0,
                "total": 0,
                "total_size_mb": 0.0,
                "size_bytes": 0,
                "oldest_entry_age_days": 0,
                "cache_dir": str(self.cache_dir),
                "cache_format_version": EXTRACTION_CACHE_FORMAT_VERSION,
                "format_versions": {},
                "templates": {},
                "providers": {},
                "models": {},
            }

        import asyncio

        async def analyze_file(cache_file: Path) -> dict[str, Any] | None:
            """Analyze one cache file, returning metadata or None if unreadable."""
            try:
                stat_result = await asyncio.to_thread(cache_file.stat)
                async with aiofiles.open(cache_file) as f:
                    content = await f.read()
                    data = json.loads(content)

                value = data.get("value", data)
                timestamp = float(value.get("timestamp", time.time()))
                format_version = value.get("cache_format_version", "legacy")
                template_name = value.get("template_name", "unknown")
                provider = value.get("provider", "unknown")
                model = value.get("model", "unknown")

                return {
                    "size_bytes": stat_result.st_size,
                    "timestamp": timestamp,
                    "format_version": str(format_version),
                    "template_name": template_name,
                    "provider": provider,
                    "model": model,
                }
            except (json.JSONDecodeError, KeyError, OSError, ValueError):
                return None

        file_stats = await asyncio.gather(*[analyze_file(f) for f in cache_files])
        readable_stats = [stat for stat in file_stats if stat is not None]

        total_size = sum(stat["size_bytes"] for stat in readable_stats)
        total_size_mb = total_size / (1024 * 1024)
        timestamps = [stat["timestamp"] for stat in readable_stats]
        oldest_timestamp = min(timestamps) if timestamps else time.time()

        oldest_age_days = (time.time() - oldest_timestamp) / (24 * 60 * 60)

        def count_by(field: str) -> dict[str, int]:
            counts: dict[str, int] = {}
            for stat in readable_stats:
                value = str(stat[field])
                counts[value] = counts.get(value, 0) + 1
            return counts

        return {
            "total_entries": total_entries,
            "total": total_entries,
            "total_size_mb": round(total_size_mb, 2),
            "size_bytes": total_size,
            "oldest_entry_age_days": round(oldest_age_days, 1),
            "cache_dir": str(self.cache_dir),
            "cache_format_version": EXTRACTION_CACHE_FORMAT_VERSION,
            "format_versions": count_by("format_version"),
            "templates": count_by("template_name"),
            "providers": count_by("provider"),
            "models": count_by("model"),
        }

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics (FileCache-compatible method).

        Returns:
            Dictionary with cache stats
        """
        return await self._cache.stats()
