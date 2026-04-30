"""Unit tests for pipeline orchestrator metadata defaults."""

from pathlib import Path

from inkwell.config.schema import GlobalConfig
from inkwell.pipeline.models import PipelineOptions
from inkwell.pipeline.orchestrator import PipelineOrchestrator


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
