"""Credential encryption and decryption using Fernet."""

import stat
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet

from inkwell.utils.errors import ConfigError, SecurityError
from inkwell.utils.logging import get_logger

logger = get_logger()


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

        # Write primary key file
        self.key_path.write_bytes(key)

        # Set restrictive permissions (owner read/write only)
        self.key_path.chmod(0o600)

        # Create backup keyfile with same permissions
        backup_path = self.key_path.parent / ".keyfile.backup"
        backup_path.write_bytes(key)
        backup_path.chmod(0o600)

        # Create recovery instructions
        recovery_doc = self.key_path.parent / "KEYFILE_RECOVERY.txt"
        recovery_doc.write_text(
            f"ENCRYPTION KEY BACKUP\n"
            f"====================\n\n"
            f"Your encryption key is stored at:\n"
            f"  Primary: {self.key_path}\n"
            f"  Backup:  {backup_path}\n\n"
            f"IMPORTANT: If you lose both files, all encrypted feed credentials\n"
            f"will be permanently unrecoverable. Back up these files securely!\n\n"
            f"To restore from backup:\n"
            f"  cp {backup_path} {self.key_path}\n"
            f"  chmod 600 {self.key_path}\n\n"
            f"To back up to external location:\n"
            f"  cp {self.key_path} /path/to/secure/backup/location/\n\n"
            f"Security Notes:\n"
            f"  - Keep backups secure (encrypted USB, password manager, etc.)\n"
            f"  - Never commit keyfile to git\n"
            f"  - Never share keyfile (it decrypts all your credentials)\n"
            f"  - If compromised, regenerate and re-add all feeds\n\n"
            f"Generated: {datetime.now().isoformat()}\n"
        )
        recovery_doc.chmod(0o600)

        # Warn user about critical files
        logger.warning(
            f"Created new encryption key at {self.key_path}\n"
            f"IMPORTANT: A backup has been created at {backup_path}\n"
            f"See {recovery_doc} for recovery instructions.\n"
            f"Losing both files will result in permanent data loss!"
        )

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
            raise SecurityError(
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
        except SecurityError:
            raise  # Re-raise security errors directly
        except Exception as e:
            raise ConfigError(f"Failed to encrypt data: {e}") from e

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
        except SecurityError:
            raise  # Re-raise security errors directly
        except Exception as e:
            # Decryption failures are security issues (tampering/corruption)
            raise SecurityError(f"Failed to decrypt data: {e}") from e

    def verify_backup_exists(self) -> bool:
        """Check if backup keyfile exists and matches primary.

        Returns:
            True if backup exists and matches primary key, False otherwise
        """
        backup_path = self.key_path.parent / ".keyfile.backup"

        if not backup_path.exists():
            return False

        # Verify backup matches primary
        if self.key_path.exists():
            primary_key = self.key_path.read_bytes()
            backup_key = backup_path.read_bytes()
            return primary_key == backup_key

        return True

    def restore_from_backup(self) -> bool:
        """Restore primary keyfile from backup.

        Returns:
            True if restoration was successful, False otherwise
        """
        backup_path = self.key_path.parent / ".keyfile.backup"

        if not backup_path.exists():
            logger.error("Backup keyfile not found")
            return False

        backup_key = backup_path.read_bytes()
        self.key_path.write_bytes(backup_key)
        self.key_path.chmod(0o600)

        logger.info(f"Restored keyfile from backup: {backup_path}")
        return True

    def rotate_key(self, new_key_path: Path) -> None:
        """Rotate to a new encryption key.

        This is a placeholder for future implementation.

        Args:
            new_key_path: Path to the new key file

        Raises:
            NotImplementedError: Key rotation not yet implemented
        """
        raise NotImplementedError("Key rotation will be implemented in a future version")
