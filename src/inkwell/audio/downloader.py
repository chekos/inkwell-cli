"""Audio downloader using yt-dlp."""

import asyncio
import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import platformdirs
from pydantic import BaseModel, Field
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

from inkwell.utils.errors import APIError

logger = logging.getLogger(__name__)


class DownloadProgress(BaseModel):
    """Progress information for audio download."""

    status: str = Field(..., description="Current download status")
    downloaded_bytes: int = Field(default=0, ge=0, description="Bytes downloaded so far")
    total_bytes: int | None = Field(
        default=None, ge=0, description="Total bytes to download (if known)"
    )
    speed: float | None = Field(default=None, ge=0, description="Download speed in bytes/sec")
    eta: int | None = Field(default=None, ge=0, description="Estimated time remaining (seconds)")

    @property
    def percentage(self) -> float | None:
        """Calculate download percentage if total is known."""
        if self.total_bytes and self.total_bytes > 0:
            return (self.downloaded_bytes / self.total_bytes) * 100
        return None


class AudioDownloader:
    """Download audio from URLs using yt-dlp.

    Supports YouTube URLs, direct audio URLs, and other sources supported by yt-dlp.
    Downloads in M4A/AAC 128kbps format per ADR-011.
    Caches downloaded audio files to avoid re-downloading.
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        cache_dir: Path | None = None,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ):
        """Initialize audio downloader.

        Args:
            output_dir: Directory to save downloaded audio (default: temp dir)
            cache_dir: Directory to cache audio files (default: platform cache dir)
            progress_callback: Optional callback for progress updates
        """
        self.output_dir = output_dir or Path.cwd() / "downloads"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Use platform-appropriate cache directory for audio files
        self.cache_dir = cache_dir or Path(platformdirs.user_cache_dir("inkwell")) / "audio"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.progress_callback = progress_callback

    def _get_cache_path(self, url: str) -> Path:
        """Get cached audio file path for a URL.

        Args:
            url: The audio URL

        Returns:
            Path where cached audio would be stored
        """
        # Create a hash of the URL for the filename
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        return self.cache_dir / f"{url_hash}.m4a"

    def _check_cache(self, url: str) -> Path | None:
        """Check if audio for this URL is already cached.

        Args:
            url: The audio URL

        Returns:
            Path to cached file if it exists, None otherwise
        """
        cache_path = self._get_cache_path(url)
        if cache_path.exists():
            logger.info(f"Found cached audio: {cache_path}")
            return cache_path
        return None

    def _progress_hook(self, progress_dict: dict[str, Any]) -> None:
        """Process yt-dlp progress updates."""
        if not self.progress_callback:
            return

        status = progress_dict.get("status", "unknown")

        # Build progress object
        total_bytes = progress_dict.get("total_bytes") or progress_dict.get("total_bytes_estimate")
        progress = DownloadProgress(
            status=status,
            downloaded_bytes=progress_dict.get("downloaded_bytes", 0),
            total_bytes=total_bytes,
            speed=progress_dict.get("speed"),
            eta=progress_dict.get("eta"),
        )

        self.progress_callback(progress)

    async def download(
        self,
        url: str,
        output_filename: str | None = None,
        username: str | None = None,
        password: str | None = None,
        use_cache: bool = True,
    ) -> Path:
        """Download audio from URL.

        Args:
            url: URL to download audio from
            output_filename: Optional output filename (without extension)
            username: Optional username for authentication
            password: Optional password for authentication
            use_cache: Whether to use cached audio if available (default: True)

        Returns:
            Path to downloaded audio file

        Raises:
            AudioDownloadError: If download fails
        """
        # Check cache first
        if use_cache:
            cached_path = self._check_cache(url)
            if cached_path:
                return cached_path

        # Use cache directory for consistent storage
        cache_path = self._get_cache_path(url)
        output_template = str(cache_path.with_suffix(".%(ext)s"))

        # Configure yt-dlp options per ADR-011 (M4A/AAC 128kbps)
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "128",
                }
            ],
            "outtmpl": output_template,
            "progress_hooks": [self._progress_hook],
            "quiet": True,
            "no_warnings": True,
        }

        # Add authentication if provided
        if username:
            ydl_opts["username"] = username
        if password:
            ydl_opts["password"] = password

        try:
            # Run yt-dlp in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            output_path = await loop.run_in_executor(
                None, self._download_sync, url, ydl_opts, output_template
            )

            return output_path

        except DownloadError as e:
            raise APIError(
                f"Failed to download audio from {url}. "
                f"This may be due to network issues, invalid URL, or unsupported source. "
                f"Error: {e}"
            ) from e
        except ExtractorError as e:
            raise APIError(
                f"Failed to extract audio information from {url}. "
                f"The URL may be invalid or the content may not be accessible. "
                f"Error: {e}"
            ) from e
        except Exception as e:
            raise APIError(f"Unexpected error downloading audio from {url}: {e}") from e

    def _download_sync(self, url: str, ydl_opts: dict[str, Any], output_template: str) -> Path:
        """Synchronous download operation for thread pool execution.

        Args:
            url: URL to download
            ydl_opts: yt-dlp options
            output_template: Output filename template

        Returns:
            Path to downloaded file
        """
        with YoutubeDL(ydl_opts) as ydl:
            # Extract info to get final filename
            info = ydl.extract_info(url, download=True)

            if not info:
                raise APIError("Failed to extract video information")

            # Determine output filename - we use hash-based names now
            output_path = Path(output_template.replace(".%(ext)s", ".m4a"))

            if not output_path.exists():
                raise APIError(
                    f"Download completed but file not found at expected location: {output_path}"
                )

            logger.info(f"Cached audio to: {output_path}")
            return output_path

    async def get_info(self, url: str) -> dict[str, Any]:
        """Get information about audio/video without downloading.

        Args:
            url: URL to get info from

        Returns:
            Dictionary with metadata (title, duration, formats, etc.)

        Raises:
            AudioDownloadError: If info extraction fails
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self._get_info_sync, url, ydl_opts)
            return info

        except (DownloadError, ExtractorError) as e:
            raise APIError(f"Failed to get information from {url}: {e}") from e

    def _get_info_sync(self, url: str, ydl_opts: dict[str, Any]) -> dict[str, Any]:
        """Synchronous info extraction for thread pool execution."""
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise APIError("Failed to extract information")
            return info
