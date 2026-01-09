"""E2E Test Framework for Inkwell

This module provides infrastructure for end-to-end testing of the complete
Inkwell pipeline, from podcast episode fetching through markdown generation.

Test Scenarios:
1. Short technical podcast (15 min, YouTube transcript)
2. Long interview podcast (90 min, Gemini transcription)
3. Multi-host discussion (45 min, multiple speakers)
4. Educational content (30 min, structured format)
5. Storytelling podcast (60 min, narrative style)

For each scenario, we validate:
- Transcription quality and cost
- Extraction quality (completeness, accuracy)
- Cost tracking
- Output structure
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


@dataclass
class PodcastTestCase:
    """Test case representing a podcast episode for E2E testing."""

    # Identification
    name: str
    podcast_name: str
    episode_title: str
    episode_url: str

    # Characteristics
    duration_minutes: int
    speaker_count: int
    content_type: str  # "technical", "interview", "discussion", "educational", "storytelling"
    complexity: str  # "simple", "medium", "complex"

    # Expected transcription
    expected_word_count: int
    expected_transcript_source: str  # "youtube", "gemini"

    # Expected extraction
    expected_sections: list[str]  # Expected template sections
    expected_entity_count: int  # Approximate entity count
    expected_tag_count: int  # Approximate tag count

    # Expected costs (USD)
    expected_transcription_cost: float
    expected_extraction_cost: float
    expected_total_cost: float

    def __str__(self) -> str:
        return f"{self.name} ({self.duration_minutes}min, {self.content_type})"


# Test cases representing diverse podcast types
E2E_TEST_CASES = [
    # Case 1: Short technical podcast
    PodcastTestCase(
        name="short-technical",
        podcast_name="Syntax FM",
        episode_title="Modern CSS Features",
        episode_url="https://syntax.fm/show/xxx/modern-css-features",
        duration_minutes=15,
        speaker_count=2,
        content_type="technical",
        complexity="simple",
        expected_word_count=2500,
        expected_transcript_source="youtube",
        expected_sections=["summary", "key-concepts", "tools-mentioned"],
        expected_entity_count=8,
        expected_tag_count=5,
        expected_transcription_cost=0.00,  # YouTube API is free
        expected_extraction_cost=0.005,  # Gemini Flash
        expected_total_cost=0.005,
    ),
    # Case 2: Long interview podcast
    PodcastTestCase(
        name="long-interview",
        podcast_name="The Tim Ferriss Show",
        episode_title="Naval Ravikant on Wisdom",
        episode_url="https://example.com/tim-ferriss/naval",
        duration_minutes=90,
        speaker_count=2,
        content_type="interview",
        complexity="complex",
        expected_word_count=18000,
        expected_transcript_source="gemini",
        expected_sections=["summary", "quotes", "key-concepts", "books-mentioned"],
        expected_entity_count=25,
        expected_tag_count=12,
        expected_transcription_cost=0.15,  # Gemini transcription ~$0.10-0.20
        expected_extraction_cost=0.025,  # Long context
        expected_total_cost=0.175,
    ),
    # Case 3: Multi-host discussion
    PodcastTestCase(
        name="multi-host-discussion",
        podcast_name="All-In Podcast",
        episode_title="AI and the Future of Work",
        episode_url="https://example.com/all-in/ai-future",
        duration_minutes=45,
        speaker_count=4,
        content_type="discussion",
        complexity="medium",
        expected_word_count=9000,
        expected_transcript_source="youtube",
        expected_sections=["summary", "key-concepts", "people-mentioned"],
        expected_entity_count=15,
        expected_tag_count=8,
        expected_transcription_cost=0.00,
        expected_extraction_cost=0.012,
        expected_total_cost=0.012,
    ),
    # Case 4: Educational content
    PodcastTestCase(
        name="educational",
        podcast_name="Huberman Lab",
        episode_title="The Science of Sleep",
        episode_url="https://example.com/huberman/sleep",
        duration_minutes=30,
        speaker_count=1,
        content_type="educational",
        complexity="medium",
        expected_word_count=6000,
        expected_transcript_source="youtube",
        expected_sections=["summary", "key-concepts", "actionable-advice"],
        expected_entity_count=12,
        expected_tag_count=7,
        expected_transcription_cost=0.00,
        expected_extraction_cost=0.008,
        expected_total_cost=0.008,
    ),
    # Case 5: Storytelling podcast
    PodcastTestCase(
        name="storytelling",
        podcast_name="This American Life",
        episode_title="The Middle of Somewhere",
        episode_url="https://example.com/tal/middle",
        duration_minutes=60,
        speaker_count=3,
        content_type="storytelling",
        complexity="complex",
        expected_word_count=12000,
        expected_transcript_source="gemini",
        expected_sections=["summary", "quotes", "themes"],
        expected_entity_count=18,
        expected_tag_count=10,
        expected_transcription_cost=0.10,
        expected_extraction_cost=0.015,
        expected_total_cost=0.115,
    ),
]


class E2ETestResult(BaseModel):
    """Results from an E2E test run."""

    test_case_name: str
    success: bool
    error_message: str | None = None

    # Timing
    total_duration_seconds: float
    transcription_duration_seconds: float
    extraction_duration_seconds: float
    output_generation_duration_seconds: float

    # Quality metrics
    transcript_word_count: int
    transcript_source: str

    # Extraction results
    templates_processed: int
    entities_extracted: int
    tags_generated: int
    wikilinks_created: int

    # Output validation
    files_generated: int
    total_output_size_kb: float
    has_frontmatter: bool
    has_wikilinks: bool
    has_tags: bool

    # Cost tracking
    transcription_cost_usd: float
    extraction_cost_usd: float
    total_cost_usd: float

    # Validation results
    validation_passed: bool
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)

    @property
    def cost_per_minute(self) -> float:
        """Calculate cost per minute of podcast."""
        return (
            self.total_cost_usd / self.test_case.duration_minutes
            if hasattr(self, "test_case")
            else 0.0
        )

    @property
    def processing_time_per_minute(self) -> float:
        """Calculate processing time per minute of podcast."""
        return (
            self.total_duration_seconds / (self.test_case.duration_minutes * 60)
            if hasattr(self, "test_case")
            else 0.0
        )


class E2EBenchmark(BaseModel):
    """Benchmark results across multiple test runs."""

    test_cases_run: int
    success_count: int
    failure_count: int

    # Aggregate timing
    total_processing_time_seconds: float
    avg_processing_time_per_case: float
    min_processing_time: float
    max_processing_time: float

    # Aggregate costs
    total_cost_usd: float
    avg_cost_per_case: float
    min_cost: float
    max_cost: float

    # Aggregate quality
    avg_entities_extracted: float
    avg_tags_generated: float
    avg_wikilinks_created: float

    # Resource usage (if collected)
    peak_memory_mb: float | None = None
    avg_memory_mb: float | None = None

    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def from_results(cls, results: list[E2ETestResult]) -> "E2EBenchmark":
        """Create benchmark summary from test results."""
        successful = [r for r in results if r.success]

        return cls(
            test_cases_run=len(results),
            success_count=len(successful),
            failure_count=len(results) - len(successful),
            total_processing_time_seconds=sum(r.total_duration_seconds for r in results),
            avg_processing_time_per_case=sum(r.total_duration_seconds for r in results)
            / len(results)
            if results
            else 0.0,
            min_processing_time=min((r.total_duration_seconds for r in results), default=0.0),
            max_processing_time=max((r.total_duration_seconds for r in results), default=0.0),
            total_cost_usd=sum(r.total_cost_usd for r in results),
            avg_cost_per_case=sum(r.total_cost_usd for r in results) / len(results)
            if results
            else 0.0,
            min_cost=min((r.total_cost_usd for r in results), default=0.0),
            max_cost=max((r.total_cost_usd for r in results), default=0.0),
            avg_entities_extracted=sum(r.entities_extracted for r in successful) / len(successful)
            if successful
            else 0.0,
            avg_tags_generated=sum(r.tags_generated for r in successful) / len(successful)
            if successful
            else 0.0,
            avg_wikilinks_created=sum(r.wikilinks_created for r in successful) / len(successful)
            if successful
            else 0.0,
        )


def validate_e2e_output(
    output_dir: Path, test_case: PodcastTestCase
) -> tuple[bool, list[str], list[str]]:
    """Validate E2E test output meets quality standards.

    Args:
        output_dir: Directory containing generated output
        test_case: Test case with expected values

    Returns:
        Tuple of (passed, errors, warnings)
    """
    errors = []
    warnings = []

    # Check directory exists
    if not output_dir.exists():
        errors.append(f"Output directory does not exist: {output_dir}")
        return False, errors, warnings

    # Check expected files exist
    metadata_file = output_dir / ".metadata.yaml"
    if not metadata_file.exists():
        errors.append("Missing .metadata.yaml file")

    expected_files = [f"{section}.md" for section in test_case.expected_sections]
    for filename in expected_files:
        filepath = output_dir / filename
        if not filepath.exists():
            errors.append(f"Missing expected file: {filename}")
        else:
            # Check file is not empty
            if filepath.stat().st_size < 100:
                warnings.append(f"File {filename} is suspiciously small (<100 bytes)")

    # Check frontmatter exists in files
    for filename in expected_files:
        filepath = output_dir / filename
        if filepath.exists():
            content = filepath.read_text()
            if not content.startswith("---"):
                warnings.append(f"File {filename} missing frontmatter")

    # Check for wikilinks
    has_wikilinks = False
    for filename in expected_files:
        filepath = output_dir / filename
        if filepath.exists():
            content = filepath.read_text()
            if "[[" in content and "]]" in content:
                has_wikilinks = True
                break

    if not has_wikilinks:
        warnings.append("No wikilinks found in any output files")

    # Check for tags
    has_tags = False
    for filename in expected_files:
        filepath = output_dir / filename
        if filepath.exists():
            content = filepath.read_text()
            if "#" in content:
                has_tags = True
                break

    if not has_tags:
        warnings.append("No tags found in any output files")

    passed = len(errors) == 0
    return passed, errors, warnings
