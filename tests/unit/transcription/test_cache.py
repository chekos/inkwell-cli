"""Tests for transcript cache."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from inkwell.transcription import Transcript, TranscriptCache, TranscriptSegment


class TestTranscriptCache:
    """Test TranscriptCache class."""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path: Path) -> Path:
        """Create temporary cache directory."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        return cache_dir

    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> TranscriptCache:
        """Create TranscriptCache instance."""
        return TranscriptCache(cache_dir=temp_cache_dir, ttl_days=30)

    @pytest.fixture
    def sample_transcript(self) -> Transcript:
        """Create sample transcript."""
        return Transcript(
            segments=[
                TranscriptSegment(text="Hello world", start=0.0, duration=2.0),
                TranscriptSegment(text="Test transcript", start=2.0, duration=3.0),
            ],
            source="youtube",
            language="en",
            episode_url="https://example.com/episode",
        )

    def test_initialization(self, temp_cache_dir: Path) -> None:
        """Test cache initialization."""
        cache = TranscriptCache(cache_dir=temp_cache_dir, ttl_days=15)

        assert cache.cache_dir == temp_cache_dir
        assert cache.ttl_days == 15
        assert temp_cache_dir.exists()

    def test_initialization_creates_directory(self, tmp_path: Path) -> None:
        """Test cache creates directory if it doesn't exist."""
        cache_dir = tmp_path / "new" / "cache"
        assert not cache_dir.exists()

        cache = TranscriptCache(cache_dir=cache_dir)

        assert cache.cache_dir == cache_dir
        assert cache_dir.exists()

    def test_initialization_default_directory(self) -> None:
        """Test cache uses XDG directory by default."""
        cache = TranscriptCache()

        # Should use platformdirs
        assert "inkwell" in str(cache.cache_dir).lower()
        assert cache.cache_dir.exists()

    def test_get_cache_key(self, cache: TranscriptCache) -> None:
        """Test cache key generation."""
        url = "https://example.com/episode"
        key = cache._get_cache_key(url)

        # Should be SHA256 hex digest
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

        # Same URL should produce same key
        assert cache._get_cache_key(url) == key

        # Different URL should produce different key
        assert cache._get_cache_key("https://different.com") != key

    def test_get_cache_path(self, cache: TranscriptCache, temp_cache_dir: Path) -> None:
        """Test cache path generation."""
        url = "https://example.com/episode"
        path = cache._get_cache_path(url)

        assert path.parent == temp_cache_dir
        assert path.suffix == ".json"
        assert len(path.stem) == 64  # SHA256 hash length

    def test_is_expired_fresh(self, cache: TranscriptCache) -> None:
        """Test expiration check for fresh entry."""
        now = datetime.now(timezone.utc)
        assert cache._is_expired(now) is False

    def test_is_expired_old(self, cache: TranscriptCache) -> None:
        """Test expiration check for old entry."""
        old_time = datetime.now(timezone.utc) - timedelta(days=31)
        assert cache._is_expired(old_time) is True

    def test_is_expired_boundary(self, cache: TranscriptCache) -> None:
        """Test expiration check at exact boundary."""
        boundary_time = datetime.now(timezone.utc) - timedelta(days=30, seconds=1)
        assert cache._is_expired(boundary_time) is True

        just_before = datetime.now(timezone.utc) - timedelta(days=29, hours=23)
        assert cache._is_expired(just_before) is False

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache: TranscriptCache, sample_transcript: Transcript) -> None:
        """Test caching and retrieval."""
        url = "https://example.com/episode"

        # Cache transcript
        await cache.set(url, sample_transcript)

        # Retrieve transcript
        cached = await cache.get(url)

        assert cached is not None
        assert len(cached.segments) == 2
        assert cached.segments[0].text == "Hello world"
        assert cached.segments[1].text == "Test transcript"
        assert cached.source == "cached"  # Source updated to indicate cache hit
        assert cached.language == "en"

    @pytest.mark.asyncio
    async def test_get_missing(self, cache: TranscriptCache) -> None:
        """Test retrieval of non-existent entry."""
        result = await cache.get("https://nonexistent.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_expired(
        self, cache: TranscriptCache, sample_transcript: Transcript, temp_cache_dir: Path
    ) -> None:
        """Test retrieval of expired entry."""
        url = "https://example.com/episode"
        cache_path = cache._get_cache_path(url)

        # Create expired cache entry
        data = {
            "cached_at": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
            "episode_url": url,
            "transcript": sample_transcript.model_dump(mode="json"),
        }

        with cache_path.open("w") as f:
            json.dump(data, f)

        # Should return None and delete expired entry
        result = await cache.get(url)

        assert result is None
        assert not cache_path.exists()

    @pytest.mark.asyncio
    async def test_get_corrupted_file(self, cache: TranscriptCache, temp_cache_dir: Path) -> None:
        """Test retrieval with corrupted cache file."""
        url = "https://example.com/episode"
        cache_path = cache._get_cache_path(url)

        # Create corrupted cache file
        cache_path.write_text("invalid json{")

        # Should return None and remove corrupted file
        result = await cache.get(url)

        assert result is None
        assert not cache_path.exists()

    @pytest.mark.asyncio
    async def test_set_with_metadata(
        self, cache: TranscriptCache, sample_transcript: Transcript
    ) -> None:
        """Test that cached data includes metadata."""
        url = "https://example.com/episode"
        await cache.set(url, sample_transcript)

        cache_path = cache._get_cache_path(url)
        with cache_path.open("r") as f:
            data = json.load(f)

        assert "cached_at" in data
        assert "value" in data
        assert "episode_url" in data["value"]
        assert "transcript" in data["value"]
        assert data["value"]["episode_url"] == url

        # Verify timestamp is valid
        cached_at = datetime.fromisoformat(data["cached_at"])
        assert cached_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_set_preserves_cost_metadata(self, cache: TranscriptCache) -> None:
        """Test that cost metadata is preserved in cache."""
        transcript = Transcript(
            segments=[TranscriptSegment(text="Test", start=0.0, duration=1.0)],
            source="gemini",
            language="en",
            episode_url="https://example.com/episode",
            cost_usd=0.001,
        )

        url = "https://example.com/episode"
        await cache.set(url, transcript)

        cached = await cache.get(url)
        assert cached is not None
        assert cached.cost_usd == 0.001

    @pytest.mark.asyncio
    async def test_delete_existing(
        self, cache: TranscriptCache, sample_transcript: Transcript
    ) -> None:
        """Test deleting existing entry."""
        url = "https://example.com/episode"
        await cache.set(url, sample_transcript)

        result = await cache.delete(url)

        assert result is True
        assert await cache.get(url) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache: TranscriptCache) -> None:
        """Test deleting non-existent entry."""
        result = await cache.delete("https://nonexistent.com")

        assert result is False

    @pytest.mark.asyncio
    async def test_clear(self, cache: TranscriptCache, sample_transcript: Transcript) -> None:
        """Test clearing all cache entries."""
        # Add multiple entries
        await cache.set("https://example.com/episode1", sample_transcript)
        await cache.set("https://example.com/episode2", sample_transcript)
        await cache.set("https://example.com/episode3", sample_transcript)

        count = await cache.clear()

        assert count == 3
        assert await cache.get("https://example.com/episode1") is None
        assert await cache.get("https://example.com/episode2") is None
        assert await cache.get("https://example.com/episode3") is None

    @pytest.mark.asyncio
    async def test_clear_empty(self, cache: TranscriptCache) -> None:
        """Test clearing empty cache."""
        count = await cache.clear()

        assert count == 0

    @pytest.mark.asyncio
    async def test_clear_expired(
        self, cache: TranscriptCache, sample_transcript: Transcript, temp_cache_dir: Path
    ) -> None:
        """Test clearing only expired entries."""
        # Add fresh entry
        fresh_url = "https://example.com/fresh"
        await cache.set(fresh_url, sample_transcript)

        # Add expired entry
        expired_url = "https://example.com/expired"
        expired_path = cache._get_cache_path(expired_url)
        data = {
            "cached_at": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
            "episode_url": expired_url,
            "transcript": sample_transcript.model_dump(mode="json"),
        }
        with expired_path.open("w") as f:
            json.dump(data, f)

        count = await cache.clear_expired()

        assert count == 1
        assert await cache.get(fresh_url) is not None  # Fresh entry still there
        assert not expired_path.exists()  # Expired entry removed

    @pytest.mark.asyncio
    async def test_clear_expired_corrupted(
        self, cache: TranscriptCache, temp_cache_dir: Path
    ) -> None:
        """Test that clear_expired removes corrupted files."""
        # Create corrupted file
        corrupted_path = temp_cache_dir / "corrupted.json"
        corrupted_path.write_text("invalid json{")

        count = await cache.clear_expired()

        assert count == 1
        assert not corrupted_path.exists()

    @pytest.mark.asyncio
    async def test_stats_empty(self, cache: TranscriptCache) -> None:
        """Test stats for empty cache."""
        stats = await cache.stats()

        assert stats["total"] == 0
        assert stats["expired"] == 0
        assert stats["valid"] == 0
        assert stats["size_bytes"] == 0
        assert stats["sources"] == {}
        assert "cache_dir" in stats

    @pytest.mark.asyncio
    async def test_stats_with_entries(
        self, cache: TranscriptCache, sample_transcript: Transcript, temp_cache_dir: Path
    ) -> None:
        """Test stats with multiple entries."""
        # Add fresh entries
        await cache.set("https://example.com/episode1", sample_transcript)

        transcript2 = Transcript(
            segments=[TranscriptSegment(text="Test", start=0.0, duration=1.0)],
            source="gemini",
            language="en",
            episode_url="https://example.com/episode2",
        )
        await cache.set("https://example.com/episode2", transcript2)

        # Add expired entry
        expired_url = "https://example.com/expired"
        expired_path = cache._get_cache_path(expired_url)
        data = {
            "cached_at": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
            "episode_url": expired_url,
            "transcript": sample_transcript.model_dump(mode="json"),
        }
        with expired_path.open("w") as f:
            json.dump(data, f)

        stats = await cache.stats()

        assert stats["total"] == 3
        assert stats["expired"] == 1
        assert stats["valid"] == 2
        assert stats["size_bytes"] > 0
        assert stats["sources"]["youtube"] == 2  # Original source preserved
        assert stats["sources"]["gemini"] == 1

    @pytest.mark.asyncio
    async def test_stats_with_corrupted(self, cache: TranscriptCache, temp_cache_dir: Path) -> None:
        """Test that stats counts but skips processing corrupted files."""
        # Create corrupted file
        corrupted_path = temp_cache_dir / "corrupted.json"
        corrupted_path.write_text("invalid json{")

        stats = await cache.stats()

        # Should count the file but not crash processing it
        assert stats["total"] == 1
        assert stats["expired"] == 0
        assert stats["valid"] == 1  # Can't determine expiration, counts as valid
        assert stats["sources"] == {}  # No source info extracted

    @pytest.mark.asyncio
    async def test_cache_atomic_write(
        self, cache: TranscriptCache, sample_transcript: Transcript, temp_cache_dir: Path
    ) -> None:
        """Test that writes are atomic (temp file + rename)."""
        url = "https://example.com/episode"

        await cache.set(url, sample_transcript)

        # Verify final file exists
        cache_path = cache._get_cache_path(url)
        assert cache_path.exists()

        # Verify temp file doesn't exist
        temp_path = cache_path.with_suffix(".tmp")
        assert not temp_path.exists()

    @pytest.mark.asyncio
    async def test_cache_different_ttl(
        self, temp_cache_dir: Path, sample_transcript: Transcript
    ) -> None:
        """Test cache with different TTL."""
        cache = TranscriptCache(cache_dir=temp_cache_dir, ttl_days=7)

        url = "https://example.com/episode"
        cache_path = cache._get_cache_path(url)

        # Create entry that's 8 days old (expired for 7-day TTL)
        data = {
            "cached_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
            "episode_url": url,
            "transcript": sample_transcript.model_dump(mode="json"),
        }
        with cache_path.open("w") as f:
            json.dump(data, f)

        # Should be expired
        result = await cache.get(url)
        assert result is None
        assert not cache_path.exists()
