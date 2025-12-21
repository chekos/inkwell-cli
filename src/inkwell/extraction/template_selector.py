"""Template selection and category detection.

This module provides functionality for automatically selecting appropriate
templates based on episode category and content analysis.
"""

import logging

from inkwell.feeds.models import Episode

from .models import ExtractionTemplate
from .templates import TemplateLoader

logger = logging.getLogger(__name__)


class TemplateSelector:
    """Select appropriate templates for an episode.

    The selector determines which templates to apply based on:
    - Episode category (if explicitly provided)
    - Content analysis (auto-detection from transcript)
    - Custom template list (user override)

    Example:
        >>> selector = TemplateSelector(template_loader)
        >>> templates = selector.select_templates(
        ...     episode,
        ...     category="tech",
        ...     custom_templates=["tools-mentioned"]
        ... )
    """

    def __init__(self, template_loader: TemplateLoader):
        """Initialize template selector.

        Args:
            template_loader: TemplateLoader instance for loading templates
        """
        self.loader = template_loader
        logger.debug("TemplateSelector initialized")

    def select_templates(
        self,
        episode: Episode,
        category: str | None = None,
        custom_templates: list[str] | None = None,
        transcript: str | None = None,
    ) -> list[ExtractionTemplate]:
        """Select templates for episode extraction.

        Selection logic:
        1. Always include default templates (summary, quotes, key-concepts)
        2. Add category-specific templates if category provided
        3. Auto-detect category from transcript if not provided
        4. Add custom templates if specified
        5. Sort by priority (lower = earlier)

        Args:
            episode: Episode to extract from
            category: Explicit category (e.g., "tech", "interview")
            custom_templates: Additional template names to include
            transcript: Transcript text for auto-detection (optional)

        Returns:
            List of templates sorted by priority
        """
        selected = []

        # Step 1: Always include default templates
        default_templates = ["summary", "quotes", "key-concepts"]
        for name in default_templates:
            try:
                template = self.loader.load_template(name)
                selected.append(template)
                logger.debug(f"Added default template: {name}")
            except Exception as e:
                logger.warning(f"Default template '{name}' not found: {e}")

        # Step 2: Auto-detect category if not provided
        if category is None and transcript:
            category = self.detect_category(transcript)
            if category:
                logger.info(f"Auto-detected category: {category}")

        # Step 3: Add category-specific templates
        if category:
            category_templates = self.loader.list_templates(category=category)
            for name in category_templates:
                # Skip if already included (default templates)
                if any(t.name == name for t in selected):
                    continue

                try:
                    template = self.loader.load_template(name)
                    # Check if template applies to this category
                    if category in template.applies_to or "all" in template.applies_to:
                        selected.append(template)
                        logger.debug(f"Added category template: {name}")
                except Exception as e:
                    logger.warning(f"Failed to load category template '{name}': {e}")

        # Step 4: Add custom templates
        if custom_templates:
            for name in custom_templates:
                # Skip if already included
                if any(t.name == name for t in selected):
                    continue

                try:
                    template = self.loader.load_template(name)
                    selected.append(template)
                    logger.debug(f"Added custom template: {name}")
                except Exception as e:
                    logger.error(f"Custom template '{name}' not found: {e}")

        # Step 5: Sort by priority (lower = earlier)
        selected.sort(key=lambda t: t.priority)

        logger.info(
            f"Selected {len(selected)} templates for extraction: {[t.name for t in selected]}"
        )
        return selected

    def detect_category(self, transcript: str) -> str | None:
        """Auto-detect podcast category from transcript content.

        Uses keyword-based heuristics to identify category:
        - "tech": Technical content (programming, software, tools)
        - "interview": Interview format (guest, conversation, book)
        - None: General/unknown

        Args:
            transcript: Full transcript text

        Returns:
            Detected category or None
        """
        if not transcript:
            return None

        transcript_lower = transcript.lower()

        # Tech keywords (programming, software development)
        tech_keywords = [
            "software",
            "programming",
            "code",
            "developer",
            "api",
            "framework",
            "library",
            "github",
            "python",
            "javascript",
            "rust",
            "database",
            "cloud",
            "devops",
        ]

        # Interview keywords (conversational format)
        interview_keywords = [
            "guest",
            "author",
            "book",
            "conversation",
            "interview",
            "wrote",
            "published",
            "story",
            "experience",
        ]

        # Count keyword matches
        tech_score = sum(1 for kw in tech_keywords if kw in transcript_lower)
        interview_score = sum(1 for kw in interview_keywords if kw in transcript_lower)

        # Thresholds for detection (at least 3 matching keywords)
        min_threshold = 3

        if tech_score >= min_threshold and tech_score > interview_score:
            logger.debug(f"Detected 'tech' category (score: {tech_score} vs {interview_score})")
            return "tech"
        elif interview_score >= min_threshold and interview_score > tech_score:
            logger.debug(
                f"Detected 'interview' category (score: {interview_score} vs {tech_score})"
            )
            return "interview"

        logger.debug(
            f"No clear category detected (tech: {tech_score}, interview: {interview_score})"
        )
        return None

    def get_templates_for_category(self, category: str) -> list[str]:
        """Get list of template names for a specific category.

        Args:
            category: Category name

        Returns:
            List of template names applicable to category
        """
        return self.loader.list_templates(category=category)
