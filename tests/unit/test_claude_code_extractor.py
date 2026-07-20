"""Built-in Local Claude extraction adapter tests."""

from typing import Any

import pytest

from inkwell.agent_runtime.models import (
    RuntimeBilling,
    RuntimeProvenance,
    RuntimeReadiness,
    RuntimeResponse,
    RuntimeUsage,
)
from inkwell.extraction.extractors.claude_code import ClaudeCodeExtractor
from inkwell.extraction.models import ExtractionTemplate


class FakeBackend:
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
        assert request.requested_model == "sonnet"
        assert request.output_schema["required"] == ["content"]
        return RuntimeResponse(
            final_value={"content": "A concise summary."},
            terminal_status="completed",
            lifecycle_events=["result.success"],
            attempts=["claude-code:claude-sonnet-4-5-20250929:turns=1"],
            usage=RuntimeUsage(input_tokens=10, output_tokens=4),
            provenance=RuntimeProvenance(
                kind="claude-code-cli",
                version="2.1.215",
                protocol_version=1,
                requested_model="sonnet",
                effective_model="claude-sonnet-4-5-20250929",
                auth_class="claude_subscription",
                billing_class="subscription_limits",
            ),
            billing=RuntimeBilling(mode="runtime_managed", amount_usd=None),
            duration_seconds=0.2,
        )


def _template() -> ExtractionTemplate:
    return ExtractionTemplate(
        name="summary",
        version="1.0",
        description="Summarize",
        system_prompt="Be concise.",
        user_prompt_template="{{ transcript }}",
        expected_format="markdown",
    )


@pytest.mark.asyncio
async def test_claude_code_extractor_preserves_runtime_metadata() -> None:
    extractor = ClaudeCodeExtractor(backend=FakeBackend())  # type: ignore[arg-type]
    extractor.configure({"model": "sonnet"})

    output = await extractor.extract_with_metadata(_template(), "Transcript", {})

    assert output.raw_content == "A concise summary."
    assert output.provider == "claude-code"
    assert output.model == "claude-sonnet-4-5-20250929"
    assert output.cost_known is False
    assert output.billing == {"mode": "runtime_managed", "amount_usd": None}
    assert output.runtime is not None
    assert output.runtime["auth_class"] == "claude_subscription"


def test_claude_code_extractor_requires_explicit_model() -> None:
    extractor = ClaudeCodeExtractor(backend=FakeBackend())  # type: ignore[arg-type]

    with pytest.raises(Exception, match="model"):
        extractor.configure({})
