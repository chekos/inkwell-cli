"""Unit tests for generic FileCache."""

import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from inkwell.utils.cache import FileCache


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


class TestFileCache:
    """Tests for generic FileCache."""

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        """Test cache creates directory if it doesn't exist."""
        cache_dir = tmp_path / "nonexistent" / "cache"
        assert not cache_dir.exists()

        _cache = FileCache[str](cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_init_with_custom_ttl(self, temp_cache_dir: Path) -> None:
        """Test cache initialization with custom TTL."""
        cache = FileCache[str](cache_dir=temp_cache_dir, ttl_days=15)
        assert cache.ttl_days == 15

    @pytest.mark.asyncio
    async def test_set_and_get_string(self, temp_cache_dir: Path) -> None:
        """Test setting and getting cached string values."""
        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        await cache.set("key1", value="test value")
        result = await cache.get("key1")
        assert result == "test value"

    @pytest.mark.asyncio
    async def test_set_and_get_dict(self, temp_cache_dir: Path) -> None:
        """Test setting and getting cached dict values."""
        cache = FileCache[dict](
            cache_dir=temp_cache_dir,
            serializer=lambda x: x,  # Dict can be serialized as-is
            deserializer=lambda d: d,
        )

        test_data = {"name": "test", "count": 42}
        await cache.set("key1", value=test_data)
        result = await cache.get("key1")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, temp_cache_dir: Path) -> None:
        """Test getting non-existent cache entry returns None."""
        cache = FileCache[str](cache_dir=temp_cache_dir)
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_keys(self, temp_cache_dir: Path) -> None:
        """Test caching multiple keys with different values."""
        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        await cache.set("key1", value="value1")
        await cache.set("key2", value="value2")
        await cache.set("key3", value="value3")

        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"

    @pytest.mark.asyncio
    async def test_overwrite_existing_key(self, temp_cache_dir: Path) -> None:
        """Test overwriting existing cache entry."""
        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        await cache.set("key1", value="original")
        await cache.set("key1", value="updated")

        result = await cache.get("key1")
        assert result == "updated"

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, temp_cache_dir: Path) -> None:
        """Test that cache entries expire after TTL."""
        # Very short TTL for testing (1 second = 1/86400 days)
        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            ttl_days=1 / 86400,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        await cache.set("key1", value="test")
        assert await cache.get("key1") == "test"

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_existing(self, temp_cache_dir: Path) -> None:
        """Test deleting existing entry."""
        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        await cache.set("key1", value="test")
        result = await cache.delete("key1")

        assert result is True
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, temp_cache_dir: Path) -> None:
        """Test deleting non-existent entry."""
        cache = FileCache[str](cache_dir=temp_cache_dir)
        result = await cache.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_all(self, temp_cache_dir: Path) -> None:
        """Test clearing all cache entries."""
        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        # Add multiple entries
        await cache.set("key1", value="value1")
        await cache.set("key2", value="value2")
        await cache.set("key3", value="value3")

        # Clear all
        count = await cache.clear()
        assert count == 3

        # Verify all cleared
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert await cache.get("key3") is None

    @pytest.mark.asyncio
    async def test_clear_empty(self, temp_cache_dir: Path) -> None:
        """Test clearing empty cache."""
        cache = FileCache[str](cache_dir=temp_cache_dir)
        count = await cache.clear()
        assert count == 0

    @pytest.mark.asyncio
    async def test_clear_expired(self, temp_cache_dir: Path) -> None:
        """Test clearing only expired entries."""
        # Create cache with short TTL
        short_cache = FileCache[str](
            cache_dir=temp_cache_dir,
            ttl_days=1 / 86400,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        # Add entry that will expire
        await short_cache.set("old", value="old value")
        time.sleep(1.1)

        # Create new cache with long TTL
        long_cache = FileCache[str](
            cache_dir=temp_cache_dir,
            ttl_days=30,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        # Add entry that won't expire
        await long_cache.set("new", value="new value")

        # Clear expired using short cache
        count = await short_cache.clear_expired()
        assert count == 1

        # Old should be gone, new should remain
        assert await short_cache.get("old") is None
        assert await long_cache.get("new") == "new value"

    @pytest.mark.asyncio
    async def test_stats_empty(self, temp_cache_dir: Path) -> None:
        """Test stats for empty cache."""
        cache = FileCache[str](cache_dir=temp_cache_dir)
        stats = await cache.stats()

        assert stats["total"] == 0
        assert stats["expired"] == 0
        assert stats["valid"] == 0
        assert stats["size_bytes"] == 0
        assert "cache_dir" in stats

    @pytest.mark.asyncio
    async def test_stats_with_entries(self, temp_cache_dir: Path) -> None:
        """Test stats with cached entries."""
        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        # Add entries
        await cache.set("key1", value="value1")
        await cache.set("key2", value="value2")

        stats = await cache.stats()
        assert stats["total"] == 2
        assert stats["valid"] == 2
        assert stats["expired"] == 0
        assert stats["size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_corrupted_cache_file_removed(self, temp_cache_dir: Path) -> None:
        """Test that corrupted cache files are removed."""
        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        # Create corrupted cache file
        cache_key = cache.key_generator("key1")
        cache_file = temp_cache_dir / f"{cache_key}.json"
        cache_file.write_text("not valid json {{{")

        # Try to get from cache (should handle gracefully)
        result = await cache.get("key1")
        assert result is None
        assert not cache_file.exists()

    @pytest.mark.asyncio
    async def test_custom_key_generator(self, temp_cache_dir: Path) -> None:
        """Test cache with custom key generator."""

        def custom_key_gen(prefix: str, id: int) -> str:
            return f"{prefix}_{id}"

        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            key_generator=custom_key_gen,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        await cache.set("user", 123, value="test user")
        result = await cache.get("user", 123)
        assert result == "test user"

    @pytest.mark.asyncio
    async def test_atomic_write(self, temp_cache_dir: Path) -> None:
        """Test that writes are atomic (temp file + rename)."""
        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        await cache.set("key1", value="test")

        # Verify final file exists
        cache_key = cache.key_generator("key1")
        cache_file = temp_cache_dir / f"{cache_key}.json"
        assert cache_file.exists()

        # Verify temp file doesn't exist
        temp_file = cache_file.with_suffix(".tmp")
        assert not temp_file.exists()

    @pytest.mark.asyncio
    async def test_cache_file_structure(self, temp_cache_dir: Path) -> None:
        """Test that cache files have correct structure."""
        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        await cache.set("key1", value="test")

        # Find the cache file
        cache_files = list(temp_cache_dir.glob("*.json"))
        assert len(cache_files) == 1

        # Check structure
        with cache_files[0].open("r") as f:
            data = json.load(f)

        assert "cached_at" in data
        assert "value" in data
        assert data["value"]["value"] == "test"

        # Verify timestamp is valid
        cached_at = datetime.fromisoformat(data["cached_at"])
        assert cached_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_persists_across_instances(self, temp_cache_dir: Path) -> None:
        """Test that cache persists across FileCache instances."""
        # First instance
        cache1 = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )
        await cache1.set("key1", value="cached value")

        # Second instance (same directory)
        cache2 = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )
        assert await cache2.get("key1") == "cached value"

    @pytest.mark.asyncio
    async def test_special_characters_in_value(self, temp_cache_dir: Path) -> None:
        """Test caching values with special characters."""
        cache = FileCache[str](
            cache_dir=temp_cache_dir,
            serializer=lambda x: {"value": x},
            deserializer=lambda d: d["value"],
        )

        special_value = 'Value with "quotes", newlines\nand\ttabs'
        await cache.set("key1", value=special_value)

        assert await cache.get("key1") == special_value

    @pytest.mark.asyncio
    async def test_default_serializer_with_dict(self, temp_cache_dir: Path) -> None:
        """Test default serializer works with dict values."""
        cache = FileCache[dict](cache_dir=temp_cache_dir)

        test_data = {"name": "test", "count": 42}
        await cache.set("key1", value=test_data)
        result = await cache.get("key1")
        assert result == test_data
