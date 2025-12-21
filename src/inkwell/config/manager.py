"""Configuration manager for loading and saving Inkwell config."""

import fcntl
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import yaml
from pydantic import ValidationError

from inkwell.config.crypto import CredentialEncryptor
from inkwell.config.defaults import (
    DEFAULT_GLOBAL_CONFIG,
    get_default_config_content,
    get_default_feeds_content,
)
from inkwell.config.schema import FeedConfig, Feeds, GlobalConfig
from inkwell.utils.datetime import now_utc
from inkwell.utils.errors import (
    ConfigError,
    NotFoundError,
)
from inkwell.utils.errors import (
    ValidationError as InkwellValidationError,
)
from inkwell.utils.paths import (
    get_config_dir,
    get_config_file,
    get_feeds_file,
    get_key_file,
)
from inkwell.utils.yaml_integrity import YAMLIntegrityError, YAMLWithIntegrity


class ConfigManager:
    """Manages Inkwell configuration files."""

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize the config manager.

        Args:
            config_dir: Optional custom config directory. Defaults to XDG config dir.
        """
        if config_dir is None:
            self.config_dir = get_config_dir()
            self.config_file = get_config_file()
            self.feeds_file = get_feeds_file()
            self.key_file = get_key_file()
        else:
            self.config_dir = config_dir
            self.config_file = config_dir / "config.yaml"
            self.feeds_file = config_dir / "feeds.yaml"
            self.key_file = config_dir / ".keyfile"

        self.audit_log = self.config_dir / "audit.log"
        self.encryptor = CredentialEncryptor(self.key_file)

    @contextmanager
    def _feeds_lock(self) -> Iterator[None]:
        """Context manager for feeds file locking.

        Uses fcntl-based file locking to prevent concurrent access to the feeds
        file. This prevents data corruption and lost updates when multiple processes
        attempt to add/remove/update feeds simultaneously.

        Yields:
            None

        Note:
            This uses POSIX fcntl locking. On Windows systems, fcntl is not
            available, so locking is skipped (graceful degradation).
        """
        if sys.platform == "win32":
            # Windows doesn't support fcntl, skip locking
            # This matches the pattern in session_manager.py and costs.py
            yield
            return

        lock_file_path = self.feeds_file.with_suffix(".lock")
        lock_fd = None

        try:
            # Open lock file in write mode (creates if doesn't exist)
            lock_fd = open(lock_file_path, "w")

            # Acquire exclusive lock (will block if another process holds the lock)
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)

            # Lock acquired, execute protected code
            yield

        finally:
            # Release lock and close file
            if lock_fd:
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                    lock_fd.close()
                except Exception:
                    # Ignore errors during cleanup
                    pass

    def _log_change(self, operation: str, details: dict) -> None:
        """Append change to audit log with full context.

        Args:
            operation: Type of operation (add_feed, remove_feed, update_feed, update_config)
            details: Dictionary with operation-specific details
        """
        log_entry = {
            "timestamp": now_utc().isoformat(),
            "operation": operation,
            "details": details,
            "user": os.getenv("USER", "unknown"),
            "hostname": os.getenv("HOSTNAME", os.getenv("COMPUTERNAME", "unknown")),
            "pid": os.getpid(),
        }

        # Ensure audit log directory exists
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)

        # Append to log (atomic on most filesystems)
        with open(self.audit_log, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def load_config(self) -> GlobalConfig:
        """Load and validate global configuration with integrity checking.

        Returns:
            Validated GlobalConfig instance

        Raises:
            InvalidConfigError: If config is invalid or corrupted
        """
        if not self.config_file.exists():
            # Create default config
            self._create_default_config()
            return DEFAULT_GLOBAL_CONFIG

        try:
            # Load with integrity verification
            data = YAMLWithIntegrity.read_yaml_with_verification(self.config_file)
            return GlobalConfig(**data)
        except YAMLIntegrityError as e:
            # Integrity check failed - file is corrupted
            raise ConfigError(
                f"Configuration file is corrupted:\n{e}\n\nRun 'inkwell config edit' to fix"
            ) from e
        except ValidationError as e:
            # Format Pydantic validation errors nicely
            error_lines = ["Invalid configuration in config.yaml:"]
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                msg = error["msg"]
                error_lines.append(f"  • {field}: {msg}")
            error_lines.append("\nRun 'inkwell config edit' to fix")
            raise ConfigError("\n".join(error_lines)) from e
        except yaml.YAMLError as e:
            raise ConfigError(
                f"Invalid YAML syntax in config.yaml:\n{e}\n\nRun 'inkwell config edit' to fix"
            ) from e
        except Exception as e:
            raise ConfigError(f"Error loading configuration: {e}") from e

    def save_config(self, config: GlobalConfig) -> None:
        """Save global configuration.

        Args:
            config: GlobalConfig instance to save
        """
        # Load old config to detect changes (if exists)
        old_config = None
        if self.config_file.exists():
            try:
                old_config = self.load_config()
            except Exception:
                # If we can't load old config, just save new one without logging
                pass

        # Convert to dict and handle Path objects
        data = config.model_dump(mode="python")

        # Convert Path to string
        if "default_output_dir" in data and isinstance(data["default_output_dir"], Path):
            data["default_output_dir"] = str(data["default_output_dir"])

        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Write with integrity checksum
        YAMLWithIntegrity.write_yaml_with_checksum(self.config_file, data)

        # Log config changes
        if old_config:
            changes = {}
            if str(old_config.default_output_dir) != str(config.default_output_dir):
                changes["default_output_dir"] = {
                    "old": str(old_config.default_output_dir),
                    "new": str(config.default_output_dir),
                }
            if old_config.transcription_model != config.transcription_model:
                changes["transcription_model"] = {
                    "old": old_config.transcription_model,
                    "new": config.transcription_model,
                }
            if old_config.interview_model != config.interview_model:
                changes["interview_model"] = {
                    "old": old_config.interview_model,
                    "new": config.interview_model,
                }
            if old_config.log_level != config.log_level:
                changes["log_level"] = {
                    "old": old_config.log_level,
                    "new": config.log_level,
                }

            if changes:
                self._log_change("update_config", {"changes": changes})

    def _validate_decrypted_credential(
        self, value: str, field_name: str, feed_name: str, max_length: int = 255
    ) -> None:
        """Validate decrypted credential format.

        Args:
            value: The decrypted credential value
            field_name: Name of the credential field (e.g., "username", "password", "token")
            feed_name: Name of the feed for error messages
            max_length: Maximum allowed length for the credential

        Raises:
            ValueError: If credential format is invalid
        """
        if not value:
            raise ValueError(f"{field_name} is empty after decryption for feed '{feed_name}'")

        if len(value) > max_length:
            raise ValueError(
                f"{field_name} exceeds maximum length ({max_length}) for feed '{feed_name}'"
            )

        if "\x00" in value:
            raise ValueError(
                f"{field_name} contains null bytes (likely corruption) for feed '{feed_name}'"
            )

    def load_feeds(self) -> Feeds:
        """Load feeds configuration with decrypted credentials.

        Returns:
            Feeds instance with decrypted credentials

        Raises:
            InvalidConfigError: If feeds file is invalid or credentials cannot be decrypted
        """
        if not self.feeds_file.exists():
            # Create empty feeds file
            self._create_default_feeds()
            return Feeds()

        try:
            # Load with integrity verification
            data = YAMLWithIntegrity.read_yaml_with_verification(self.feeds_file)

            # Decrypt and validate credentials in feed configs
            if "feeds" in data:
                for feed_name, feed_data in data["feeds"].items():
                    if "auth" in feed_data:
                        auth = feed_data["auth"]

                        try:
                            if auth.get("username"):
                                decrypted_username = self.encryptor.decrypt(auth["username"])
                                self._validate_decrypted_credential(
                                    decrypted_username, "username", feed_name, max_length=255
                                )
                                auth["username"] = decrypted_username

                            if auth.get("password"):
                                decrypted_password = self.encryptor.decrypt(auth["password"])
                                self._validate_decrypted_credential(
                                    decrypted_password, "password", feed_name, max_length=255
                                )
                                auth["password"] = decrypted_password

                            if auth.get("token"):
                                decrypted_token = self.encryptor.decrypt(auth["token"])
                                self._validate_decrypted_credential(
                                    decrypted_token, "token", feed_name, max_length=1000
                                )
                                auth["token"] = decrypted_token

                        except Exception as e:
                            raise ConfigError(
                                f"Failed to decrypt credentials for feed '{feed_name}': {e}\n"
                                f"Your keyfile may be corrupted. Possible fixes:\n"
                                f"  1. Restore .keyfile from backup\n"
                                f"  2. Re-add the feed with correct credentials\n"
                                f"  3. Check keyfile permissions (should be 0600)"
                            ) from e

            return Feeds(**data)
        except YAMLIntegrityError as e:
            # Integrity check failed - file is corrupted
            raise ConfigError(
                f"Feeds configuration file is corrupted:\n{e}\n\nCheck feeds.yaml for errors"
            ) from e
        except ValidationError as e:
            # Format Pydantic validation errors nicely
            error_lines = ["Invalid feeds configuration in feeds.yaml:"]
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                msg = error["msg"]
                error_lines.append(f"  • {field}: {msg}")
            error_lines.append("\nRun 'inkwell config edit' to fix feeds.yaml")
            raise ConfigError("\n".join(error_lines)) from e
        except yaml.YAMLError as e:
            raise ConfigError(
                f"Invalid YAML syntax in feeds.yaml:\n{e}\n\nCheck feeds.yaml for syntax errors"
            ) from e
        except ConfigError:
            # Re-raise our custom ConfigError from credential validation
            raise
        except Exception as e:
            raise ConfigError(f"Error loading feeds configuration: {e}") from e

    def save_feeds(self, feeds: Feeds) -> None:
        """Save feeds configuration with encrypted credentials.

        Args:
            feeds: Feeds instance to save
        """
        # Convert to dict
        data = feeds.model_dump(mode="python")

        # Encrypt credentials
        if "feeds" in data:
            for _feed_name, feed_data in data["feeds"].items():
                if "auth" in feed_data:
                    auth = feed_data["auth"]
                    if auth.get("username"):
                        auth["username"] = self.encryptor.encrypt(auth["username"])
                    if auth.get("password"):
                        auth["password"] = self.encryptor.encrypt(auth["password"])
                    if auth.get("token"):
                        auth["token"] = self.encryptor.encrypt(auth["token"])

                # Convert URL to string
                if "url" in feed_data:
                    feed_data["url"] = str(feed_data["url"])

        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Write with integrity checksum
        YAMLWithIntegrity.write_yaml_with_checksum(self.feeds_file, data)

    def add_feed(self, name: str, feed_config: FeedConfig) -> None:
        """Add or update a feed.

        Uses file locking to prevent race conditions in concurrent operations.

        Args:
            name: Feed identifier
            feed_config: Feed configuration

        Raises:
            DuplicateFeedError: If feed already exists (use update instead)
        """
        with self._feeds_lock():
            feeds = self.load_feeds()

            if name in feeds.feeds:
                raise InkwellValidationError(
                    f"Feed '{name}' already exists. Use update to modify it.",
                    suggestion="Use 'inkwell remove' first, or choose a different name",
                )

            feeds.feeds[name] = feed_config
            self.save_feeds(feeds)

            # Log the feed addition
            self._log_change(
                "add_feed",
                {
                    "feed_name": name,
                    "url": str(feed_config.url),
                    "auth_type": feed_config.auth.type if feed_config.auth else "none",
                    "category": feed_config.category,
                },
            )

    def update_feed(self, name: str, feed_config: FeedConfig) -> None:
        """Update an existing feed.

        Uses file locking to prevent race conditions in concurrent operations.

        Args:
            name: Feed identifier
            feed_config: Updated feed configuration

        Raises:
            FeedNotFoundError: If feed doesn't exist
        """
        with self._feeds_lock():
            feeds = self.load_feeds()

            if name not in feeds.feeds:
                raise NotFoundError(
                    "Feed", name, suggestion="Run 'inkwell list' to see available feeds"
                )

            # Capture old config for diff
            old_config = feeds.feeds[name]

            feeds.feeds[name] = feed_config
            self.save_feeds(feeds)

            # Log what changed
            changes = {}
            if str(old_config.url) != str(feed_config.url):
                changes["url"] = {
                    "old": str(old_config.url),
                    "new": str(feed_config.url),
                }
            if old_config.auth.type != feed_config.auth.type:
                changes["auth_type_changed"] = True
            if old_config.category != feed_config.category:
                changes["category"] = {
                    "old": old_config.category,
                    "new": feed_config.category,
                }

            self._log_change(
                "update_feed",
                {
                    "feed_name": name,
                    "changes": changes,
                },
            )

    def remove_feed(self, name: str) -> None:
        """Remove a feed.

        Uses file locking to prevent race conditions in concurrent operations.

        Args:
            name: Feed identifier to remove

        Raises:
            FeedNotFoundError: If feed doesn't exist
        """
        with self._feeds_lock():
            feeds = self.load_feeds()

            if name not in feeds.feeds:
                raise NotFoundError(
                    "Feed", name, suggestion="Run 'inkwell list' to see available feeds"
                )

            # Capture feed details before deletion
            removed_feed = feeds.feeds[name]

            del feeds.feeds[name]
            self.save_feeds(feeds)

            # Log the removal with feed details
            self._log_change(
                "remove_feed",
                {
                    "feed_name": name,
                    "url": str(removed_feed.url),
                    "auth_type": removed_feed.auth.type if removed_feed.auth else "none",
                    "category": removed_feed.category,
                },
            )

    def get_feed(self, name: str) -> FeedConfig:
        """Get a single feed configuration.

        Args:
            name: Feed identifier

        Returns:
            FeedConfig instance

        Raises:
            FeedNotFoundError: If feed doesn't exist
        """
        feeds = self.load_feeds()

        if name not in feeds.feeds:
            raise NotFoundError(
                "Feed", name, suggestion="Run 'inkwell list' to see available feeds"
            )

        return feeds.feeds[name]

    def list_feeds(self) -> dict[str, FeedConfig]:
        """List all feeds.

        Returns:
            Dictionary of feed name to FeedConfig
        """
        feeds = self.load_feeds()
        return feeds.feeds

    def get_feed_history(self, feed_name: str) -> list[dict]:
        """Get all changes for a specific feed.

        Args:
            feed_name: Name of the feed to get history for

        Returns:
            List of audit log entries for the feed, in chronological order
        """
        if not self.audit_log.exists():
            return []

        history = []
        with open(self.audit_log) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry["details"].get("feed_name") == feed_name:
                        history.append(entry)
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

        return history

    def get_recent_changes(self, limit: int = 10) -> list[dict]:
        """Get N most recent configuration changes.

        Args:
            limit: Maximum number of recent changes to return

        Returns:
            List of recent audit log entries, most recent first
        """
        if not self.audit_log.exists():
            return []

        entries = []
        with open(self.audit_log) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    entries.append(entry)
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

        # Return most recent entries (last N lines)
        return entries[-limit:][::-1]  # Reverse to show most recent first

    def _create_default_config(self) -> None:
        """Create default config.yaml file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(get_default_config_content())

    def _create_default_feeds(self) -> None:
        """Create default feeds.yaml file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.feeds_file.write_text(get_default_feeds_content())
