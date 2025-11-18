"""Default configuration templates for Inkwell."""

from pathlib import Path

from inkwell.config.schema import GlobalConfig

# Default global configuration
DEFAULT_GLOBAL_CONFIG = GlobalConfig()

# YAML template for config.yaml
CONFIG_YAML_TEMPLATE = """# Inkwell Configuration
# See https://github.com/your-repo/inkwell-cli for documentation

version: "1"

# Directory where processed episodes will be saved
default_output_dir: ~/podcasts

# LLM models to use
transcription_model: gemini-2.5-flash
interview_model: claude-sonnet-4-5

# Check YouTube for existing transcripts before transcribing
youtube_check: true

# Logging level (DEBUG, INFO, WARNING, ERROR)
log_level: INFO

# Default templates to apply to all episodes
default_templates:
  - summary
  - quotes
  - key-concepts

# Category-specific templates
template_categories:
  tech:
    - tools-mentioned
    - frameworks-mentioned
  interview:
    - books-mentioned
    - people-mentioned
"""

# YAML template for feeds.yaml
FEEDS_YAML_TEMPLATE = """# Podcast Feeds
# Add feeds using: inkwell add <url> --name <name>
# This file will be automatically populated

feeds: {}
"""


def get_default_config_content() -> str:
    """Get the default config.yaml content.

    Returns:
        YAML string for config.yaml
    """
    return CONFIG_YAML_TEMPLATE.strip()


def get_default_feeds_content() -> str:
    """Get the default feeds.yaml content.

    Returns:
        YAML string for feeds.yaml
    """
    return FEEDS_YAML_TEMPLATE.strip()


def write_default_config(config_file: Path) -> None:
    """Write default config.yaml file.

    Args:
        config_file: Path to config.yaml file
    """
    config_file.write_text(get_default_config_content())


def write_default_feeds(feeds_file: Path) -> None:
    """Write default feeds.yaml file.

    Args:
        feeds_file: Path to feeds.yaml file
    """
    feeds_file.write_text(get_default_feeds_content())
