"""Tests for path utilities."""

from pathlib import Path
from unittest.mock import patch

from inkwell.utils.paths import (
    ensure_config_files_exist,
    get_cache_dir,
    get_config_dir,
    get_config_file,
    get_data_dir,
    get_feeds_file,
    get_key_file,
    get_log_file,
)


class TestPathUtilities:
    """Tests for XDG-compliant path utilities."""

    def test_get_config_dir_creates_directory(self, tmp_path: Path) -> None:
        """Test that get_config_dir creates the directory if it doesn't exist."""
        with patch("inkwell.utils.paths.user_config_dir", return_value=str(tmp_path / "config")):
            config_dir = get_config_dir()
            assert config_dir.exists()
            assert config_dir.is_dir()

    def test_get_data_dir_creates_directory(self, tmp_path: Path) -> None:
        """Test that get_data_dir creates the directory if it doesn't exist."""
        with patch("inkwell.utils.paths.user_data_dir", return_value=str(tmp_path / "data")):
            data_dir = get_data_dir()
            assert data_dir.exists()
            assert data_dir.is_dir()

    def test_get_cache_dir_creates_directory(self, tmp_path: Path) -> None:
        """Test that get_cache_dir creates the directory if it doesn't exist."""
        with patch("inkwell.utils.paths.user_cache_dir", return_value=str(tmp_path / "cache")):
            cache_dir = get_cache_dir()
            assert cache_dir.exists()
            assert cache_dir.is_dir()

    def test_get_config_file_returns_correct_path(self, tmp_path: Path) -> None:
        """Test that get_config_file returns the correct file path."""
        with patch("inkwell.utils.paths.user_config_dir", return_value=str(tmp_path)):
            config_file = get_config_file()
            assert config_file == tmp_path / "config.yaml"

    def test_get_feeds_file_returns_correct_path(self, tmp_path: Path) -> None:
        """Test that get_feeds_file returns the correct file path."""
        with patch("inkwell.utils.paths.user_config_dir", return_value=str(tmp_path)):
            feeds_file = get_feeds_file()
            assert feeds_file == tmp_path / "feeds.yaml"

    def test_get_key_file_returns_correct_path(self, tmp_path: Path) -> None:
        """Test that get_key_file returns the correct file path."""
        with patch("inkwell.utils.paths.user_config_dir", return_value=str(tmp_path)):
            key_file = get_key_file()
            assert key_file == tmp_path / ".keyfile"

    def test_get_log_file_returns_correct_path(self, tmp_path: Path) -> None:
        """Test that get_log_file returns the correct file path."""
        with patch("inkwell.utils.paths.user_cache_dir", return_value=str(tmp_path)):
            log_file = get_log_file()
            assert log_file == tmp_path / "inkwell.log"

    def test_ensure_config_files_exist_creates_all_dirs(self, tmp_path: Path) -> None:
        """Test that ensure_config_files_exist creates all required directories."""
        with (
            patch("inkwell.utils.paths.user_config_dir", return_value=str(tmp_path / "config")),
            patch("inkwell.utils.paths.user_data_dir", return_value=str(tmp_path / "data")),
            patch("inkwell.utils.paths.user_cache_dir", return_value=str(tmp_path / "cache")),
        ):
            ensure_config_files_exist()

            assert (tmp_path / "config").exists()
            assert (tmp_path / "data").exists()
            assert (tmp_path / "cache").exists()

    def test_paths_are_pathlib_objects(self, tmp_path: Path) -> None:
        """Test that all path functions return pathlib.Path objects."""
        with (
            patch("inkwell.utils.paths.user_config_dir", return_value=str(tmp_path)),
            patch("inkwell.utils.paths.user_data_dir", return_value=str(tmp_path)),
            patch("inkwell.utils.paths.user_cache_dir", return_value=str(tmp_path)),
        ):
            assert isinstance(get_config_dir(), Path)
            assert isinstance(get_data_dir(), Path)
            assert isinstance(get_cache_dir(), Path)
            assert isinstance(get_config_file(), Path)
            assert isinstance(get_feeds_file(), Path)
            assert isinstance(get_key_file(), Path)
            assert isinstance(get_log_file(), Path)
