"""Unit tests for Gemini extractor."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from inkwell.extraction.extractors.gemini import GeminiExtractor
from inkwell.extraction.models import ExtractionTemplate
from inkwell.utils.api_keys import APIKeyError
from inkwell.utils.errors import APIError, ValidationError


@pytest.fixture
def mock_api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set mock API key."""
    # Use a valid-format API key for testing (meets length and format requirements)
    api_key = "AIzaSyD" + "X" * 32  # Valid Gemini key format
    monkeypatch.setenv("GOOGLE_API_KEY", api_key)
    return api_key


@pytest.fixture
def sample_template() -> ExtractionTemplate:
    """Create sample extraction template."""
    return ExtractionTemplate(
        name="test-template",
        version="1.0",
        description="Test template",
        system_prompt="You are a test assistant.",
        user_prompt_template="Extract from: {{ transcript }}",
        expected_format="text",
        max_tokens=1000,
        temperature=0.3,
    )


@pytest.fixture
def json_template() -> ExtractionTemplate:
    """Create JSON extraction template with schema."""
    return ExtractionTemplate(
        name="json-test",
        version="1.0",
        description="JSON test",
        system_prompt="Extract as JSON.",
        user_prompt_template="{{ transcript }}",
        expected_format="json",
        output_schema={
            "type": "object",
            "required": ["items"],
            "properties": {"items": {"type": "array"}},
        },
        max_tokens=1000,
        temperature=0.2,
    )


class TestGeminiExtractorInit:
    """Tests for GeminiExtractor initialization."""

    def test_init_with_api_key(self) -> None:
        """Test initializing with explicit API key."""
        # Use a valid-format test key
        test_key = "AIzaSyD" + "X" * 32
        with patch("inkwell.extraction.extractors.gemini.genai.Client"):
            extractor = GeminiExtractor(api_key=test_key)
            assert extractor.api_key == test_key

    def test_init_with_env_var(self, mock_api_key: str) -> None:
        """Test initializing with env var API key."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client"):
            extractor = GeminiExtractor()
            assert extractor.api_key == mock_api_key

    def test_init_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization fails without API key."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        with pytest.raises(APIKeyError) as exc_info:
            GeminiExtractor()

        assert "API key is required" in str(exc_info.value)

    def test_supports_structured_output(self, mock_api_key: str) -> None:
        """Test that Gemini supports structured output."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client"):
            extractor = GeminiExtractor()
            assert extractor.supports_structured_output() is True


class TestGeminiExtractorExtract:
    """Tests for Gemini extraction."""

    @pytest.mark.asyncio
    async def test_extract_text_success(
        self, mock_api_key: str, sample_template: ExtractionTemplate
    ) -> None:
        """Test successful text extraction."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock response
            mock_response = Mock()
            mock_response.text = "Extracted content here"
            mock_client.models.generate_content.return_value = mock_response

            extractor = GeminiExtractor()

            # Patch asyncio.to_thread to run sync
            with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_response)):
                result = await extractor.extract(
                    template=sample_template,
                    transcript="Test transcript",
                    metadata={"podcast_name": "Test Podcast"},
                )

                assert result == "Extracted content here"

    @pytest.mark.asyncio
    async def test_extract_json_success(
        self, mock_api_key: str, json_template: ExtractionTemplate
    ) -> None:
        """Test successful JSON extraction."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock valid JSON response
            mock_response = Mock()
            mock_response.text = '{"items": ["one", "two"]}'
            mock_client.models.generate_content.return_value = mock_response

            extractor = GeminiExtractor()

            with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_response)):
                result = await extractor.extract(
                    template=json_template,
                    transcript="Test transcript",
                    metadata={},
                )

                assert result == '{"items": ["one", "two"]}'

    @pytest.mark.asyncio
    async def test_extract_empty_response(
        self, mock_api_key: str, sample_template: ExtractionTemplate
    ) -> None:
        """Test extraction with empty response raises error."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            mock_response = Mock()
            mock_response.text = ""

            extractor = GeminiExtractor()

            with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_response)):
                with pytest.raises(ValidationError) as exc_info:
                    await extractor.extract(
                        template=sample_template,
                        transcript="Test",
                        metadata={},
                    )

                assert "empty response" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extract_invalid_json(
        self, mock_api_key: str, json_template: ExtractionTemplate
    ) -> None:
        """Test extraction with invalid JSON raises error."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock invalid JSON response
            mock_response = Mock()
            mock_response.text = "not valid json"

            extractor = GeminiExtractor()

            with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_response)):
                with pytest.raises(ValidationError) as exc_info:
                    await extractor.extract(
                        template=json_template,
                        transcript="Test",
                        metadata={},
                    )

                assert "invalid json" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extract_missing_required_field(
        self, mock_api_key: str, json_template: ExtractionTemplate
    ) -> None:
        """Test extraction with missing required field raises error."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock JSON missing required field
            mock_response = Mock()
            mock_response.text = '{"other_field": "value"}'  # Missing "items"

            extractor = GeminiExtractor()

            with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_response)):
                with pytest.raises(ValidationError) as exc_info:
                    await extractor.extract(
                        template=json_template,
                        transcript="Test",
                        metadata={},
                    )

                assert "required field" in str(exc_info.value).lower()
                assert "items" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extract_api_error(
        self, mock_api_key: str, sample_template: ExtractionTemplate
    ) -> None:
        """Test extraction with API error raises APIError."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            extractor = GeminiExtractor()

            # Mock API error
            with patch("asyncio.to_thread", new=AsyncMock()) as mock_thread:
                mock_thread.side_effect = Exception("API error")

                with pytest.raises(APIError) as exc_info:
                    await extractor.extract(
                        template=sample_template,
                        transcript="Test",
                        metadata={},
                    )

                assert exc_info.value.provider == "gemini"
                assert "api error" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extract_combines_system_and_user_prompt(
        self, mock_api_key: str, sample_template: ExtractionTemplate
    ) -> None:
        """Test that system prompt is combined with user prompt."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            mock_response = Mock()
            mock_response.text = "Result"

            captured_prompt = []

            async def capture_call(*args, **kwargs):
                # Capture the prompt from kwargs (new SDK uses keyword args)
                if "contents" in kwargs:
                    captured_prompt.append(kwargs["contents"])
                return mock_response

            extractor = GeminiExtractor()

            with patch("asyncio.to_thread", new=capture_call):
                await extractor.extract(
                    template=sample_template,
                    transcript="Test",
                    metadata={},
                )

                # Check that system prompt was combined
                assert len(captured_prompt) > 0
                full_prompt = captured_prompt[0]
                assert sample_template.system_prompt in full_prompt


class TestGeminiExtractorCostEstimation:
    """Tests for cost estimation."""

    def test_estimate_cost_basic_short_context(self, mock_api_key: str) -> None:
        """Test basic cost estimation for short context."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client"):
            extractor = GeminiExtractor()

            template = ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="System prompt",
                user_prompt_template="User prompt",
                expected_format="text",
                max_tokens=1000,
                temperature=0.3,
            )

            # Short transcript (< 128K tokens)
            cost = extractor.estimate_cost(template, transcript_length=10000)

            # Should be non-zero
            assert cost > 0
            # Should be cheaper than Claude (< $0.10 for this input)
            assert cost < 0.1

    def test_estimate_cost_long_context(self, mock_api_key: str) -> None:
        """Test cost estimation for long context (tiered pricing)."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client"):
            extractor = GeminiExtractor()

            template = ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="System",
                user_prompt_template="User",
                expected_format="text",
                max_tokens=1000,
                temperature=0.3,
            )

            # Long transcript (> 128K tokens = 512K characters)
            cost_long = extractor.estimate_cost(template, transcript_length=600000)
            cost_short = extractor.estimate_cost(template, transcript_length=10000)

            # Long context should cost more
            assert cost_long > cost_short

    def test_estimate_cost_with_examples(self, mock_api_key: str) -> None:
        """Test cost estimation includes few-shot examples."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client"):
            extractor = GeminiExtractor()

            template_with_examples = ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="System",
                user_prompt_template="User",
                expected_format="json",
                max_tokens=1000,
                temperature=0.3,
                few_shot_examples=[
                    {"input": "Example input", "output": {"key": "value"}},
                ],
            )

            template_no_examples = ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="System",
                user_prompt_template="User",
                expected_format="json",
                max_tokens=1000,
                temperature=0.3,
            )

            cost_with = extractor.estimate_cost(template_with_examples, transcript_length=5000)
            cost_without = extractor.estimate_cost(template_no_examples, transcript_length=5000)

            # Cost with examples should be higher
            assert cost_with > cost_without

    def test_estimate_cost_proportional(self, mock_api_key: str) -> None:
        """Test cost scales with transcript length."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client"):
            extractor = GeminiExtractor()

            template = ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="System",
                user_prompt_template="User",
                expected_format="text",
                max_tokens=1000,
                temperature=0.3,
            )

            cost_short = extractor.estimate_cost(template, transcript_length=5000)
            cost_long = extractor.estimate_cost(template, transcript_length=50000)

            # Longer transcript should cost more
            assert cost_long > cost_short


class TestGeminiExtractorComparison:
    """Tests comparing Gemini to Claude."""

    def test_gemini_cheaper_than_claude(self, mock_api_key: str) -> None:
        """Test that Gemini is significantly cheaper than Claude."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client"):
            from inkwell.extraction.extractors.claude import ClaudeExtractor

            gemini = GeminiExtractor()
            # Use valid-format Claude API key for testing
            claude = ClaudeExtractor(api_key="sk-ant-api03-" + "X" * 32)

            template = ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="System prompt",
                user_prompt_template="User prompt",
                expected_format="text",
                max_tokens=1000,
                temperature=0.3,
            )

            gemini_cost = gemini.estimate_cost(template, transcript_length=20000)
            claude_cost = claude.estimate_cost(template, transcript_length=20000)

            # Gemini should be much cheaper (at least 10x based on pricing)
            assert gemini_cost < claude_cost
            assert claude_cost / gemini_cost > 10


class TestGeminiExtractorPromptBuilding:
    """Tests for prompt building (inherited from base)."""

    def test_build_prompt_basic(self, mock_api_key: str) -> None:
        """Test basic prompt building."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client"):
            extractor = GeminiExtractor()

            template = ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="System",
                user_prompt_template="Process: {{ transcript }}",
                expected_format="text",
            )

            prompt = extractor.build_prompt(
                template=template,
                transcript="Hello world",
                metadata={"podcast_name": "Test"},
            )

            assert "Hello world" in prompt
            assert "Process:" in prompt

    def test_build_prompt_with_metadata(self, mock_api_key: str) -> None:
        """Test prompt building with metadata."""
        with patch("inkwell.extraction.extractors.gemini.genai.Client"):
            extractor = GeminiExtractor()

            template = ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="System",
                user_prompt_template="Podcast: {{ metadata.podcast_name }}\n{{ transcript }}",
                expected_format="text",
            )

            prompt = extractor.build_prompt(
                template=template,
                transcript="Content",
                metadata={"podcast_name": "My Podcast"},
            )

            assert "My Podcast" in prompt
            assert "Content" in prompt
