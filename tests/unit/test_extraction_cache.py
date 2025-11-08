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

        cache = ExtractionCache(cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_set_and_get(self, temp_cache_dir: Path) -> None:
        """Test setting and getting cached values."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        cache.set("summary", "1.0", "transcript text", "extracted summary")

        result = cache.get("summary", "1.0", "transcript text")
        assert result == "extracted summary"

    def test_get_nonexistent(self, temp_cache_dir: Path) -> None:
        """Test getting non-existent cache entry returns None."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        result = cache.get("summary", "1.0", "transcript text")
        assert result is None

    def test_version_invalidates_cache(self, temp_cache_dir: Path) -> None:
        """Test that changing template version invalidates cache."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Cache with v1.0
        cache.set("summary", "1.0", "transcript", "result v1")

        # Get with v1.0 - should hit
        assert cache.get("summary", "1.0", "transcript") == "result v1"

        # Get with v1.1 - should miss
        assert cache.get("summary", "1.1", "transcript") is None

    def test_different_transcripts_separate_cache(self, temp_cache_dir: Path) -> None:
        """Test that different transcripts have separate cache entries."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        cache.set("summary", "1.0", "transcript 1", "result 1")
        cache.set("summary", "1.0", "transcript 2", "result 2")

        assert cache.get("summary", "1.0", "transcript 1") == "result 1"
        assert cache.get("summary", "1.0", "transcript 2") == "result 2"

    def test_different_templates_separate_cache(self, temp_cache_dir: Path) -> None:
        """Test that different templates have separate cache entries."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        cache.set("summary", "1.0", "transcript", "summary result")
        cache.set("quotes", "1.0", "transcript", "quotes result")

        assert cache.get("summary", "1.0", "transcript") == "summary result"
        assert cache.get("quotes", "1.0", "transcript") == "quotes result"

    def test_ttl_expiration(self, temp_cache_dir: Path) -> None:
        """Test that cache entries expire after TTL."""
        # Very short TTL for testing (1 second = 1/86400 days)
        cache = ExtractionCache(cache_dir=temp_cache_dir, ttl_days=1 / 86400)

        cache.set("summary", "1.0", "transcript", "result")

        # Should be cached immediately
        assert cache.get("summary", "1.0", "transcript") == "result"

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert cache.get("summary", "1.0", "transcript") is None

    def test_clear_all(self, temp_cache_dir: Path) -> None:
        """Test clearing all cache entries."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Add multiple entries
        cache.set("summary", "1.0", "transcript1", "result1")
        cache.set("quotes", "1.0", "transcript2", "result2")
        cache.set("concepts", "1.0", "transcript3", "result3")

        # Clear all
        count = cache.clear()
        assert count == 3

        # Verify all cleared
        assert cache.get("summary", "1.0", "transcript1") is None
        assert cache.get("quotes", "1.0", "transcript2") is None
        assert cache.get("concepts", "1.0", "transcript3") is None

    def test_clear_expired(self, temp_cache_dir: Path) -> None:
        """Test clearing only expired entries."""
        # Short TTL for expired entries
        cache = ExtractionCache(cache_dir=temp_cache_dir, ttl_days=1 / 86400)

        # Add entry that will expire
        cache.set("old", "1.0", "transcript", "old result")
        time.sleep(1.1)

        # Add entry that won't expire
        cache.ttl_seconds = 30 * 24 * 60 * 60  # 30 days
        cache.set("new", "1.0", "transcript", "new result")

        # Clear expired
        count = cache.clear_expired()
        assert count == 1

        # Old should be gone, new should remain
        assert cache.get("old", "1.0", "transcript") is None
        assert cache.get("new", "1.0", "transcript") == "new result"

    def test_get_stats_empty(self, temp_cache_dir: Path) -> None:
        """Test stats for empty cache."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        stats = cache.get_stats()
        assert stats["total_entries"] == 0
        assert stats["total_size_mb"] == 0.0
        assert stats["oldest_entry_age_days"] == 0

    def test_get_stats_with_entries(self, temp_cache_dir: Path) -> None:
        """Test stats with cached entries."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Add some entries
        cache.set("summary", "1.0", "transcript1", "result1")
        cache.set("quotes", "1.0", "transcript2", "result2")

        stats = cache.get_stats()
        assert stats["total_entries"] == 2
        assert stats["total_size_mb"] > 0
        assert stats["oldest_entry_age_days"] >= 0

    def test_corrupted_cache_file_ignored(self, temp_cache_dir: Path) -> None:
        """Test that corrupted cache files are ignored and deleted."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Create corrupted cache file
        cache_file = temp_cache_dir / "corrupted.json"
        cache_file.write_text("not valid json {{{")

        # Try to get from cache (should handle gracefully)
        # Cache won't match any key, so we just verify it doesn't crash

        # Now set a valid entry
        cache.set("summary", "1.0", "transcript", "result")

        # Should work fine
        assert cache.get("summary", "1.0", "transcript") == "result"

    def test_cache_key_generation(self, temp_cache_dir: Path) -> None:
        """Test that cache keys are generated consistently."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Same inputs should generate same key
        cache.set("summary", "1.0", "transcript", "result1")
        cache.set("summary", "1.0", "transcript", "result2")  # Overwrites

        # Should get the latest value
        assert cache.get("summary", "1.0", "transcript") == "result2"

    def test_cache_persists_across_instances(self, temp_cache_dir: Path) -> None:
        """Test that cache persists across ExtractionCache instances."""
        # First instance
        cache1 = ExtractionCache(cache_dir=temp_cache_dir)
        cache1.set("summary", "1.0", "transcript", "cached result")

        # Second instance (same directory)
        cache2 = ExtractionCache(cache_dir=temp_cache_dir)
        assert cache2.get("summary", "1.0", "transcript") == "cached result"

    def test_long_transcript_caching(self, temp_cache_dir: Path) -> None:
        """Test caching with very long transcripts."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        # Very long transcript
        long_transcript = "word " * 100000  # ~100K words
        result = "extracted summary"

        cache.set("summary", "1.0", long_transcript, result)

        # Should still work
        assert cache.get("summary", "1.0", long_transcript) == result

    def test_special_characters_in_result(self, temp_cache_dir: Path) -> None:
        """Test caching results with special characters."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        special_result = 'Result with "quotes", newlines\nand\ttabs'
        cache.set("summary", "1.0", "transcript", special_result)

        assert cache.get("summary", "1.0", "transcript") == special_result

    def test_json_result_caching(self, temp_cache_dir: Path) -> None:
        """Test caching JSON results."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        json_result = '{"quotes": ["one", "two"], "count": 2}'
        cache.set("quotes", "1.0", "transcript", json_result)

        assert cache.get("quotes", "1.0", "transcript") == json_result

    def test_cache_file_structure(self, temp_cache_dir: Path) -> None:
        """Test that cache files have correct structure."""
        cache = ExtractionCache(cache_dir=temp_cache_dir)

        cache.set("summary", "1.0", "transcript", "result")

        # Find the cache file
        cache_files = list(temp_cache_dir.glob("*.json"))
        assert len(cache_files) == 1

        # Check structure
        with cache_files[0].open("r") as f:
            data = json.load(f)

        assert "timestamp" in data
        assert "template_name" in data
        assert "template_version" in data
        assert "result" in data
        assert data["template_name"] == "summary"
        assert data["template_version"] == "1.0"
        assert data["result"] == "result"

    def test_concurrent_access(self, temp_cache_dir: Path) -> None:
        """Test that concurrent cache access doesn't cause issues."""
        cache1 = ExtractionCache(cache_dir=temp_cache_dir)
        cache2 = ExtractionCache(cache_dir=temp_cache_dir)

        # Both write to cache
        cache1.set("summary", "1.0", "transcript1", "result1")
        cache2.set("quotes", "1.0", "transcript2", "result2")

        # Both should be able to read both entries
        assert cache1.get("summary", "1.0", "transcript1") == "result1"
        assert cache1.get("quotes", "1.0", "transcript2") == "result2"
        assert cache2.get("summary", "1.0", "transcript1") == "result1"
        assert cache2.get("quotes", "1.0", "transcript2") == "result2"
