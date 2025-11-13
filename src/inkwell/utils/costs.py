"""Cost tracking utilities for API usage.

This module provides tools to track and analyze API costs across:
- Different providers (Gemini, Claude, etc.)
- Different operations (transcription, extraction, tag generation)
- Different podcasts and episodes

Based on actual API usage data, not estimates.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


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
        model="gemini-1.5-flash-latest",
        input_price_per_m=0.075,  # <128K tokens
        output_price_per_m=0.30,
    ),
    "gemini-flash-long": ProviderPricing(
        provider="gemini",
        model="gemini-1.5-flash-latest",
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

    provider: Literal["gemini", "claude", "youtube"] = Field(
        ..., description="API provider"
    )
    model: str = Field(..., description="Model used (e.g., gemini-1.5-flash)")
    operation: Literal["transcription", "extraction", "tag_generation", "interview"] = (
        Field(..., description="Type of operation")
    )

    # Token usage
    input_tokens: int = Field(0, ge=0, description="Input tokens used")
    output_tokens: int = Field(0, ge=0, description="Output tokens used")
    total_tokens: int = Field(0, ge=0, description="Total tokens used")

    # Cost
    cost_usd: float = Field(0.0, ge=0, description="Cost in USD")

    # Context
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When operation occurred"
    )
    episode_title: str | None = Field(None, description="Episode title if applicable")
    template_name: str | None = Field(
        None, description="Template name if applicable"
    )

    def model_post_init(self, __context: Any) -> None:
        """Calculate derived fields after initialization."""
        # Calculate total tokens if not set
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens


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
                    summary.costs_by_episode.get(usage.episode_title, 0.0)
                    + usage.cost_usd
                )

        return summary


class CostTracker:
    """Track and persist API costs to disk.

    Stores cost data in a JSON file for later analysis.
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

    def _load(self) -> None:
        """Load costs from disk."""
        try:
            with open(self.costs_file) as f:
                data = json.load(f)
                self.usage_history = [APIUsage.model_validate(item) for item in data]
        except (json.JSONDecodeError, ValueError) as e:
            # Corrupt file, start fresh
            print(f"Warning: Could not load costs file: {e}")
            self.usage_history = []

    def _save(self) -> None:
        """Save costs to disk."""
        data = [usage.model_dump(mode="json") for usage in self.usage_history]
        with open(self.costs_file, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def track(self, usage: APIUsage) -> None:
        """Track a new API usage.

        Args:
            usage: APIUsage record to track
        """
        self.usage_history.append(usage)
        self._save()

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
        sorted_usage = sorted(
            self.usage_history, key=lambda u: u.timestamp, reverse=True
        )
        return sorted_usage[:limit]

    def clear(self) -> None:
        """Clear all cost history."""
        self.usage_history = []
        self._save()


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
