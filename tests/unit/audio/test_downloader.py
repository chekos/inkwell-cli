"""Tests for audio downloader."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from yt_dlp.utils import DownloadError, ExtractorError

from inkwell.audio import AudioDownloader, DownloadProgress
from inkwell.utils.errors import APIError


class TestDownloadProgress:
    """Test DownloadProgress model."""

    def test_basic_progress(self) -> None:
        """Test basic progress creation."""
        progress = DownloadProgress(
            status="downloading",
            downloaded_bytes=1024,
            total_bytes=2048,
            speed=512.0,
            eta=2,
        )

        assert progress.status == "downloading"
        assert progress.downloaded_bytes == 1024
        assert progress.total_bytes == 2048
        assert progress.speed == 512.0
        assert progress.eta == 2

    def test_percentage_calculation(self) -> None:
        """Test percentage calculation."""
        progress = DownloadProgress(
            status="downloading",
            downloaded_bytes=500,
            total_bytes=1000,
        )

        assert progress.percentage == 50.0

    def test_percentage_unknown_total(self) -> None:
        """Test percentage when total is unknown."""
        progress = DownloadProgress(
            status="downloading",
            downloaded_bytes=500,
        )

        assert progress.percentage is None

    def test_percentage_zero_total(self) -> None:
        """Test percentage with zero total."""
        progress = DownloadProgress(
            status="downloading",
            downloaded_bytes=0,
            total_bytes=0,
        )

        assert progress.percentage is None

    def test_validation_negative_bytes(self) -> None:
        """Test validation rejects negative bytes."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            DownloadProgress(
                status="downloading",
                downloaded_bytes=-100,
            )


class TestAudioDownloader:
    """Test AudioDownloader class."""

    @pytest.fixture
    def temp_dir(self, tmp_path: Path) -> Path:
        """Create temporary download directory."""
        download_dir = tmp_path / "downloads"
        download_dir.mkdir()
        return download_dir

    @pytest.fixture
    def cache_dir(self, tmp_path: Path) -> Path:
        """Create temporary cache directory."""
        cache = tmp_path / "cache"
        cache.mkdir()
        return cache

    @pytest.fixture
    def downloader(self, temp_dir: Path, cache_dir: Path) -> AudioDownloader:
        """Create AudioDownloader instance."""
        return AudioDownloader(output_dir=temp_dir, cache_dir=cache_dir)

    @pytest.fixture
    def mock_ydl_instance(self) -> Mock:
        """Create mock YoutubeDL instance."""
        mock = MagicMock()
        mock.extract_info.return_value = {
            "title": "Test Video",
            "id": "test123",
            "duration": 300,
        }
        return mock

    @pytest.fixture
    def mock_ydl_class(self, mock_ydl_instance: Mock) -> Mock:
        """Create mock YoutubeDL class that works as context manager."""
        mock_class = MagicMock()
        mock_class.return_value.__enter__.return_value = mock_ydl_instance
        mock_class.return_value.__exit__.return_value = None
        return mock_class

    def test_initialization(self, temp_dir: Path) -> None:
        """Test downloader initialization."""
        downloader = AudioDownloader(output_dir=temp_dir)

        assert downloader.output_dir == temp_dir
        assert temp_dir.exists()

    def test_initialization_creates_directory(self, tmp_path: Path) -> None:
        """Test downloader creates output directory if it doesn't exist."""
        new_dir = tmp_path / "new" / "downloads"
        assert not new_dir.exists()

        downloader = AudioDownloader(output_dir=new_dir)

        assert downloader.output_dir == new_dir
        assert new_dir.exists()

    def test_initialization_default_directory(self) -> None:
        """Test downloader uses default directory."""
        downloader = AudioDownloader()

        assert downloader.output_dir == Path.cwd() / "downloads"

    @pytest.mark.asyncio
    async def test_download_success(
        self,
        downloader: AudioDownloader,
        mock_ydl_class: Mock,
        mock_ydl_instance: Mock,
    ) -> None:
        """Test successful download."""
        url = "https://youtube.com/watch?v=test123"
        output_file = downloader._get_cache_path(url)

        # Mock yt-dlp to create the file (simulating actual download)
        def mock_download(download_url: str, download: bool) -> dict:
            output_file.touch()
            return {"title": "Test Video", "id": "test123", "duration": 300}

        mock_ydl_instance.extract_info.side_effect = mock_download

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            result = await downloader.download(url)

        assert result == output_file
        assert result.exists()

        # Verify yt-dlp was called with correct options
        mock_ydl_instance.extract_info.assert_called_once_with(url, download=True)

    @pytest.mark.asyncio
    async def test_download_with_custom_filename(
        self, downloader: AudioDownloader, mock_ydl_class: Mock, mock_ydl_instance: Mock
    ) -> None:
        """Test download with custom filename (still uses cache path)."""
        url = "https://youtube.com/watch?v=test123custom"
        output_file = downloader._get_cache_path(url)

        # Mock yt-dlp to create the file
        def mock_download(download_url: str, download: bool) -> dict:
            output_file.touch()
            return {"title": "Test Video", "id": "test123", "duration": 300}

        mock_ydl_instance.extract_info.side_effect = mock_download

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            result = await downloader.download(
                url,
                output_filename="custom-name",  # Note: ignored now, uses cache path
            )

        assert result == output_file
        assert result.exists()

    @pytest.mark.asyncio
    async def test_download_with_authentication(
        self, downloader: AudioDownloader, mock_ydl_class: Mock, mock_ydl_instance: Mock
    ) -> None:
        """Test download with username and password."""
        url = "https://example.com/private"
        output_file = downloader._get_cache_path(url)

        # Mock yt-dlp to create the file
        def mock_download(download_url: str, download: bool) -> dict:
            output_file.touch()
            return {"title": "Test Video", "id": "test123", "duration": 300}

        mock_ydl_instance.extract_info.side_effect = mock_download

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            await downloader.download(
                url,
                username="testuser",
                password="testpass",
            )

        # Check that authentication was passed to yt-dlp
        call_args = mock_ydl_class.call_args
        opts = call_args[0][0]
        assert opts["username"] == "testuser"
        assert opts["password"] == "testpass"

    @pytest.mark.asyncio
    async def test_download_format_configuration(
        self, downloader: AudioDownloader, mock_ydl_class: Mock, mock_ydl_instance: Mock
    ) -> None:
        """Test that download uses correct format per ADR-011."""
        url = "https://youtube.com/watch?v=test123format"
        output_file = downloader._get_cache_path(url)

        # Mock yt-dlp to create the file
        def mock_download(download_url: str, download: bool) -> dict:
            output_file.touch()
            return {"title": "Test Video", "id": "test123", "duration": 300}

        mock_ydl_instance.extract_info.side_effect = mock_download

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            await downloader.download(url)

        # Verify format configuration (M4A/AAC 128kbps per ADR-011)
        call_args = mock_ydl_class.call_args
        opts = call_args[0][0]

        assert opts["format"] == "bestaudio/best"
        assert len(opts["postprocessors"]) == 1
        assert opts["postprocessors"][0]["key"] == "FFmpegExtractAudio"
        assert opts["postprocessors"][0]["preferredcodec"] == "m4a"
        assert opts["postprocessors"][0]["preferredquality"] == "128"

    @pytest.mark.asyncio
    async def test_progress_callback(
        self, temp_dir: Path, cache_dir: Path, mock_ydl_instance: Mock
    ) -> None:
        """Test progress callback is invoked."""
        progress_updates: list[DownloadProgress] = []

        def callback(progress: DownloadProgress) -> None:
            progress_updates.append(progress)

        downloader = AudioDownloader(
            output_dir=temp_dir, cache_dir=cache_dir, progress_callback=callback
        )

        url = "https://youtube.com/watch?v=test123progress"
        output_file = downloader._get_cache_path(url)

        # Simulate progress hooks being called
        def mock_extract_info(download_url: str, download: bool) -> dict:
            # Trigger progress hook
            if downloader.progress_callback:
                downloader._progress_hook(
                    {
                        "status": "downloading",
                        "downloaded_bytes": 1024,
                        "total_bytes": 2048,
                        "speed": 512.0,
                        "eta": 2,
                    }
                )
                downloader._progress_hook(
                    {
                        "status": "finished",
                        "downloaded_bytes": 2048,
                        "total_bytes": 2048,
                    }
                )
            # Create the output file
            output_file.touch()
            return {
                "title": "Test Video",
                "id": "test123",
                "duration": 300,
            }

        mock_ydl_instance.extract_info.side_effect = mock_extract_info

        # Create mock context manager
        mock_ydl_class = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_class.return_value.__exit__.return_value = None

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            await downloader.download(url)

        # Verify callbacks were invoked
        assert len(progress_updates) == 2
        assert progress_updates[0].status == "downloading"
        assert progress_updates[0].downloaded_bytes == 1024
        assert progress_updates[1].status == "finished"
        assert progress_updates[1].downloaded_bytes == 2048

    @pytest.mark.asyncio
    async def test_download_error_handling(self, downloader: AudioDownloader) -> None:
        """Test handling of download errors."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.side_effect = DownloadError("Network error")

        mock_ydl_class = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_class.return_value.__exit__.return_value = None

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            with pytest.raises(APIError) as exc_info:
                await downloader.download("https://youtube.com/watch?v=test123")

        assert "Failed to download audio" in str(exc_info.value)
        assert "network issues" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extractor_error_handling(self, downloader: AudioDownloader) -> None:
        """Test handling of extractor errors."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.side_effect = ExtractorError("Invalid URL")

        mock_ydl_class = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_class.return_value.__exit__.return_value = None

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            with pytest.raises(APIError) as exc_info:
                await downloader.download("https://invalid.com/video")

        assert "Failed to extract audio information" in str(exc_info.value)
        assert "invalid" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generic_error_handling(self, downloader: AudioDownloader) -> None:
        """Test handling of unexpected errors."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.side_effect = RuntimeError("Unexpected error")

        with patch("inkwell.audio.downloader.YoutubeDL", return_value=mock_ydl):
            with pytest.raises(APIError) as exc_info:
                await downloader.download("https://youtube.com/watch?v=test123")

        assert "Unexpected error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_output_file(
        self, downloader: AudioDownloader, mock_ydl_class: Mock
    ) -> None:
        """Test error when output file is not created."""
        # Don't create the output file to simulate failure

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            with pytest.raises(APIError) as exc_info:
                await downloader.download("https://youtube.com/watch?v=test123")

        assert "file not found at expected location" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_info_success(
        self, downloader: AudioDownloader, mock_ydl_class: Mock, mock_ydl_instance: Mock
    ) -> None:
        """Test successful info extraction."""
        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            info = await downloader.get_info("https://youtube.com/watch?v=test123")

        assert info["title"] == "Test Video"
        assert info["id"] == "test123"
        assert info["duration"] == 300

        # Verify download=False was used
        mock_ydl_instance.extract_info.assert_called_once_with(
            "https://youtube.com/watch?v=test123", download=False
        )

    @pytest.mark.asyncio
    async def test_get_info_error(self, downloader: AudioDownloader) -> None:
        """Test info extraction error handling."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.side_effect = ExtractorError("Invalid URL")

        mock_ydl_class = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_class.return_value.__exit__.return_value = None

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            with pytest.raises(APIError) as exc_info:
                await downloader.get_info("https://invalid.com/video")

        assert "Failed to get information" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_info_no_result(self, downloader: AudioDownloader) -> None:
        """Test info extraction when no info is returned."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = None

        mock_ydl_class = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_class.return_value.__exit__.return_value = None

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            with pytest.raises(APIError) as exc_info:
                await downloader.get_info("https://youtube.com/watch?v=test123")

        assert "Failed to extract information" in str(exc_info.value)

    def test_progress_hook_no_callback(self, downloader: AudioDownloader) -> None:
        """Test progress hook does nothing when no callback is set."""
        # Should not raise an error
        downloader._progress_hook({"status": "downloading"})

    def test_progress_hook_with_estimate(self, temp_dir: Path) -> None:
        """Test progress hook handles total_bytes_estimate."""
        progress_updates: list[DownloadProgress] = []

        def callback(progress: DownloadProgress) -> None:
            progress_updates.append(progress)

        downloader = AudioDownloader(output_dir=temp_dir, progress_callback=callback)

        downloader._progress_hook(
            {
                "status": "downloading",
                "downloaded_bytes": 1000,
                "total_bytes_estimate": 5000,
                "speed": 100.0,
                "eta": 40,
            }
        )

        assert len(progress_updates) == 1
        assert progress_updates[0].total_bytes == 5000
        assert progress_updates[0].percentage == 20.0

    @pytest.mark.asyncio
    async def test_download_uses_cache(
        self, downloader: AudioDownloader, mock_ydl_class: Mock
    ) -> None:
        """Test that cached audio is returned without re-downloading."""
        url = "https://youtube.com/watch?v=cached123"
        cache_path = downloader._get_cache_path(url)
        cache_path.touch()  # Pre-create the cached file

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            result = await downloader.download(url)

        # Should return cached file
        assert result == cache_path

        # yt-dlp should NOT have been called
        mock_ydl_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_bypass_cache(
        self, downloader: AudioDownloader, mock_ydl_class: Mock
    ) -> None:
        """Test that cache can be bypassed."""
        url = "https://youtube.com/watch?v=bypass123"
        cache_path = downloader._get_cache_path(url)
        cache_path.touch()  # Pre-create the cached file

        with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
            result = await downloader.download(url, use_cache=False)

        # Should have downloaded fresh (even though cache existed)
        # yt-dlp SHOULD have been called
        mock_ydl_class.assert_called_once()
