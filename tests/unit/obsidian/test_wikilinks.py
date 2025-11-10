"""Tests for wikilink generation."""

import pytest

from inkwell.obsidian.models import Entity, EntityType, WikilinkConfig, WikilinkStyle
from inkwell.obsidian.wikilinks import WikilinkGenerator


class TestEntity:
    """Test Entity model."""

    def test_entity_creation(self):
        """Test creating an entity."""
        entity = Entity(name="Cal Newport", type=EntityType.PERSON)

        assert entity.name == "Cal Newport"
        assert entity.type == EntityType.PERSON
        assert entity.confidence == 1.0  # default

    def test_entity_to_wikilink_simple(self):
        """Test converting entity to simple wikilink."""
        entity = Entity(name="Cal Newport", type=EntityType.PERSON)
        wikilink = entity.to_wikilink()

        assert wikilink == "[[Cal Newport]]"

    def test_entity_to_wikilink_prefixed(self):
        """Test converting entity to prefixed wikilink."""
        entity = Entity(name="Cal Newport", type=EntityType.PERSON)
        wikilink = entity.to_wikilink(style=WikilinkStyle.PREFIXED)

        assert wikilink == "[[Person - Cal Newport]]"

    def test_entity_to_wikilink_with_display_text(self):
        """Test converting entity to wikilink with custom display text."""
        entity = Entity(name="Cal Newport", type=EntityType.PERSON)
        wikilink = entity.to_wikilink(display_text="Cal")

        assert wikilink == "[[Cal Newport|Cal]]"

    def test_entity_equality(self):
        """Test entity equality (case-insensitive)."""
        entity1 = Entity(name="Cal Newport", type=EntityType.PERSON)
        entity2 = Entity(name="cal newport", type=EntityType.PERSON)
        entity3 = Entity(name="Cal Newport", type=EntityType.BOOK)

        assert entity1 == entity2  # Same name (case-insensitive), same type
        assert entity1 != entity3  # Same name, different type

    def test_entity_hashable(self):
        """Test that entities can be added to sets."""
        entity1 = Entity(name="Cal Newport", type=EntityType.PERSON)
        entity2 = Entity(name="cal newport", type=EntityType.PERSON)

        entities = {entity1, entity2}
        assert len(entities) == 1  # Deduped


class TestWikilinkGenerator:
    """Test WikilinkGenerator."""

    def test_generator_creation(self):
        """Test creating a generator."""
        generator = WikilinkGenerator()

        assert generator.config.enabled is True
        assert generator.config.style == WikilinkStyle.SIMPLE

    def test_generator_with_custom_config(self):
        """Test creating generator with custom config."""
        config = WikilinkConfig(
            style=WikilinkStyle.PREFIXED,
            min_confidence=0.8,
        )
        generator = WikilinkGenerator(config=config)

        assert generator.config.style == WikilinkStyle.PREFIXED
        assert generator.config.min_confidence == 0.8

    def test_extract_people_from_text(self):
        """Test extracting people from text."""
        generator = WikilinkGenerator()
        text = "Cal Newport discusses deep work with Andrew Huberman on his podcast."

        entities = generator._extract_from_text(text, "test")

        # Should find at least the full names
        person_entities = [e for e in entities if e.type == EntityType.PERSON]
        names = [e.name for e in person_entities]

        assert "Cal Newport" in names
        assert "Andrew Huberman" in names

    def test_extract_books_from_template(self):
        """Test extracting books from structured template."""
        generator = WikilinkGenerator()
        books_content = """
- **Deep Work** by Cal Newport
- The Shallows by Nicholas Carr
- Flow by Mihaly Csikszentmihalyi
"""

        entities = generator._extract_books_from_template(books_content)

        assert len(entities) >= 2
        titles = [e.name for e in entities]
        assert "Deep Work" in titles
        assert "The Shallows" in titles

    def test_extract_tools_from_template(self):
        """Test extracting tools from structured template."""
        generator = WikilinkGenerator()
        tools_content = """
- Notion
- Obsidian
- Roam Research
"""

        entities = generator._extract_tools_from_template(tools_content)

        assert len(entities) >= 2
        tools = [e.name for e in entities]
        assert "Notion" in tools or "Obsidian" in tools

    def test_filter_entities_by_confidence(self):
        """Test filtering entities by confidence threshold."""
        config = WikilinkConfig(min_confidence=0.8)
        generator = WikilinkGenerator(config=config)

        entities = [
            Entity(name="High Confidence", type=EntityType.PERSON, confidence=0.9),
            Entity(name="Low Confidence", type=EntityType.PERSON, confidence=0.6),
            Entity(name="Medium Confidence", type=EntityType.PERSON, confidence=0.75),
        ]

        filtered = generator._filter_entities(entities)

        assert len(filtered) == 1
        assert filtered[0].name == "High Confidence"

    def test_deduplicate_entities(self):
        """Test deduplicating entities."""
        generator = WikilinkGenerator()

        entities = [
            Entity(name="Cal Newport", type=EntityType.PERSON),
            Entity(name="cal newport", type=EntityType.PERSON),  # Duplicate (case)
            Entity(name="Cal Newport", type=EntityType.BOOK),  # Different type, not dup
            Entity(name="Deep Work", type=EntityType.BOOK),
        ]

        deduped = generator._deduplicate_entities(entities)

        assert len(deduped) == 3  # 2 Cal Newport (different types) + 1 Deep Work

    def test_format_wikilinks(self):
        """Test formatting entities as wikilinks."""
        generator = WikilinkGenerator()

        entities = [
            Entity(name="Cal Newport", type=EntityType.PERSON),
            Entity(name="Andrew Huberman", type=EntityType.PERSON),
            Entity(name="Deep Work", type=EntityType.BOOK),
            Entity(name="Notion", type=EntityType.TOOL),
        ]

        wikilinks = generator.format_wikilinks(entities)

        assert len(wikilinks["person"]) == 2
        assert "[[Cal Newport]]" in wikilinks["person"]
        assert "[[Andrew Huberman]]" in wikilinks["person"]
        assert len(wikilinks["book"]) == 1
        assert "[[Deep Work]]" in wikilinks["book"]
        assert len(wikilinks["tool"]) == 1
        assert "[[Notion]]" in wikilinks["tool"]

    def test_apply_wikilinks_to_markdown(self):
        """Test applying wikilinks to markdown content."""
        generator = WikilinkGenerator()

        markdown = "Cal Newport discusses Deep Work and productivity."
        entities = [
            Entity(name="Cal Newport", type=EntityType.PERSON, confidence=0.9),
            Entity(name="Deep Work", type=EntityType.BOOK, confidence=0.9),
        ]

        result = generator.apply_wikilinks_to_markdown(markdown, entities)

        assert "[[Cal Newport]]" in result
        assert "[[Deep Work]]" in result

    def test_apply_wikilinks_preserves_existing(self):
        """Test that existing wikilinks are preserved."""
        generator = WikilinkGenerator()

        markdown = "[[Cal Newport]] discusses Deep Work."
        entities = [
            Entity(name="Cal Newport", type=EntityType.PERSON, confidence=0.9),
        ]

        result = generator.apply_wikilinks_to_markdown(markdown, entities, preserve_existing=True)

        # Should not double-link
        assert result.count("[[Cal Newport]]") == 1

    def test_generate_related_section(self):
        """Test generating related notes section."""
        generator = WikilinkGenerator()

        entities = [
            Entity(name="Cal Newport", type=EntityType.PERSON),
            Entity(name="Andrew Huberman", type=EntityType.PERSON),
            Entity(name="Deep Work", type=EntityType.BOOK),
            Entity(name="Notion", type=EntityType.TOOL),
        ]

        section = generator.generate_related_section(entities)

        assert "## Related Notes" in section
        assert "### People" in section
        assert "### Books" in section
        assert "### Tools" in section
        assert "[[Cal Newport]]" in section
        assert "[[Deep Work]]" in section

    def test_extract_entities_end_to_end(self):
        """Test complete entity extraction flow."""
        generator = WikilinkGenerator()

        transcript = """
        In this episode, Cal Newport discusses his book Deep Work.
        He talks about using tools like Notion and Obsidian for productivity.
        Andrew Huberman also joins to discuss focus strategies.
        """

        extraction_results = {
            "summary": "Episode about deep work and focus.",
            "books-mentioned": "- Deep Work by Cal Newport\n- The Shallows",
            "tools-mentioned": "- Notion\n- Obsidian\n- Roam Research",
        }

        entities = generator.extract_entities(
            transcript=transcript,
            extraction_results=extraction_results,
        )

        # Should have extracted various entities
        assert len(entities) > 0

        # Check we have different types
        types_found = {e.type for e in entities}
        assert EntityType.PERSON in types_found
        assert EntityType.BOOK in types_found
        assert EntityType.TOOL in types_found

        # Check specific entities
        names = {e.name for e in entities}
        assert "Cal Newport" in names or "Deep Work" in names or "Notion" in names

    def test_limit_entities_per_type(self):
        """Test limiting number of entities per type."""
        config = WikilinkConfig(max_entities_per_type=2)
        generator = WikilinkGenerator(config=config)

        entities = [
            Entity(name=f"Person {i}", type=EntityType.PERSON, confidence=0.9 - i * 0.1)
            for i in range(5)
        ]

        limited = generator._limit_entities_per_type(entities)

        assert len(limited) <= 2
        # Should keep highest confidence ones
        assert limited[0].name == "Person 0"
        assert limited[1].name == "Person 1"
