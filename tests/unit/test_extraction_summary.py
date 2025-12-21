"""Unit tests for extraction summary and error handling."""

from unittest.mock import AsyncMock, patch

import pytest

from inkwell.extraction.engine import ExtractionEngine
from inkwell.extraction.models import (
    ExtractionAttempt,
    ExtractionStatus,
    ExtractionSummary,
    ExtractionTemplate,
)


@pytest.fixture
def mock_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set mock API keys."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-claude-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-gemini-key")


@pytest.fixture
def summary_template() -> ExtractionTemplate:
    """Create summary extraction template."""
    return ExtractionTemplate(
        name="summary",
        version="1.0",
        description="Test summary",
        system_prompt="Summarize",
        user_prompt_template="{{ transcript }}",
        expected_format="text",
        max_tokens=1000,
        temperature=0.3,
    )


@pytest.fixture
def quotes_template() -> ExtractionTemplate:
    """Create quotes extraction template."""
    return ExtractionTemplate(
        name="quotes",
        version="1.0",
        description="Extract quotes",
        system_prompt="Extract quotes",
        user_prompt_template="{{ transcript }}",
        expected_format="json",
        max_tokens=1000,
        temperature=0.2,
    )


@pytest.fixture
def concepts_template() -> ExtractionTemplate:
    """Create concepts extraction template."""
    return ExtractionTemplate(
        name="key-concepts",
        version="1.0",
        description="Extract key concepts",
        system_prompt="Extract concepts",
        user_prompt_template="{{ transcript }}",
        expected_format="json",
        max_tokens=1000,
        temperature=0.2,
    )


class TestExtractionSummary:
    """Tests for ExtractionSummary dataclass."""

    def test_success_rate_all_successful(self) -> None:
        """Test success rate calculation with all successful extractions."""
        attempts = [
            ExtractionAttempt(
                template_name="summary",
                status=ExtractionStatus.SUCCESS,
                duration_seconds=1.5,
            ),
            ExtractionAttempt(
                template_name="quotes",
                status=ExtractionStatus.SUCCESS,
                duration_seconds=2.0,
            ),
        ]
        summary = ExtractionSummary(
            total=2,
            successful=2,
            failed=0,
            cached=0,
            attempts=attempts,
        )

        assert summary.success_rate == 100.0

    def test_success_rate_partial_success(self) -> None:
        """Test success rate calculation with partial success."""
        attempts = [
            ExtractionAttempt(
                template_name="summary",
                status=ExtractionStatus.SUCCESS,
                duration_seconds=1.5,
            ),
            ExtractionAttempt(
                template_name="quotes",
                status=ExtractionStatus.FAILED,
                error_message="Timeout error",
                duration_seconds=2.0,
            ),
            ExtractionAttempt(
                template_name="concepts",
                status=ExtractionStatus.SUCCESS,
                duration_seconds=1.8,
            ),
        ]
        summary = ExtractionSummary(
            total=3,
            successful=2,
            failed=1,
            cached=0,
            attempts=attempts,
        )

        assert summary.success_rate == pytest.approx(66.67, rel=0.01)

    def test_success_rate_all_failed(self) -> None:
        """Test success rate calculation with all failed extractions."""
        attempts = [
            ExtractionAttempt(
                template_name="summary",
                status=ExtractionStatus.FAILED,
                error_message="Error",
                duration_seconds=1.5,
            ),
        ]
        summary = ExtractionSummary(
            total=1,
            successful=0,
            failed=1,
            cached=0,
            attempts=attempts,
        )

        assert summary.success_rate == 0.0

    def test_success_rate_empty(self) -> None:
        """Test success rate calculation with no attempts."""
        summary = ExtractionSummary(
            total=0,
            successful=0,
            failed=0,
            cached=0,
            attempts=[],
        )

        assert summary.success_rate == 0.0

    def test_failed_templates_list(self) -> None:
        """Test failed_templates property returns correct list."""
        attempts = [
            ExtractionAttempt(
                template_name="summary",
                status=ExtractionStatus.SUCCESS,
                duration_seconds=1.5,
            ),
            ExtractionAttempt(
                template_name="quotes",
                status=ExtractionStatus.FAILED,
                error_message="Timeout error",
                duration_seconds=2.0,
            ),
            ExtractionAttempt(
                template_name="concepts",
                status=ExtractionStatus.CACHED,
                duration_seconds=0.0,
            ),
            ExtractionAttempt(
                template_name="tools",
                status=ExtractionStatus.FAILED,
                error_message="API error",
                duration_seconds=1.2,
            ),
        ]
        summary = ExtractionSummary(
            total=4,
            successful=1,
            failed=2,
            cached=1,
            attempts=attempts,
        )

        assert summary.failed_templates == ["quotes", "tools"]

    def test_failed_templates_empty(self) -> None:
        """Test failed_templates property with no failures."""
        attempts = [
            ExtractionAttempt(
                template_name="summary",
                status=ExtractionStatus.SUCCESS,
                duration_seconds=1.5,
            ),
        ]
        summary = ExtractionSummary(
            total=1,
            successful=1,
            failed=0,
            cached=0,
            attempts=attempts,
        )

        assert summary.failed_templates == []

    def test_format_summary_all_successful(self) -> None:
        """Test format_summary output for all successful extractions."""
        attempts = [
            ExtractionAttempt(
                template_name="summary",
                status=ExtractionStatus.SUCCESS,
                duration_seconds=1.5,
            ),
            ExtractionAttempt(
                template_name="quotes",
                status=ExtractionStatus.CACHED,
                duration_seconds=0.0,
            ),
        ]
        summary = ExtractionSummary(
            total=2,
            successful=1,
            failed=0,
            cached=1,
            attempts=attempts,
        )

        formatted = summary.format_summary()

        assert "Extraction Summary:" in formatted
        assert "Total: 2" in formatted
        assert "Successful: 1" in formatted
        assert "Failed: 0" in formatted
        assert "Cached: 1" in formatted
        assert "Success Rate: 50.0%" in formatted
        assert "Failed Templates:" not in formatted  # No failures

    def test_format_summary_with_failures(self) -> None:
        """Test format_summary output includes failure details."""
        attempts = [
            ExtractionAttempt(
                template_name="summary",
                status=ExtractionStatus.SUCCESS,
                duration_seconds=1.5,
            ),
            ExtractionAttempt(
                template_name="quotes",
                status=ExtractionStatus.FAILED,
                error_message="TimeoutError: Request timed out after 30s",
                duration_seconds=30.0,
            ),
        ]
        summary = ExtractionSummary(
            total=2,
            successful=1,
            failed=1,
            cached=0,
            attempts=attempts,
        )

        formatted = summary.format_summary()

        assert "Extraction Summary:" in formatted
        assert "Total: 2" in formatted
        assert "Successful: 1" in formatted
        assert "Failed: 1" in formatted
        assert "Success Rate: 50.0%" in formatted
        assert "Failed Templates:" in formatted
        assert "quotes: TimeoutError: Request timed out after 30s" in formatted


class TestExtractionEngineWithSummary:
    """Tests for ExtractionEngine with summary support."""

    @pytest.mark.asyncio
    async def test_extract_all_returns_tuple(
        self,
        mock_api_keys: None,
        summary_template: ExtractionTemplate,
        quotes_template: ExtractionTemplate,
    ) -> None:
        """Test extract_all returns tuple of (results, summary)."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

            # Setup mock extractors (summary uses Gemini, quotes uses Claude)
            engine.gemini_extractor.extract = AsyncMock(return_value="Test output")
            engine.gemini_extractor.estimate_cost = lambda t, l: 0.01
            engine.claude_extractor.extract = AsyncMock(return_value='{"quotes": []}')
            engine.claude_extractor.estimate_cost = lambda t, l: 0.10

            # Fix class name for provider detection
            engine.claude_extractor.__class__.__name__ = "ClaudeExtractor"
            engine.gemini_extractor.__class__.__name__ = "GeminiExtractor"

            templates = [summary_template, quotes_template]
            transcript = "Test transcript"
            metadata = {"episode_url": "https://example.com/ep1"}

            # Extract
            results, summary = await engine.extract_all(
                templates, transcript, metadata, use_cache=False
            )

            # Verify return types
            assert isinstance(results, list)
            assert isinstance(summary, ExtractionSummary)

            # Verify summary statistics
            assert summary.total == 2
            assert summary.successful == 2
            assert summary.failed == 0

    @pytest.mark.asyncio
    async def test_extract_all_tracks_failures(
        self,
        mock_api_keys: None,
        summary_template: ExtractionTemplate,
        quotes_template: ExtractionTemplate,
    ) -> None:
        """Test extract_all properly tracks extraction failures."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

            # Setup mock - first succeeds, second fails
            engine.gemini_extractor.extract = AsyncMock(
                side_effect=["Success output", Exception("API Error")]
            )
            engine.gemini_extractor.estimate_cost = lambda t, l: 0.01

            templates = [summary_template, quotes_template]
            transcript = "Test transcript"
            metadata = {"episode_url": "https://example.com/ep1"}

            # Extract
            results, summary = await engine.extract_all(
                templates, transcript, metadata, use_cache=False
            )

            # Verify only successful result returned
            assert len(results) == 1

            # Verify summary tracks both attempts
            assert summary.total == 2
            assert summary.successful == 1
            assert summary.failed == 1
            assert "quotes" in summary.failed_templates

    @pytest.mark.asyncio
    async def test_extract_all_batched_returns_tuple(
        self,
        mock_api_keys: None,
        summary_template: ExtractionTemplate,
        quotes_template: ExtractionTemplate,
    ) -> None:
        """Test extract_all_batched returns tuple of (results, summary)."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

            # Setup mock
            engine.gemini_extractor.extract = AsyncMock(
                return_value='{"summary": "test", "quotes": []}'
            )
            engine.gemini_extractor.estimate_cost = lambda t, l: 0.01
            engine.gemini_extractor.build_prompt = lambda t, tr, m: "prompt"

            templates = [summary_template, quotes_template]
            transcript = "Test transcript"
            metadata = {"episode_url": "https://example.com/ep1"}

            # Extract
            results, summary = await engine.extract_all_batched(
                templates, transcript, metadata, use_cache=False
            )

            # Verify return types
            assert isinstance(results, list)
            assert isinstance(summary, ExtractionSummary)

            # Verify summary statistics
            assert summary.total == 2

    @pytest.mark.asyncio
    async def test_extract_all_empty_templates(self, mock_api_keys: None) -> None:
        """Test extract_all with empty template list returns empty summary."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )
            templates = []
            transcript = "Test transcript"
            metadata = {"episode_url": "https://example.com/ep1"}

            # Extract
            results, summary = await engine.extract_all(templates, transcript, metadata)

            # Verify empty results
            assert len(results) == 0
            assert summary.total == 0
            assert summary.successful == 0
            assert summary.failed == 0
            assert summary.cached == 0

    @pytest.mark.asyncio
    async def test_extract_all_batched_empty_templates(self, mock_api_keys: None) -> None:
        """Test extract_all_batched with empty template list returns empty summary."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )
            templates = []
            transcript = "Test transcript"
            metadata = {"episode_url": "https://example.com/ep1"}

            # Extract
            results, summary = await engine.extract_all_batched(templates, transcript, metadata)

            # Verify empty results
            assert len(results) == 0
            assert summary.total == 0
            assert summary.successful == 0
            assert summary.failed == 0
            assert summary.cached == 0

    @pytest.mark.asyncio
    async def test_extract_all_tracks_cached_results(
        self,
        mock_api_keys: None,
        summary_template: ExtractionTemplate,
        quotes_template: ExtractionTemplate,
        tmp_path,
    ) -> None:
        """Test extract_all properly tracks cached vs fresh extractions."""
        from inkwell.extraction.cache import ExtractionCache

        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            # Use temp cache to avoid cross-test contamination
            temp_cache = ExtractionCache(cache_dir=tmp_path / "cache")
            engine = ExtractionEngine(
                cache=temp_cache,
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

            # Setup mock extractors (summary uses Gemini, quotes uses Claude)
            engine.gemini_extractor.extract = AsyncMock(return_value="Test output")
            engine.gemini_extractor.estimate_cost = lambda t, l: 0.01
            engine.claude_extractor.extract = AsyncMock(return_value='{"quotes": []}')
            engine.claude_extractor.estimate_cost = lambda t, l: 0.10

            # Fix class name for provider detection
            engine.claude_extractor.__class__.__name__ = "ClaudeExtractor"
            engine.gemini_extractor.__class__.__name__ = "GeminiExtractor"

            templates = [summary_template, quotes_template]
            transcript = "Test transcript"
            metadata = {"episode_url": "https://example.com/ep1"}

            # First extraction (fresh)
            results1, summary1 = await engine.extract_all(
                templates, transcript, metadata, use_cache=True
            )

            assert summary1.successful == 2
            assert summary1.cached == 0

            # Second extraction (should be cached)
            results2, summary2 = await engine.extract_all(
                templates, transcript, metadata, use_cache=True
            )

            assert summary2.successful == 0  # Cached doesn't count as "successful"
            assert summary2.cached == 2
