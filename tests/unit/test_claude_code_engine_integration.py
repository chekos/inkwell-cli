"""Local Claude engine routing, cache, and provenance integration tests."""

from pathlib import Path
from typing import Any

import pytest

from inkwell.agent_runtime.models import (
    RuntimeBilling,
    RuntimeProvenance,
    RuntimeReadiness,
    RuntimeResponse,
    RuntimeUsage,
)
from inkwell.extraction.cache import ExtractionCache
from inkwell.extraction.engine import ExtractionEngine
from inkwell.extraction.extractors.claude_code import ClaudeCodeExtractor
from inkwell.extraction.models import ExtractionTemplate
from inkwell.plugins.registry import PluginRegistry
from inkwell.utils.costs import CostTracker


class CountingBackend:
    def __init__(self) -> None:
        self.invocations = 0

    async def probe(self) -> RuntimeReadiness:
        return RuntimeReadiness(
            runtime="claude-code-cli",
            ready=True,
            installed=True,
            authenticated=True,
            supported=True,
            executable="/fake/claude",
            version="2.1.215",
            auth_class="claude_subscription",
        )

    async def invoke(self, request: Any) -> RuntimeResponse:
        self.invocations += 1
        return RuntimeResponse(
            final_value={"content": "Local Claude summary"},
            terminal_status="completed",
            lifecycle_events=["result.success"],
            attempts=["claude-code:claude-sonnet-4-5-20250929:turns=1"],
            usage=RuntimeUsage(input_tokens=20, output_tokens=5),
            provenance=RuntimeProvenance(
                kind="claude-code-cli",
                version="2.1.215",
                protocol_version=1,
                requested_model=request.requested_model,
                effective_model="claude-sonnet-4-5-20250929",
                auth_class="claude_subscription",
                billing_class="subscription_limits",
            ),
            billing=RuntimeBilling(mode="runtime_managed", amount_usd=None),
            duration_seconds=0.1,
        )


def _template() -> ExtractionTemplate:
    return ExtractionTemplate(
        name="summary",
        version="1.0",
        description="Summary",
        system_prompt="Summarize.",
        user_prompt_template="{{ transcript }}",
        expected_format="markdown",
    )


@pytest.mark.asyncio
async def test_explicit_claude_code_cache_preserves_origin_provenance(tmp_path: Path) -> None:
    backend = CountingBackend()
    extractor = ClaudeCodeExtractor(backend=backend)  # type: ignore[arg-type]
    extractor.configure({"model": "sonnet"})
    tracker = CostTracker(costs_file=tmp_path / "costs.json")
    engine = ExtractionEngine(
        cache=ExtractionCache(cache_dir=tmp_path / "cache"),
        extractor_override="claude-code",
        cost_tracker=tracker,
    )
    engine._registry.register(
        name="claude-code",
        plugin=extractor,
        priority=PluginRegistry.PRIORITY_BUILTIN,
        source="test",
    )
    engine._plugins_loaded = True

    first = await engine.extract(_template(), "Long enough transcript", {})
    second = await engine.extract(_template(), "Long enough transcript", {})

    assert first.provider == "claude-code"
    assert first.cost_known is False
    assert second.from_cache is True
    assert second.runtime == first.runtime
    assert backend.invocations == 1
    assert tracker.get_summary().unknown_cost_operations == 1


def test_claude_code_is_not_an_automatic_routing_candidate() -> None:
    engine = ExtractionEngine()

    attempts = engine.routing_policy._candidate_order(
        _template().model_copy(update={"model_preference": "claude-code"}),
        default_provider="gemini",
        override=None,
    )

    assert "claude-code" not in attempts
    assert attempts[0] == "gemini"
