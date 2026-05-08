"""Tests for the demo service glue layer.

Covers the m2 invariants: kill switch, forced extractor + model,
allowlisted templates, temp-dir cleanup, and the post-transcription
duration backstop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inkwell.config.schema import GlobalConfig
from inkwell.demo.classifier import ClassifiedUrl, UrlKind
from inkwell.demo.config import DemoConfig
from inkwell.demo.resolver import ResolvedDemoSource
from inkwell.demo.service import (
    DemoDurationBackstopError,
    DemoPipelineDisabledError,
    _DurationBackstop,
    configure_demo_runtime,
    process_demo_job,
)


def _resolved(duration_seconds: int = 600) -> ResolvedDemoSource:
    return ResolvedDemoSource(
        kind=UrlKind.PUBLIC_RSS,
        pipeline_url="https://cdn.example.com/audio.mp3",
        duration_seconds=duration_seconds,
        podcast_name="Demo Pod",
        episode_title="Latest episode",
    )


def _classified(url: str = "https://example.com/feed.rss") -> ClassifiedUrl:
    return ClassifiedUrl(kind=UrlKind.PUBLIC_RSS, normalized_url=url)


def _demo_config(**overrides: Any) -> DemoConfig:
    base: dict[str, Any] = {"max_duration_seconds": 30 * 60}
    base.update(overrides)
    # ``enabled`` uses validation_alias for env-var binding, so direct
    # constructor kwargs don't reach it. ``model_validate`` accepts the
    # alias and lets tests flip the kill switch.
    return DemoConfig.model_validate(base)


class TestDurationBackstop:
    """The backstop must compare against media duration, not wall-time.

    Codex flagged this as a P1 on PR #73: ``transcription_complete`` was
    carrying ``TranscriptionResult.duration_seconds`` (elapsed
    transcription wall time) under the ``duration_seconds`` key, and the
    backstop was reading that field. Fix is to read
    ``media_duration_seconds`` from the orchestrator payload.
    """

    def test_aborts_when_media_duration_exceeds_cap(self) -> None:
        backstop = _DurationBackstop(cap_seconds=1800, metadata_duration_seconds=600)
        with pytest.raises(DemoDurationBackstopError) as excinfo:
            backstop(
                "transcription_complete",
                {"media_duration_seconds": 1801, "duration_seconds": 5.0},
            )
        assert "30-minute" in str(excinfo.value)
        assert "1801s" in str(excinfo.value)

    def test_ignores_wall_time_field(self) -> None:
        # Old buggy behavior would read ``duration_seconds`` (wall time)
        # and reject this. The fix means we only react to
        # ``media_duration_seconds``, so a long transcription on a short
        # episode passes through.
        backstop = _DurationBackstop(cap_seconds=1800, metadata_duration_seconds=600)
        backstop(
            "transcription_complete",
            {"media_duration_seconds": 600, "duration_seconds": 9999.0},
        )

    def test_noop_when_under_cap(self) -> None:
        backstop = _DurationBackstop(cap_seconds=1800, metadata_duration_seconds=600)
        backstop(
            "transcription_complete",
            {"media_duration_seconds": 600, "duration_seconds": 5.0},
        )

    def test_noop_when_media_duration_missing(self) -> None:
        # If the orchestrator doesn't carry ``media_duration_seconds``
        # (e.g., a transcript with no segment data), don't reject the
        # job — fall through to the metadata cap that already passed.
        backstop = _DurationBackstop(cap_seconds=1800, metadata_duration_seconds=600)
        backstop("transcription_complete", {"duration_seconds": 5.0})

    def test_noop_on_other_steps(self) -> None:
        backstop = _DurationBackstop(cap_seconds=1800, metadata_duration_seconds=600)
        backstop("transcription_start", {})
        backstop(
            "extraction_complete",
            {"media_duration_seconds": 9999},
        )


class TestConfigureDemoRuntime:
    def test_pins_gemini_model(self) -> None:
        from inkwell.extraction.extractors.gemini import GeminiExtractor

        original = GeminiExtractor.MODEL
        try:
            GeminiExtractor.MODEL = "gemini-3-pro-preview"
            configure_demo_runtime(_demo_config())
            assert GeminiExtractor.MODEL == "gemini-2.5-flash"
        finally:
            GeminiExtractor.MODEL = original

    def test_idempotent_when_already_pinned(self) -> None:
        from inkwell.extraction.extractors.gemini import GeminiExtractor

        original = GeminiExtractor.MODEL
        try:
            GeminiExtractor.MODEL = "gemini-2.5-flash"
            configure_demo_runtime(_demo_config())
            assert GeminiExtractor.MODEL == "gemini-2.5-flash"
        finally:
            GeminiExtractor.MODEL = original


class TestProcessDemoJob:
    @pytest.mark.asyncio
    async def test_kill_switch_refuses_jobs(self) -> None:
        with pytest.raises(DemoPipelineDisabledError):
            await process_demo_job(
                _classified(),
                demo_config=_demo_config(DEMO_PIPELINE_ENABLED=False),
                global_config=GlobalConfig(),
            )

    @pytest.mark.asyncio
    async def test_runs_orchestrator_with_demo_invariants(self) -> None:
        # Verifies process_demo_job constructs PipelineOptions with the
        # forced extractor + demo template allowlist, that it pins the
        # Gemini model before invoking the orchestrator, and that the
        # temp directory used as output_dir is cleaned up after.
        from inkwell.extraction.extractors.gemini import GeminiExtractor

        captured: dict[str, Any] = {}

        async def _fake_process_episode(
            options: Any,
            *,
            progress_callback: Any | None = None,
        ) -> Any:
            captured["options"] = options
            captured["output_dir"] = options.output_dir
            captured["output_dir_exists"] = (
                options.output_dir is not None and Path(options.output_dir).exists()
            )
            captured["model_at_call"] = GeminiExtractor.MODEL
            return _build_pipeline_result()

        original_model = GeminiExtractor.MODEL
        try:
            GeminiExtractor.MODEL = "gemini-3-pro-preview"
            with (
                patch(
                    "inkwell.demo.service.resolve_demo_source",
                    AsyncMock(return_value=_resolved(duration_seconds=900)),
                ),
                patch("inkwell.demo.service.PipelineOrchestrator") as orch_cls,
                patch(
                    "inkwell.demo.service.build_demo_payload",
                    return_value=MagicMock(),
                ),
            ):
                orch_cls.return_value.process_episode = _fake_process_episode
                result = await process_demo_job(
                    _classified(),
                    demo_config=_demo_config(),
                    global_config=GlobalConfig(),
                )
        finally:
            GeminiExtractor.MODEL = original_model

        opts = captured["options"]
        assert opts.extractor == "gemini"
        assert opts.overwrite is True
        assert opts.skip_cache is True
        assert opts.interview is False
        # Forced templates: allowlist enforced even though GlobalConfig
        # has its own defaults.
        assert opts.templates == list(_demo_config().allowed_templates)
        assert opts.url == "https://cdn.example.com/audio.mp3"
        assert opts.episode_title == "Latest episode"
        assert opts.podcast_name == "Demo Pod"

        # Model is pinned by the time the orchestrator gets invoked.
        assert captured["model_at_call"] == "gemini-2.5-flash"
        # Temp dir existed during the call …
        assert captured["output_dir_exists"] is True
        # … and is cleaned up by the time process_demo_job returns.
        assert not Path(captured["output_dir"]).exists()

        assert result.resolved_source.duration_seconds == 900

    @pytest.mark.asyncio
    async def test_temp_dir_cleaned_up_on_failure(self) -> None:
        captured: dict[str, Any] = {}

        async def _failing_process_episode(
            options: Any,
            *,
            progress_callback: Any | None = None,
        ) -> Any:
            captured["output_dir"] = options.output_dir
            raise RuntimeError("orchestrator boom")

        with (
            patch(
                "inkwell.demo.service.resolve_demo_source",
                AsyncMock(return_value=_resolved()),
            ),
            patch("inkwell.demo.service.PipelineOrchestrator") as orch_cls,
        ):
            orch_cls.return_value.process_episode = _failing_process_episode
            with pytest.raises(RuntimeError, match="orchestrator boom"):
                await process_demo_job(
                    _classified(),
                    demo_config=_demo_config(),
                    global_config=GlobalConfig(),
                )

        assert captured["output_dir"] is not None
        assert not Path(captured["output_dir"]).exists()


def _build_pipeline_result() -> Any:
    """Minimal PipelineResult-shaped object for happy-path tests."""
    result = MagicMock()
    result.episode_output = MagicMock()
    result.extraction_cost_usd = 0.01
    result.total_cost_usd = 0.01
    return result
