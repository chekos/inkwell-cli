"""Credential encryption and decryption using Fernet."""

import stat
from pathlib import Path

from cryptography.fernet import Fernet

from inkwell.utils.errors import EncryptionError


class CredentialEncryptor:
    """Handles encryption and decryption of credentials using Fernet symmetric encryption."""

    def __init__(self, key_path: Path) -> None:
        """Initialize the credential encryptor.

        Args:
            key_path: Path to the encryption key file

        Raises:
            EncryptionError: If key file permissions are too open
        """
        self.key_path = key_path
        self._cipher: Fernet | None = None

    def _ensure_key(self) -> bytes:
        """Ensure encryption key exists and has correct permissions.

        Returns:
            The encryption key as bytes

        Raises:
            EncryptionError: If key file has insecure permissions
        """
        if self.key_path.exists():
            # Check permissions
            self._validate_key_permissions()
            return self.key_path.read_bytes()

        # Generate new key
        key = Fernet.generate_key()

        # Ensure parent directory exists
        self.key_path.parent.mkdir(parents=True, exist_ok=True)

        # Write key file
        self.key_path.write_bytes(key)

        # Set restrictive permissions (owner read/write only)
        self.key_path.chmod(0o600)

        return key

    def _validate_key_permissions(self) -> None:
        """Validate that key file has secure permissions.

        Raises:
            EncryptionError: If permissions are too open (e.g., world-readable)
        """
        if not self.key_path.exists():
            return

        file_stat = self.key_path.stat()
        mode = stat.S_IMODE(file_stat.st_mode)

        # Check if file is readable by group or others
        if mode & (stat.S_IRGRP | stat.S_IROTH | stat.S_IWGRP | stat.S_IWOTH):
            raise EncryptionError(
                f"Key file {self.key_path} has insecure permissions ({oct(mode)}). "
                f"Run: chmod 600 {self.key_path}"
            )

    def _get_cipher(self) -> Fernet:
        """Get or create the Fernet cipher instance.

        Returns:
            Fernet cipher instance
        """
        if self._cipher is None:
            key = self._ensure_key()
            self._cipher = Fernet(key)
        return self._cipher

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string

        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            return ""

        try:
            cipher = self._get_cipher()
            encrypted_bytes = cipher.encrypt(plaintext.encode("utf-8"))
            return encrypted_bytes.decode("utf-8")
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt data: {e}") from e

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt an encrypted string.

        Args:
            ciphertext: The base64-encoded encrypted string

        Returns:
            Decrypted plaintext string

        Raises:
            EncryptionError: If decryption fails
        """
        if not ciphertext:
            return ""

        try:
            cipher = self._get_cipher()
            decrypted_bytes = cipher.decrypt(ciphertext.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt data: {e}") from e

    def rotate_key(self, new_key_path: Path) -> None:
        """Rotate to a new encryption key.

        This is a placeholder for future implementation.

        Args:
            new_key_path: Path to the new key file

        Raises:
            NotImplementedError: Key rotation not yet implemented
        """
        raise NotImplementedError("Key rotation will be implemented in a future version")
