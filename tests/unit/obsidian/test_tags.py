"""Tests for tag generation system."""

import pytest

from inkwell.obsidian.models import Entity, EntityType
from inkwell.obsidian.tag_models import Tag, TagCategory, TagConfig, TagStyle
from inkwell.obsidian.tags import TagGenerator


class TestTag:
    """Test Tag model."""

    def test_tag_creation(self):
        """Test basic tag creation."""
        tag = Tag(
            name="deep-work",
            category=TagCategory.CONCEPT,
            confidence=0.9,
            source="llm",
        )

        assert tag.name == "deep-work"
        assert tag.category == TagCategory.CONCEPT
        assert tag.confidence == 0.9
        assert tag.source == "llm"

    def test_tag_normalization_lowercase(self):
        """Test tag name normalization to lowercase."""
        tag = Tag(name="Deep Work", category=TagCategory.CONCEPT)
        assert tag.name == "deep-work"

    def test_tag_normalization_spaces(self):
        """Test space to hyphen conversion."""
        tag = Tag(name="artificial intelligence", category=TagCategory.TOPIC)
        assert tag.name == "artificial-intelligence"

    def test_tag_normalization_special_chars(self):
        """Test removal of special characters."""
        tag = Tag(name="AI & ML!", category=TagCategory.TOPIC)
        assert tag.name == "ai-ml"

    def test_tag_normalization_multiple_hyphens(self):
        """Test collapsing multiple hyphens."""
        tag = Tag(name="deep---work", category=TagCategory.CONCEPT)
        assert tag.name == "deep-work"

    def test_tag_normalization_leading_trailing(self):
        """Test removal of leading/trailing hyphens."""
        tag = Tag(name="-deep-work-", category=TagCategory.CONCEPT)
        assert tag.name == "deep-work"

    def test_tag_to_obsidian_hierarchical(self):
        """Test hierarchical tag formatting."""
        tag = Tag(name="ai", category=TagCategory.TOPIC)
        assert tag.to_obsidian_tag(TagStyle.HIERARCHICAL) == "#topic/ai"

    def test_tag_to_obsidian_flat(self):
        """Test flat tag formatting."""
        tag = Tag(name="ai", category=TagCategory.TOPIC)
        assert tag.to_obsidian_tag(TagStyle.FLAT) == "#ai"

    def test_tag_to_obsidian_no_category(self):
        """Test tag without category (always flat)."""
        tag = Tag(name="podcast", category=None)
        assert tag.to_obsidian_tag(TagStyle.HIERARCHICAL) == "#podcast"
        assert tag.to_obsidian_tag(TagStyle.FLAT) == "#podcast"

    def test_tag_equality(self):
        """Test case-insensitive equality."""
        tag1 = Tag(name="ai", category=TagCategory.TOPIC)
        tag2 = Tag(name="AI", category=TagCategory.TOPIC)
        tag3 = Tag(name="ai", category=TagCategory.CONCEPT)

        assert tag1 == tag2  # Same name and category
        assert tag1 != tag3  # Different category

    def test_tag_hashable(self):
        """Test tags can be used in sets for deduplication."""
        tag1 = Tag(name="ai", category=TagCategory.TOPIC)
        tag2 = Tag(name="AI", category=TagCategory.TOPIC)  # Duplicate
        tag3 = Tag(name="ai", category=TagCategory.CONCEPT)  # Different category

        tags_set = {tag1, tag2, tag3}
        assert len(tags_set) == 2  # tag1 and tag2 are duplicates


class TestTagGenerator:
    """Test TagGenerator class."""

    def test_generator_creation(self):
        """Test basic generator creation."""
        generator = TagGenerator()
        assert generator.config.enabled is True
        assert generator.config.max_tags == 7

    def test_generator_with_custom_config(self):
        """Test generator with custom configuration."""
        config = TagConfig(
            max_tags=5,
            min_confidence=0.8,
            style=TagStyle.FLAT,
        )
        generator = TagGenerator(config=config)

        assert generator.config.max_tags == 5
        assert generator.config.min_confidence == 0.8
        assert generator.config.style == TagStyle.FLAT

    def test_tags_from_metadata(self):
        """Test tag generation from metadata."""
        generator = TagGenerator()
        metadata = {
            "podcast_name": "Lex Fridman Podcast",
            "episode_title": "AI and the Future",
        }

        tags = generator._tags_from_metadata(metadata)

        # Should have podcast name + base tags
        tag_names = [t.name for t in tags]
        assert "lex-fridman-podcast" in tag_names
        assert "podcast" in tag_names
        assert "inkwell" in tag_names

    def test_tags_from_entities(self):
        """Test tag generation from entities."""
        generator = TagGenerator()
        entities = [
            Entity(name="Cal Newport", type=EntityType.PERSON, confidence=0.9),
            Entity(name="Deep Work", type=EntityType.BOOK, confidence=0.85),
            Entity(name="Notion", type=EntityType.TOOL, confidence=0.8),
            Entity(name="Focus", type=EntityType.CONCEPT, confidence=0.7),  # Too low
        ]

        tags = generator._tags_from_entities(entities)

        # Should create tags for high-confidence entities (>=0.8)
        tag_names = [t.name for t in tags]
        assert "cal-newport" in tag_names
        assert "deep-work" in tag_names
        assert "notion" in tag_names
        assert "focus" not in tag_names  # Confidence too low

    def test_tags_from_entities_categories(self):
        """Test entity to tag category mapping."""
        generator = TagGenerator()
        entities = [
            Entity(name="Cal Newport", type=EntityType.PERSON, confidence=0.9),
            Entity(name="Deep Work", type=EntityType.BOOK, confidence=0.9),
            Entity(name="Obsidian", type=EntityType.TOOL, confidence=0.9),
            Entity(name="Flow State", type=EntityType.CONCEPT, confidence=0.9),
        ]

        tags = generator._tags_from_entities(entities)

        # Verify categories
        tag_dict = {t.name: t.category for t in tags}
        assert tag_dict["cal-newport"] == TagCategory.PERSON
        assert tag_dict["deep-work"] == TagCategory.BOOK
        assert tag_dict["obsidian"] == TagCategory.TOOL
        assert tag_dict["flow-state"] == TagCategory.CONCEPT

    def test_deduplicate_tags(self):
        """Test tag deduplication."""
        generator = TagGenerator()
        tags = [
            Tag(name="ai", category=TagCategory.TOPIC, confidence=0.9),
            Tag(name="AI", category=TagCategory.TOPIC, confidence=0.8),  # Duplicate
            Tag(name="machine-learning", category=TagCategory.TOPIC, confidence=0.85),
        ]

        deduped = generator._deduplicate_tags(tags)

        assert len(deduped) == 2
        tag_names = [t.name for t in deduped]
        assert "ai" in tag_names
        assert "machine-learning" in tag_names

    def test_filter_tags_by_confidence(self):
        """Test filtering tags by confidence threshold."""
        config = TagConfig(min_confidence=0.7)
        generator = TagGenerator(config=config)

        tags = [
            Tag(name="ai", category=TagCategory.TOPIC, confidence=0.9),
            Tag(name="ml", category=TagCategory.TOPIC, confidence=0.7),
            Tag(name="data", category=TagCategory.TOPIC, confidence=0.6),  # Too low
        ]

        filtered = generator._filter_tags(tags)

        assert len(filtered) == 2
        tag_names = [t.name for t in filtered]
        assert "ai" in tag_names
        assert "ml" in tag_names
        assert "data" not in tag_names

    def test_limit_tags(self):
        """Test limiting number of tags."""
        config = TagConfig(max_tags=3)
        generator = TagGenerator(config=config)

        tags = [
            Tag(name="ai", category=TagCategory.TOPIC, confidence=0.9),
            Tag(name="ml", category=TagCategory.TOPIC, confidence=0.85),
            Tag(name="data", category=TagCategory.TOPIC, confidence=0.8),
            Tag(name="python", category=TagCategory.TOOL, confidence=0.75),
            Tag(name="tech", category=TagCategory.INDUSTRY, confidence=0.7),
        ]

        limited = generator._limit_tags(tags)

        assert len(limited) == 3
        # Should keep top 3 by confidence
        tag_names = [t.name for t in limited]
        assert "ai" in tag_names
        assert "ml" in tag_names
        assert "data" in tag_names

    def test_format_tags_hierarchical(self):
        """Test formatting tags as hierarchical Obsidian tags."""
        config = TagConfig(style=TagStyle.HIERARCHICAL)
        generator = TagGenerator(config=config)

        tags = [
            Tag(name="ai", category=TagCategory.TOPIC),
            Tag(name="cal-newport", category=TagCategory.PERSON),
            Tag(name="podcast", category=None),
        ]

        formatted = generator.format_tags(tags)

        assert "#topic/ai" in formatted
        assert "#person/cal-newport" in formatted
        assert "#podcast" in formatted

    def test_format_tags_flat(self):
        """Test formatting tags as flat Obsidian tags."""
        config = TagConfig(style=TagStyle.FLAT)
        generator = TagGenerator(config=config)

        tags = [
            Tag(name="ai", category=TagCategory.TOPIC),
            Tag(name="cal-newport", category=TagCategory.PERSON),
            Tag(name="podcast", category=None),
        ]

        formatted = generator.format_tags(tags)

        assert "#ai" in formatted
        assert "#cal-newport" in formatted
        assert "#podcast" in formatted

    def test_format_frontmatter_tags_hierarchical(self):
        """Test formatting tags for YAML frontmatter (hierarchical)."""
        config = TagConfig(style=TagStyle.HIERARCHICAL)
        generator = TagGenerator(config=config)

        tags = [
            Tag(name="ai", category=TagCategory.TOPIC),
            Tag(name="cal-newport", category=TagCategory.PERSON),
            Tag(name="podcast", category=None),
        ]

        formatted = generator.format_frontmatter_tags(tags)

        assert "topic/ai" in formatted
        assert "person/cal-newport" in formatted
        assert "podcast" in formatted
        # Should not have # prefix
        assert all(not t.startswith("#") for t in formatted)

    def test_format_frontmatter_tags_flat(self):
        """Test formatting tags for YAML frontmatter (flat)."""
        config = TagConfig(style=TagStyle.FLAT)
        generator = TagGenerator(config=config)

        tags = [
            Tag(name="ai", category=TagCategory.TOPIC),
            Tag(name="podcast", category=None),
        ]

        formatted = generator.format_frontmatter_tags(tags)

        assert "ai" in formatted
        assert "podcast" in formatted
        assert all(not t.startswith("#") for t in formatted)

    def test_generate_tags_integration(self):
        """Test full tag generation pipeline."""
        config = TagConfig(
            max_tags=5,
            min_confidence=0.7,
            include_llm_tags=False,  # Skip LLM for unit test
        )
        generator = TagGenerator(config=config)

        entities = [
            Entity(name="Cal Newport", type=EntityType.PERSON, confidence=0.9),
            Entity(name="Deep Work", type=EntityType.BOOK, confidence=0.85),
        ]

        metadata = {
            "podcast_name": "Lex Fridman Podcast",
            "episode_title": "Cal Newport on Deep Work",
        }

        transcript = "Cal Newport discusses the concept of deep work..."

        tags = generator.generate_tags(
            entities=entities,
            transcript=transcript,
            metadata=metadata,
        )

        # Should have metadata tags + entity tags
        tag_names = [t.name for t in tags]
        assert "lex-fridman-podcast" in tag_names
        assert "podcast" in tag_names
        assert "inkwell" in tag_names
        assert "cal-newport" in tag_names
        assert "deep-work" in tag_names

        # Should not exceed max_tags
        assert len(tags) <= 5

        # Should be sorted by confidence
        confidences = [t.confidence for t in tags]
        assert confidences == sorted(confidences, reverse=True)

    def test_map_category(self):
        """Test mapping category strings to enums."""
        generator = TagGenerator()

        assert generator._map_category("topic") == TagCategory.TOPIC
        assert generator._map_category("theme") == TagCategory.THEME
        assert generator._map_category("person") == TagCategory.PERSON
        assert generator._map_category("book") == TagCategory.BOOK
        assert generator._map_category("tool") == TagCategory.TOOL
        assert generator._map_category("concept") == TagCategory.CONCEPT
        assert generator._map_category("industry") == TagCategory.INDUSTRY
        assert generator._map_category("custom") == TagCategory.CUSTOM
        assert generator._map_category("unknown") is None

    def test_parse_llm_response(self):
        """Test parsing LLM JSON response."""
        generator = TagGenerator()

        response_text = """
        Here are the suggested tags:
        {
            "tags": [
                {"name": "artificial-intelligence", "category": "topic", "confidence": 0.9, "reasoning": "Main topic"},
                {"name": "productivity", "category": "theme", "confidence": 0.8, "reasoning": "Recurring theme"}
            ]
        }
        """

        tags = generator._parse_llm_response(response_text)

        assert len(tags) == 2
        assert tags[0].name == "artificial-intelligence"
        assert tags[0].category == TagCategory.TOPIC
        assert tags[0].confidence == 0.9
        assert tags[1].name == "productivity"
        assert tags[1].category == TagCategory.THEME

    def test_parse_llm_response_invalid_json(self):
        """Test graceful handling of invalid JSON."""
        generator = TagGenerator()

        response_text = "This is not valid JSON"

        tags = generator._parse_llm_response(response_text)

        # Should return empty list, not crash
        assert tags == []

    def test_build_llm_context(self):
        """Test building context for LLM."""
        generator = TagGenerator()

        metadata = {
            "podcast_name": "Lex Fridman Podcast",
            "episode_title": "AI and Consciousness",
        }

        transcript = "This is a long transcript about AI..." * 100

        extraction_results = {
            "summary": {"content": "This episode discusses AI and consciousness..."},
            "key-concepts": {
                "concepts": [
                    {"name": "Artificial Intelligence"},
                    {"name": "Consciousness"},
                ]
            },
        }

        context = generator._build_llm_context(transcript, metadata, extraction_results)

        assert "Lex Fridman Podcast" in context
        assert "AI and Consciousness" in context
        assert "Artificial Intelligence" in context
        assert "Consciousness" in context
        # Transcript should be truncated
        assert len(context) < len(transcript)
