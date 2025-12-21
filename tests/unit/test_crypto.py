"""Tests for credential encryption."""

import stat
from pathlib import Path

import pytest

from inkwell.config.crypto import CredentialEncryptor
from inkwell.utils.errors import SecurityError


class TestCredentialEncryptor:
    """Tests for CredentialEncryptor class."""

    def test_encrypt_decrypt_roundtrip(self, tmp_path: Path) -> None:
        """Test that encryption and decryption work correctly."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        plaintext = "my-secret-password"
        encrypted = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(encrypted)

        assert decrypted == plaintext
        assert encrypted != plaintext  # Ensure it's actually encrypted

    def test_key_generation_on_first_use(self, tmp_path: Path) -> None:
        """Test that encryption key is generated on first use."""
        key_file = tmp_path / ".keyfile"
        assert not key_file.exists()

        encryptor = CredentialEncryptor(key_file)
        encryptor.encrypt("test")

        assert key_file.exists()

    def test_key_file_permissions(self, tmp_path: Path) -> None:
        """Test that key file is created with 600 permissions."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)
        encryptor.encrypt("test")

        file_stat = key_file.stat()
        mode = stat.S_IMODE(file_stat.st_mode)

        # Should be 0o600 (owner read/write only)
        assert mode == 0o600

    def test_key_file_reused(self, tmp_path: Path) -> None:
        """Test that existing key file is reused."""
        key_file = tmp_path / ".keyfile"

        # First encryptor
        encryptor1 = CredentialEncryptor(key_file)
        encrypted1 = encryptor1.encrypt("secret")

        # Second encryptor with same key file
        encryptor2 = CredentialEncryptor(key_file)
        decrypted = encryptor2.decrypt(encrypted1)

        assert decrypted == "secret"

    def test_encrypt_empty_string(self, tmp_path: Path) -> None:
        """Test encrypting empty string returns empty string."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        encrypted = encryptor.encrypt("")
        assert encrypted == ""

    def test_decrypt_empty_string(self, tmp_path: Path) -> None:
        """Test decrypting empty string returns empty string."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        decrypted = encryptor.decrypt("")
        assert decrypted == ""

    def test_insecure_permissions_raises_error(self, tmp_path: Path) -> None:
        """Test that insecure key file permissions raise SecurityError."""
        key_file = tmp_path / ".keyfile"

        # Create key file with world-readable permissions
        key_file.write_text("fake-key")
        key_file.chmod(0o644)  # World-readable

        encryptor = CredentialEncryptor(key_file)

        with pytest.raises(SecurityError, match="insecure permissions"):
            encryptor.encrypt("test")

    def test_decrypt_invalid_ciphertext_raises_error(self, tmp_path: Path) -> None:
        """Test that decrypting invalid ciphertext raises SecurityError."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        with pytest.raises(SecurityError, match="Failed to decrypt"):
            encryptor.decrypt("not-valid-ciphertext")

    def test_different_plaintexts_produce_different_ciphertexts(self, tmp_path: Path) -> None:
        """Test that different plaintexts produce different ciphertexts."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        encrypted1 = encryptor.encrypt("password1")
        encrypted2 = encryptor.encrypt("password2")

        assert encrypted1 != encrypted2

    def test_same_plaintext_with_different_keys(self, tmp_path: Path) -> None:
        """Test that same plaintext with different keys produces different ciphertexts."""
        key_file1 = tmp_path / ".keyfile1"
        key_file2 = tmp_path / ".keyfile2"

        encryptor1 = CredentialEncryptor(key_file1)
        encryptor2 = CredentialEncryptor(key_file2)

        plaintext = "same-password"
        encrypted1 = encryptor1.encrypt(plaintext)
        encrypted2 = encryptor2.encrypt(plaintext)

        assert encrypted1 != encrypted2

        # But each can decrypt its own ciphertext
        assert encryptor1.decrypt(encrypted1) == plaintext
        assert encryptor2.decrypt(encrypted2) == plaintext

    def test_unicode_handling(self, tmp_path: Path) -> None:
        """Test that Unicode characters are handled correctly."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        plaintext = "パスワード🔐"  # Japanese + emoji
        encrypted = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(encrypted)

        assert decrypted == plaintext

    def test_long_plaintext(self, tmp_path: Path) -> None:
        """Test encryption of long plaintext."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        plaintext = "a" * 10000  # Very long string
        encrypted = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(encrypted)

        assert decrypted == plaintext

    def test_rotate_key_not_implemented(self, tmp_path: Path) -> None:
        """Test that key rotation raises NotImplementedError."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        with pytest.raises(NotImplementedError, match="Key rotation"):
            encryptor.rotate_key(tmp_path / "new_key")

    def test_backup_keyfile_created_on_generation(self, tmp_path: Path) -> None:
        """Test that backup keyfile is created when generating new key."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        # Trigger key generation
        encryptor.encrypt("test")

        # Verify backup exists
        backup_path = tmp_path / ".keyfile.backup"
        recovery_doc = tmp_path / "KEYFILE_RECOVERY.txt"

        assert key_file.exists()
        assert backup_path.exists()
        assert recovery_doc.exists()

    def test_backup_matches_primary_key(self, tmp_path: Path) -> None:
        """Test that backup keyfile matches primary key."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        # Trigger key generation
        encryptor.encrypt("test")

        # Verify backup matches primary
        primary_key = key_file.read_bytes()
        backup_key = (tmp_path / ".keyfile.backup").read_bytes()

        assert primary_key == backup_key

    def test_backup_file_permissions(self, tmp_path: Path) -> None:
        """Test that backup keyfile has 600 permissions."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        # Trigger key generation
        encryptor.encrypt("test")

        # Verify backup permissions
        backup_path = tmp_path / ".keyfile.backup"
        file_stat = backup_path.stat()
        mode = stat.S_IMODE(file_stat.st_mode)

        # Should be 0o600 (owner read/write only)
        assert mode == 0o600

    def test_recovery_doc_permissions(self, tmp_path: Path) -> None:
        """Test that recovery document has 600 permissions."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        # Trigger key generation
        encryptor.encrypt("test")

        # Verify recovery doc permissions
        recovery_doc = tmp_path / "KEYFILE_RECOVERY.txt"
        file_stat = recovery_doc.stat()
        mode = stat.S_IMODE(file_stat.st_mode)

        # Should be 0o600 (owner read/write only)
        assert mode == 0o600

    def test_recovery_doc_contains_paths(self, tmp_path: Path) -> None:
        """Test that recovery document contains correct file paths."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        # Trigger key generation
        encryptor.encrypt("test")

        # Verify recovery doc content
        recovery_doc = tmp_path / "KEYFILE_RECOVERY.txt"
        content = recovery_doc.read_text()

        assert str(key_file) in content
        assert str(tmp_path / ".keyfile.backup") in content
        assert "ENCRYPTION KEY BACKUP" in content
        assert "permanently unrecoverable" in content

    def test_verify_backup_exists_returns_true_when_matching(self, tmp_path: Path) -> None:
        """Test verify_backup_exists returns True when backup matches."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        # Trigger key generation
        encryptor.encrypt("test")

        # Verify backup exists and matches
        assert encryptor.verify_backup_exists()

    def test_verify_backup_exists_returns_false_when_missing(self, tmp_path: Path) -> None:
        """Test verify_backup_exists returns False when backup is missing."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        # Trigger key generation
        encryptor.encrypt("test")

        # Delete backup
        backup_path = tmp_path / ".keyfile.backup"
        backup_path.unlink()

        # Verify detects missing backup
        assert not encryptor.verify_backup_exists()

    def test_verify_backup_exists_returns_false_when_mismatched(self, tmp_path: Path) -> None:
        """Test verify_backup_exists returns False when backup doesn't match."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        # Trigger key generation
        encryptor.encrypt("test")

        # Corrupt backup
        backup_path = tmp_path / ".keyfile.backup"
        backup_path.write_bytes(b"corrupted-key-data")

        # Verify detects mismatch
        assert not encryptor.verify_backup_exists()

    def test_restore_from_backup_restores_primary(self, tmp_path: Path) -> None:
        """Test that primary keyfile can be restored from backup."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        # Trigger key generation
        original_encrypted = encryptor.encrypt("test-data")

        # Delete primary keyfile (simulate loss)
        key_file.unlink()
        assert not key_file.exists()

        # Restore from backup
        assert encryptor.restore_from_backup()
        assert key_file.exists()

        # Verify restored key works
        decrypted = encryptor.decrypt(original_encrypted)
        assert decrypted == "test-data"

    def test_restore_from_backup_returns_false_when_no_backup(self, tmp_path: Path) -> None:
        """Test restore_from_backup returns False when backup is missing."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        # No backup exists
        assert not encryptor.restore_from_backup()

    def test_restore_from_backup_sets_correct_permissions(self, tmp_path: Path) -> None:
        """Test that restored keyfile has correct permissions."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        # Trigger key generation
        encryptor.encrypt("test")

        # Delete primary
        key_file.unlink()

        # Restore from backup
        encryptor.restore_from_backup()

        # Verify permissions
        file_stat = key_file.stat()
        mode = stat.S_IMODE(file_stat.st_mode)
        assert mode == 0o600

    def test_backup_not_created_when_key_already_exists(self, tmp_path: Path) -> None:
        """Test that backup is not recreated when key already exists."""
        key_file = tmp_path / ".keyfile"

        # Create initial key
        encryptor1 = CredentialEncryptor(key_file)
        encryptor1.encrypt("test")

        # Get backup timestamp
        backup_path = tmp_path / ".keyfile.backup"
        original_mtime = backup_path.stat().st_mtime

        # Create second encryptor with existing key
        encryptor2 = CredentialEncryptor(key_file)
        encryptor2.encrypt("test")

        # Backup should not be modified
        current_mtime = backup_path.stat().st_mtime
        assert original_mtime == current_mtime
