"""Tests for cost tracking utilities."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from inkwell.utils.costs import (
    APIUsage,
    CostSummary,
    CostTracker,
    ProviderPricing,
    calculate_cost_from_usage,
)


class TestProviderPricing:
    """Test provider pricing calculations."""

    def test_gemini_flash_pricing(self):
        """Test Gemini Flash pricing calculation."""
        pricing = ProviderPricing(
            provider="gemini",
            model="gemini-1.5-flash",
            input_price_per_m=0.075,
            output_price_per_m=0.30,
        )

        # 1000 input tokens + 500 output tokens
        cost = pricing.calculate_cost(input_tokens=1000, output_tokens=500)

        # Expected: (1000 / 1M) * 0.075 + (500 / 1M) * 0.30
        expected = 0.001 * 0.075 + 0.0005 * 0.30
        assert abs(cost - expected) < 0.000001

    def test_claude_pricing(self):
        """Test Claude pricing calculation."""
        pricing = ProviderPricing(
            provider="claude",
            model="claude-3-5-sonnet",
            input_price_per_m=3.00,
            output_price_per_m=15.00,
        )

        # 10,000 input tokens + 2,000 output tokens
        cost = pricing.calculate_cost(input_tokens=10_000, output_tokens=2_000)

        # Expected: (10000 / 1M) * 3.00 + (2000 / 1M) * 15.00
        expected = 0.01 * 3.00 + 0.002 * 15.00
        assert abs(cost - expected) < 0.000001

    def test_zero_tokens(self):
        """Test pricing with zero tokens."""
        pricing = ProviderPricing(
            provider="test", model="test", input_price_per_m=1.0, output_price_per_m=2.0
        )

        cost = pricing.calculate_cost(input_tokens=0, output_tokens=0)
        assert cost == 0.0


class TestAPIUsage:
    """Test APIUsage model."""

    def test_create_usage(self):
        """Test creating API usage record."""
        usage = APIUsage(
            provider="gemini",
            model="gemini-1.5-flash",
            operation="extraction",
            input_tokens=5000,
            output_tokens=1000,
            cost_usd=0.005,
            episode_title="Test Episode",
            template_name="summary",
        )

        assert usage.provider == "gemini"
        assert usage.input_tokens == 5000
        assert usage.output_tokens == 1000
        assert usage.total_tokens == 6000  # Auto-calculated
        assert usage.cost_usd == 0.005

    def test_total_tokens_auto_calculated(self):
        """Test total_tokens is calculated automatically."""
        usage = APIUsage(
            provider="claude",
            model="claude-3-5-sonnet",
            operation="transcription",
            input_tokens=10_000,
            output_tokens=500,
            cost_usd=0.035,
        )

        assert usage.total_tokens == 10_500

    def test_timestamp_auto_set(self):
        """Test timestamp is set automatically."""
        before = datetime.utcnow()
        usage = APIUsage(
            provider="gemini",
            model="gemini-1.5-flash",
            operation="extraction",
            input_tokens=1000,
            output_tokens=200,
            cost_usd=0.001,
        )
        after = datetime.utcnow()

        assert before <= usage.timestamp <= after


class TestCostSummary:
    """Test cost summary aggregation."""

    def test_empty_summary(self):
        """Test summary with no usage."""
        summary = CostSummary.from_usage_list([])

        assert summary.total_operations == 0
        assert summary.total_cost_usd == 0.0
        assert len(summary.costs_by_provider) == 0

    def test_single_usage(self):
        """Test summary with single usage."""
        usage = APIUsage(
            provider="gemini",
            model="gemini-1.5-flash",
            operation="extraction",
            input_tokens=5000,
            output_tokens=1000,
            cost_usd=0.005,
            episode_title="Test Episode",
        )

        summary = CostSummary.from_usage_list([usage])

        assert summary.total_operations == 1
        assert summary.total_input_tokens == 5000
        assert summary.total_output_tokens == 1000
        assert summary.total_tokens == 6000
        assert summary.total_cost_usd == 0.005
        assert summary.costs_by_provider["gemini"] == 0.005
        assert summary.costs_by_operation["extraction"] == 0.005
        assert summary.costs_by_episode["Test Episode"] == 0.005

    def test_multiple_usage(self):
        """Test summary with multiple usage records."""
        usage1 = APIUsage(
            provider="gemini",
            model="gemini-1.5-flash",
            operation="extraction",
            input_tokens=5000,
            output_tokens=1000,
            cost_usd=0.005,
            episode_title="Episode 1",
        )

        usage2 = APIUsage(
            provider="claude",
            model="claude-3-5-sonnet",
            operation="extraction",
            input_tokens=10_000,
            output_tokens=2000,
            cost_usd=0.040,
            episode_title="Episode 2",
        )

        usage3 = APIUsage(
            provider="gemini",
            model="gemini-1.5-flash",
            operation="tag_generation",
            input_tokens=3000,
            output_tokens=500,
            cost_usd=0.003,
            episode_title="Episode 1",
        )

        summary = CostSummary.from_usage_list([usage1, usage2, usage3])

        assert summary.total_operations == 3
        assert summary.total_input_tokens == 18_000
        assert summary.total_output_tokens == 3_500
        assert summary.total_tokens == 21_500
        assert abs(summary.total_cost_usd - 0.048) < 0.0001

        # By provider
        assert abs(summary.costs_by_provider["gemini"] - 0.008) < 0.0001
        assert abs(summary.costs_by_provider["claude"] - 0.040) < 0.0001

        # By operation
        assert abs(summary.costs_by_operation["extraction"] - 0.045) < 0.0001
        assert abs(summary.costs_by_operation["tag_generation"] - 0.003) < 0.0001

        # By episode
        assert abs(summary.costs_by_episode["Episode 1"] - 0.008) < 0.0001
        assert abs(summary.costs_by_episode["Episode 2"] - 0.040) < 0.0001


class TestCostTracker:
    """Test cost tracker."""

    def test_create_tracker(self, tmp_path):
        """Test creating cost tracker."""
        costs_file = tmp_path / "costs.json"
        tracker = CostTracker(costs_file=costs_file)

        assert tracker.costs_file == costs_file
        assert len(tracker.usage_history) == 0

    def test_track_usage(self, tmp_path):
        """Test tracking API usage."""
        costs_file = tmp_path / "costs.json"
        tracker = CostTracker(costs_file=costs_file)

        usage = APIUsage(
            provider="gemini",
            model="gemini-1.5-flash",
            operation="extraction",
            input_tokens=5000,
            output_tokens=1000,
            cost_usd=0.005,
        )

        tracker.track(usage)

        assert len(tracker.usage_history) == 1
        assert tracker.usage_history[0] == usage
        assert costs_file.exists()

    def test_persistence(self, tmp_path):
        """Test costs are persisted to disk."""
        costs_file = tmp_path / "costs.json"

        # Create tracker and add usage
        tracker1 = CostTracker(costs_file=costs_file)
        usage = APIUsage(
            provider="gemini",
            model="gemini-1.5-flash",
            operation="extraction",
            input_tokens=5000,
            output_tokens=1000,
            cost_usd=0.005,
        )
        tracker1.track(usage)

        # Create new tracker - should load persisted data
        tracker2 = CostTracker(costs_file=costs_file)

        assert len(tracker2.usage_history) == 1
        assert tracker2.usage_history[0].provider == "gemini"
        assert tracker2.usage_history[0].input_tokens == 5000

    def test_get_total_cost(self, tmp_path):
        """Test getting total cost."""
        costs_file = tmp_path / "costs.json"
        tracker = CostTracker(costs_file=costs_file)

        tracker.track(
            APIUsage(
                provider="gemini",
                model="gemini-1.5-flash",
                operation="extraction",
                input_tokens=5000,
                output_tokens=1000,
                cost_usd=0.005,
            )
        )

        tracker.track(
            APIUsage(
                provider="claude",
                model="claude-3-5-sonnet",
                operation="extraction",
                input_tokens=10_000,
                output_tokens=2000,
                cost_usd=0.040,
            )
        )

        total = tracker.get_total_cost()
        assert abs(total - 0.045) < 0.0001

    def test_get_summary_no_filter(self, tmp_path):
        """Test getting summary without filters."""
        costs_file = tmp_path / "costs.json"
        tracker = CostTracker(costs_file=costs_file)

        tracker.track(
            APIUsage(
                provider="gemini",
                model="gemini-1.5-flash",
                operation="extraction",
                input_tokens=5000,
                output_tokens=1000,
                cost_usd=0.005,
            )
        )

        summary = tracker.get_summary()

        assert summary.total_operations == 1
        assert summary.total_cost_usd == 0.005

    def test_get_summary_with_provider_filter(self, tmp_path):
        """Test getting summary filtered by provider."""
        costs_file = tmp_path / "costs.json"
        tracker = CostTracker(costs_file=costs_file)

        tracker.track(
            APIUsage(
                provider="gemini",
                model="gemini-1.5-flash",
                operation="extraction",
                input_tokens=5000,
                output_tokens=1000,
                cost_usd=0.005,
            )
        )

        tracker.track(
            APIUsage(
                provider="claude",
                model="claude-3-5-sonnet",
                operation="extraction",
                input_tokens=10_000,
                output_tokens=2000,
                cost_usd=0.040,
            )
        )

        # Filter by gemini
        summary = tracker.get_summary(provider="gemini")

        assert summary.total_operations == 1
        assert summary.total_cost_usd == 0.005

        # Filter by claude
        summary = tracker.get_summary(provider="claude")

        assert summary.total_operations == 1
        assert summary.total_cost_usd == 0.040

    def test_get_summary_with_operation_filter(self, tmp_path):
        """Test getting summary filtered by operation."""
        costs_file = tmp_path / "costs.json"
        tracker = CostTracker(costs_file=costs_file)

        tracker.track(
            APIUsage(
                provider="gemini",
                model="gemini-1.5-flash",
                operation="extraction",
                input_tokens=5000,
                output_tokens=1000,
                cost_usd=0.005,
            )
        )

        tracker.track(
            APIUsage(
                provider="gemini",
                model="gemini-1.5-flash",
                operation="tag_generation",
                input_tokens=3000,
                output_tokens=500,
                cost_usd=0.003,
            )
        )

        # Filter by extraction
        summary = tracker.get_summary(operation="extraction")

        assert summary.total_operations == 1
        assert summary.total_cost_usd == 0.005

    def test_get_summary_with_episode_filter(self, tmp_path):
        """Test getting summary filtered by episode."""
        costs_file = tmp_path / "costs.json"
        tracker = CostTracker(costs_file=costs_file)

        tracker.track(
            APIUsage(
                provider="gemini",
                model="gemini-1.5-flash",
                operation="extraction",
                input_tokens=5000,
                output_tokens=1000,
                cost_usd=0.005,
                episode_title="Episode 1",
            )
        )

        tracker.track(
            APIUsage(
                provider="gemini",
                model="gemini-1.5-flash",
                operation="extraction",
                input_tokens=3000,
                output_tokens=500,
                cost_usd=0.003,
                episode_title="Episode 2",
            )
        )

        # Filter by episode
        summary = tracker.get_summary(episode_title="Episode 1")

        assert summary.total_operations == 1
        assert summary.total_cost_usd == 0.005

    def test_get_summary_with_since_filter(self, tmp_path):
        """Test getting summary filtered by date."""
        costs_file = tmp_path / "costs.json"
        tracker = CostTracker(costs_file=costs_file)

        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        tracker.track(
            APIUsage(
                provider="gemini",
                model="gemini-1.5-flash",
                operation="extraction",
                input_tokens=5000,
                output_tokens=1000,
                cost_usd=0.005,
                timestamp=two_days_ago,
            )
        )

        tracker.track(
            APIUsage(
                provider="gemini",
                model="gemini-1.5-flash",
                operation="extraction",
                input_tokens=3000,
                output_tokens=500,
                cost_usd=0.003,
                timestamp=now,
            )
        )

        # Filter by since yesterday
        summary = tracker.get_summary(since=yesterday)

        assert summary.total_operations == 1
        assert summary.total_cost_usd == 0.003

    def test_get_recent_usage(self, tmp_path):
        """Test getting recent usage."""
        costs_file = tmp_path / "costs.json"
        tracker = CostTracker(costs_file=costs_file)

        # Add 5 usage records
        for i in range(5):
            tracker.track(
                APIUsage(
                    provider="gemini",
                    model="gemini-1.5-flash",
                    operation="extraction",
                    input_tokens=1000 * (i + 1),
                    output_tokens=200,
                    cost_usd=0.001 * (i + 1),
                )
            )

        # Get recent 3
        recent = tracker.get_recent_usage(limit=3)

        assert len(recent) == 3
        # Should be newest first
        assert recent[0].input_tokens == 5000
        assert recent[1].input_tokens == 4000
        assert recent[2].input_tokens == 3000

    def test_clear(self, tmp_path):
        """Test clearing cost history."""
        costs_file = tmp_path / "costs.json"
        tracker = CostTracker(costs_file=costs_file)

        tracker.track(
            APIUsage(
                provider="gemini",
                model="gemini-1.5-flash",
                operation="extraction",
                input_tokens=5000,
                output_tokens=1000,
                cost_usd=0.005,
            )
        )

        assert len(tracker.usage_history) == 1

        tracker.clear()

        assert len(tracker.usage_history) == 0
        assert tracker.get_total_cost() == 0.0

    def test_corrupt_file_handling(self, tmp_path):
        """Test handling of corrupt costs file."""
        costs_file = tmp_path / "costs.json"

        # Write corrupt JSON
        costs_file.write_text("not valid json {")

        # Should handle gracefully and start fresh
        tracker = CostTracker(costs_file=costs_file)

        assert len(tracker.usage_history) == 0


class TestCalculateCostFromUsage:
    """Test cost calculation helper."""

    def test_gemini_short_context(self):
        """Test Gemini cost calculation for short context."""
        cost = calculate_cost_from_usage(
            provider="gemini",
            model="gemini-1.5-flash",
            input_tokens=50_000,
            output_tokens=2000,
        )

        # Should use short pricing (< 128K)
        expected = (50_000 / 1_000_000) * 0.075 + (2000 / 1_000_000) * 0.30
        assert abs(cost - expected) < 0.000001

    def test_gemini_long_context(self):
        """Test Gemini cost calculation for long context."""
        cost = calculate_cost_from_usage(
            provider="gemini",
            model="gemini-1.5-flash",
            input_tokens=200_000,
            output_tokens=2000,
        )

        # Should use long pricing (> 128K)
        expected = (200_000 / 1_000_000) * 0.15 + (2000 / 1_000_000) * 0.30
        assert abs(cost - expected) < 0.000001

    def test_claude(self):
        """Test Claude cost calculation."""
        cost = calculate_cost_from_usage(
            provider="claude",
            model="claude-3-5-sonnet",
            input_tokens=10_000,
            output_tokens=2000,
        )

        expected = (10_000 / 1_000_000) * 3.00 + (2000 / 1_000_000) * 15.00
        assert abs(cost - expected) < 0.000001

    def test_unsupported_provider(self):
        """Test error for unsupported provider."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            calculate_cost_from_usage(
                provider="unknown",
                model="some-model",
                input_tokens=1000,
                output_tokens=500,
            )
