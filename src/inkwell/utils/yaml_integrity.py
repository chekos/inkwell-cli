"""YAML read/write utilities with integrity checking.

Provides SHA-256 checksum-based verification for YAML files to detect corruption
from filesystem errors, improper encoding, or other data integrity issues.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class YAMLIntegrityError(ValueError):
    """Raised when YAML file fails integrity check."""

    pass


class YAMLWithIntegrity:
    """YAML read/write with integrity checking using embedded checksums.

    This class embeds SHA-256 checksums as YAML comments to detect file corruption.
    The checksums are calculated from the YAML content and embedded at the end of
    the file as a comment, which YAML parsers naturally ignore.

    Example file format:
        ```yaml
        podcast_name: "My Podcast"
        episode_title: "Great Episode"
        pub_date: "2025-11-14T10:00:00+00:00"

        # checksum: 5f3b8c4a9e2d1f6a8b3c7e4d2a9f1b5c8e3a6d2f9b4c1e7a3d8f2b6c9e1a4d7
        ```

    Features:
    - Detects any corruption (even single bit flips)
    - Backward compatible (old files without checksum still load with warning)
    - No external metadata files needed
    - Clear error messages for corrupted files

    Common corruption causes detected:
    - Bad disk sectors (HDD aging)
    - Filesystem bugs (especially network filesystems)
    - Interrupted writes (power loss, process kill during fsync)
    - Bit flips in memory or storage (cosmic rays, hardware faults)
    - Encoding conversion errors (UTF-8 ↔ system encoding)
    """

    @staticmethod
    def write_yaml_with_checksum(file_path: Path, data: dict[str, Any]) -> None:
        """Write YAML with embedded checksum for integrity verification.

        Args:
            file_path: Path to YAML file to write
            data: Dictionary to serialize as YAML

        Raises:
            OSError: If file write fails
        """
        # Generate YAML content
        yaml_content = yaml.dump(data, default_flow_style=False, sort_keys=False)

        # Ensure consistent trailing newline (yaml.dump may or may not include it)
        if not yaml_content.endswith("\n"):
            yaml_content += "\n"

        # Calculate checksum (SHA-256 of content)
        checksum = hashlib.sha256(yaml_content.encode("utf-8")).hexdigest()

        # Add checksum as comment at end (YAML parsers ignore comments)
        final_content = f"{yaml_content}# checksum: {checksum}\n"

        # Write atomically (temp file + rename)
        temp_file = file_path.with_suffix(f"{file_path.suffix}.tmp")
        try:
            temp_file.write_text(final_content, encoding="utf-8")
            temp_file.replace(file_path)
        except Exception:
            # Clean up temp file on error
            temp_file.unlink(missing_ok=True)
            raise

    @staticmethod
    def read_yaml_with_verification(file_path: Path) -> dict[str, Any]:
        """Read YAML and verify checksum.

        Args:
            file_path: Path to YAML file to read

        Returns:
            Parsed YAML data as dictionary

        Raises:
            YAMLIntegrityError: If checksum verification fails
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        if not file_path.exists():
            raise FileNotFoundError(f"YAML file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        # Extract checksum if present
        if "# checksum: " in content:
            # Split on checksum line
            parts = content.rsplit("# checksum: ", 1)
            if len(parts) == 2:
                main_content = parts[0]
                checksum_line = parts[1]
                expected_checksum = checksum_line.strip()

                # Validate checksum format (64 hex characters)
                if not _is_valid_sha256_checksum(expected_checksum):
                    logger.warning(
                        f"YAML file {file_path} has invalid checksum format. "
                        f"Expected 64 hex characters, got: {expected_checksum[:20]}..."
                    )
                    # Fall through to load without verification
                else:
                    # Recalculate checksum
                    actual_checksum = hashlib.sha256(main_content.encode("utf-8")).hexdigest()

                    # Verify integrity
                    if actual_checksum != expected_checksum:
                        raise YAMLIntegrityError(
                            f"YAML file {file_path} failed integrity check.\n"
                            f"Expected checksum: {expected_checksum}\n"
                            f"Actual checksum:   {actual_checksum}\n"
                            f"\n"
                            f"The file may be corrupted. Possible fixes:\n"
                            f"1. Restore from backup if available\n"
                            f"2. Delete and regenerate the file\n"
                            f"3. Check filesystem for errors (run fsck/chkdsk)"
                        )

                    # Use main content (without checksum comment)
                    content = main_content
        else:
            # No checksum (old file format), log warning
            logger.warning(
                f"YAML file {file_path} has no integrity checksum (old format). "
                f"Consider regenerating to add checksum protection."
            )

        return yaml.safe_load(content) or {}


def _is_valid_sha256_checksum(checksum: str) -> bool:
    """Validate that a string is a valid SHA-256 checksum.

    Args:
        checksum: String to validate

    Returns:
        True if valid SHA-256 hex string (64 hex characters)
    """
    if len(checksum) != 64:
        return False
    # Accept both uppercase and lowercase hex characters
    return all(c in "0123456789abcdefABCDEF" for c in checksum)
