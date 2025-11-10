"""Wikilink generation for Obsidian integration.

This module extracts entities from podcast transcripts and extracted content,
then converts them to Obsidian wikilinks for cross-referencing.
"""

import re
from typing import Any

from inkwell.obsidian.models import Entity, EntityType, WikilinkConfig, WikilinkStyle


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

        # Pattern regexes for entity extraction
        self._patterns = {
            EntityType.PERSON: [
                # Full names with title (Dr., Prof., etc.)
                r"\b(?:Dr\.?|Prof\.?|Mr\.?|Ms\.?|Mrs\.?)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
                # Full names (First Last, possibly with middle initial)
                r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\b",
                # Names in possessive form
                r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)'s\b",
            ],
            EntityType.BOOK: [
                # Books in quotes
                r'"([A-Z][^"]{2,})"',
                r"'([A-Z][^']{2,})'",
                # "Book: Title" or "his book Title"
                r"\b(?:book|titled)\s+['\"]?([A-Z][^'\"]{2,})['\"]?",
            ],
            EntityType.TOOL: [
                # Software/tools (capitalized product names)
                r"\b([A-Z][a-z]*(?:[A-Z][a-z]*)+)\b",  # CamelCase
                # Tools with specific markers
                r"\b(?:using|via|with|tool)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
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

        Args:
            text: Text to extract from
            source: Source description for context

        Returns:
            List of extracted entities
        """
        entities: list[Entity] = []

        for entity_type, patterns in self._patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text)
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

        return entities

    def _extract_books_from_template(self, books_content: Any) -> list[Entity]:
        """Extract books from books-mentioned template.

        Args:
            books_content: Content from books-mentioned template

        Returns:
            List of book entities
        """
        entities: list[Entity] = []

        if isinstance(books_content, str):
            # Parse markdown list format
            lines = books_content.split("\n")
            for line in lines:
                # Match patterns like "- Book Title by Author" or "- **Book Title**"
                # First try to match with markdown bold: - **Title** by Author
                match = re.match(r"^\s*[-*]\s+\*\*([^*]+)\*\*(?:\s+by\s+(.+))?", line)
                if match:
                    title = match.group(1).strip()
                    author = match.group(2).strip() if match.group(2) else None
                else:
                    # Try to match without markdown: - Title by Author
                    match = re.match(r"^\s*[-*]\s+([^-*\n]+?)(?:\s+by\s+(.+))?$", line)
                    if match:
                        title = match.group(1).strip()
                        author = match.group(2).strip() if match.group(2) else None
                    else:
                        continue

                if len(title) > 3:
                    metadata = {"author": author} if author else {}
                    entities.append(
                        Entity(
                            name=title,
                            type=EntityType.BOOK,
                            confidence=0.9,  # High confidence from structured template
                            context=line.strip(),
                            metadata=metadata,
                        )
                    )

        return entities

    def _extract_tools_from_template(self, tools_content: Any) -> list[Entity]:
        """Extract tools from tools-mentioned template.

        Args:
            tools_content: Content from tools-mentioned template

        Returns:
            List of tool entities
        """
        entities: list[Entity] = []

        if isinstance(tools_content, str):
            # Parse markdown list or table format
            lines = tools_content.split("\n")
            for line in lines:
                # Match list items or table rows
                match = re.match(r"^\s*[-*|]\s*([A-Z][^-*|\n]+?)(?:\s*[-|]|$)", line)
                if match:
                    tool_name = match.group(1).strip()

                    if len(tool_name) > 2 and len(tool_name) < 30:
                        entities.append(
                            Entity(
                                name=tool_name,
                                type=EntityType.TOOL,
                                confidence=0.9,
                                context=line.strip(),
                            )
                        )

        return entities

    def _extract_people_from_template(self, people_content: Any) -> list[Entity]:
        """Extract people from people-mentioned template.

        Args:
            people_content: Content from people-mentioned template

        Returns:
            List of person entities
        """
        entities: list[Entity] = []

        if isinstance(people_content, str):
            # Parse markdown list format
            lines = people_content.split("\n")
            for line in lines:
                # Match patterns like "- Person Name" or "- **Person Name**"
                match = re.match(r"^\s*[-*]\s+\*?\*?([A-Z][^*\n]+?)\*?\*?(?:\s*[-:]|$)", line)
                if match:
                    name = match.group(1).strip()

                    if len(name) > 3 and len(name) < 40:
                        entities.append(
                            Entity(
                                name=name,
                                type=EntityType.PERSON,
                                confidence=0.9,
                                context=line.strip(),
                            )
                        )

        return entities

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

    def apply_wikilinks_to_markdown(
        self, markdown: str, entities: list[Entity], preserve_existing: bool = True
    ) -> str:
        """Apply wikilinks to markdown content by replacing entity mentions.

        Args:
            markdown: Markdown content to update
            entities: List of entities to link
            preserve_existing: Don't link entities that are already in wikilinks

        Returns:
            Updated markdown with wikilinks

        Example:
            >>> generator = WikilinkGenerator()
            >>> markdown = "Cal Newport discusses deep work."
            >>> entities = [Entity(name="Cal Newport", type=EntityType.PERSON)]
            >>> result = generator.apply_wikilinks_to_markdown(markdown, entities)
            >>> "[[Cal Newport]]" in result
            True
        """
        if not entities:
            return markdown

        # Sort entities by name length (longest first) to avoid partial replacements
        sorted_entities = sorted(entities, key=lambda e: len(e.name), reverse=True)

        result = markdown

        for entity in sorted_entities:
            # Skip if confidence too low
            if entity.confidence < self.config.min_confidence:
                continue

            wikilink = entity.to_wikilink(style=self.config.style)

            # Check if already in wikilink format
            if preserve_existing and f"[[{entity.name}" in result:
                continue

            # Replace entity mentions with wikilinks
            # Use word boundaries to avoid partial replacements
            pattern = r"\b" + re.escape(entity.name) + r"\b"
            result = re.sub(pattern, wikilink, result, count=3)  # Limit to first 3 occurrences

        return result

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
