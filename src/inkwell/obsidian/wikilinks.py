"""Wikilink generation for Obsidian integration.

This module extracts entities from podcast transcripts and extracted content,
then converts them to Obsidian wikilinks for cross-referencing.
"""

import logging
import re
from typing import Any, Pattern

import regex

from inkwell.obsidian.models import Entity, EntityType, WikilinkConfig

logger = logging.getLogger(__name__)


class WikilinkGenerator:
    """Generate wikilinks from extracted entities.

    Extracts entities (people, books, tools, concepts) from transcripts and
    converts them to Obsidian wikilinks for cross-referencing.

    Examples:
        >>> generator = WikilinkGenerator()
        >>> entities = generator.extract_entities(
        ...     transcript="Cal Newport discusses deep work...",
        ...     extraction_results={"summary": "...", "quotes": "..."}
        ... )
        >>> wikilinks = generator.format_wikilinks(entities)
        >>> '[[Cal Newport]]' in wikilinks
        True
    """

    def __init__(self, config: WikilinkConfig | None = None):
        """Initialize wikilink generator.

        Args:
            config: Optional wikilink configuration
        """
        self.config = config or WikilinkConfig()

        # Regex timeout in seconds (protects against ReDoS attacks)
        self._regex_timeout = 1.0

        # Maximum chunk size for processing large text (50KB)
        self._max_chunk_size = 50000

        # Compiled pattern regexes for entity extraction with timeout protection
        # Note: timeout is passed to finditer(), not compile()
        self._patterns: dict[EntityType, list[Pattern]] = {
            EntityType.PERSON: [
                # Full names with title (Dr., Prof., etc.)
                regex.compile(
                    r"\b(?:Dr\.?|Prof\.?|Mr\.?|Ms\.?|Mrs\.?)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)"
                ),
                # Full names (First Last, possibly with middle initial)
                regex.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\b"),
                # Names in possessive form
                regex.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)'s\b"),
            ],
            EntityType.BOOK: [
                # Books in quotes
                regex.compile(r'"([A-Z][^"]{2,})"'),
                regex.compile(r"'([A-Z][^']{2,})'"),
                # "Book: Title" or "his book Title"
                regex.compile(r"\b(?:book|titled)\s+['\"]?([A-Z][^'\"]{2,})['\"]?"),
            ],
            EntityType.TOOL: [
                # Software/tools (capitalized product names)
                regex.compile(r"\b([A-Z][a-z]*(?:[A-Z][a-z]*)+)\b"),  # CamelCase
                # Tools with specific markers
                regex.compile(r"\b(?:using|via|with|tool)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"),
            ],
        }

        # Common false positives to filter out
        self._stopwords = {
            "person": {
                "YouTube",
                "Google",
                "Facebook",
                "Twitter",
                "Amazon",
                "Apple",
                "Microsoft",
            },
            "book": set(),
            "tool": {"The", "That", "This", "What", "When", "Where", "Which", "Who"},
        }

    def extract_entities(
        self,
        transcript: str,
        extraction_results: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> list[Entity]:
        """Extract entities from transcript and extraction results.

        Args:
            transcript: Full episode transcript
            extraction_results: Dict of extraction results (summary, quotes, etc.)
            metadata: Optional episode metadata

        Returns:
            List of extracted entities

        Example:
            >>> generator = WikilinkGenerator()
            >>> entities = generator.extract_entities(
            ...     transcript="Cal Newport discusses his book Deep Work...",
            ...     extraction_results={"summary": "Episode about focus..."}
            ... )
            >>> len(entities) > 0
            True
        """
        entities: list[Entity] = []

        # Extract from transcript
        entities.extend(self._extract_from_text(transcript, "transcript"))

        # Extract from extraction results
        for template_name, content in extraction_results.items():
            if isinstance(content, str):
                entities.extend(self._extract_from_text(content, f"template:{template_name}"))
            elif isinstance(content, dict):
                # Handle structured extraction results
                content_str = str(content)
                entities.extend(self._extract_from_text(content_str, f"template:{template_name}"))

        # Extract structured entities from specific templates
        if "books-mentioned" in extraction_results:
            entities.extend(self._extract_books_from_template(extraction_results["books-mentioned"]))

        if "tools-mentioned" in extraction_results:
            entities.extend(self._extract_tools_from_template(extraction_results["tools-mentioned"]))

        if "people-mentioned" in extraction_results:
            entities.extend(
                self._extract_people_from_template(extraction_results["people-mentioned"])
            )

        # Filter and deduplicate
        entities = self._filter_entities(entities)

        if self.config.deduplicate:
            entities = self._deduplicate_entities(entities)

        # Sort by confidence and limit per type
        entities = self._limit_entities_per_type(entities)

        return entities

    def _extract_from_text(self, text: str, source: str) -> list[Entity]:
        """Extract entities from text using regex patterns.

        This method implements ReDoS protection through:
        - Text chunking to limit input size
        - Regex timeouts to prevent catastrophic backtracking
        - Graceful error handling for timeout events

        Args:
            text: Text to extract from
            source: Source description for context

        Returns:
            List of extracted entities
        """
        entities: list[Entity] = []

        # Process text in chunks to prevent excessive processing and limit ReDoS impact
        if len(text) > self._max_chunk_size:
            logger.info(
                f"Text size ({len(text)} chars) exceeds max chunk size "
                f"({self._max_chunk_size}). Processing in chunks."
            )
            for i in range(0, len(text), self._max_chunk_size):
                chunk = text[i : i + self._max_chunk_size]
                entities.extend(self._extract_from_chunk(chunk, source))
        else:
            entities.extend(self._extract_from_chunk(text, source))

        return entities

    def _extract_from_chunk(self, text: str, source: str) -> list[Entity]:
        """Extract entities from a single text chunk with timeout protection.

        Args:
            text: Text chunk to extract from
            source: Source description for context

        Returns:
            List of extracted entities
        """
        entities: list[Entity] = []

        for entity_type, patterns in self._patterns.items():
            for pattern in patterns:
                try:
                    # Using regex.finditer with timeout protection
                    # Pass timeout parameter to finditer() to prevent ReDoS
                    matches = pattern.finditer(text, timeout=self._regex_timeout)
                    for match in matches:
                        name = match.group(1).strip()

                        # Skip if too short or too long
                        if len(name) < 3 or len(name) > 50:
                            continue

                        # Skip stopwords
                        if name in self._stopwords.get(entity_type.value, set()):
                            continue

                        # Get context (50 chars before and after)
                        start = max(0, match.start() - 50)
                        end = min(len(text), match.end() + 50)
                        context = text[start:end].replace("\n", " ")

                        entities.append(
                            Entity(
                                name=name,
                                type=entity_type,
                                confidence=0.7,  # Pattern-based confidence
                                context=context,
                            )
                        )
                except regex.TimeoutError:
                    # Regex took too long - possible ReDoS attack or very complex input
                    logger.warning(
                        f"Regex timeout for {entity_type.value} pattern in {source}. "
                        f"Pattern: {pattern.pattern[:50]}... "
                        f"This may indicate a ReDoS attack or very complex input. "
                        f"Skipping this pattern for current chunk."
                    )
                    continue

        return entities

    def _extract_from_template(
        self,
        content: Any,
        entity_type: EntityType,
        patterns: list[str] | None = None,
        min_length: int = 3,
        max_length: int = 50,
    ) -> list[Entity]:
        """Generic extraction from structured template content.

        This method consolidates the common extraction logic used by
        _extract_books_from_template, _extract_tools_from_template, and
        _extract_people_from_template. It handles different content types
        and extracts entities from markdown lists.

        Args:
            content: Template content (string, list, or dict)
            entity_type: Type of entities to extract
            patterns: Optional regex patterns for validation
            min_length: Minimum entity name length
            max_length: Maximum entity name length

        Returns:
            List of extracted entities

        Examples:
            >>> # Extract books
            >>> entities = self._extract_from_template(
            ...     books_content,
            ...     EntityType.BOOK,
            ...     patterns=[r'^[\w\s:,\-\(\)]+$']
            ... )
            >>> # Extract tools
            >>> entities = self._extract_from_template(
            ...     tools_content,
            ...     EntityType.TOOL,
            ...     patterns=[r'^[\w\s\.\-]+$']
            ... )
        """
        entities: list[Entity] = []

        # Handle different content types
        if isinstance(content, dict):
            # Extract from dict values
            content = str(content.get("content", ""))
        elif isinstance(content, list):
            # Join list items
            content = "\n".join(str(item) for item in content)
        elif not isinstance(content, str):
            # Convert to string
            content = str(content)

        # Split into lines
        lines = content.split("\n")

        for line in lines:
            # Clean line
            line = line.strip()

            # Skip empty or markdown headers
            if not line or line.startswith("#"):
                continue

            # Remove markdown list markers
            line = re.sub(r"^[\-\*\+]\s+", "", line)
            line = re.sub(r"^\d+\.\s+", "", line)

            # Remove markdown bold/italic markers
            line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
            line = re.sub(r"\*([^*]+)\*", r"\1", line)

            # Remove quotes if present
            line = line.strip('"').strip("'")

            # For books, extract just the title (before " by ")
            if entity_type == EntityType.BOOK and " by " in line:
                parts = line.split(" by ", 1)
                title = parts[0].strip()
                author = parts[1].strip() if len(parts) > 1 else None
                line = title
                metadata = {"author": author} if author else {}
            else:
                metadata = {}

            # Remove table separators and clean
            line = line.strip("|").strip()

            # Validate length
            if len(line) < min_length or len(line) > max_length:
                continue

            # Apply custom patterns if provided
            if patterns:
                matches = False
                for pattern in patterns:
                    if re.match(pattern, line):
                        matches = True
                        break
                if not matches:
                    continue

            # Create entity
            if metadata:
                entity = Entity(
                    name=line,
                    type=entity_type,
                    confidence=0.9,  # High confidence from structured data
                    metadata=metadata,
                )
            else:
                entity = Entity(
                    name=line,
                    type=entity_type,
                    confidence=0.9,  # High confidence from structured data
                )
            entities.append(entity)

        return entities

    def _extract_books_from_template(self, books_content: Any) -> list[Entity]:
        """Extract books from books-mentioned template.

        Args:
            books_content: Content from books-mentioned template

        Returns:
            List of book entities
        """
        return self._extract_from_template(
            books_content,
            EntityType.BOOK,
            patterns=[r'^[\w\s:,\-\(\)\.\'\&]+$'],  # Book title pattern
            min_length=3,
            max_length=100,
        )

    def _extract_tools_from_template(self, tools_content: Any) -> list[Entity]:
        """Extract tools from tools-mentioned template.

        Args:
            tools_content: Content from tools-mentioned template

        Returns:
            List of tool entities
        """
        return self._extract_from_template(
            tools_content,
            EntityType.TOOL,
            patterns=[r'^[\w\s\.\-]+$'],  # Tool name pattern
            min_length=2,
            max_length=50,
        )

    def _extract_people_from_template(self, people_content: Any) -> list[Entity]:
        """Extract people from people-mentioned template.

        Args:
            people_content: Content from people-mentioned template

        Returns:
            List of person entities
        """
        return self._extract_from_template(
            people_content,
            EntityType.PERSON,
            patterns=[r'^[A-Z][\w\s\.\-]+$'],  # Person name pattern (capitalized)
            min_length=3,
            max_length=50,
        )

    def _filter_entities(self, entities: list[Entity]) -> list[Entity]:
        """Filter entities based on confidence threshold.

        Args:
            entities: List of entities to filter

        Returns:
            Filtered list of entities
        """
        return [e for e in entities if e.confidence >= self.config.min_confidence]

    def _deduplicate_entities(self, entities: list[Entity]) -> list[Entity]:
        """Remove duplicate entities (case-insensitive).

        Args:
            entities: List of entities to deduplicate

        Returns:
            Deduplicated list of entities
        """
        seen: set[Entity] = set()
        unique: list[Entity] = []

        for entity in entities:
            if entity not in seen:
                seen.add(entity)
                unique.append(entity)

        return unique

    def _limit_entities_per_type(self, entities: list[Entity]) -> list[Entity]:
        """Limit number of entities per type to avoid clutter.

        Args:
            entities: List of entities to limit

        Returns:
            Limited list of entities
        """
        by_type: dict[EntityType, list[Entity]] = {}

        for entity in entities:
            if entity.type not in by_type:
                by_type[entity.type] = []
            by_type[entity.type].append(entity)

        # Sort each type by confidence and take top N
        limited: list[Entity] = []
        for entity_type, type_entities in by_type.items():
            sorted_entities = sorted(type_entities, key=lambda e: e.confidence, reverse=True)
            limited.extend(sorted_entities[: self.config.max_entities_per_type])

        return limited

    def format_wikilinks(self, entities: list[Entity]) -> dict[str, list[str]]:
        """Format entities as wikilinks grouped by type.

        Args:
            entities: List of entities to format

        Returns:
            Dict mapping entity type to list of wikilinks

        Example:
            >>> generator = WikilinkGenerator()
            >>> entities = [
            ...     Entity(name="Cal Newport", type=EntityType.PERSON),
            ...     Entity(name="Deep Work", type=EntityType.BOOK)
            ... ]
            >>> wikilinks = generator.format_wikilinks(entities)
            >>> wikilinks["person"]
            ['[[Cal Newport]]']
        """
        wikilinks: dict[str, list[str]] = {
            "person": [],
            "book": [],
            "tool": [],
            "concept": [],
            "episode": [],
        }

        for entity in entities:
            wikilink = entity.to_wikilink(style=self.config.style)
            wikilinks[entity.type.value].append(wikilink)

        return wikilinks

    def generate_related_section(
        self, entities: list[Entity], title: str = "Related Notes"
    ) -> str:
        """Generate a markdown section with related notes (wikilinks).

        Args:
            entities: List of entities to include
            title: Section title

        Returns:
            Markdown section with wikilinks

        Example:
            >>> generator = WikilinkGenerator()
            >>> entities = [
            ...     Entity(name="Cal Newport", type=EntityType.PERSON),
            ...     Entity(name="Deep Work", type=EntityType.BOOK)
            ... ]
            >>> section = generator.generate_related_section(entities)
            >>> "## Related Notes" in section
            True
        """
        if not entities:
            return ""

        wikilinks = self.format_wikilinks(entities)

        sections = [f"## {title}\n"]

        # Add each type if it has entities
        type_names = {
            "person": "People",
            "book": "Books",
            "tool": "Tools",
            "concept": "Concepts",
            "episode": "Episodes",
        }

        for entity_type, links in wikilinks.items():
            if links:
                sections.append(f"### {type_names[entity_type]}\n")
                for link in links:
                    sections.append(f"- {link}\n")
                sections.append("\n")

        return "".join(sections)
