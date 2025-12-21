"""Cost tracking utilities for API usage.

This module provides tools to track and analyze API costs across:
- Different providers (Gemini, Claude, etc.)
- Different operations (transcription, extraction, tag generation)
- Different podcasts and episodes

Based on actual API usage data, not estimates.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from inkwell.utils.datetime import now_utc, validate_timezone_aware
from inkwell.utils.logging import get_logger

# Cross-platform file locking
if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

logger = get_logger()


# Provider pricing (USD per million tokens)
class ProviderPricing(BaseModel):
    """Pricing information for an API provider."""

    provider: str
    model: str
    input_price_per_m: float = Field(ge=0, description="Input token price per million")
    output_price_per_m: float = Field(ge=0, description="Output token price per million")

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for given token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        input_cost = (input_tokens / 1_000_000) * self.input_price_per_m
        output_cost = (output_tokens / 1_000_000) * self.output_price_per_m
        return input_cost + output_cost


# Current pricing for supported providers (as of Nov 2024)
PROVIDER_PRICING = {
    "gemini-flash": ProviderPricing(
        provider="gemini",
        model="gemini-2.5-flash",
        input_price_per_m=0.075,  # <128K tokens
        output_price_per_m=0.30,
    ),
    "gemini-flash-long": ProviderPricing(
        provider="gemini",
        model="gemini-2.5-flash",
        input_price_per_m=0.15,  # >128K tokens
        output_price_per_m=0.30,
    ),
    "claude-sonnet": ProviderPricing(
        provider="claude",
        model="claude-3-5-sonnet-20241022",
        input_price_per_m=3.00,
        output_price_per_m=15.00,
    ),
}


class APIUsage(BaseModel):
    """API usage information for a single operation.

    Tracks actual token usage and calculated cost.
    """

    # Unique identifier for true deduplication
    usage_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique identifier for this usage record"
    )

    provider: Literal["gemini", "claude", "youtube"] = Field(..., description="API provider")
    model: str = Field(..., description="Model used (e.g., gemini-2.5-flash)")
    operation: Literal["transcription", "extraction", "tag_generation", "interview"] = Field(
        ..., description="Type of operation"
    )

    # Token usage
    input_tokens: int = Field(0, ge=0, description="Input tokens used")
    output_tokens: int = Field(0, ge=0, description="Output tokens used")
    total_tokens: int = Field(0, ge=0, description="Total tokens used")

    # Cost
    cost_usd: float = Field(0.0, ge=0, description="Cost in USD")

    # Context
    timestamp: datetime = Field(default_factory=now_utc, description="When operation occurred")
    episode_title: str | None = Field(None, description="Episode title if applicable")
    template_name: str | None = Field(None, description="Template name if applicable")

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware."""
        if isinstance(v, datetime):
            if v.tzinfo is None:
                # Assume UTC for naive datetimes
                return v.replace(tzinfo=timezone.utc)
        return v

    def model_post_init(self, __context: Any) -> None:
        """Calculate derived fields after initialization."""
        # Calculate total tokens if not set
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens

        # Validate timestamp is timezone-aware (runtime check)
        validate_timezone_aware(self.timestamp, "timestamp")


class CostSummary(BaseModel):
    """Summary of costs across multiple operations."""

    total_operations: int = Field(0, ge=0)
    total_input_tokens: int = Field(0, ge=0)
    total_output_tokens: int = Field(0, ge=0)
    total_tokens: int = Field(0, ge=0)
    total_cost_usd: float = Field(0.0, ge=0)

    # Breakdown by provider
    costs_by_provider: dict[str, float] = Field(default_factory=dict)

    # Breakdown by operation
    costs_by_operation: dict[str, float] = Field(default_factory=dict)

    # Breakdown by episode
    costs_by_episode: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def from_usage_list(cls, usage_list: list[APIUsage]) -> "CostSummary":
        """Create summary from list of API usage records.

        Args:
            usage_list: List of APIUsage records

        Returns:
            CostSummary aggregating all usage
        """
        summary = cls()
        summary.total_operations = len(usage_list)

        for usage in usage_list:
            # Aggregate totals
            summary.total_input_tokens += usage.input_tokens
            summary.total_output_tokens += usage.output_tokens
            summary.total_tokens += usage.total_tokens
            summary.total_cost_usd += usage.cost_usd

            # Breakdown by provider
            provider = usage.provider
            summary.costs_by_provider[provider] = (
                summary.costs_by_provider.get(provider, 0.0) + usage.cost_usd
            )

            # Breakdown by operation
            operation = usage.operation
            summary.costs_by_operation[operation] = (
                summary.costs_by_operation.get(operation, 0.0) + usage.cost_usd
            )

            # Breakdown by episode
            if usage.episode_title:
                summary.costs_by_episode[usage.episode_title] = (
                    summary.costs_by_episode.get(usage.episode_title, 0.0) + usage.cost_usd
                )

        return summary


class CostTracker:
    """Track and persist API costs to disk.

    Stores cost data in a JSON file for later analysis.
    Supports dependency injection pattern for testability.
    """

    def __init__(self, costs_file: Path | None = None):
        """Initialize cost tracker.

        Args:
            costs_file: Path to costs JSON file (default: ~/.config/inkwell/costs.json)
        """
        if costs_file is None:
            from inkwell.utils.paths import get_config_dir

            config_dir = get_config_dir()
            costs_file = config_dir / "costs.json"

        self.costs_file = costs_file
        self.costs_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing costs
        self.usage_history: list[APIUsage] = []
        if self.costs_file.exists():
            self._load()

        # In-memory tracking for current session
        self._session_cost = 0.0

    def _load(self) -> None:
        """Load costs from disk with shared lock."""
        try:
            with open(self.costs_file) as f:
                # Acquire shared lock for reading
                self._acquire_lock(f, exclusive=False)
                try:
                    data = json.load(f)
                    # Migrate old records without usage_id
                    needs_migration = False
                    for item in data:
                        if "usage_id" not in item:
                            item["usage_id"] = str(uuid4())
                            needs_migration = True

                    self.usage_history = [APIUsage.model_validate(item) for item in data]
                finally:
                    self._release_lock(f)

            # Save migrated data back to disk (outside the lock context)
            if needs_migration:
                logger.info("Migrated %d cost records to include usage_id", len(data))
                # Write directly to file to avoid merge logic
                temp_fd, temp_path = tempfile.mkstemp(
                    dir=self.costs_file.parent, prefix=".tmp_costs_", suffix=".json"
                )
                try:
                    with open(temp_fd, "w") as f:
                        json.dump(data, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                    # Atomic replace
                    Path(temp_path).replace(self.costs_file)
                except Exception:
                    Path(temp_path).unlink(missing_ok=True)
                    raise
        except (json.JSONDecodeError, ValueError) as e:
            # Corrupt file - try backup
            logger.warning("Failed to load costs file: %s", e)
            self._load_from_backup()

    def _load_from_backup(self) -> None:
        """Load from backup file if main file is corrupt."""
        backup_file = self.costs_file.with_suffix(".json.bak")
        if backup_file.exists():
            try:
                with open(backup_file) as f:
                    data = json.load(f)
                    self.usage_history = [APIUsage.model_validate(item) for item in data]
                logger.warning("Loaded costs from backup: %s", backup_file)
                return
            except Exception as e:
                logger.warning("Backup file also corrupt: %s", e)

        # Both failed - archive corrupt file
        if self.costs_file.exists():
            corrupt_backup = self.costs_file.with_suffix(f".json.corrupt.{int(time.time())}")
            try:
                self.costs_file.rename(corrupt_backup)
                logger.error("Archived corrupt cost file to %s", corrupt_backup)
            except Exception as e:
                logger.error("Failed to archive corrupt file: %s", e)

        self.usage_history = []

    def _acquire_lock(self, file_obj: IO[str], exclusive: bool = True) -> None:
        """Acquire file lock (cross-platform).

        Args:
            file_obj: Open file object
            exclusive: If True, acquire exclusive lock; if False, acquire shared lock
        """
        if sys.platform == "win32":
            # Windows: msvcrt locking
            # Note: msvcrt doesn't support shared locks, always exclusive
            msvcrt.locking(file_obj.fileno(), msvcrt.LK_LOCK, 1)
        else:
            # POSIX: fcntl locking
            lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(file_obj.fileno(), lock_type)

    def _release_lock(self, file_obj: IO[str]) -> None:
        """Release file lock (cross-platform).

        Args:
            file_obj: Open file object
        """
        if sys.platform == "win32":
            # Windows: msvcrt unlock
            msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            # POSIX: fcntl unlock
            fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)

    def _save(self) -> None:
        """Save costs to disk with file locking and atomic write."""
        # Create backup first if file exists
        backup_file = self.costs_file.with_suffix(".json.bak")
        if self.costs_file.exists() and self.costs_file.stat().st_size > 0:
            try:
                shutil.copy2(self.costs_file, backup_file)
            except Exception as e:
                logger.warning("Failed to create backup: %s", e)

        # Atomic write with exclusive lock
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.costs_file.parent, prefix=".tmp_costs_", suffix=".json"
        )

        try:
            # Open file in 'a+' mode which creates it if it doesn't exist
            # This is safer for concurrent access
            with open(self.costs_file, "a+") as lock_file:
                # Acquire exclusive lock
                self._acquire_lock(lock_file, exclusive=True)

                try:
                    # Re-read to get latest data (another process might have written)
                    lock_file.seek(0)
                    content = lock_file.read()

                    # Parse existing data
                    try:
                        if content.strip():
                            existing_data = json.loads(content)
                            existing = [APIUsage.model_validate(item) for item in existing_data]
                        else:
                            existing = []
                    except (json.JSONDecodeError, ValueError):
                        existing = []

                    # Merge: add entries not already present (by unique usage_id)
                    # This prevents false duplicates when same episode is processed again
                    existing_ids = {u.usage_id for u in existing}
                    new_entries = [u for u in self.usage_history if u.usage_id not in existing_ids]
                    combined = existing + new_entries

                    # Write to temp file
                    with open(temp_fd, "w") as f:
                        data = [usage.model_dump(mode="json") for usage in combined]
                        json.dump(data, f, indent=2, default=str)
                        f.flush()
                        os.fsync(f.fileno())

                    # Atomic replace
                    Path(temp_path).replace(self.costs_file)

                    # Update in-memory state
                    self.usage_history = combined

                finally:
                    self._release_lock(lock_file)

        except Exception:
            # Clean up temp file on error
            Path(temp_path).unlink(missing_ok=True)
            raise

    def track(self, usage: APIUsage) -> None:
        """Track a new API usage.

        Args:
            usage: APIUsage record to track
        """
        self.usage_history.append(usage)
        self._session_cost += usage.cost_usd
        self._save()

    def add_cost(
        self,
        provider: str,
        model: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        episode_title: str | None = None,
        template_name: str | None = None,
    ) -> float:
        """Add a cost record and return the calculated cost.

        This is the primary method for managers to track costs.

        Args:
            provider: API provider (gemini, claude, youtube)
            model: Model used
            operation: Operation type (transcription, extraction, etc.)
            input_tokens: Input tokens used
            output_tokens: Output tokens used
            episode_title: Optional episode title
            template_name: Optional template name

        Returns:
            Cost in USD for this operation
        """
        # Calculate cost
        cost_usd = calculate_cost_from_usage(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        # Create usage record
        usage = APIUsage(
            provider=provider,  # type: ignore[arg-type]
            model=model,
            operation=operation,  # type: ignore[arg-type]
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            episode_title=episode_title,
            template_name=template_name,
        )

        # Track it
        self.track(usage)

        return cost_usd

    def get_session_cost(self) -> float:
        """Get total cost for current session.

        Returns:
            Total cost in USD for operations tracked since initialization
        """
        return self._session_cost

    def reset_session_cost(self) -> None:
        """Reset session cost tracking to zero.

        This does not affect persisted usage history.
        """
        self._session_cost = 0.0

    def get_summary(
        self,
        provider: str | None = None,
        operation: str | None = None,
        episode_title: str | None = None,
        since: datetime | None = None,
    ) -> CostSummary:
        """Get cost summary with optional filters.

        Args:
            provider: Filter by provider (gemini, claude, etc.)
            operation: Filter by operation type
            episode_title: Filter by episode title
            since: Only include usage after this date

        Returns:
            CostSummary for filtered usage
        """
        filtered = self.usage_history

        # Apply filters
        if provider:
            filtered = [u for u in filtered if u.provider == provider]
        if operation:
            filtered = [u for u in filtered if u.operation == operation]
        if episode_title:
            filtered = [u for u in filtered if u.episode_title == episode_title]
        if since:
            filtered = [u for u in filtered if u.timestamp >= since]

        return CostSummary.from_usage_list(filtered)

    def get_total_cost(self) -> float:
        """Get total cost across all usage.

        Returns:
            Total cost in USD
        """
        return sum(u.cost_usd for u in self.usage_history)

    def get_recent_usage(self, limit: int = 10) -> list[APIUsage]:
        """Get most recent API usage records.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of recent APIUsage records (newest first)
        """
        sorted_usage = sorted(self.usage_history, key=lambda u: u.timestamp, reverse=True)
        return sorted_usage[:limit]

    def clear(self) -> None:
        """Clear all cost history."""
        # Clear in-memory history
        self.usage_history = []

        # Overwrite file directly (no merge needed for clearing)
        if self.costs_file.exists():
            backup_file = self.costs_file.with_suffix(".json.bak")
            try:
                shutil.copy2(self.costs_file, backup_file)
            except Exception as e:
                logger.warning("Failed to create backup: %s", e)

        # Write empty array
        with open(self.costs_file, "w") as f:
            self._acquire_lock(f, exclusive=True)
            try:
                json.dump([], f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            finally:
                self._release_lock(f)


def calculate_cost_from_usage(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> float:
    """Calculate cost from token usage.

    Args:
        provider: Provider name (gemini, claude)
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD

    Raises:
        ValueError: If provider/model not supported
    """
    # Determine pricing key
    if provider == "gemini":
        # Check if long context
        if input_tokens >= 128_000:
            pricing_key = "gemini-flash-long"
        else:
            pricing_key = "gemini-flash"
    elif provider == "claude":
        pricing_key = "claude-sonnet"
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    if pricing_key not in PROVIDER_PRICING:
        raise ValueError(f"No pricing found for {provider} / {model}")

    pricing = PROVIDER_PRICING[pricing_key]
    return pricing.calculate_cost(input_tokens, output_tokens)
