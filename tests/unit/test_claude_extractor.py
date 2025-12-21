"""Unit tests for Claude extractor."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from anthropic.types import ContentBlock, Message

from inkwell.extraction.extractors.claude import ClaudeExtractor
from inkwell.extraction.models import ExtractionTemplate
from inkwell.utils.api_keys import APIKeyError
from inkwell.utils.errors import APIError, ValidationError


@pytest.fixture
def mock_api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set mock API key."""
    # Use a valid-format API key for testing (meets length and format requirements)
    api_key = "sk-ant-api03-" + "X" * 32  # Valid Claude key format
    monkeypatch.setenv("ANTHROPIC_API_KEY", api_key)
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


class TestClaudeExtractorInit:
    """Tests for ClaudeExtractor initialization."""

    def test_init_with_api_key(self) -> None:
        """Test initializing with explicit API key."""
        # Use a valid-format test key
        test_key = "sk-ant-api03-" + "X" * 32
        extractor = ClaudeExtractor(api_key=test_key)
        assert extractor.api_key == test_key

    def test_init_with_env_var(self, mock_api_key: str) -> None:
        """Test initializing with env var API key."""
        extractor = ClaudeExtractor()
        assert extractor.api_key == mock_api_key

    def test_init_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization fails without API key."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(APIKeyError) as exc_info:
            ClaudeExtractor()

        assert "API key is required" in str(exc_info.value)

    def test_supports_structured_output(self, mock_api_key: str) -> None:
        """Test that Claude supports structured output."""
        extractor = ClaudeExtractor()
        assert extractor.supports_structured_output() is True


class TestClaudeExtractorExtract:
    """Tests for Claude extraction."""

    @pytest.mark.asyncio
    async def test_extract_text_success(
        self, mock_api_key: str, sample_template: ExtractionTemplate
    ) -> None:
        """Test successful text extraction."""
        extractor = ClaudeExtractor()

        # Mock response
        mock_response = Mock(spec=Message)
        mock_content = Mock(spec=ContentBlock)
        mock_content.text = "Extracted content here"
        mock_response.content = [mock_content]

        # Patch client
        with patch.object(extractor.client.messages, "create", new=AsyncMock()) as mock_create:
            mock_create.return_value = mock_response

            result = await extractor.extract(
                template=sample_template,
                transcript="Test transcript",
                metadata={"podcast_name": "Test Podcast"},
            )

            assert result == "Extracted content here"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_json_success(
        self, mock_api_key: str, json_template: ExtractionTemplate
    ) -> None:
        """Test successful JSON extraction."""
        extractor = ClaudeExtractor()

        # Mock valid JSON response
        mock_response = Mock(spec=Message)
        mock_content = Mock(spec=ContentBlock)
        mock_content.text = '{"items": ["one", "two"]}'
        mock_response.content = [mock_content]

        with patch.object(extractor.client.messages, "create", new=AsyncMock()) as mock_create:
            mock_create.return_value = mock_response

            result = await extractor.extract(
                template=json_template,
                transcript="Test transcript",
                metadata={},
            )

            assert result == '{"items": ["one", "two"]}'

    @pytest.mark.asyncio
    async def test_extract_multiple_content_blocks(
        self, mock_api_key: str, sample_template: ExtractionTemplate
    ) -> None:
        """Test extraction with multiple content blocks."""
        extractor = ClaudeExtractor()

        # Mock response with multiple blocks
        mock_response = Mock(spec=Message)
        mock_block1 = Mock(spec=ContentBlock)
        mock_block1.text = "Part one "
        mock_block2 = Mock(spec=ContentBlock)
        mock_block2.text = "part two"
        mock_response.content = [mock_block1, mock_block2]

        with patch.object(extractor.client.messages, "create", new=AsyncMock()) as mock_create:
            mock_create.return_value = mock_response

            result = await extractor.extract(
                template=sample_template,
                transcript="Test",
                metadata={},
            )

            assert result == "Part one part two"

    @pytest.mark.asyncio
    async def test_extract_empty_response(
        self, mock_api_key: str, sample_template: ExtractionTemplate
    ) -> None:
        """Test extraction with empty response raises error."""
        extractor = ClaudeExtractor()

        mock_response = Mock(spec=Message)
        mock_response.content = []

        with patch.object(extractor.client.messages, "create", new=AsyncMock()) as mock_create:
            mock_create.return_value = mock_response

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
        extractor = ClaudeExtractor()

        # Mock invalid JSON response
        mock_response = Mock(spec=Message)
        mock_content = Mock(spec=ContentBlock)
        mock_content.text = "not valid json"
        mock_response.content = [mock_content]

        with patch.object(extractor.client.messages, "create", new=AsyncMock()) as mock_create:
            mock_create.return_value = mock_response

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
        extractor = ClaudeExtractor()

        # Mock JSON missing required field
        mock_response = Mock(spec=Message)
        mock_content = Mock(spec=ContentBlock)
        mock_content.text = '{"other_field": "value"}'  # Missing "items"
        mock_response.content = [mock_content]

        with patch.object(extractor.client.messages, "create", new=AsyncMock()) as mock_create:
            mock_create.return_value = mock_response

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
        extractor = ClaudeExtractor()

        # Mock API error
        with patch.object(extractor.client.messages, "create", new=AsyncMock()) as mock_create:
            mock_create.side_effect = Exception("API error")

            with pytest.raises(APIError) as exc_info:
                await extractor.extract(
                    template=sample_template,
                    transcript="Test",
                    metadata={},
                )

            assert exc_info.value.provider == "claude"
            assert "api error" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extract_with_json_mode(
        self, mock_api_key: str, json_template: ExtractionTemplate
    ) -> None:
        """Test that JSON mode is enabled for JSON templates."""
        extractor = ClaudeExtractor()

        mock_response = Mock(spec=Message)
        mock_content = Mock(spec=ContentBlock)
        mock_content.text = '{"items": []}'
        mock_response.content = [mock_content]

        with patch.object(extractor.client.messages, "create", new=AsyncMock()) as mock_create:
            mock_create.return_value = mock_response

            await extractor.extract(
                template=json_template,
                transcript="Test",
                metadata={},
            )

            # Verify JSON mode was enabled
            call_kwargs = mock_create.call_args.kwargs
            assert "response_format" in call_kwargs
            assert call_kwargs["response_format"]["type"] == "json_object"


class TestClaudeExtractorCostEstimation:
    """Tests for cost estimation."""

    def test_estimate_cost_basic(self, mock_api_key: str) -> None:
        """Test basic cost estimation."""
        extractor = ClaudeExtractor()

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

        cost = extractor.estimate_cost(template, transcript_length=10000)

        # Should be non-zero
        assert cost > 0
        # Should be reasonable (< $1 for this input)
        assert cost < 1.0

    def test_estimate_cost_with_examples(self, mock_api_key: str) -> None:
        """Test cost estimation includes few-shot examples."""
        extractor = ClaudeExtractor()

        template = ExtractionTemplate(
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
                {"input": "Another example", "output": {"key": "value2"}},
            ],
        )

        cost_with_examples = extractor.estimate_cost(template, transcript_length=5000)

        # Create template without examples
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

        cost_no_examples = extractor.estimate_cost(template_no_examples, transcript_length=5000)

        # Cost with examples should be higher
        assert cost_with_examples > cost_no_examples

    def test_estimate_cost_proportional(self, mock_api_key: str) -> None:
        """Test cost scales with transcript length."""
        extractor = ClaudeExtractor()

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
        # Should be roughly 10x, but realistically 2-3x due to fixed costs (system prompt, output tokens)
        assert cost_long > cost_short * 2


class TestClaudeExtractorPromptBuilding:
    """Tests for prompt building (inherited from base)."""

    def test_build_prompt_basic(self, mock_api_key: str) -> None:
        """Test basic prompt building."""
        extractor = ClaudeExtractor()

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
        extractor = ClaudeExtractor()

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

    def test_build_prompt_with_examples(self, mock_api_key: str) -> None:
        """Test prompt building includes few-shot examples."""
        extractor = ClaudeExtractor()

        template = ExtractionTemplate(
            name="test",
            version="1.0",
            description="Test",
            system_prompt="System",
            user_prompt_template="{{ transcript }}",
            expected_format="json",
            few_shot_examples=[
                {"input": "Example 1", "output": {"result": "output1"}},
            ],
        )

        prompt = extractor.build_prompt(
            template=template,
            transcript="Transcript",
            metadata={},
        )

        assert "Example" in prompt
        assert "Example 1" in prompt
        assert "output1" in prompt
