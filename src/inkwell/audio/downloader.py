"""Audio downloader using yt-dlp."""

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import platformdirs
from pydantic import BaseModel, Field
from yt_dlp import YoutubeDL  # type: ignore[import-untyped]
from yt_dlp.utils import DownloadError, ExtractorError  # type: ignore[import-untyped]

from inkwell.utils.errors import APIError

logger = logging.getLogger(__name__)

AUDIO_CACHE_FORMAT_VERSION = 1


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
        cache_enabled: bool = True,
        cache_max_mb: int | None = None,
        cache_ttl_days: int | None = None,
    ):
        """Initialize audio downloader.

        Args:
            output_dir: Directory to save downloaded audio (default: temp dir)
            cache_dir: Directory to cache audio files (default: platform cache dir)
            progress_callback: Optional callback for progress updates
            cache_enabled: Whether to cache downloaded media/audio
            cache_max_mb: Maximum media/audio cache size in megabytes
            cache_ttl_days: Maximum media/audio cache entry age in days
        """
        self.output_dir = output_dir or Path.cwd() / "downloads"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.cache_dir = cache_dir or self.default_cache_dir()
        self.cache_enabled = cache_enabled
        self.cache_max_mb = cache_max_mb
        self.cache_ttl_days = cache_ttl_days
        self.cache_max_bytes = cache_max_mb * 1024 * 1024 if cache_max_mb else None

        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.progress_callback = progress_callback

    @staticmethod
    def default_cache_dir() -> Path:
        """Return the default audio/media cache directory."""
        return Path(platformdirs.user_cache_dir("inkwell")) / "audio"

    @classmethod
    def cache_stats(cls, cache_dir: Path | None = None) -> dict[str, Any]:
        """Get audio/media cache statistics without enforcing retention policy."""
        resolved_cache_dir = cache_dir or cls.default_cache_dir()

        if not resolved_cache_dir.exists():
            return {
                "total": 0,
                "size_bytes": 0,
                "cache_dir": str(resolved_cache_dir),
                "cache_format_version": AUDIO_CACHE_FORMAT_VERSION,
                "extensions": {},
            }

        cache_files = [path for path in resolved_cache_dir.iterdir() if path.is_file()]
        total_size = 0
        extensions: dict[str, int] = {}

        for cache_file in cache_files:
            try:
                stat_result = cache_file.stat()
            except OSError:
                continue
            total_size += stat_result.st_size
            extension = cache_file.suffix.lower() or "<none>"
            extensions[extension] = extensions.get(extension, 0) + 1

        return {
            "total": len(cache_files),
            "size_bytes": total_size,
            "cache_dir": str(resolved_cache_dir),
            "cache_format_version": AUDIO_CACHE_FORMAT_VERSION,
            "extensions": extensions,
        }

    def _get_cache_path(self, url: str) -> Path:
        """Get cached audio file path for a URL.

        Args:
            url: The audio URL

        Returns:
            Path where cached audio would be stored
        """
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        return self.cache_dir / f"{url_hash}.m4a"

    def _get_output_path(self, url: str, output_filename: str | None = None) -> Path:
        """Get non-cache download output path for a URL."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        stem = Path(output_filename).stem if output_filename else url_hash
        return self.output_dir / f"{stem or url_hash}.m4a"

    def _iter_cache_files(self) -> list[Path]:
        """Return current files in the media cache directory."""
        if not self.cache_dir.exists():
            return []
        return [path for path in self.cache_dir.iterdir() if path.is_file()]

    def _is_cache_file_expired(self, path: Path) -> bool:
        """Return whether a media cache file exceeds the configured TTL."""
        if not self.cache_ttl_days or self.cache_ttl_days <= 0:
            return False

        try:
            age_seconds = time.time() - path.stat().st_mtime
        except OSError:
            return False

        return age_seconds > self.cache_ttl_days * 24 * 60 * 60

    def _delete_cache_file(self, path: Path) -> int | None:
        """Delete a cache file and return deleted bytes when successful."""
        try:
            size = path.stat().st_size
            path.unlink()
            return size
        except OSError as e:
            logger.debug(f"Failed to delete media cache file {path}: {e}")
            return None

    def enforce_cache_policy(self, protected_path: Path | None = None) -> dict[str, int]:
        """Apply media cache TTL and size limits.

        Args:
            protected_path: Cache file that must not be evicted, usually the file
                just downloaded and about to be returned to the caller.

        Returns:
            Counts of deleted expired/size-limit files and deleted bytes.
        """
        result = {"expired_files": 0, "size_files": 0, "bytes_deleted": 0}

        if not self.cache_enabled:
            return result

        protected_path = protected_path.resolve() if protected_path else None

        for cache_file in self._iter_cache_files():
            if protected_path and cache_file.resolve() == protected_path:
                continue
            if not self._is_cache_file_expired(cache_file):
                continue

            deleted_bytes = self._delete_cache_file(cache_file)
            if deleted_bytes is None:
                continue
            result["expired_files"] += 1
            result["bytes_deleted"] += deleted_bytes

        if self.cache_max_bytes is None:
            return result

        cache_files: list[tuple[float, int, Path]] = []
        total_size = 0

        for cache_file in self._iter_cache_files():
            try:
                stat_result = cache_file.stat()
            except OSError:
                continue
            total_size += stat_result.st_size
            cache_files.append((stat_result.st_mtime, stat_result.st_size, cache_file))

        if total_size <= self.cache_max_bytes:
            return result

        for _, size, cache_file in sorted(cache_files, key=lambda item: item[0]):
            if total_size <= self.cache_max_bytes:
                break
            if protected_path and cache_file.resolve() == protected_path:
                continue

            deleted_bytes = self._delete_cache_file(cache_file)
            if deleted_bytes is None:
                continue
            total_size -= size
            result["size_files"] += 1
            result["bytes_deleted"] += deleted_bytes

        return result

    def _check_cache(self, url: str) -> Path | None:
        """Check if audio for this URL is already cached.

        Args:
            url: The audio URL

        Returns:
            Path to cached file if it exists, None otherwise
        """
        if not self.cache_enabled:
            return None

        cache_path = self._get_cache_path(url)
        if cache_path.exists():
            if self._is_cache_file_expired(cache_path):
                self._delete_cache_file(cache_path)
                logger.info(f"Expired cached audio: {cache_path}")
                return None

            logger.info(f"Found cached audio: {cache_path}")
            return cache_path
        return None

    def _progress_hook(self, progress_dict: dict[str, Any]) -> None:
        """Process yt-dlp progress updates."""
        if not self.progress_callback:
            return

        status = progress_dict.get("status", "unknown")

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
        if self.cache_enabled:
            self.enforce_cache_policy()

        if use_cache and self.cache_enabled:
            cached_path = self._check_cache(url)
            if cached_path:
                return cached_path

        output_path = (
            self._get_cache_path(url)
            if self.cache_enabled
            else self._get_output_path(url, output_filename)
        )
        output_template = str(output_path.with_suffix(".%(ext)s"))

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

            if self.cache_enabled:
                self.enforce_cache_policy(protected_path=output_path)

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

            logger.info(f"Downloaded audio to: {output_path}")
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
            return dict(info)
