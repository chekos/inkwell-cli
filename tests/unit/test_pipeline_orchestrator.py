"""Unit tests for pipeline orchestrator metadata defaults."""

from pathlib import Path

import pytest

from inkwell.config.schema import GlobalConfig
from inkwell.output.models import EpisodeMetadata
from inkwell.pipeline.models import PipelineOptions
from inkwell.pipeline.orchestrator import PipelineOrchestrator
from inkwell.utils.errors import InkwellError


def _orchestrator(tmp_path: Path) -> PipelineOrchestrator:
    config = GlobalConfig(default_output_dir=tmp_path)
    return PipelineOrchestrator(config)


def test_direct_youtube_url_uses_inbox_and_supplied_episode_title(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path)
    options = PipelineOptions(
        url="https://www.youtube.com/watch?v=abc123",
        episode_title="How to Build Durable Systems",
    )

    podcast_name, episode_title = orchestrator._resolve_episode_metadata_defaults(options)

    assert podcast_name == "_inbox"
    assert episode_title == "How to Build Durable Systems"


def test_direct_generic_url_derives_readable_title(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path)
    options = PipelineOptions(
        url="https://cdn.example.com/audio/ship-it-fast-and-safe.mp3",
    )

    podcast_name, episode_title = orchestrator._resolve_episode_metadata_defaults(options)

    assert podcast_name == "_inbox"
    assert episode_title == "ship it fast and safe"


def test_direct_url_falls_back_to_untitled_capture(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path)
    options = PipelineOptions(url="https://example.com/")

    podcast_name, episode_title = orchestrator._resolve_episode_metadata_defaults(options)

    assert podcast_name == "_inbox"
    assert episode_title == "Untitled capture"


def test_podcast_name_override_wins_over_inbox_default(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path)
    options = PipelineOptions(
        url="https://example.com/audio/episode-12.mp3",
        podcast_name="My Override",
    )

    podcast_name, episode_title = orchestrator._resolve_episode_metadata_defaults(options)

    assert podcast_name == "My Override"
    assert episode_title == "episode 12"


@pytest.mark.asyncio
async def test_transcribe_source_text_bypasses_media_transcription(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path)

    result = await orchestrator._transcribe(
        "stdin://input",
        source_text="Already clean source text",
        source_kind="stdin",
    )

    assert result.success is True
    assert result.transcript is not None
    assert result.transcript.source == "text"
    assert result.transcript.full_text == "Already clean source text"
    assert result.attempts == ["stdin"]
    assert result.cost_usd == 0.0


def test_template_safe_episode_url_uses_placeholder_for_local_sources(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path)

    assert orchestrator._template_safe_episode_url("/tmp/source.md") == (
        "https://local.inkwell/source"
    )
    assert orchestrator._template_safe_episode_url("stdin://input") == (
        "https://local.inkwell/source"
    )
    assert orchestrator._template_safe_episode_url("https://example.com/episode.mp3") == (
        "https://example.com/episode.mp3"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("extractor", ["claude-code", "codex"])
async def test_hosted_pipeline_rejects_local_runtime_extractors(
    tmp_path: Path, extractor: str
) -> None:
    config = GlobalConfig(default_output_dir=tmp_path)
    orchestrator = PipelineOrchestrator(config, allow_local_runtime=False)
    metadata = EpisodeMetadata(
        podcast_name="Test",
        episode_title="Boundary",
        episode_url="https://example.com/episode",
        transcription_source="text",
    )

    with pytest.raises(InkwellError, match="hosted workers") as raised:
        await orchestrator._extract_content(
            templates=[],
            transcript="source",
            metadata=metadata,
            provider=None,
            skip_cache=False,
            dry_run=True,
            extractor_override=extractor,
        )

    assert raised.value.details["code"] == "local_runtime_hosted_forbidden"
