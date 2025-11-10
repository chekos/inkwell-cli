"""Obsidian integration module for wikilinks, tags, and Dataview support."""

from inkwell.obsidian.dataview import (
    DataviewConfig,
    DataviewFrontmatter,
    create_frontmatter_dict,
    format_frontmatter_yaml,
)
from inkwell.obsidian.models import Entity, EntityType, WikilinkStyle
from inkwell.obsidian.tag_models import Tag, TagCategory, TagConfig, TagStyle
from inkwell.obsidian.tags import TagGenerator
from inkwell.obsidian.wikilinks import WikilinkGenerator

__all__ = [
    "DataviewConfig",
    "DataviewFrontmatter",
    "Entity",
    "EntityType",
    "Tag",
    "TagCategory",
    "TagConfig",
    "TagGenerator",
    "TagStyle",
    "WikilinkGenerator",
    "WikilinkStyle",
    "create_frontmatter_dict",
    "format_frontmatter_yaml",
]
