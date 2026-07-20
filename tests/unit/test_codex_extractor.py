"""Built-in Codex extraction adapter tests."""

from typing import Any

import pytest

from inkwell.agent_runtime.models import (
    RuntimeBilling,
    RuntimeProvenance,
    RuntimeReadiness,
    RuntimeResponse,
    RuntimeUsage,
)
from inkwell.extraction.extractors.codex import CodexExtractor
from inkwell.extraction.models import ExtractionTemplate


class FakeBackend:
    async def probe(self) -> RuntimeReadiness:
        return RuntimeReadiness(
            runtime="codex-cli",
            ready=True,
            installed=True,
            authenticated=True,
            supported=True,
            executable="/fake/codex",
            version="0.144.6",
            auth_class="chatgpt",
        )

    async def invoke(self, request: Any) -> RuntimeResponse:
        assert request.requested_model == "explicit-model"
        assert request.output_schema["required"] == ["content"]
        return RuntimeResponse(
            final_value={"content": "A concise summary."},
            terminal_status="completed",
            lifecycle_events=["turn.completed"],
            attempts=["codex-cli"],
            usage=RuntimeUsage(input_tokens=10, output_tokens=4),
            provenance=RuntimeProvenance(
                kind="codex-cli",
                version="0.144.6",
                protocol_version=1,
                requested_model="explicit-model",
                effective_model="explicit-model",
                auth_class="chatgpt",
                billing_class="runtime_managed",
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
async def test_codex_extractor_returns_concurrency_safe_metadata() -> None:
    extractor = CodexExtractor(backend=FakeBackend())  # type: ignore[arg-type]
    extractor.configure({"model": "explicit-model"})

    output = await extractor.extract_with_metadata(_template(), "Transcript", {})

    assert output.raw_content == "A concise summary."
    assert output.provider == "codex"
    assert output.model == "explicit-model"
    assert output.cost_known is False
    assert output.billing == {"mode": "runtime_managed", "amount_usd": None}
    assert output.runtime is not None
    assert output.runtime["version"] == "0.144.6"


def test_codex_extractor_requires_explicit_model() -> None:
    extractor = CodexExtractor(backend=FakeBackend())  # type: ignore[arg-type]

    with pytest.raises(Exception, match="model"):
        extractor.configure({})
