"""Tests for YAML integrity checking utilities."""

import hashlib
from pathlib import Path

import pytest
import yaml

from inkwell.utils.yaml_integrity import (
    YAMLIntegrityError,
    YAMLWithIntegrity,
    _is_valid_sha256_checksum,
)


class TestYAMLWithIntegrity:
    """Test YAMLWithIntegrity class."""

    def test_write_and_read_with_checksum(self, tmp_path: Path) -> None:
        """Test writing and reading YAML with valid checksum."""
        yaml_file = tmp_path / "test.yaml"
        data = {"name": "Test", "value": 123, "nested": {"key": "value"}}

        # Write with checksum
        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)

        # Verify file exists
        assert yaml_file.exists()

        # Verify checksum is embedded in file
        content = yaml_file.read_text()
        assert "# checksum: " in content

        # Read and verify
        loaded = YAMLWithIntegrity.read_yaml_with_verification(yaml_file)
        assert loaded == data

    def test_detects_corruption(self, tmp_path: Path) -> None:
        """Test that checksum detects file corruption."""
        yaml_file = tmp_path / "test.yaml"
        data = {"name": "Test", "value": 123}

        # Write with checksum
        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)

        # Corrupt the file (change one character)
        content = yaml_file.read_text()
        corrupted = content.replace("Test", "Tent")
        yaml_file.write_text(corrupted)

        # Should detect corruption
        with pytest.raises(YAMLIntegrityError) as exc_info:
            YAMLWithIntegrity.read_yaml_with_verification(yaml_file)

        error_msg = str(exc_info.value)
        assert "integrity check" in error_msg.lower()
        assert "corrupted" in error_msg.lower()
        assert "Expected checksum:" in error_msg
        assert "Actual checksum:" in error_msg

    def test_backward_compatible_no_checksum(self, tmp_path: Path) -> None:
        """Test that old YAML files without checksum still load successfully."""
        yaml_file = tmp_path / "old.yaml"

        # Write old-style YAML (no checksum)
        data = {"name": "Old Format", "value": 456}
        content = yaml.dump(data)
        yaml_file.write_text(content)

        # Should load successfully (with warning logged, but we don't test that here)
        loaded = YAMLWithIntegrity.read_yaml_with_verification(yaml_file)

        # Verify data is loaded correctly despite missing checksum
        assert loaded == data

    def test_checksum_format_validation(self, tmp_path: Path) -> None:
        """Test that checksum is valid SHA-256 hex."""
        yaml_file = tmp_path / "test.yaml"
        data = {"name": "Test"}

        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)

        content = yaml_file.read_text()
        assert "# checksum: " in content

        # Extract checksum
        checksum = content.split("# checksum: ")[1].strip()

        # Verify format: 64 hex characters
        assert len(checksum) == 64
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_checksum_is_correct(self, tmp_path: Path) -> None:
        """Test that embedded checksum matches actual content hash."""
        yaml_file = tmp_path / "test.yaml"
        data = {"name": "Test", "value": 123}

        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)

        # Read file and parse manually
        content = yaml_file.read_text()
        main_content, checksum_line = content.rsplit("# checksum: ", 1)
        embedded_checksum = checksum_line.strip()

        # Calculate expected checksum
        expected_checksum = hashlib.sha256(main_content.encode("utf-8")).hexdigest()

        assert embedded_checksum == expected_checksum

    def test_detects_bit_flip(self, tmp_path: Path) -> None:
        """Test detection of single bit flip in content."""
        yaml_file = tmp_path / "test.yaml"
        data = {"episode_title": "Great Episode"}

        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)

        # Simulate bit flip: 'e' (0x65) -> 'i' (0x69)
        content = yaml_file.read_text()
        corrupted = content.replace("Great", "Greit", 1)
        yaml_file.write_text(corrupted)

        with pytest.raises(YAMLIntegrityError):
            YAMLWithIntegrity.read_yaml_with_verification(yaml_file)

    def test_detects_truncation(self, tmp_path: Path) -> None:
        """Test detection of file truncation."""
        yaml_file = tmp_path / "test.yaml"
        data = {
            "line1": "value1",
            "line2": "value2",
            "line3": "value3",
            "line4": "value4",
        }

        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)

        # Truncate file (remove last 2 lines before checksum)
        content = yaml_file.read_text()
        lines = content.splitlines()
        truncated = "\n".join(lines[:-3]) + "\n" + lines[-1]  # Keep checksum line
        yaml_file.write_text(truncated)

        with pytest.raises(YAMLIntegrityError):
            YAMLWithIntegrity.read_yaml_with_verification(yaml_file)

    def test_detects_encoding_corruption(self, tmp_path: Path) -> None:
        """Test detection of encoding corruption."""
        yaml_file = tmp_path / "test.yaml"
        data = {"episode_title": "Café Discussion"}

        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)

        # Simulate encoding corruption by modifying the escaped character
        content = yaml_file.read_text()
        # YAML escapes é as \xE9, so we corrupt the escape sequence
        corrupted = content.replace("\\xE9", "\\xE8")  # é -> è
        yaml_file.write_text(corrupted)

        with pytest.raises(YAMLIntegrityError):
            YAMLWithIntegrity.read_yaml_with_verification(yaml_file)

    def test_invalid_checksum_format(self, tmp_path: Path) -> None:
        """Test handling of invalid checksum format with graceful degradation."""
        yaml_file = tmp_path / "test.yaml"
        data = {"name": "Test"}

        # Write file with invalid checksum format
        yaml_content = yaml.dump(data)
        invalid_content = f"{yaml_content}\n# checksum: INVALID_CHECKSUM\n"
        yaml_file.write_text(invalid_content)

        # Should load successfully with graceful degradation (warning logged)
        loaded = YAMLWithIntegrity.read_yaml_with_verification(yaml_file)

        # Verify data is loaded correctly despite invalid checksum format
        assert loaded == data

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Test error when file doesn't exist."""
        yaml_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError) as exc_info:
            YAMLWithIntegrity.read_yaml_with_verification(yaml_file)

        assert "not found" in str(exc_info.value).lower()

    def test_empty_file(self, tmp_path: Path) -> None:
        """Test handling of empty YAML file."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        # Should return empty dict
        loaded = YAMLWithIntegrity.read_yaml_with_verification(yaml_file)
        assert loaded == {}

    def test_complex_nested_data(self, tmp_path: Path) -> None:
        """Test with complex nested data structures."""
        yaml_file = tmp_path / "complex.yaml"
        data = {
            "podcast_name": "My Podcast",
            "episode_metadata": {
                "title": "Episode 1",
                "pub_date": "2025-11-14T10:00:00+00:00",
                "duration_seconds": 3600,
                "tags": ["tech", "ai", "python"],
                "chapters": [
                    {"time": 0, "title": "Intro"},
                    {"time": 300, "title": "Main Content"},
                ],
            },
            "stats": {
                "total_cost_usd": 0.42,
                "templates_applied": ["summary", "quotes", "key-concepts"],
            },
        }

        # Write and read
        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)
        loaded = YAMLWithIntegrity.read_yaml_with_verification(yaml_file)

        assert loaded == data

    def test_unicode_characters(self, tmp_path: Path) -> None:
        """Test with various Unicode characters."""
        yaml_file = tmp_path / "unicode.yaml"
        data = {
            "title": "Test 日本語 中文 한국어",
            "emoji": "🎙️📝✨",
            "special": "Café, naïve, résumé",
        }

        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)
        loaded = YAMLWithIntegrity.read_yaml_with_verification(yaml_file)

        assert loaded == data

    def test_atomic_write_on_error(self, tmp_path: Path) -> None:
        """Test that atomic write cleans up temp file on error."""
        yaml_file = tmp_path / "test.yaml"

        # Create read-only directory to force write error
        yaml_file.parent.chmod(0o444)

        try:
            with pytest.raises(OSError):
                YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, {"key": "value"})

            # Verify no temp files left behind
            temp_files = list(yaml_file.parent.glob("*.tmp"))
            assert len(temp_files) == 0
        finally:
            # Restore permissions
            yaml_file.parent.chmod(0o755)

    def test_checksum_at_end_of_file(self, tmp_path: Path) -> None:
        """Test that checksum is placed at end of file."""
        yaml_file = tmp_path / "test.yaml"
        data = {"name": "Test"}

        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)

        content = yaml_file.read_text()
        lines = content.strip().splitlines()

        # Last line should be checksum comment
        assert lines[-1].startswith("# checksum: ")

    def test_multiple_writes_update_checksum(self, tmp_path: Path) -> None:
        """Test that overwriting file updates checksum."""
        yaml_file = tmp_path / "test.yaml"

        # Write first version
        data1 = {"name": "Version 1"}
        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data1)
        content1 = yaml_file.read_text()
        checksum1 = content1.split("# checksum: ")[1].strip()

        # Write second version
        data2 = {"name": "Version 2"}
        YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data2)
        content2 = yaml_file.read_text()
        checksum2 = content2.split("# checksum: ")[1].strip()

        # Checksums should be different
        assert checksum1 != checksum2

        # Should read second version correctly
        loaded = YAMLWithIntegrity.read_yaml_with_verification(yaml_file)
        assert loaded == data2


class TestIsValidSHA256Checksum:
    """Test _is_valid_sha256_checksum helper function."""

    def test_valid_checksum(self) -> None:
        """Test valid SHA-256 checksum."""
        # Valid 64-character SHA-256 hex string
        valid = "5f3b8c4a9e2d1f6a8b3c7e4d2a9f1b5c8e3a6d2f9b4c1e7a3d8f2b6c9e1a4d7f"
        assert _is_valid_sha256_checksum(valid) is True

    def test_valid_uppercase(self) -> None:
        """Test valid checksum with uppercase letters."""
        # Valid 64-character SHA-256 hex string (uppercase)
        valid = "5F3B8C4A9E2D1F6A8B3C7E4D2A9F1B5C8E3A6D2F9B4C1E7A3D8F2B6C9E1A4D7F"
        assert _is_valid_sha256_checksum(valid) is True

    def test_invalid_length_too_short(self) -> None:
        """Test invalid checksum (too short)."""
        invalid = "5f3b8c4a9e2d1f6a8b3c7e4d2a9f1b5c"
        assert _is_valid_sha256_checksum(invalid) is False

    def test_invalid_length_too_long(self) -> None:
        """Test invalid checksum (too long)."""
        invalid = "5f3b8c4a9e2d1f6a8b3c7e4d2a9f1b5c8e3a6d2f9b4c1e7a3d8f2b6c9e1a4d7fabc"
        assert _is_valid_sha256_checksum(invalid) is False

    def test_invalid_characters(self) -> None:
        """Test invalid checksum (non-hex characters)."""
        invalid = "5f3b8c4a9e2d1f6a8b3c7e4d2a9f1b5c8e3a6d2f9b4c1e7a3d8f2b6c9e1GHIJ"
        assert _is_valid_sha256_checksum(invalid) is False

    def test_empty_string(self) -> None:
        """Test invalid checksum (empty string)."""
        assert _is_valid_sha256_checksum("") is False

    def test_mixed_case(self) -> None:
        """Test valid checksum with mixed case."""
        # Valid 64-character SHA-256 hex string (mixed case)
        valid = "5F3b8C4a9E2d1F6a8B3c7E4d2A9f1B5c8E3a6D2f9B4c1E7a3D8f2B6c9E1a4D7f"
        assert _is_valid_sha256_checksum(valid) is True
