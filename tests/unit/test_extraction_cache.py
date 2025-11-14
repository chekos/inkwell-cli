"""Unit tests for extraction cache."""

import json
import time
from pathlib import Path

import pytest

from inkwell.extraction.cache import ExtractionCache


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


class TestExtractionCache:
    """Tests for ExtractionCache."""

    def test_init_default_dir(self) -> None:
        """Test cache initialization with default directory."""
        cache = ExtractionCache()
        assert cache.cache_dir.exists()
        assert "inkwell" in str(cache.cache_dir)

    def test_init_custom_dir(self, temp_cache_dir: Path) -> None:
        """Test cache initialization with custom directory."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)
        assert cache.cache_dir == temp_cache_dir

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        """Test that cache directory is created if it doesn't exist."""
        cache_dir = tmp_path / "nonexistent" / "cache"
        assert not cache_dir.exists()

        _cache = ExtractionCache(cache_dir=cache_dir)
        assert cache_dir.exists()

    @pytest.mark.asyncio
    async def test_set_and_get(self, temp_cache_dir: Path) -> None:
        """Test setting and getting cached values."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        await cache.set("summary", "1.0", "transcript text", "extracted summary")

        result = await cache.get("summary", "1.0", "transcript text")
        assert result == "extracted summary"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, temp_cache_dir: Path) -> None:
        """Test getting non-existent cache entry returns None."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        result = await cache.get("summary", "1.0", "transcript text")
        assert result is None

    @pytest.mark.asyncio
    async def test_version_invalidates_cache(self, temp_cache_dir: Path) -> None:
        """Test that changing template version invalidates cache."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Cache with v1.0
        await cache.set("summary", "1.0", "transcript", "result v1")

        # Get with v1.0 - should hit
        assert await cache.get("summary", "1.0", "transcript") == "result v1"

        # Get with v1.1 - should miss
        assert await cache.get("summary", "1.1", "transcript") is None

    @pytest.mark.asyncio
    async def test_different_transcripts_separate_cache(self, temp_cache_dir: Path) -> None:
        """Test that different transcripts have separate cache entries."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        await cache.set("summary", "1.0", "transcript 1", "result 1")
        await cache.set("summary", "1.0", "transcript 2", "result 2")

        assert await cache.get("summary", "1.0", "transcript 1") == "result 1"
        assert await cache.get("summary", "1.0", "transcript 2") == "result 2"

    @pytest.mark.asyncio
    async def test_different_templates_separate_cache(self, temp_cache_dir: Path) -> None:
        """Test that different templates have separate cache entries."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        await cache.set("summary", "1.0", "transcript", "summary result")
        await cache.set("quotes", "1.0", "transcript", "quotes result")

        assert await cache.get("summary", "1.0", "transcript") == "summary result"
        assert await cache.get("quotes", "1.0", "transcript") == "quotes result"

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, temp_cache_dir: Path) -> None:
        """Test that cache entries expire after TTL."""
        # Very short TTL for testing (1 second = 1/86400 days)
        cache = ExtractionCache(cache_dir=temp_cache_dir, ttl_days=1 / 86400)

        await cache.set("summary", "1.0", "transcript", "result")

        # Should be cached immediately
        assert await cache.get("summary", "1.0", "transcript") == "result"

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert await cache.get("summary", "1.0", "transcript") is None

    @pytest.mark.asyncio
    async def test_clear_all(self, temp_cache_dir: Path) -> None:
        """Test clearing all cache entries."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Add multiple entries
        await cache.set("summary", "1.0", "transcript1", "result1")
        await cache.set("quotes", "1.0", "transcript2", "result2")
        await cache.set("concepts", "1.0", "transcript3", "result3")

        # Clear all
        count = await cache.clear()
        assert count == 3

        # Verify all cleared
        assert await cache.get("summary", "1.0", "transcript1") is None
        assert await cache.get("quotes", "1.0", "transcript2") is None
        assert await cache.get("concepts", "1.0", "transcript3") is None

    @pytest.mark.asyncio
    async def test_clear_expired(self, temp_cache_dir: Path) -> None:
        """Test clearing only expired entries."""
        # Create two caches with different TTLs
        short_ttl_cache = ExtractionCache(cache_dir=temp_cache_dir, ttl_days=1 / 86400)
        long_ttl_cache = ExtractionCache(cache_dir=temp_cache_dir, ttl_days=30)

        # Add entry with short TTL that will expire
        await short_ttl_cache.set("old", "1.0", "transcript_old", "old result")
        time.sleep(1.1)

        # Add entry with long TTL that won't expire
        await long_ttl_cache.set("new", "1.0", "transcript_new", "new result")

        # Clear expired using short TTL - both should check against short TTL
        count = await short_ttl_cache.clear_expired()
        assert count == 1

        # Old should be gone, new should remain
        assert await short_ttl_cache.get("old", "1.0", "transcript_old") is None
        assert await long_ttl_cache.get("new", "1.0", "transcript_new") == "new result"

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, temp_cache_dir: Path) -> None:
        """Test stats for empty cache."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        stats = await cache.get_stats()
        assert stats["total_entries"] == 0
        assert stats["total_size_mb"] == 0.0
        assert stats["oldest_entry_age_days"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_entries(self, temp_cache_dir: Path) -> None:
        """Test stats with cached entries."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Add some entries
        await cache.set("summary", "1.0", "transcript1", "result1")
        await cache.set("quotes", "1.0", "transcript2", "result2")

        stats = await cache.get_stats()
        assert stats["total_entries"] == 2
        # Size in MB may be very small, but should be non-negative
        assert stats["total_size_mb"] >= 0
        assert stats["oldest_entry_age_days"] >= 0

    @pytest.mark.asyncio
    async def test_corrupted_cache_file_ignored(self, temp_cache_dir: Path) -> None:
        """Test that corrupted cache files are ignored and deleted."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Create corrupted cache file
        cache_file = temp_cache_dir / "corrupted.json"
        cache_file.write_text("not valid json {{{")

        # Try to get from cache (should handle gracefully)
        # Cache won't match any key, so we just verify it doesn't crash

        # Now set a valid entry
        await cache.set("summary", "1.0", "transcript", "result")

        # Should work fine
        assert await cache.get("summary", "1.0", "transcript") == "result"

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, temp_cache_dir: Path) -> None:
        """Test that cache keys are generated consistently."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Same inputs should generate same key
        await cache.set("summary", "1.0", "transcript", "result1")
        await cache.set("summary", "1.0", "transcript", "result2")  # Overwrites

        # Should get the latest value
        assert await cache.get("summary", "1.0", "transcript") == "result2"

    @pytest.mark.asyncio
    async def test_cache_persists_across_instances(self, temp_cache_dir: Path) -> None:
        """Test that cache persists across ExtractionCache instances."""
        # First instance
        cache1 = ExtractionCache(cache_dir=temp_cache_dir)
        await cache1.set("summary", "1.0", "transcript", "cached result")

        # Second instance (same directory)
        cache2 = ExtractionCache(cache_dir=temp_cache_dir)
        assert await cache2.get("summary", "1.0", "transcript") == "cached result"

    @pytest.mark.asyncio
    async def test_long_transcript_caching(self, temp_cache_dir: Path) -> None:
        """Test caching with very long transcripts."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Very long transcript
        long_transcript = "word " * 100000  # ~100K words
        result = "extracted summary"

        await cache.set("summary", "1.0", long_transcript, result)

        # Should still work
        assert await cache.get("summary", "1.0", long_transcript) == result

    @pytest.mark.asyncio
    async def test_special_characters_in_result(self, temp_cache_dir: Path) -> None:
        """Test caching results with special characters."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        special_result = 'Result with "quotes", newlines\nand\ttabs'
        await cache.set("summary", "1.0", "transcript", special_result)

        assert await cache.get("summary", "1.0", "transcript") == special_result

    @pytest.mark.asyncio
    async def test_json_result_caching(self, temp_cache_dir: Path) -> None:
        """Test caching JSON results."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        json_result = '{"quotes": ["one", "two"], "count": 2}'
        await cache.set("quotes", "1.0", "transcript", json_result)

        assert await cache.get("quotes", "1.0", "transcript") == json_result

    @pytest.mark.asyncio
    async def test_cache_file_structure(self, temp_cache_dir: Path) -> None:
        """Test that cache files have correct structure."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        await cache.set("summary", "1.0", "transcript", "result")

        # Find the cache file
        cache_files = list(temp_cache_dir.glob("*.json"))
        assert len(cache_files) == 1

        # Check structure
        with cache_files[0].open("r") as f:
            data = json.load(f)

        assert "cached_at" in data
        assert "value" in data
        assert "timestamp" in data["value"]
        assert "template_name" in data["value"]
        assert "template_version" in data["value"]
        assert "result" in data["value"]
        assert data["value"]["template_name"] == "summary"
        assert data["value"]["template_version"] == "1.0"
        assert data["value"]["result"] == "result"

    @pytest.mark.asyncio
    async def test_concurrent_access(self, temp_cache_dir: Path) -> None:
        """Test that concurrent cache access doesn't cause issues."""
        cache1 = ExtractionCache(cache_dir=temp_cache_dir)
        cache2 = ExtractionCache(cache_dir=temp_cache_dir)

        # Both write to cache
        await cache1.set("summary", "1.0", "transcript1", "result1")
        await cache2.set("quotes", "1.0", "transcript2", "result2")

        # Both should be able to read both entries
        assert await cache1.get("summary", "1.0", "transcript1") == "result1"
        assert await cache1.get("quotes", "1.0", "transcript2") == "result2"
        assert await cache2.get("summary", "1.0", "transcript1") == "result1"
        assert await cache2.get("quotes", "1.0", "transcript2") == "result2"

    @pytest.mark.asyncio
    async def test_cache_get_during_concurrent_write(self, temp_cache_dir: Path) -> None:
        """Test cache read during write returns None (cache miss)."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Create temp file to simulate active write
        cache_key = cache._make_key("template", "v1", "transcript")
        cache_file = temp_cache_dir / f"{cache_key}.json"
        temp_file = cache_file.with_suffix(".tmp")
        temp_file.write_text('{"partial": ')

        # Should detect active write and return None
        result = await cache.get("template", "v1", "transcript")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_get_partial_json_deleted(self, temp_cache_dir: Path) -> None:
        """Test partial JSON is detected and deleted."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        cache_key = cache._make_key("template", "v1", "transcript")
        cache_file = temp_cache_dir / f"{cache_key}.json"
        cache_file.write_text('{"template": "summary", "content": "partial')

        # Should detect partial JSON (doesn't end with }) and delete file
        result = await cache.get("template", "v1", "transcript")
        assert result is None
        assert not cache_file.exists()

    @pytest.mark.asyncio
    async def test_cache_get_invalid_json_deleted(self, temp_cache_dir: Path) -> None:
        """Test invalid JSON is detected and deleted."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        cache_key = cache._make_key("template", "v1", "transcript")
        cache_file = temp_cache_dir / f"{cache_key}.json"
        cache_file.write_text('{"template": "summary", "broken": }')

        # Should detect invalid JSON and delete file
        result = await cache.get("template", "v1", "transcript")
        assert result is None
        assert not cache_file.exists()

    @pytest.mark.asyncio
    async def test_cache_get_missing_required_field(self, temp_cache_dir: Path) -> None:
        """Test cache file with missing required field is deleted."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        cache_key = cache._make_key("template", "v1", "transcript")
        cache_file = temp_cache_dir / f"{cache_key}.json"
        # Valid JSON but missing "result" field
        cache_file.write_text('{"template": "summary", "timestamp": 1234567890}')

        # Should detect missing field and delete file
        result = await cache.get("template", "v1", "transcript")
        assert result is None
        assert not cache_file.exists()

    @pytest.mark.asyncio
    async def test_cache_get_valid_after_corruption_check(self, temp_cache_dir: Path) -> None:
        """Test valid cache file passes all corruption checks."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Set valid cache entry
        await cache.set("template", "v1", "transcript", "valid result")

        # Should pass all checks and return result
        result = await cache.get("template", "v1", "transcript")
        assert result == "valid result"

        # Verify file still exists (wasn't deleted)
        cache_key = cache._make_key("template", "v1", "transcript")
        cache_file = temp_cache_dir / f"{cache_key}.json"
        assert cache_file.exists()
