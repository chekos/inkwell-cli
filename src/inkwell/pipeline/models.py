"""Data models for the pipeline orchestrator."""

from dataclasses import dataclass
from pathlib import Path

from inkwell.extraction.models import ExtractionResult, ExtractionSummary
from inkwell.interview import SimpleInterviewResult
from inkwell.output.models import EpisodeOutput
from inkwell.transcription.models import TranscriptionResult


@dataclass
class PipelineOptions:
    """Configuration for episode processing pipeline."""

    url: str
    category: str | None = None
    templates: list[str] | None = None
    provider: str | None = None
    interview: bool = False
    no_resume: bool = False
    resume_session: str | None = None
    output_dir: Path | None = None
    skip_cache: bool = False
    dry_run: bool = False
    overwrite: bool = False
    interview_template: str | None = None
    interview_format: str | None = None
    max_questions: int | None = None
    # Audio download authentication (for private feeds)
    auth_username: str | None = None
    auth_password: str | None = None
    # Episode metadata (from RSS feed)
    episode_title: str | None = None
    podcast_name: str | None = None


@dataclass
class PipelineResult:
    """Result of episode processing pipeline."""

    episode_output: EpisodeOutput
    transcript_result: TranscriptionResult
    extraction_results: list[ExtractionResult]
    extraction_summary: ExtractionSummary
    interview_result: SimpleInterviewResult | None
    extraction_cost_usd: float
    interview_cost_usd: float

    @property
    def total_cost_usd(self) -> float:
        """Calculate total cost across all pipeline stages."""
        return self.extraction_cost_usd + self.interview_cost_usd
