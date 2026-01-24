"""TranscriptionPlugin base class for audio-to-text conversion.

This module defines the base class that all transcription plugins must implement.
It provides the transcription interface with flexible input handling via TranscriptionRequest.
"""

from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from inkwell.plugins.base import InkwellPlugin

if TYPE_CHECKING:
    from inkwell.transcription.models import Transcript
    from inkwell.utils.costs import CostTracker


@dataclass
class TranscriptionRequest:
    """Flexible input for transcription plugins.

    Supports URLs, local files, and raw audio bytes. Plugins declare
    which input types they support via CAPABILITIES.

    Attributes:
        url: URL of the audio/video content (e.g., YouTube URL)
        file_path: Path to local audio file
        audio_bytes: Raw audio data as bytes

    Raises:
        ValueError: If not exactly one input type is provided

    Example:
        >>> # From URL (e.g., YouTube)
        >>> request = TranscriptionRequest(url="https://youtube.com/watch?v=abc123")
        >>> request.source_type
        'url'
        >>>
        >>> # From file
        >>> request = TranscriptionRequest(file_path=Path("/tmp/audio.mp3"))
        >>> request.source_type
        'file'
    """

    url: str | None = None
    file_path: Path | None = None
    audio_bytes: bytes | None = None

    @property
    def source_type(self) -> Literal["url", "file", "bytes"]:
        """Determine the type of input source."""
        if self.url:
            return "url"
        elif self.file_path:
            return "file"
        return "bytes"

    def __post_init__(self) -> None:
        """Validate that exactly one source is provided."""
        sources = sum(1 for x in [self.url, self.file_path, self.audio_bytes] if x)
        if sources != 1:
            raise ValueError("Exactly one of url, file_path, or audio_bytes must be provided")


class TranscriptionPlugin(InkwellPlugin):
    """Base class for transcription plugins.

    Provides plugin lifecycle management combined with the transcription interface.
    All transcription plugins must inherit from this class and implement the
    abstract methods.

    All methods are async. Sync implementations should use asyncio.to_thread().

    Class Attributes (required):
        NAME: Unique plugin identifier (e.g., "youtube", "gemini")
        VERSION: Plugin version (e.g., "1.0.0")
        DESCRIPTION: Short description of the plugin

    Class Attributes (optional):
        HANDLES_URLS: URL patterns this plugin can handle (e.g., ["youtube.com", "youtu.be"])
        CAPABILITIES: Dict describing plugin capabilities

    Example:
        >>> class WhisperTranscriber(TranscriptionPlugin):
        ...     NAME = "whisper"
        ...     VERSION = "1.0.0"
        ...     DESCRIPTION = "Local Whisper transcription"
        ...     CAPABILITIES = {
        ...         "formats": ["mp3", "wav", "m4a"],
        ...         "requires_internet": False,
        ...         "supports_file": True,
        ...         "supports_url": False,
        ...     }
        ...
        ...     async def transcribe(self, request: TranscriptionRequest) -> Transcript:
        ...         # Implementation
        ...         pass
    """

    # Class-level capability declarations (enables filtering without instantiation)
    HANDLES_URLS: ClassVar[list[str]] = []  # URL patterns, e.g., ["youtube.com", "youtu.be"]
    CAPABILITIES: ClassVar[dict[str, Any]] = {
        "formats": ["mp3", "wav", "m4a", "mp4"],
        "max_duration_hours": None,  # None = no limit
        "requires_internet": True,
        "supports_file": True,
        "supports_url": False,
        "supports_bytes": False,
    }

    def __init__(self) -> None:
        """Initialize the transcription plugin.

        The plugin is not ready for use until configure() is called.
        """
        InkwellPlugin.__init__(self)

    @abstractmethod
    async def transcribe(self, request: TranscriptionRequest) -> "Transcript":
        """Transcribe audio to text.

        Args:
            request: Input containing URL, file path, or raw bytes

        Returns:
            Transcript object with text and metadata

        Raises:
            APIError: If transcription fails
        """
        pass

    def can_handle(self, request: TranscriptionRequest) -> bool:
        """Check if this plugin can handle the given request.

        Default implementation checks source type against CAPABILITIES
        and URL patterns against HANDLES_URLS.

        Args:
            request: The transcription request to check

        Returns:
            True if this plugin can handle the request

        Example:
            >>> plugin = YouTubeTranscriberPlugin()
            >>> request = TranscriptionRequest(url="https://youtube.com/watch?v=abc")
            >>> plugin.can_handle(request)
            True
        """
        caps = self.CAPABILITIES

        if request.source_type == "url":
            if not caps.get("supports_url", False):
                return False
            if self.HANDLES_URLS and request.url:
                return any(pattern in request.url for pattern in self.HANDLES_URLS)
            return True
        elif request.source_type == "file":
            return bool(caps.get("supports_file", True))
        else:  # bytes
            return bool(caps.get("supports_bytes", False))

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate cost for transcribing audio of given duration.

        Override this method for paid transcription services.

        Args:
            duration_seconds: Duration of audio in seconds

        Returns:
            Estimated cost in USD (default: 0.0 for free services)
        """
        return 0.0  # Default: free

    def configure(
        self,
        config: dict[str, Any],
        cost_tracker: "CostTracker | None" = None,
    ) -> None:
        """Configure the plugin with settings and cost tracker.

        Subclasses can override to perform additional initialization,
        such as creating API clients.

        Args:
            config: Plugin-specific configuration dict.
            cost_tracker: Optional cost tracker for API usage tracking.
        """
        super().configure(config, cost_tracker)

    # track_cost() is inherited from InkwellPlugin base class
