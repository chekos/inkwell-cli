"""Codex engine routing, cache, and provenance integration tests."""

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
from inkwell.extraction.extractors.codex import CodexExtractor
from inkwell.extraction.models import ExtractionTemplate
from inkwell.plugins.registry import PluginRegistry


class CountingBackend:
    def __init__(self) -> None:
        self.invocations = 0

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
        self.invocations += 1
        return RuntimeResponse(
            final_value={"content": "Codex summary"},
            terminal_status="completed",
            lifecycle_events=["turn.completed"],
            attempts=["codex-cli"],
            usage=RuntimeUsage(input_tokens=20, output_tokens=5),
            provenance=RuntimeProvenance(
                kind="codex-cli",
                version="0.144.6",
                protocol_version=1,
                requested_model=request.requested_model,
                effective_model=request.requested_model,
                auth_class="chatgpt",
                billing_class="runtime_managed",
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
async def test_explicit_codex_cache_hit_preserves_origin_provenance(tmp_path: Path) -> None:
    backend = CountingBackend()
    extractor = CodexExtractor(backend=backend)  # type: ignore[arg-type]
    extractor.configure({"model": "explicit-model"})
    engine = ExtractionEngine(
        cache=ExtractionCache(cache_dir=tmp_path / "cache"),
        extractor_override="codex",
    )
    engine._registry.register(
        name="codex",
        plugin=extractor,
        priority=PluginRegistry.PRIORITY_BUILTIN,
        source="test",
    )
    engine._plugins_loaded = True

    first = await engine.extract(_template(), "Long enough transcript", {})
    second = await engine.extract(_template(), "Long enough transcript", {})

    assert first.provider == "codex"
    assert first.cost_known is False
    assert first.from_cache is False
    assert second.provider == "codex"
    assert second.model == "explicit-model"
    assert second.runtime == first.runtime
    assert second.cost_known is False
    assert second.from_cache is True
    assert backend.invocations == 1


@pytest.mark.asyncio
async def test_batched_codex_cache_uses_same_runtime_identity_for_write_and_read(
    tmp_path: Path,
) -> None:
    backend = CountingBackend()
    extractor = CodexExtractor(backend=backend)  # type: ignore[arg-type]
    extractor.configure({"model": "explicit-model"})
    engine = ExtractionEngine(
        cache=ExtractionCache(cache_dir=tmp_path / "cache"),
        extractor_override="codex",
    )
    engine._registry.register(
        name="codex",
        plugin=extractor,
        priority=PluginRegistry.PRIORITY_BUILTIN,
        source="test",
    )
    engine._plugins_loaded = True

    first, _ = await engine.extract_all_batched([_template()], "Transcript", {})
    second, _ = await engine.extract_all_batched([_template()], "Transcript", {})

    assert first[0].from_cache is False
    assert second[0].from_cache is True
    assert second[0].runtime == first[0].runtime
    assert backend.invocations == 1


def test_codex_is_not_an_automatic_routing_candidate() -> None:
    engine = ExtractionEngine()

    attempts = engine.routing_policy._candidate_order(
        _template().model_copy(update={"model_preference": "codex"}),
        default_provider="gemini",
        override=None,
    )

    assert "codex" not in attempts
    assert attempts[0] == "gemini"
