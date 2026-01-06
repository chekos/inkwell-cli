"""Unit tests for TranscriptionPlugin base class and integration."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from inkwell.plugins import PluginRegistry, TranscriptionPlugin, TranscriptionRequest
from inkwell.plugins.base import PLUGIN_API_VERSION


class TestTranscriptionRequest:
    """Tests for TranscriptionRequest dataclass."""

    def test_url_source_type(self) -> None:
        """Test that URL-based request has correct source_type."""
        request = TranscriptionRequest(url="https://youtube.com/watch?v=abc123")
        assert request.source_type == "url"
        assert request.url == "https://youtube.com/watch?v=abc123"
        assert request.file_path is None
        assert request.audio_bytes is None

    def test_file_source_type(self) -> None:
        """Test that file-based request has correct source_type."""
        path = Path("/tmp/audio.mp3")
        request = TranscriptionRequest(file_path=path)
        assert request.source_type == "file"
        assert request.file_path == path
        assert request.url is None
        assert request.audio_bytes is None

    def test_bytes_source_type(self) -> None:
        """Test that bytes-based request has correct source_type."""
        audio_data = b"fake audio data"
        request = TranscriptionRequest(audio_bytes=audio_data)
        assert request.source_type == "bytes"
        assert request.audio_bytes == audio_data
        assert request.url is None
        assert request.file_path is None

    def test_requires_exactly_one_source(self) -> None:
        """Test that request requires exactly one source."""
        # No sources should fail
        with pytest.raises(ValueError, match="Exactly one"):
            TranscriptionRequest()

        # Multiple sources should fail
        with pytest.raises(ValueError, match="Exactly one"):
            TranscriptionRequest(
                url="https://youtube.com/watch?v=abc123",
                file_path=Path("/tmp/audio.mp3"),
            )


class TestTranscriptionPluginBase:
    """Tests for TranscriptionPlugin base class."""

    def test_plugin_requires_abstract_methods(self) -> None:
        """Test that plugins must implement abstract methods."""
        # This should raise TypeError for abstract class
        with pytest.raises(TypeError, match="abstract"):

            class BadPlugin(TranscriptionPlugin):
                NAME = "bad-plugin"
                VERSION = "1.0.0"
                DESCRIPTION = "Incomplete plugin"

            BadPlugin()  # Should fail because abstract methods not implemented

    def test_plugin_inherits_from_inkwell_plugin(self) -> None:
        """Test that TranscriptionPlugin inherits from InkwellPlugin."""
        from inkwell.plugins.base import InkwellPlugin

        assert issubclass(TranscriptionPlugin, InkwellPlugin)

    def test_plugin_api_version(self) -> None:
        """Test that TranscriptionPlugin has correct API version."""
        assert TranscriptionPlugin.API_VERSION == PLUGIN_API_VERSION

    def test_plugin_has_capabilities(self) -> None:
        """Test that TranscriptionPlugin has default capabilities."""
        assert "formats" in TranscriptionPlugin.CAPABILITIES
        assert "supports_file" in TranscriptionPlugin.CAPABILITIES
        assert "supports_url" in TranscriptionPlugin.CAPABILITIES
        assert "requires_internet" in TranscriptionPlugin.CAPABILITIES

    def test_default_estimate_cost_is_zero(self) -> None:
        """Test that default estimate_cost returns 0 (free)."""
        # Create a concrete test plugin
        class TestPlugin(TranscriptionPlugin):
            NAME = "test"
            VERSION = "1.0.0"
            DESCRIPTION = "Test plugin"

            async def transcribe(self, request: TranscriptionRequest):
                pass

        plugin = TestPlugin()
        assert plugin.estimate_cost(3600.0) == 0.0  # 1 hour


class TestYouTubePluginIntegration:
    """Tests for YouTubeTranscriber as a plugin."""

    def test_youtube_transcriber_is_transcription_plugin(self) -> None:
        """Test that YouTubeTranscriber is a TranscriptionPlugin."""
        from inkwell.transcription.youtube import YouTubeTranscriber

        assert issubclass(YouTubeTranscriber, TranscriptionPlugin)

    def test_youtube_transcriber_has_required_metadata(self) -> None:
        """Test that YouTubeTranscriber has required plugin metadata."""
        from inkwell.transcription.youtube import YouTubeTranscriber

        assert YouTubeTranscriber.NAME == "youtube"
        assert YouTubeTranscriber.VERSION == "1.0.0"
        assert YouTubeTranscriber.DESCRIPTION is not None
        assert len(YouTubeTranscriber.DESCRIPTION) > 0

    def test_youtube_transcriber_handles_urls(self) -> None:
        """Test that YouTubeTranscriber declares URL handling."""
        from inkwell.transcription.youtube import YouTubeTranscriber

        assert "youtube.com" in YouTubeTranscriber.HANDLES_URLS
        assert "youtu.be" in YouTubeTranscriber.HANDLES_URLS

    def test_youtube_transcriber_capabilities(self) -> None:
        """Test YouTubeTranscriber capabilities."""
        from inkwell.transcription.youtube import YouTubeTranscriber

        caps = YouTubeTranscriber.CAPABILITIES
        assert caps["supports_url"] is True
        assert caps["supports_file"] is False
        assert caps["requires_internet"] is True

    def test_youtube_can_handle_youtube_url(self) -> None:
        """Test can_handle for YouTube URLs."""
        from inkwell.transcription.youtube import YouTubeTranscriber

        transcriber = YouTubeTranscriber()

        # Should handle YouTube URLs
        youtube_request = TranscriptionRequest(url="https://youtube.com/watch?v=abc123")
        assert transcriber.can_handle(youtube_request) is True

        youtu_be_request = TranscriptionRequest(url="https://youtu.be/xyz789")
        assert transcriber.can_handle(youtu_be_request) is True

        # Should not handle non-YouTube URLs
        other_request = TranscriptionRequest(url="https://example.com/audio.mp3")
        assert transcriber.can_handle(other_request) is False

        # Should not handle file requests
        file_request = TranscriptionRequest(file_path=Path("/tmp/audio.mp3"))
        assert transcriber.can_handle(file_request) is False

    def test_youtube_estimate_cost_is_zero(self) -> None:
        """Test that YouTube transcription is free."""
        from inkwell.transcription.youtube import YouTubeTranscriber

        transcriber = YouTubeTranscriber()
        assert transcriber.estimate_cost(3600.0) == 0.0


class TestGeminiPluginIntegration:
    """Tests for GeminiTranscriber as a plugin."""

    def test_gemini_transcriber_is_transcription_plugin(self) -> None:
        """Test that GeminiTranscriber is a TranscriptionPlugin."""
        from inkwell.transcription.gemini import GeminiTranscriber

        assert issubclass(GeminiTranscriber, TranscriptionPlugin)

    def test_gemini_transcriber_has_required_metadata(self) -> None:
        """Test that GeminiTranscriber has required plugin metadata."""
        from inkwell.transcription.gemini import GeminiTranscriber

        assert GeminiTranscriber.NAME == "gemini"
        assert GeminiTranscriber.VERSION == "1.0.0"
        assert GeminiTranscriber.DESCRIPTION is not None
        assert len(GeminiTranscriber.DESCRIPTION) > 0

    def test_gemini_transcriber_capabilities(self) -> None:
        """Test GeminiTranscriber capabilities."""
        from inkwell.transcription.gemini import GeminiTranscriber

        caps = GeminiTranscriber.CAPABILITIES
        assert caps["supports_file"] is True
        assert caps["supports_url"] is False
        assert caps["requires_internet"] is True
        assert "mp3" in caps["formats"]
        assert "wav" in caps["formats"]

    def test_gemini_can_handle_file_request(self, tmp_path: Path) -> None:
        """Test can_handle for file requests."""
        from inkwell.transcription.gemini import GeminiTranscriber

        # Can't instantiate without API key in normal mode
        # Create with lazy_init to skip API key requirement
        transcriber = GeminiTranscriber.__new__(GeminiTranscriber)
        object.__setattr__(transcriber, "_lazy_init", True)

        # Create a test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Should handle file requests with supported formats
        request = TranscriptionRequest(file_path=audio_file)
        assert transcriber.can_handle(request) is True

        # Should not handle unsupported formats
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not audio")
        txt_request = TranscriptionRequest(file_path=txt_file)
        assert transcriber.can_handle(txt_request) is False

        # Should not handle URL requests
        url_request = TranscriptionRequest(url="https://example.com/audio.mp3")
        assert transcriber.can_handle(url_request) is False

    def test_gemini_estimate_cost(self) -> None:
        """Test that Gemini has non-zero cost estimation."""
        from inkwell.transcription.gemini import GeminiTranscriber

        transcriber = GeminiTranscriber.__new__(GeminiTranscriber)

        # 1 hour of audio should have some cost
        cost = transcriber.estimate_cost(3600.0)
        assert cost > 0.0


class TestTranscriptionPluginRegistry:
    """Tests for TranscriptionPlugin registry integration."""

    def test_registry_can_hold_transcription_plugins(self) -> None:
        """Test that PluginRegistry can be parameterized with TranscriptionPlugin."""
        registry: PluginRegistry[TranscriptionPlugin] = PluginRegistry(TranscriptionPlugin)
        assert len(registry) == 0

    def test_register_transcription_plugin(self) -> None:
        """Test registering a transcription plugin."""
        from inkwell.transcription.youtube import YouTubeTranscriber

        registry: PluginRegistry[TranscriptionPlugin] = PluginRegistry(TranscriptionPlugin)

        transcriber = YouTubeTranscriber()
        registry.register(
            name="youtube",
            plugin=transcriber,
            priority=100,
            source="test:youtube",
        )

        assert len(registry) == 1
        assert "youtube" in registry
        retrieved = registry.get("youtube")
        assert retrieved is transcriber


class TestTranscriptionManagerRegistry:
    """Tests for TranscriptionManager plugin registry integration."""

    @pytest.fixture
    def mock_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set mock API key."""
        monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyD" + "X" * 32)

    def test_manager_has_transcription_registry(self, mock_api_key: None) -> None:
        """Test that TranscriptionManager exposes transcription_registry."""
        from inkwell.transcription.manager import TranscriptionManager

        # Create manager without plugin registry to avoid entry point discovery
        manager = TranscriptionManager(use_plugin_registry=False)
        assert hasattr(manager, "transcription_registry")
        assert isinstance(manager.transcription_registry, PluginRegistry)

    def test_manager_uses_legacy_transcribers_when_registry_disabled(
        self, mock_api_key: None
    ) -> None:
        """Test that manager uses legacy transcribers when plugin registry disabled."""
        from inkwell.transcription.gemini import GeminiTranscriber
        from inkwell.transcription.manager import TranscriptionManager
        from inkwell.transcription.youtube import YouTubeTranscriber

        manager = TranscriptionManager(use_plugin_registry=False)

        # Should use legacy transcribers
        assert isinstance(manager.youtube_transcriber, YouTubeTranscriber)
        assert isinstance(manager.gemini_transcriber, GeminiTranscriber)


class TestTranscriptionPluginConfigure:
    """Tests for TranscriptionPlugin configuration."""

    def test_plugin_configure_sets_cost_tracker(self) -> None:
        """Test that configure() sets cost tracker."""
        from inkwell.transcription.youtube import YouTubeTranscriber
        from inkwell.utils.costs import CostTracker

        transcriber = YouTubeTranscriber()
        cost_tracker = CostTracker()

        transcriber.configure({}, cost_tracker)

        assert transcriber._cost_tracker is cost_tracker
        assert transcriber.is_initialized is True

    def test_youtube_configure_with_preferred_languages(self) -> None:
        """Test that configure() can set preferred languages."""
        from inkwell.transcription.youtube import YouTubeTranscriber

        # Create with lazy init (like plugin discovery does)
        transcriber = YouTubeTranscriber(lazy_init=True)

        # Configure should set up preferred languages
        transcriber.configure({"preferred_languages": ["es", "en"]})

        assert transcriber.preferred_languages == ["es", "en"]

    def test_gemini_configure_with_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that configure() can provide API key."""
        from inkwell.transcription.gemini import GeminiTranscriber

        # Don't set env var
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)

        # Create with lazy init (like plugin discovery does)
        transcriber = GeminiTranscriber(lazy_init=True)

        # Configure should set up the API key
        api_key = "AIzaSyD" + "Y" * 32
        transcriber.configure({"api_key": api_key})

        assert transcriber.api_key == api_key
        assert transcriber.client is not None
