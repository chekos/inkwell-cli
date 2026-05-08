"""Convert pipeline output into a JSON-serializable demo response.

The demo never persists files into a user vault. Instead, the worker
runs the pipeline into a temp directory, this module pulls the rendered
markdown out, and the worker deletes the temp directory before
acknowledging the Cloud Tasks request.

Two invariants live here:

- The frontend payload only contains files whose template is on the
  ``allowed_templates`` list from :class:`DemoConfig`.
- File content is returned as plain markdown (frontmatter merged in via
  :attr:`OutputFile.full_content`). The frontend renders it directly; we
  do not surface raw template internals.
"""

from __future__ import annotations

from dataclasses import dataclass

from inkwell.demo.config import DemoConfig
from inkwell.output.models import EpisodeOutput


@dataclass(frozen=True)
class DemoNoteFile:
    """One rendered markdown file in the demo response."""

    template: str
    filename: str
    title: str
    markdown: str


@dataclass(frozen=True)
class DemoResultPayload:
    """Top-level frontend payload for a completed demo job."""

    podcast_name: str
    episode_title: str
    episode_url: str
    duration_seconds: float | None
    transcription_source: str
    files: list[DemoNoteFile]
    extraction_cost_usd: float
    total_cost_usd: float


def build_demo_payload(
    *,
    episode_output: EpisodeOutput,
    config: DemoConfig,
    extraction_cost_usd: float,
    total_cost_usd: float,
) -> DemoResultPayload:
    """Convert :class:`EpisodeOutput` into a frontend-shaped payload.

    Files whose template isn't on the demo allowlist are dropped on the
    floor. We also drop the transcript dump and any auxiliary files the
    pipeline emits — the demo response is intentionally narrow.
    """
    allowed = set(config.allowed_templates)
    notes: list[DemoNoteFile] = []
    for file in episode_output.files:
        if file.template_name not in allowed:
            continue
        notes.append(
            DemoNoteFile(
                template=file.template_name,
                filename=file.filename,
                title=_humanize(file.template_name),
                markdown=file.full_content,
            )
        )

    notes.sort(key=lambda note: config.allowed_templates.index(note.template))

    return DemoResultPayload(
        podcast_name=episode_output.metadata.podcast_name,
        episode_title=episode_output.metadata.episode_title,
        episode_url=episode_output.metadata.episode_url,
        duration_seconds=episode_output.metadata.duration_seconds,
        transcription_source=episode_output.metadata.transcription_source,
        files=notes,
        extraction_cost_usd=extraction_cost_usd,
        total_cost_usd=total_cost_usd,
    )


def _humanize(template_name: str) -> str:
    """Map an internal template name to a human-friendly section title."""
    return template_name.replace("-", " ").replace("_", " ").strip().title()
