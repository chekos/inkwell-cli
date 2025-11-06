"""Configuration manager for loading and saving Inkwell config."""

from pathlib import Path

import yaml

from inkwell.config.crypto import CredentialEncryptor
from inkwell.config.defaults import (
    DEFAULT_GLOBAL_CONFIG,
    get_default_config_content,
    get_default_feeds_content,
)
from inkwell.config.schema import AuthConfig, FeedConfig, Feeds, GlobalConfig
from inkwell.utils.errors import (
    ConfigNotFoundError,
    DuplicateFeedError,
    FeedNotFoundError,
    InvalidConfigError,
)
from inkwell.utils.paths import (
    get_config_dir,
    get_config_file,
    get_feeds_file,
    get_key_file,
)


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

        self.encryptor = CredentialEncryptor(self.key_file)

    def load_config(self) -> GlobalConfig:
        """Load and validate global configuration.

        Returns:
            Validated GlobalConfig instance

        Raises:
            ConfigNotFoundError: If config file doesn't exist
            InvalidConfigError: If config is invalid
        """
        if not self.config_file.exists():
            # Create default config
            self._create_default_config()
            return DEFAULT_GLOBAL_CONFIG

        try:
            with open(self.config_file) as f:
                data = yaml.safe_load(f) or {}
            return GlobalConfig(**data)
        except Exception as e:
            raise InvalidConfigError(
                f"Invalid configuration in {self.config_file}: {e}"
            ) from e

    def save_config(self, config: GlobalConfig) -> None:
        """Save global configuration.

        Args:
            config: GlobalConfig instance to save
        """
        # Convert to dict and handle Path objects
        data = config.model_dump(mode="python")

        # Convert Path to string
        if "default_output_dir" in data and isinstance(
            data["default_output_dir"], Path
        ):
            data["default_output_dir"] = str(data["default_output_dir"])

        self.config_dir.mkdir(parents=True, exist_ok=True)

        with open(self.config_file, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

    def load_feeds(self) -> Feeds:
        """Load feeds configuration with decrypted credentials.

        Returns:
            Feeds instance with decrypted credentials

        Raises:
            InvalidConfigError: If feeds file is invalid
        """
        if not self.feeds_file.exists():
            # Create empty feeds file
            self._create_default_feeds()
            return Feeds()

        try:
            with open(self.feeds_file) as f:
                data = yaml.safe_load(f) or {}

            # Decrypt credentials in feed configs
            if "feeds" in data:
                for feed_name, feed_data in data["feeds"].items():
                    if "auth" in feed_data:
                        auth = feed_data["auth"]
                        if auth.get("username"):
                            auth["username"] = self.encryptor.decrypt(auth["username"])
                        if auth.get("password"):
                            auth["password"] = self.encryptor.decrypt(auth["password"])
                        if auth.get("token"):
                            auth["token"] = self.encryptor.decrypt(auth["token"])

            return Feeds(**data)
        except Exception as e:
            raise InvalidConfigError(
                f"Invalid feeds configuration in {self.feeds_file}: {e}"
            ) from e

    def save_feeds(self, feeds: Feeds) -> None:
        """Save feeds configuration with encrypted credentials.

        Args:
            feeds: Feeds instance to save
        """
        # Convert to dict
        data = feeds.model_dump(mode="python")

        # Encrypt credentials
        if "feeds" in data:
            for feed_name, feed_data in data["feeds"].items():
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

        with open(self.feeds_file, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

    def add_feed(self, name: str, feed_config: FeedConfig) -> None:
        """Add or update a feed.

        Args:
            name: Feed identifier
            feed_config: Feed configuration

        Raises:
            DuplicateFeedError: If feed already exists (use update instead)
        """
        feeds = self.load_feeds()

        if name in feeds.feeds:
            raise DuplicateFeedError(f"Feed '{name}' already exists. Use update to modify it.")

        feeds.feeds[name] = feed_config
        self.save_feeds(feeds)

    def update_feed(self, name: str, feed_config: FeedConfig) -> None:
        """Update an existing feed.

        Args:
            name: Feed identifier
            feed_config: Updated feed configuration

        Raises:
            FeedNotFoundError: If feed doesn't exist
        """
        feeds = self.load_feeds()

        if name not in feeds.feeds:
            raise FeedNotFoundError(f"Feed '{name}' not found")

        feeds.feeds[name] = feed_config
        self.save_feeds(feeds)

    def remove_feed(self, name: str) -> None:
        """Remove a feed.

        Args:
            name: Feed identifier to remove

        Raises:
            FeedNotFoundError: If feed doesn't exist
        """
        feeds = self.load_feeds()

        if name not in feeds.feeds:
            raise FeedNotFoundError(f"Feed '{name}' not found")

        del feeds.feeds[name]
        self.save_feeds(feeds)

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
            raise FeedNotFoundError(f"Feed '{name}' not found")

        return feeds.feeds[name]

    def list_feeds(self) -> dict[str, FeedConfig]:
        """List all feeds.

        Returns:
            Dictionary of feed name to FeedConfig
        """
        feeds = self.load_feeds()
        return feeds.feeds

    def _create_default_config(self) -> None:
        """Create default config.yaml file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(get_default_config_content())

    def _create_default_feeds(self) -> None:
        """Create default feeds.yaml file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.feeds_file.write_text(get_default_feeds_content())
