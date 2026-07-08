"""Tests for token-aware extraction routing policy."""

from unittest.mock import Mock

import pytest

from inkwell.config.schema import ExtractionConfig
from inkwell.extraction.cache import ExtractionCache
from inkwell.extraction.engine import ExtractionEngine
from inkwell.extraction.models import ExtractionTemplate
from inkwell.extraction.routing import ExtractionRoutingPolicy
from inkwell.plugins.types import ExtractionCapabilities


@pytest.fixture
def summary_template() -> ExtractionTemplate:
    return ExtractionTemplate(
        name="summary",
        version="1.0",
        description="Summary",
        system_prompt="Summarize the source.",
        user_prompt_template="Title: {{ metadata.title }}\n\n{{ transcript }}",
        expected_format="text",
        max_tokens=100,
    )


def test_routing_policy_uses_override_as_hard_candidate(
    summary_template: ExtractionTemplate,
) -> None:
    policy = ExtractionRoutingPolicy()

    attempts = policy.plan(
        template=summary_template,
        transcript="short transcript",
        metadata={"title": "Example"},
        available_capabilities={
            "claude": ExtractionCapabilities(
                model_name="claude-test",
                max_input_tokens=1000,
            ),
            "gemini": ExtractionCapabilities(
                model_name="gemini-test",
                max_input_tokens=1000,
            ),
        },
        default_provider="gemini",
        override="claude",
    )

    assert [attempt.provider for attempt in attempts] == ["claude"]
    assert attempts[0].model == "claude-test"
    assert attempts[0].reason == "override"


def test_routing_policy_skips_models_that_cannot_fit_prompt(
    summary_template: ExtractionTemplate,
) -> None:
    policy = ExtractionRoutingPolicy()
    transcript = "word " * 200

    attempts = policy.plan(
        template=summary_template,
        transcript=transcript,
        metadata={"title": "Example"},
        available_capabilities={
            "gemini": ExtractionCapabilities(
                model_name="gemini-small",
                max_input_tokens=10,
            ),
            "claude": ExtractionCapabilities(
                model_name="claude-roomy",
                max_input_tokens=1000,
            ),
        },
        default_provider="gemini",
    )

    assert [attempt.provider for attempt in attempts] == ["claude"]
    assert attempts[0].estimated_prompt_tokens > 10


@pytest.mark.asyncio
async def test_engine_fails_before_api_spend_when_no_attempt_fits(
    summary_template: ExtractionTemplate,
    tmp_path,
) -> None:
    policy = Mock(spec=ExtractionRoutingPolicy)
    policy.plan.return_value = []
    policy.estimate_prompt_tokens.return_value = 999999
    engine = ExtractionEngine(
        config=ExtractionConfig(short_content_bypass_enabled=False),
        cache=ExtractionCache(cache_dir=tmp_path / "cache"),
        use_plugin_registry=False,
        routing_policy=policy,
    )

    result = await engine.extract(
        template=summary_template,
        transcript="source",
        metadata={"episode_url": "https://example.com/source"},
    )

    assert result.success is False
    assert "No configured extraction provider" in (result.error or "")
    policy.plan.assert_called_once()
