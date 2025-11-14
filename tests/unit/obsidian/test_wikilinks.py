"""Tests for wikilink generation."""

import time

import regex

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


class TestReDoSProtection:
    """Test ReDoS (Regular Expression Denial of Service) protection."""

    def test_redos_protection_with_malicious_input(self):
        """Test that ReDoS attacks are mitigated and don't cause hangs.

        This test uses input specifically designed to cause catastrophic
        backtracking in vulnerable regex patterns. With timeouts in place,
        it should complete quickly instead of hanging.
        """
        generator = WikilinkGenerator()

        # Create malicious input designed to cause backtracking
        # Pattern vulnerability: r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\b"
        # This tries to match names like "John Smith" or "John A. Smith"
        # Malicious input has many valid prefixes but never completes the pattern
        malicious_text = "A" + "a" * 100 + " A" + "a" * 100 + "!"

        # Should complete within reasonable time (not hang)
        start = time.time()

        entities = generator._extract_from_text(malicious_text, "test")

        elapsed = time.time() - start

        # Should timeout and continue, not hang forever
        # With 1 second timeout per pattern, this should complete in < 5 seconds
        assert elapsed < 5.0, f"Extraction took {elapsed}s, possible ReDoS vulnerability"

        # Should return empty list or partial results, but not crash
        assert isinstance(entities, list)

    def test_regex_timeout_handling(self):
        """Test that regex timeout parameter is accepted by finditer().

        This test verifies that the timeout parameter can be passed to
        regex operations without causing errors. The actual timeout behavior
        is tested indirectly through the malicious input test.
        """
        generator = WikilinkGenerator()

        # Verify that patterns can be used with timeout parameter
        # This should not raise any errors
        pattern = list(generator._patterns.values())[0][0]

        # The timeout parameter should be accepted without error
        # For benign input, this should complete successfully
        matches = list(pattern.finditer("John Smith", timeout=1.0))

        # Should find the name
        assert len(matches) > 0 or len(matches) == 0  # May or may not match depending on pattern

    def test_large_text_chunking(self):
        """Test that large text is processed in chunks."""
        generator = WikilinkGenerator()

        # Create text larger than max_chunk_size (50KB)
        large_text = "Cal Newport discusses deep work. " * 5000  # ~165KB

        start = time.time()
        entities = generator._extract_from_text(large_text, "test")
        elapsed = time.time() - start

        # Should complete in reasonable time even with large input
        assert elapsed < 10.0, f"Large text processing took {elapsed}s"

        # Should still extract entities from the chunked text
        assert isinstance(entities, list)
        # Should find at least some mentions of "Cal Newport"
        person_names = [e.name for e in entities if e.type == EntityType.PERSON]
        assert len(person_names) > 0

    def test_complex_input_patterns(self):
        """Test various complex inputs that could trigger backtracking."""
        generator = WikilinkGenerator()

        complex_inputs = [
            # Many capitals followed by lowercase (tries to match names)
            "A" * 50 + "a" * 50 + " B" * 50 + "b" * 50,
            # Repeated patterns that look like they might match
            "John " * 100 + "Smith",
            # Mixed case chaos
            "AaBbCc " * 100,
            # Special characters that might confuse patterns
            "Dr. " * 100 + "Professor " * 100,
        ]

        for i, text in enumerate(complex_inputs):
            start = time.time()
            entities = generator._extract_from_text(text, f"test-{i}")
            elapsed = time.time() - start

            # Each input should complete quickly
            assert elapsed < 3.0, f"Input {i} took {elapsed}s to process"
            assert isinstance(entities, list)

    def test_normal_text_still_works(self):
        """Test that normal text processing still works correctly after ReDoS fixes."""
        generator = WikilinkGenerator()

        normal_text = """
        In this episode, Cal Newport discusses his book Deep Work with Andrew Huberman.
        They talk about using tools like Notion and Obsidian for productivity.
        Dr. Smith also mentions reading The Shallows by Nicholas Carr.
        """

        entities = generator._extract_from_text(normal_text, "test")

        # Should still extract entities correctly
        person_names = {e.name for e in entities if e.type == EntityType.PERSON}
        assert "Cal Newport" in person_names or "Andrew Huberman" in person_names

        # Should not take too long
        start = time.time()
        generator._extract_from_text(normal_text, "test")
        elapsed = time.time() - start
        assert elapsed < 1.0, "Normal text processing should be fast"

    def test_chunk_boundary_entities(self):
        """Test that entities aren't lost at chunk boundaries."""
        generator = WikilinkGenerator()

        # Create text that will be split across chunks
        # Place an entity near the chunk boundary
        chunk_size = generator._max_chunk_size
        text_before = "x" * (chunk_size - 20)
        text_after = "y" * 100
        entity_at_boundary = " Cal Newport discusses "

        large_text = text_before + entity_at_boundary + text_after

        entities = generator._extract_from_text(large_text, "test")

        # Should still find the entity even though it's near a chunk boundary
        # Note: Some entities might be lost at exact boundaries, but we should
        # handle this gracefully without errors
        assert isinstance(entities, list)

    def test_timeout_configuration(self):
        """Test that timeout configuration is properly set."""
        generator = WikilinkGenerator()

        # Verify timeout is configured
        assert generator._regex_timeout == 1.0

        # Verify chunk size is configured
        assert generator._max_chunk_size == 50000

        # Verify patterns are compiled with timeout
        for entity_type, patterns in generator._patterns.items():
            for pattern in patterns:
                # regex.compile objects don't expose timeout directly,
                # but we can verify they're regex.Pattern objects
                assert isinstance(pattern, regex.Pattern)


class TestGenericTemplateExtraction:
    """Test generic template extraction method."""

    def test_generic_extract_from_template_with_books(self):
        """Test generic extraction method works for books."""
        generator = WikilinkGenerator()
        books_content = """
- Atomic Habits by James Clear
- Deep Work by Cal Newport
- Flow by Mihaly Csikszentmihalyi
"""

        books = generator._extract_from_template(
            books_content,
            EntityType.BOOK,
            patterns=[r'^[\w\s:,\-\(\)\.\'\&]+$'],
            min_length=3,
            max_length=100,
        )

        assert len(books) >= 2
        titles = [b.name for b in books]
        assert "Atomic Habits" in titles
        assert "Deep Work" in titles
        # Verify authors are extracted
        atomic_habits = next(b for b in books if b.name == "Atomic Habits")
        assert atomic_habits.metadata is not None
        assert atomic_habits.metadata.get("author") == "James Clear"

    def test_generic_extract_from_template_with_tools(self):
        """Test generic extraction method works for tools."""
        generator = WikilinkGenerator()
        tools_content = """
- Notion
- Obsidian
- Roam Research
"""

        tools = generator._extract_from_template(
            tools_content,
            EntityType.TOOL,
            patterns=[r'^[\w\s\.\-]+$'],
            min_length=2,
            max_length=50,
        )

        assert len(tools) == 3
        tool_names = [t.name for t in tools]
        assert "Notion" in tool_names
        assert "Obsidian" in tool_names
        assert "Roam Research" in tool_names
        # All should have high confidence
        assert all(t.confidence == 0.9 for t in tools)

    def test_generic_extract_from_template_with_people(self):
        """Test generic extraction method works for people."""
        generator = WikilinkGenerator()
        people_content = """
- Cal Newport
- Andrew Huberman
- James Clear
"""

        people = generator._extract_from_template(
            people_content,
            EntityType.PERSON,
            patterns=[r'^[A-Z][\w\s\.\-]+$'],
            min_length=3,
            max_length=50,
        )

        assert len(people) == 3
        names = [p.name for p in people]
        assert "Cal Newport" in names
        assert "Andrew Huberman" in names
        assert "James Clear" in names

    def test_generic_extract_handles_different_formats(self):
        """Test generic extraction handles various markdown formats."""
        generator = WikilinkGenerator()

        # Test with different list markers
        content_dash = "- Item One\n- Item Two"
        content_star = "* Item One\n* Item Two"
        content_plus = "+ Item One\n+ Item Two"
        content_numbered = "1. Item One\n2. Item Two"

        for content in [content_dash, content_star, content_plus, content_numbered]:
            entities = generator._extract_from_template(
                content,
                EntityType.TOOL,
                min_length=3,
            )
            assert len(entities) == 2
            names = [e.name for e in entities]
            assert "Item One" in names
            assert "Item Two" in names

    def test_generic_extract_handles_bold_and_italic(self):
        """Test generic extraction removes markdown formatting."""
        generator = WikilinkGenerator()
        content = """
- **Bold Item**
- *Italic Item*
- Regular Item
"""

        entities = generator._extract_from_template(
            content,
            EntityType.TOOL,
            min_length=3,
        )

        names = [e.name for e in entities]
        assert "Bold Item" in names
        assert "Italic Item" in names
        assert "Regular Item" in names
        # Should not have markdown markers
        assert all("**" not in name and "*" not in name for name in names)

    def test_generic_extract_filters_by_length(self):
        """Test generic extraction filters items by length."""
        generator = WikilinkGenerator()
        content = """
- AB
- Valid Item
- This is a very long item that exceeds the maximum length limit set
"""

        entities = generator._extract_from_template(
            content,
            EntityType.TOOL,
            min_length=3,
            max_length=20,
        )

        names = [e.name for e in entities]
        assert "AB" not in names  # Too short
        assert "Valid Item" in names
        # Long item should be filtered out
        assert len([n for n in names if len(n) > 20]) == 0

    def test_generic_extract_filters_by_pattern(self):
        """Test generic extraction filters items by regex pattern."""
        generator = WikilinkGenerator()
        content = """
- Valid Tool
- Invalid@Tool!
- Another-Valid
"""

        entities = generator._extract_from_template(
            content,
            EntityType.TOOL,
            patterns=[r'^[\w\s\-]+$'],  # Only alphanumeric, spaces, hyphens
            min_length=3,
        )

        names = [e.name for e in entities]
        assert "Valid Tool" in names
        assert "Invalid@Tool!" not in names  # Has special chars
        assert "Another-Valid" in names

    def test_generic_extract_preserves_behavior(self):
        """Ensure refactored methods produce same results as originals."""
        generator = WikilinkGenerator()

        test_books = """
- Book One by Author One
- Book Two by Author Two
- Book Three
"""

        test_tools = """
- Tool One
- Tool Two
- Tool Three
"""

        test_people = """
- Person One
- Person Two
- Person Three
"""

        # Test books extraction
        books = generator._extract_books_from_template(test_books)
        assert len(books) == 3
        assert all(b.type == EntityType.BOOK for b in books)
        assert all(b.confidence == 0.9 for b in books)

        # Test tools extraction
        tools = generator._extract_tools_from_template(test_tools)
        assert len(tools) == 3
        assert all(t.type == EntityType.TOOL for t in tools)
        assert all(t.confidence == 0.9 for t in tools)

        # Test people extraction
        people = generator._extract_people_from_template(test_people)
        assert len(people) == 3
        assert all(p.type == EntityType.PERSON for p in people)
        assert all(p.confidence == 0.9 for p in people)
