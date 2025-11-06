"""Tests for credential encryption."""

import stat
from pathlib import Path

import pytest

from inkwell.config.crypto import CredentialEncryptor
from inkwell.utils.errors import EncryptionError


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
        """Test that insecure key file permissions raise EncryptionError."""
        key_file = tmp_path / ".keyfile"

        # Create key file with world-readable permissions
        key_file.write_text("fake-key")
        key_file.chmod(0o644)  # World-readable

        encryptor = CredentialEncryptor(key_file)

        with pytest.raises(EncryptionError, match="insecure permissions"):
            encryptor.encrypt("test")

    def test_decrypt_invalid_ciphertext_raises_error(self, tmp_path: Path) -> None:
        """Test that decrypting invalid ciphertext raises EncryptionError."""
        key_file = tmp_path / ".keyfile"
        encryptor = CredentialEncryptor(key_file)

        with pytest.raises(EncryptionError, match="Failed to decrypt"):
            encryptor.decrypt("not-valid-ciphertext")

    def test_different_plaintexts_produce_different_ciphertexts(
        self, tmp_path: Path
    ) -> None:
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
