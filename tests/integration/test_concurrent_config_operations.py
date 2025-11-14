"""Integration tests for concurrent ConfigManager operations.

Tests file locking behavior under concurrent access scenarios to ensure
data integrity and prevent race conditions.
"""

import multiprocessing
import time
from pathlib import Path

import pytest

from inkwell.config.manager import ConfigManager
from inkwell.config.schema import FeedConfig


@pytest.fixture
def shared_config_dir(tmp_path):
    """Create a shared config directory for concurrent tests."""
    config_dir = tmp_path / "shared_config"
    config_dir.mkdir()
    return config_dir


def add_feed_process(config_dir: Path, feed_num: int, delay: float = 0.0):
    """Process function to add a single feed.

    Args:
        config_dir: Shared config directory
        feed_num: Feed number to add
        delay: Optional delay before operation (for timing control)
    """
    if delay > 0:
        time.sleep(delay)

    manager = ConfigManager(config_dir=config_dir)
    feed_config = FeedConfig(url=f"https://example.com/feed{feed_num}.rss")  # type: ignore
    manager.add_feed(f"feed{feed_num}", feed_config)


def remove_feed_process(config_dir: Path, feed_name: str, delay: float = 0.0):
    """Process function to remove a single feed.

    Args:
        config_dir: Shared config directory
        feed_name: Feed name to remove
        delay: Optional delay before operation (for timing control)
    """
    if delay > 0:
        time.sleep(delay)

    manager = ConfigManager(config_dir=config_dir)
    try:
        manager.remove_feed(feed_name)
    except Exception:
        # Feed might not exist, ignore
        pass


def update_feed_process(config_dir: Path, feed_name: str, new_category: str, delay: float = 0.0):
    """Process function to update a single feed.

    Args:
        config_dir: Shared config directory
        feed_name: Feed name to update
        new_category: New category value
        delay: Optional delay before operation (for timing control)
    """
    if delay > 0:
        time.sleep(delay)

    manager = ConfigManager(config_dir=config_dir)
    try:
        feed = manager.get_feed(feed_name)
        feed.category = new_category
        manager.update_feed(feed_name, feed)
    except Exception:
        # Feed might not exist, ignore
        pass


class TestConcurrentConfigOperations:
    """Tests for concurrent ConfigManager operations."""

    def test_concurrent_add_feeds_no_data_loss(self, shared_config_dir):
        """Test that concurrent feed additions don't lose data.

        This is the primary race condition scenario: multiple processes
        trying to add different feeds simultaneously.
        """
        num_feeds = 10
        processes = []

        # Launch concurrent processes to add feeds
        for i in range(num_feeds):
            p = multiprocessing.Process(
                target=add_feed_process,
                args=(shared_config_dir, i),
            )
            processes.append(p)
            p.start()

        # Wait for all processes to complete
        for p in processes:
            p.join(timeout=5)

        # Verify all feeds were saved
        manager = ConfigManager(config_dir=shared_config_dir)
        feeds = manager.list_feeds()

        assert len(feeds) == num_feeds, f"Expected {num_feeds} feeds, got {len(feeds)}"

        # Verify all feed names are present
        for i in range(num_feeds):
            assert f"feed{i}" in feeds, f"Feed 'feed{i}' missing from saved feeds"

    def test_concurrent_mixed_operations(self, shared_config_dir):
        """Test concurrent add, update, and remove operations.

        More complex scenario with different operation types.
        The main goal is to verify no data loss and corruption,
        not that every operation succeeds (some may fail due to timing).
        """
        # Pre-populate with some feeds
        manager = ConfigManager(config_dir=shared_config_dir)
        for i in range(5):
            feed_config = FeedConfig(
                url=f"https://example.com/initial{i}.rss",  # type: ignore
                category="initial",
            )
            manager.add_feed(f"initial{i}", feed_config)

        processes = []

        # Add new feeds concurrently
        for i in range(5, 10):
            p = multiprocessing.Process(
                target=add_feed_process,
                args=(shared_config_dir, i),
            )
            processes.append(p)

        # Remove some feeds concurrently
        for i in range(3, 5):
            p = multiprocessing.Process(
                target=remove_feed_process,
                args=(shared_config_dir, f"initial{i}"),
            )
            processes.append(p)

        # Start all processes
        for p in processes:
            p.start()

        # Wait for completion
        for p in processes:
            p.join(timeout=5)

        # Verify final state
        manager = ConfigManager(config_dir=shared_config_dir)
        feeds = manager.list_feeds()

        # Should have: 3 initial feeds (0,1,2) + 5 new feeds (5-9) = 8 feeds
        # initial3 and initial4 were removed
        assert len(feeds) == 8, f"Expected 8 feeds, got {len(feeds)}"

        # Check all new feeds were added
        for i in range(5, 10):
            assert f"feed{i}" in feeds, f"New feed{i} should exist"

        # Check removed feeds are gone
        for i in range(3, 5):
            assert f"initial{i}" not in feeds, f"Feed initial{i} should be removed"

        # Check remaining initial feeds still exist
        for i in range(3):
            assert f"initial{i}" in feeds, f"Feed initial{i} should still exist"

    def test_lock_released_after_operation(self, shared_config_dir):
        """Test that locks are properly released after operations.

        The lock file may or may not persist on disk (OS-dependent), but
        we verify that the lock is released by successfully performing
        multiple sequential operations without blocking.
        """
        manager = ConfigManager(config_dir=shared_config_dir)
        feed_config = FeedConfig(url="https://example.com/test.rss")  # type: ignore

        # Add a feed (this should acquire and release a lock)
        manager.add_feed("test-feed", feed_config)

        # We should be able to acquire the lock again immediately for update
        # If the lock wasn't released, this would hang indefinitely
        manager.update_feed("test-feed", feed_config)

        # Should still be able to read (doesn't need a lock)
        feed = manager.get_feed("test-feed")
        assert feed is not None

        # And we should be able to acquire the lock again for removal
        manager.remove_feed("test-feed")

        # Verify successful removal
        feeds = manager.list_feeds()
        assert "test-feed" not in feeds

    def test_sequential_operations_work_correctly(self, shared_config_dir):
        """Test that locking doesn't break normal sequential operations."""
        manager = ConfigManager(config_dir=shared_config_dir)

        # Add feed
        feed_config = FeedConfig(
            url="https://example.com/test.rss",  # type: ignore
            category="tech",
        )
        manager.add_feed("test", feed_config)

        # Update feed
        feed_config.category = "interview"
        manager.update_feed("test", feed_config)

        # Read feed
        feed = manager.get_feed("test")
        assert feed.category == "interview"

        # Remove feed
        manager.remove_feed("test")

        # Verify removed
        feeds = manager.list_feeds()
        assert "test" not in feeds
