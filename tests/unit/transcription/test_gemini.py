"""Tests for Gemini transcriber."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from inkwell.transcription import CostEstimate, GeminiTranscriber, GeminiTranscriberWithSegments
from inkwell.utils.errors import APIError


class TestCostEstimate:
    """Test CostEstimate model."""

    def test_basic_estimate(self) -> None:
        """Test basic cost estimate creation."""
        estimate = CostEstimate(
            file_size_mb=10.0,
            estimated_cost_usd=0.00125,
        )

        assert estimate.file_size_mb == 10.0
        assert estimate.estimated_cost_usd == 0.00125
        assert estimate.rate_per_mb == 0.000125

    def test_formatted_cost_small(self) -> None:
        """Test formatting of small costs."""
        estimate = CostEstimate(
            file_size_mb=1.0,
            estimated_cost_usd=0.000125,
        )

        assert estimate.formatted_cost == "$0.0001"

    def test_formatted_cost_large(self) -> None:
        """Test formatting of larger costs."""
        estimate = CostEstimate(
            file_size_mb=1000.0,
            estimated_cost_usd=0.125,
        )

        assert estimate.formatted_cost == "$0.12"

    def test_validation_negative_cost(self) -> None:
        """Test validation rejects negative cost."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            CostEstimate(
                file_size_mb=10.0,
                estimated_cost_usd=-1.0,
            )


class TestGeminiTranscriber:
    """Test GeminiTranscriber class."""

    @pytest.fixture
    def mock_genai(self) -> Mock:
        """Mock google-genai SDK."""
        with patch("inkwell.transcription.gemini.genai") as mock:
            # Mock Client
            mock_client = MagicMock()
            mock.Client.return_value = mock_client

            # Mock file upload
            mock_file = MagicMock()
            mock_file.name = "test_audio.m4a"
            mock_client.files.upload.return_value = mock_file

            # Mock response
            mock_response = MagicMock()
            mock_response.text = "This is a test transcript. Speaker talks about testing."
            mock_client.models.generate_content.return_value = mock_response

            yield mock

    @pytest.fixture
    def transcriber(self, mock_genai: Mock) -> GeminiTranscriber:
        """Create GeminiTranscriber instance."""
        return GeminiTranscriber(api_key="test-api-key")

    @pytest.fixture
    def audio_file(self, tmp_path: Path) -> Path:
        """Create temporary audio file."""
        audio_path = tmp_path / "test_audio.m4a"
        # Create 10MB file
        audio_path.write_bytes(b"0" * (10 * 1024 * 1024))
        return audio_path

    def test_initialization_with_api_key(self, mock_genai: Mock) -> None:
        """Test initialization with explicit API key."""
        transcriber = GeminiTranscriber(api_key="test-key")

        assert transcriber.api_key == "test-key"
        assert transcriber.model_name == "gemini-2.5-flash"
        assert transcriber.cost_threshold_usd == 1.0

        mock_genai.Client.assert_called_once_with(api_key="test-key")

    def test_initialization_from_env(
        self, mock_genai: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test initialization from environment variable."""
        monkeypatch.setenv("GOOGLE_API_KEY", "env-key")

        transcriber = GeminiTranscriber()

        assert transcriber.api_key == "env-key"
        mock_genai.Client.assert_called_once_with(api_key="env-key")

    def test_initialization_from_deprecated_env(
        self, mock_genai: Mock, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Test initialization from deprecated GOOGLE_AI_API_KEY environment variable."""
        monkeypatch.setenv("GOOGLE_AI_API_KEY", "deprecated-key")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        transcriber = GeminiTranscriber()

        assert transcriber.api_key == "deprecated-key"
        # Warning goes to stderr
        captured = capsys.readouterr()
        assert "GOOGLE_AI_API_KEY is deprecated" in captured.err
        mock_genai.Client.assert_called_once_with(api_key="deprecated-key")

    def test_initialization_env_var_precedence(
        self, mock_genai: Mock, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Test that GOOGLE_API_KEY takes precedence over GOOGLE_AI_API_KEY."""
        monkeypatch.setenv("GOOGLE_API_KEY", "primary-key")
        monkeypatch.setenv("GOOGLE_AI_API_KEY", "deprecated-key")

        transcriber = GeminiTranscriber()

        assert transcriber.api_key == "primary-key"
        # Should not show deprecation warning when GOOGLE_API_KEY is set
        captured = capsys.readouterr()
        assert "GOOGLE_AI_API_KEY is deprecated" not in captured.err
        mock_genai.Client.assert_called_once_with(api_key="primary-key")

    def test_initialization_no_api_key(self, mock_genai: Mock) -> None:
        """Test initialization fails without API key."""
        with pytest.raises(ValueError, match="Google AI API key required"):
            GeminiTranscriber()

    def test_initialization_custom_params(self, mock_genai: Mock) -> None:
        """Test initialization with custom parameters."""
        callback = Mock()
        transcriber = GeminiTranscriber(
            api_key="test-key",
            model_name="gemini-1.5-pro",
            cost_threshold_usd=0.5,
            cost_confirmation_callback=callback,
        )

        assert transcriber.model_name == "gemini-1.5-pro"
        assert transcriber.cost_threshold_usd == 0.5
        assert transcriber.cost_confirmation_callback == callback

    @pytest.mark.asyncio
    async def test_can_transcribe_supported_format(
        self, transcriber: GeminiTranscriber, audio_file: Path
    ) -> None:
        """Test can_transcribe with supported format."""
        assert await transcriber.can_transcribe(audio_file) is True

    @pytest.mark.asyncio
    async def test_can_transcribe_unsupported_format(
        self, transcriber: GeminiTranscriber, tmp_path: Path
    ) -> None:
        """Test can_transcribe with unsupported format."""
        unsupported_file = tmp_path / "test.txt"
        unsupported_file.write_text("test")

        assert await transcriber.can_transcribe(unsupported_file) is False

    @pytest.mark.asyncio
    async def test_can_transcribe_missing_file(
        self, transcriber: GeminiTranscriber, tmp_path: Path
    ) -> None:
        """Test can_transcribe with missing file."""
        missing_file = tmp_path / "nonexistent.m4a"

        assert await transcriber.can_transcribe(missing_file) is False

    def test_estimate_cost(self, transcriber: GeminiTranscriber, audio_file: Path) -> None:
        """Test cost estimation."""
        estimate = transcriber._estimate_cost(audio_file)

        assert estimate.file_size_mb == 10.0
        assert estimate.estimated_cost_usd == pytest.approx(0.00125, rel=0.01)
        assert estimate.rate_per_mb == 0.000125

    @pytest.mark.asyncio
    async def test_confirm_cost_below_threshold(self, transcriber: GeminiTranscriber) -> None:
        """Test cost confirmation auto-approves below threshold."""
        estimate = CostEstimate(
            file_size_mb=1.0,
            estimated_cost_usd=0.0001,  # Below $1.00 threshold
        )

        result = await transcriber._confirm_cost(estimate)

        assert result is True

    @pytest.mark.asyncio
    async def test_confirm_cost_above_threshold_with_callback(self, mock_genai: Mock) -> None:
        """Test cost confirmation uses callback above threshold."""
        callback = Mock(return_value=True)
        transcriber = GeminiTranscriber(
            api_key="test-key",
            cost_threshold_usd=0.5,
            cost_confirmation_callback=callback,
        )

        estimate = CostEstimate(
            file_size_mb=10000.0,
            estimated_cost_usd=1.25,  # Above $0.50 threshold
        )

        result = await transcriber._confirm_cost(estimate)

        assert result is True
        callback.assert_called_once_with(estimate)

    @pytest.mark.asyncio
    async def test_confirm_cost_above_threshold_rejected(self, mock_genai: Mock) -> None:
        """Test cost confirmation can be rejected."""
        callback = Mock(return_value=False)
        transcriber = GeminiTranscriber(
            api_key="test-key",
            cost_threshold_usd=0.5,
            cost_confirmation_callback=callback,
        )

        estimate = CostEstimate(
            file_size_mb=10000.0,
            estimated_cost_usd=1.25,
        )

        result = await transcriber._confirm_cost(estimate)

        assert result is False

    @pytest.mark.asyncio
    async def test_transcribe_success(
        self, transcriber: GeminiTranscriber, audio_file: Path, mock_genai: Mock
    ) -> None:
        """Test successful transcription."""
        transcript = await transcriber.transcribe(audio_file)

        assert transcript.source == "gemini"
        assert transcript.language == "en"
        assert len(transcript.segments) == 1
        assert "test transcript" in transcript.segments[0].text
        assert transcript.cost_usd == pytest.approx(0.00125, rel=0.01)

        # Verify API calls (new SDK uses client.files.upload and client.models.generate_content)
        transcriber.client.files.upload.assert_called_once()
        transcriber.client.models.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_with_episode_url(
        self, transcriber: GeminiTranscriber, audio_file: Path
    ) -> None:
        """Test transcription with episode URL."""
        transcript = await transcriber.transcribe(
            audio_file, episode_url="https://example.com/podcast"
        )

        assert transcript.episode_url == "https://example.com/podcast"

    @pytest.mark.asyncio
    async def test_transcribe_missing_file(
        self, transcriber: GeminiTranscriber, tmp_path: Path
    ) -> None:
        """Test transcription fails for missing file."""
        missing_file = tmp_path / "nonexistent.m4a"

        with pytest.raises(APIError, match="Audio file not found"):
            await transcriber.transcribe(missing_file)

    @pytest.mark.asyncio
    async def test_transcribe_unsupported_format(
        self, transcriber: GeminiTranscriber, tmp_path: Path
    ) -> None:
        """Test transcription fails for unsupported format."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("test")

        with pytest.raises(APIError, match="Unsupported audio format"):
            await transcriber.transcribe(txt_file)

    @pytest.mark.asyncio
    async def test_transcribe_cost_rejected(self, mock_genai: Mock, tmp_path: Path) -> None:
        """Test transcription cancelled when cost rejected."""
        callback = Mock(return_value=False)
        transcriber = GeminiTranscriber(
            api_key="test-key",
            cost_threshold_usd=0.0,  # Force callback for any cost
            cost_confirmation_callback=callback,
        )

        audio_file = tmp_path / "large_audio.m4a"
        audio_file.write_bytes(b"0" * (10 * 1024 * 1024))

        with pytest.raises(APIError, match="Transcription cancelled"):
            await transcriber.transcribe(audio_file)

    @pytest.mark.asyncio
    async def test_transcribe_api_error(
        self, transcriber: GeminiTranscriber, audio_file: Path, mock_genai: Mock
    ) -> None:
        """Test transcription handles API errors."""
        transcriber.client.files.upload.side_effect = Exception("API error")

        with pytest.raises(APIError, match="Failed to transcribe"):
            await transcriber.transcribe(audio_file)

    @pytest.mark.asyncio
    async def test_transcribe_empty_response(
        self, transcriber: GeminiTranscriber, audio_file: Path, mock_genai: Mock
    ) -> None:
        """Test transcription handles empty response."""
        mock_response = MagicMock()
        mock_response.text = ""
        transcriber.client.models.generate_content.return_value = mock_response

        with pytest.raises(APIError, match="empty transcript"):
            await transcriber.transcribe(audio_file)


class TestGeminiTranscriberWithSegments:
    """Test GeminiTranscriberWithSegments class."""

    @pytest.fixture
    def mock_genai(self) -> Mock:
        """Mock google-genai SDK."""
        with patch("inkwell.transcription.gemini.genai") as mock:
            # Mock Client
            mock_client = MagicMock()
            mock.Client.return_value = mock_client

            mock_file = MagicMock()
            mock_client.files.upload.return_value = mock_file

            # Default response
            mock_response = MagicMock()
            mock_response.text = "Test transcript"
            mock_client.models.generate_content.return_value = mock_response

            yield mock

    @pytest.fixture
    def transcriber(self, mock_genai: Mock) -> GeminiTranscriberWithSegments:
        """Create GeminiTranscriberWithSegments instance."""
        return GeminiTranscriberWithSegments(api_key="test-api-key")

    @pytest.fixture
    def audio_file(self, tmp_path: Path) -> Path:
        """Create temporary audio file."""
        audio_path = tmp_path / "test_audio.m4a"
        audio_path.write_bytes(b"0" * (10 * 1024 * 1024))
        return audio_path

    @pytest.mark.asyncio
    async def test_parse_timestamps_hhmmss_format(
        self, transcriber: GeminiTranscriberWithSegments, audio_file: Path, mock_genai: Mock
    ) -> None:
        """Test parsing timestamps in HH:MM:SS format."""
        mock_response = MagicMock()
        mock_response.text = (
            "[00:00:00] Speaker: First segment\n"
            "[00:01:30] Speaker: Second segment\n"
            "[00:03:00] Speaker: Third segment"
        )
        transcriber.client.models.generate_content.return_value = mock_response

        transcript = await transcriber.transcribe(audio_file)

        assert len(transcript.segments) == 3
        assert transcript.segments[0].start == 0.0
        assert transcript.segments[0].text == "First segment"
        assert transcript.segments[0].duration == 90.0  # 1:30 - 0:00

        assert transcript.segments[1].start == 90.0
        assert transcript.segments[1].text == "Second segment"
        assert transcript.segments[1].duration == 90.0  # 3:00 - 1:30

        assert transcript.segments[2].start == 180.0
        assert transcript.segments[2].text == "Third segment"

    @pytest.mark.asyncio
    async def test_parse_timestamps_mmss_format(
        self, transcriber: GeminiTranscriberWithSegments, audio_file: Path, mock_genai: Mock
    ) -> None:
        """Test parsing timestamps in MM:SS format."""
        mock_response = MagicMock()
        mock_response.text = (
            "[0:00] Speaker 1: Hello\n[1:30] Speaker 2: World\n[3:15] Speaker 1: Goodbye"
        )
        transcriber.client.models.generate_content.return_value = mock_response

        transcript = await transcriber.transcribe(audio_file)

        assert len(transcript.segments) == 3
        assert transcript.segments[0].start == 0.0
        assert transcript.segments[0].duration == 90.0

        assert transcript.segments[1].start == 90.0
        assert transcript.segments[1].duration == 105.0

        assert transcript.segments[2].start == 195.0

    @pytest.mark.asyncio
    async def test_parse_no_timestamps_fallback(
        self, transcriber: GeminiTranscriberWithSegments, audio_file: Path, mock_genai: Mock
    ) -> None:
        """Test fallback to single segment when no timestamps."""
        mock_response = MagicMock()
        mock_response.text = "This is a transcript without any timestamp markers."
        transcriber.client.models.generate_content.return_value = mock_response

        transcript = await transcriber.transcribe(audio_file)

        assert len(transcript.segments) == 1
        assert transcript.segments[0].start == 0.0
        assert transcript.segments[0].duration == 0.0
        assert "without any timestamp" in transcript.segments[0].text

    @pytest.mark.asyncio
    async def test_parse_multiline_segments(
        self, transcriber: GeminiTranscriberWithSegments, audio_file: Path, mock_genai: Mock
    ) -> None:
        """Test parsing segments with multiple lines."""
        mock_response = MagicMock()
        mock_response.text = (
            "[0:00] First line\nContinuation of first\n[1:00] Second segment\nWith continuation"
        )
        transcriber.client.models.generate_content.return_value = mock_response

        transcript = await transcriber.transcribe(audio_file)

        assert len(transcript.segments) == 2
        assert "First line" in transcript.segments[0].text
        assert "Continuation of first" in transcript.segments[0].text
        assert "Second segment" in transcript.segments[1].text
        assert "With continuation" in transcript.segments[1].text
