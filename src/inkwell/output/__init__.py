"""Output generation system for markdown files.

This package handles markdown generation, frontmatter formatting,
and file writing for extracted podcast content.
"""

from .manager import OutputManager
from .markdown import MarkdownGenerator
from .models import EpisodeMetadata, EpisodeOutput, OutputFile

__all__ = [
    "EpisodeMetadata",
    "OutputFile",
    "EpisodeOutput",
    "MarkdownGenerator",
    "OutputManager",
]
