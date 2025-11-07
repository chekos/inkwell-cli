"""Audio downloader using yt-dlp."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError


class AudioDownloadError(Exception):
    """Raised when audio download fails."""

    pass


class DownloadProgress(BaseModel):
    """Progress information for audio download."""

    status: str = Field(..., description="Current download status")
    downloaded_bytes: int = Field(default=0, ge=0, description="Bytes downloaded so far")
    total_bytes: int | None = Field(
        default=None, ge=0, description="Total bytes to download (if known)"
    )
    speed: float | None = Field(
        default=None, ge=0, description="Download speed in bytes/sec"
    )
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
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ):
        """Initialize audio downloader.

        Args:
            output_dir: Directory to save downloaded audio (default: temp dir)
            progress_callback: Optional callback for progress updates
        """
        self.output_dir = output_dir or Path.cwd() / "downloads"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.progress_callback = progress_callback

    def _progress_hook(self, progress_dict: dict[str, Any]) -> None:
        """Process yt-dlp progress updates."""
        if not self.progress_callback:
            return

        status = progress_dict.get("status", "unknown")

        # Build progress object
        total_bytes = progress_dict.get("total_bytes") or progress_dict.get(
            "total_bytes_estimate"
        )
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
    ) -> Path:
        """Download audio from URL.

        Args:
            url: URL to download audio from
            output_filename: Optional output filename (without extension)
            username: Optional username for authentication
            password: Optional password for authentication

        Returns:
            Path to downloaded audio file

        Raises:
            AudioDownloadError: If download fails
        """
        # Prepare output template
        if output_filename:
            output_template = str(self.output_dir / f"{output_filename}.%(ext)s")
        else:
            output_template = str(self.output_dir / "%(title)s-%(id)s.%(ext)s")

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
            raise AudioDownloadError(
                f"Failed to download audio from {url}. "
                f"This may be due to network issues, invalid URL, or unsupported source. "
                f"Error: {e}"
            ) from e
        except ExtractorError as e:
            raise AudioDownloadError(
                f"Failed to extract audio information from {url}. "
                f"The URL may be invalid or the content may not be accessible. "
                f"Error: {e}"
            ) from e
        except Exception as e:
            raise AudioDownloadError(
                f"Unexpected error downloading audio from {url}: {e}"
            ) from e

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
                raise AudioDownloadError("Failed to extract video information")

            # Determine output filename
            # yt-dlp will have converted to m4a, so we need to adjust extension
            if "%(ext)s" in output_template:
                # Replace ext placeholder with actual extension
                output_path = Path(
                    output_template.replace("%(ext)s", "m4a")
                    .replace("%(title)s", info.get("title", "audio"))
                    .replace("%(id)s", info.get("id", "unknown"))
                )
            else:
                output_path = Path(output_template)

            if not output_path.exists():
                raise AudioDownloadError(
                    f"Download completed but file not found at expected location: {output_path}"
                )

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
            raise AudioDownloadError(
                f"Failed to get information from {url}: {e}"
            ) from e

    def _get_info_sync(self, url: str, ydl_opts: dict[str, Any]) -> dict[str, Any]:
        """Synchronous info extraction for thread pool execution."""
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise AudioDownloadError("Failed to extract information")
            return info
