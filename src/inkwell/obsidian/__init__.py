"""Obsidian integration module for wikilinks, tags, and Dataview support."""

from inkwell.obsidian.models import Entity, EntityType, WikilinkStyle
from inkwell.obsidian.wikilinks import WikilinkGenerator

__all__ = [
    "Entity",
    "EntityType",
    "WikilinkGenerator",
    "WikilinkStyle",
]
