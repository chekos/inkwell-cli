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


@pytest.mark.asyncio
async def test_transcribe_tiktok_captions_preserves_first_class_source(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path)
    result = await orchestrator._transcribe(
        "https://www.tiktok.com/@creator/video/123",
        source_text="[00:00] Caption text",
        source_kind="tiktok_captions",
        source_transcript_source="tiktok",
    )
    assert result.transcript is not None
    assert result.transcript.source == "tiktok"
    assert result.attempts == ["tiktok_captions"]


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


def test_artifact_contract_rejects_zero_artifact_false_success(tmp_path: Path) -> None:
    from inkwell.output.models import EpisodeOutput

    orchestrator = _orchestrator(tmp_path)
    output_dir = tmp_path / "local-files" / "capture"
    output_dir.mkdir(parents=True)
    metadata = EpisodeMetadata(
        podcast_name="Local Files",
        episode_title="capture",
        episode_url=str(tmp_path / "capture.txt"),
        transcription_source="text",
    )
    output = EpisodeOutput(metadata=metadata, output_dir=output_dir, files=[])

    with pytest.raises(InkwellError, match="complete artifact package") as raised:
        orchestrator._validate_artifact_contract(output, [])

    assert raised.value.details["code"] == "incomplete_artifact_package"
    assert raised.value.details["missing"] == [".metadata.yaml", "_transcript.md"]


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


@pytest.mark.asyncio
async def test_local_text_failed_extraction_writes_no_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inkwell.extraction.models import ExtractionResult, ExtractionSummary
    from inkwell.extraction.templates import TemplateLoader

    orchestrator = _orchestrator(tmp_path)
    summary_template = TemplateLoader().load_template("summary")
    monkeypatch.setattr(orchestrator, "_select_templates", lambda **_kwargs: [summary_template])

    async def failed_extract(**_kwargs):
        result = ExtractionResult(
            episode_url="https://local.inkwell/source",
            template_name="summary",
            template_version=summary_template.version,
            success=False,
            error="provider rejected extraction",
        )
        return (
            [result],
            ExtractionSummary(total=1, successful=0, failed=1, cached=0, attempts=[]),
            0.0,
        )

    monkeypatch.setattr(orchestrator, "_extract_content", failed_extract)

    with pytest.raises(InkwellError, match="no capture package was written") as raised:
        await orchestrator.process_episode(
            PipelineOptions(
                url=str(tmp_path / "notes.txt"),
                source_text="Local text must fail closed.",
                source_kind="local_text",
                episode_title="notes",
                podcast_name="Local Files",
            )
        )

    assert raised.value.details["code"] == "extraction_failed"
    assert not list(tmp_path.rglob(".metadata.yaml"))
