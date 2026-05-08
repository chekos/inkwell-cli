"""Tests for the demo payload converter.

The payload step is what enforces the demo template allowlist, so we
test it independently of the pipeline that produced the underlying
``EpisodeOutput``.
"""

from datetime import datetime, timezone
from pathlib import Path

from inkwell.demo.config import DemoConfig
from inkwell.demo.payload import build_demo_payload
from inkwell.output.models import EpisodeMetadata, EpisodeOutput, OutputFile


def _make_output(template_names: list[str]) -> EpisodeOutput:
    metadata = EpisodeMetadata(
        podcast_name="Acme Pod",
        episode_title="Ep 42",
        episode_url="https://example.com/ep42.mp3",
        transcription_source="gemini",
        published_date=datetime(2026, 5, 7, tzinfo=timezone.utc),
        duration_seconds=1234.0,
    )
    output = EpisodeOutput(metadata=metadata, output_dir=Path("/tmp/demo-job"))
    for name in template_names:
        output.add_file(
            OutputFile(
                filename=f"{name}.md",
                template_name=name,
                content=f"# {name.title()}\n\nbody for {name}",
            )
        )
    return output


def test_payload_filters_to_allowlisted_templates() -> None:
    config = DemoConfig()
    output = _make_output(
        [
            "summary",
            "quotes",
            "key-concepts",
            "tools-mentioned",  # should be dropped
            "people-mentioned",  # should be dropped
        ]
    )

    payload = build_demo_payload(
        episode_output=output,
        config=config,
        extraction_cost_usd=0.04,
        total_cost_usd=0.07,
    )

    template_names = [note.template for note in payload.files]
    assert template_names == ["summary", "quotes", "key-concepts"]


def test_payload_preserves_template_ordering() -> None:
    config = DemoConfig()
    output = _make_output(["key-concepts", "quotes", "summary"])

    payload = build_demo_payload(
        episode_output=output,
        config=config,
        extraction_cost_usd=0.04,
        total_cost_usd=0.05,
    )

    assert [note.template for note in payload.files] == [
        "summary",
        "quotes",
        "key-concepts",
    ]


def test_payload_carries_cost_and_metadata() -> None:
    config = DemoConfig()
    output = _make_output(["summary"])

    payload = build_demo_payload(
        episode_output=output,
        config=config,
        extraction_cost_usd=0.05,
        total_cost_usd=0.10,
    )

    assert payload.podcast_name == "Acme Pod"
    assert payload.episode_title == "Ep 42"
    assert payload.episode_url == "https://example.com/ep42.mp3"
    assert payload.duration_seconds == 1234.0
    assert payload.extraction_cost_usd == 0.05
    assert payload.total_cost_usd == 0.10
    assert payload.transcription_source == "gemini"


def test_payload_humanizes_template_titles() -> None:
    config = DemoConfig()
    output = _make_output(["key-concepts"])

    payload = build_demo_payload(
        episode_output=output,
        config=config,
        extraction_cost_usd=0.0,
        total_cost_usd=0.0,
    )

    note = payload.files[0]
    assert note.title == "Key Concepts"
    assert note.markdown.startswith("# Key-Concepts")
