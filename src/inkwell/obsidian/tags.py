"""Tag generation system for Obsidian integration.

Generates tags from:
1. Extracted entities (people, books, tools, concepts)
2. LLM suggestions based on content
3. Podcast metadata

Supports hierarchical organization and smart normalization.
"""

import logging
from typing import Any

import google.generativeai as genai

from inkwell.obsidian.models import Entity, EntityType
from inkwell.obsidian.tag_models import Tag, TagCategory, TagConfig, TagStyle
from inkwell.utils.api_keys import APIKeyError, get_validated_api_key
from inkwell.utils.json_utils import JSONParsingError, extract_json_from_text
from inkwell.utils.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


class TagGenerator:
    """Generate Obsidian tags from episode content.

    Features:
    - Entity-based tag generation
    - LLM-powered content analysis for additional tags
    - Hierarchical tag structure
    - Smart normalization (kebab-case, lowercase)
    - Confidence filtering
    - Deduplication
    """

    def __init__(self, config: TagConfig | None = None, api_key: str | None = None):
        """Initialize tag generator.

        Args:
            config: Tag generation configuration
            api_key: Gemini API key (defaults to GOOGLE_API_KEY env var)

        Raises:
            APIKeyError: If LLM tags enabled but API key is invalid or missing
        """
        self.config = config or TagConfig()

        # Initialize Gemini if LLM tags enabled
        if self.config.include_llm_tags:
            try:
                # Validate API key
                if api_key:
                    # If provided directly, still validate it
                    from inkwell.utils.api_keys import validate_api_key

                    self.api_key = validate_api_key(api_key, "gemini", "GOOGLE_API_KEY")
                else:
                    # Get from environment and validate
                    self.api_key = get_validated_api_key("GOOGLE_API_KEY", "gemini")

                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.config.llm_model)
            except APIKeyError as e:
                logger.error(f"API key validation failed: {e}")
                raise
        else:
            self.api_key = None
            self.model = None

    def generate_tags(
        self,
        entities: list[Entity],
        transcript: str,
        metadata: dict[str, Any],
        extraction_results: dict[str, Any] | None = None,
    ) -> list[Tag]:
        """Generate tags from episode content.

        Args:
            entities: Extracted entities (from WikilinkGenerator)
            transcript: Episode transcript
            metadata: Episode metadata (title, podcast name, etc.)
            extraction_results: Extraction results (summary, concepts, etc.)

        Returns:
            List of generated tags (filtered, deduplicated, sorted)
        """
        tags: list[Tag] = []

        # 1. Generate tags from metadata
        tags.extend(self._tags_from_metadata(metadata))

        # 2. Generate tags from entities
        if self.config.include_entity_tags:
            tags.extend(self._tags_from_entities(entities))

        # 3. Generate tags from LLM analysis
        if self.config.include_llm_tags and self.model:
            llm_tags = self._tags_from_llm(
                transcript=transcript,
                metadata=metadata,
                extraction_results=extraction_results,
            )
            tags.extend(llm_tags)

        # 4. Process tags
        tags = self._deduplicate_tags(tags)
        tags = self._filter_tags(tags)
        tags = self._limit_tags(tags)
        tags = sorted(tags, key=lambda t: t.confidence, reverse=True)

        return tags

    def _tags_from_metadata(self, metadata: dict[str, Any]) -> list[Tag]:
        """Generate tags from episode metadata.

        Args:
            metadata: Episode metadata

        Returns:
            List of metadata-based tags
        """
        tags = []

        # Podcast name tag
        if "podcast_name" in metadata:
            podcast_name = metadata["podcast_name"]
            tags.append(
                Tag(
                    name=podcast_name,
                    category=TagCategory.PODCAST,
                    confidence=1.0,
                    source="manual",
                    raw_name=podcast_name,
                )
            )

        # Always add base tags
        tags.append(
            Tag(
                name="podcast",
                category=None,
                confidence=1.0,
                source="manual",
                raw_name="podcast",
            )
        )
        tags.append(
            Tag(
                name="inkwell",
                category=None,
                confidence=1.0,
                source="manual",
                raw_name="inkwell",
            )
        )

        return tags

    def _tags_from_entities(self, entities: list[Entity]) -> list[Tag]:
        """Generate tags from extracted entities.

        Args:
            entities: Extracted entities

        Returns:
            List of entity-based tags
        """
        tags = []

        # Entity type to tag category mapping
        entity_to_category = {
            EntityType.PERSON: TagCategory.PERSON,
            EntityType.BOOK: TagCategory.BOOK,
            EntityType.TOOL: TagCategory.TOOL,
            EntityType.CONCEPT: TagCategory.CONCEPT,
        }

        for entity in entities:
            # Only create tags for high-confidence entities
            if entity.confidence < 0.8:
                continue

            category = entity_to_category.get(entity.type)
            if category:
                tags.append(
                    Tag(
                        name=entity.name,
                        category=category,
                        confidence=entity.confidence,
                        source="entity",
                        raw_name=entity.name,
                    )
                )

        return tags

    def _tags_from_llm(
        self,
        transcript: str,
        metadata: dict[str, Any],
        extraction_results: dict[str, Any] | None = None,
    ) -> list[Tag]:
        """Generate tags using LLM analysis.

        Args:
            transcript: Episode transcript
            metadata: Episode metadata
            extraction_results: Extraction results

        Returns:
            List of LLM-suggested tags
        """
        if not self.model:
            return []

        try:
            # Build context for LLM
            context = self._build_llm_context(transcript, metadata, extraction_results)

            # Create prompt
            prompt = self._create_tag_prompt(context)

            # Apply rate limiting before API call
            limiter = get_rate_limiter("gemini")
            limiter.acquire()

            # Generate tags
            response = self.model.generate_content(prompt)

            # Parse response
            tags = self._parse_llm_response(response.text)

            return tags

        except Exception as e:
            # Gracefully handle LLM failures
            logger.warning("LLM tag generation failed: %s", e, exc_info=True)
            return []

    def _build_llm_context(
        self,
        transcript: str,
        metadata: dict[str, Any],
        extraction_results: dict[str, Any] | None,
    ) -> str:
        """Build simple context for LLM tag generation.

        Args:
            transcript: Episode transcript
            metadata: Episode metadata
            extraction_results: Extraction results (optional, unused in simplified version)

        Returns:
            Formatted context string
        """
        # Extract basic metadata
        podcast_name = metadata.get("podcast_name", "Unknown")
        episode_title = metadata.get("episode_title", "Unknown")

        # First 1000 chars of transcript is sufficient for context
        transcript_sample = transcript[:1000] + ("..." if len(transcript) > 1000 else "")

        # Simple, clear context format
        return f"""Podcast: {podcast_name}
Episode: {episode_title}
Content: {transcript_sample}""".strip()

    def _create_tag_prompt(self, context: str) -> str:
        """Create prompt for LLM tag generation.

        Args:
            context: Episode context

        Returns:
            Formatted prompt
        """
        return f"""Analyze this podcast episode and suggest relevant tags for Obsidian.

{context}

Suggest 3-5 tags that capture:
1. Main topics discussed (e.g., ai, productivity, mental-health)
2. Themes and concepts (e.g., focus, decision-making, leadership)
3. Industry or field (e.g., tech, business, science)

Requirements:
- Use lowercase
- Use hyphens for multi-word tags (e.g., "deep-work", not "deep work")
- Be specific but not too narrow
- Avoid redundancy with obvious tags (podcast name, guest names)

Respond with a JSON object:
{{
    "tags": [
        {{"name": "ai", "category": "topic", "confidence": 0.9,
          "reasoning": "Main topic of discussion"}},
        {{"name": "productivity", "category": "theme", "confidence": 0.8,
          "reasoning": "Recurring theme"}}
    ]
}}

Valid categories: topic, theme, concept, industry, custom
"""

    def _parse_llm_response(self, response_text: str) -> list[Tag]:
        """Parse LLM response into Tag objects.

        Args:
            response_text: LLM response text

        Returns:
            List of parsed tags
        """
        tags = []

        try:
            # Use safe JSON extraction with size/depth limits
            # 1MB is generous for tag responses, depth of 5 is sufficient
            data = extract_json_from_text(
                response_text, max_size=1_000_000, max_depth=5
            )

            # Validate structure
            if not isinstance(data, dict):
                raise JSONParsingError(
                    f"Expected JSON object, got {type(data).__name__}"
                )

            if "tags" not in data:
                raise JSONParsingError("Missing 'tags' field in JSON response")

            if not isinstance(data["tags"], list):
                raise JSONParsingError("'tags' field must be a list")

            # Parse tags
            for tag_data in data.get("tags", []):
                try:
                    # Map string category to TagCategory enum
                    category_str = tag_data.get("category", "custom")
                    category = self._map_category(category_str)

                    tag = Tag(
                        name=tag_data["name"],
                        category=category,
                        confidence=tag_data.get("confidence", 0.7),
                        source="llm",
                        raw_name=tag_data["name"],
                    )
                    tags.append(tag)
                except (KeyError, ValueError) as e:
                    logger.warning("Failed to parse tag: %s", e)
                    continue

        except JSONParsingError as e:
            logger.warning("Failed to parse LLM response as JSON: %s", e)

        return tags

    def _map_category(self, category_str: str) -> TagCategory | None:
        """Map category string to TagCategory enum.

        Args:
            category_str: Category string from LLM

        Returns:
            TagCategory enum or None
        """
        mapping = {
            "topic": TagCategory.TOPIC,
            "theme": TagCategory.THEME,
            "concept": TagCategory.CONCEPT,
            "person": TagCategory.PERSON,
            "book": TagCategory.BOOK,
            "tool": TagCategory.TOOL,
            "industry": TagCategory.INDUSTRY,
            "podcast": TagCategory.PODCAST,
            "custom": TagCategory.CUSTOM,
        }
        return mapping.get(category_str.lower())

    def _deduplicate_tags(self, tags: list[Tag]) -> list[Tag]:
        """Remove duplicate tags (case-insensitive).

        Args:
            tags: List of tags

        Returns:
            Deduplicated list
        """
        seen = set()
        deduped = []

        for tag in tags:
            tag_key = (tag.name.lower(), tag.category)
            if tag_key not in seen:
                seen.add(tag_key)
                deduped.append(tag)

        return deduped

    def _filter_tags(self, tags: list[Tag]) -> list[Tag]:
        """Filter tags by confidence threshold.

        Args:
            tags: List of tags

        Returns:
            Filtered list
        """
        return [t for t in tags if t.confidence >= self.config.min_confidence]

    def _limit_tags(self, tags: list[Tag]) -> list[Tag]:
        """Limit number of tags.

        Args:
            tags: List of tags

        Returns:
            Limited list (sorted by confidence, top N)
        """
        # Sort by confidence (descending)
        sorted_tags = sorted(tags, key=lambda t: t.confidence, reverse=True)

        # Take top N
        return sorted_tags[: self.config.max_tags]

    def format_tags(
        self, tags: list[Tag], style: TagStyle | None = None
    ) -> list[str]:
        """Format tags as Obsidian tag strings.

        Args:
            tags: List of Tag objects
            style: Tag style (overrides config)

        Returns:
            List of formatted tag strings

        Example:
            ["#podcast/lex-fridman", "#topic/ai", "#theme/productivity"]
        """
        tag_style = style or self.config.style
        return [tag.to_obsidian_tag(tag_style) for tag in tags]

    def format_frontmatter_tags(self, tags: list[Tag]) -> list[str]:
        """Format tags for YAML frontmatter (without # prefix).

        Args:
            tags: List of Tag objects

        Returns:
            List of tag strings for frontmatter

        Example:
            ["podcast/lex-fridman", "topic/ai", "theme/productivity"]
        """
        formatted = []
        for tag in tags:
            if self.config.style == TagStyle.HIERARCHICAL and tag.category:
                formatted.append(f"{tag.category.value}/{tag.name}")
            else:
                formatted.append(tag.name)
        return formatted
