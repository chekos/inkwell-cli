"""OutputPlugin base class for output file generation.

This module defines the base class that all output plugins must implement.
Output plugins convert extraction results into formatted output (markdown, HTML, etc.).
"""

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from inkwell.plugins.base import InkwellPlugin

if TYPE_CHECKING:
    from inkwell.extraction.models import ExtractionResult
    from inkwell.utils.costs import CostTracker


class OutputPlugin(InkwellPlugin):
    """Base class for output plugins.

    Output plugins convert extraction results into formatted strings.
    Each plugin handles a specific output format (markdown, HTML, Notion, etc.).

    Class Attributes (required):
        NAME: Unique plugin identifier (e.g., "markdown", "notion")
        VERSION: Plugin version (e.g., "1.0.0")
        DESCRIPTION: Short description of the plugin

    Class Attributes (optional):
        OUTPUT_FORMAT: Human-readable format name (e.g., "Markdown", "HTML")
        FILE_EXTENSION: Default file extension including dot (e.g., ".md", ".html")

    Example:
        >>> class MyOutput(OutputPlugin):
        ...     NAME = "my-output"
        ...     VERSION = "1.0.0"
        ...     DESCRIPTION = "Custom output format"
        ...     OUTPUT_FORMAT = "My Format"
        ...     FILE_EXTENSION = ".myf"
        ...
        ...     async def render(self, result, metadata) -> str:
        ...         # Convert result to formatted string
        ...         return formatted_content
    """

    # Optional: Human-readable format name
    OUTPUT_FORMAT: ClassVar[str] = "Unknown"

    # Optional: Default file extension (including dot)
    FILE_EXTENSION: ClassVar[str] = ".txt"

    def __init__(self, lazy_init: bool = False) -> None:
        """Initialize the output plugin.

        Args:
            lazy_init: If True, defer full initialization until configure() is called.
                      Used by plugin discovery to instantiate without configuration.
        """
        super().__init__()
        self._lazy_init = lazy_init

    @property
    def output_format(self) -> str:
        """Get the human-readable format name."""
        return self.OUTPUT_FORMAT

    @property
    def file_extension(self) -> str:
        """Get the default file extension (including dot)."""
        return self.FILE_EXTENSION

    @abstractmethod
    async def render(
        self,
        result: "ExtractionResult",
        episode_metadata: dict[str, Any],
        include_frontmatter: bool = True,
    ) -> str:
        """Render extraction result to formatted output string.

        Args:
            result: ExtractionResult from extraction engine containing
                   template name, extracted content, cost, and provider info.
            episode_metadata: Episode metadata dict with keys like:
                - podcast_name: Name of the podcast
                - episode_title: Title of the episode
                - episode_url: URL of the episode (optional)
            include_frontmatter: Whether to include metadata header
                (e.g., YAML frontmatter for markdown).

        Returns:
            Formatted output string ready to be written to file.

        Raises:
            ValueError: If result or metadata is invalid.
        """
        pass

    def get_filename(self, template_name: str) -> str:
        """Get the output filename for a template.

        Default implementation uses template name + file extension.
        Override for custom naming schemes.

        Args:
            template_name: Name of the extraction template.

        Returns:
            Filename with extension (e.g., "summary.md").
        """
        return f"{template_name}{self.file_extension}"

    def configure(
        self,
        config: dict[str, Any],
        cost_tracker: "CostTracker | None" = None,
    ) -> None:
        """Configure the plugin with settings.

        Subclasses can override to perform additional initialization.

        Args:
            config: Plugin-specific configuration dict.
            cost_tracker: Optional cost tracker (rarely needed for output plugins).
        """
        super().configure(config, cost_tracker)
