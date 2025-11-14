"""Markdown output generation from extraction results.

Formats extracted content as markdown files with YAML frontmatter.
"""

import json
from datetime import datetime
from typing import Any

import yaml

from ..extraction.models import ExtractedContent, ExtractionResult


class MarkdownGenerator:
    """Generate markdown files from extraction results.

    Handles:
    - YAML frontmatter for metadata
    - Content formatting based on extraction format (JSON, text, etc.)
    - Template-specific formatting (quotes, concepts, etc.)
    - Clean markdown output

    Example:
        >>> generator = MarkdownGenerator()
        >>> markdown = generator.generate(result, metadata)
        >>> print(markdown)
        ---
        title: Episode Title
        podcast: Podcast Name
        ---
        # Summary
        ...
    """

    def generate(
        self,
        result: ExtractionResult,
        episode_metadata: dict[str, Any],
        include_frontmatter: bool = True,
    ) -> str:
        """Generate markdown from extraction result.

        Args:
            result: ExtractionResult from extraction engine
            episode_metadata: Episode metadata (podcast name, title, etc.)
            include_frontmatter: Whether to include YAML frontmatter

        Returns:
            Formatted markdown string
        """
        parts = []

        # Add frontmatter
        if include_frontmatter:
            frontmatter = self._generate_frontmatter(result, episode_metadata)
            parts.append(frontmatter)

        # Add content
        content = self._format_content(result)
        parts.append(content)

        return "\n\n".join(parts)

    def _generate_frontmatter(
        self, result: ExtractionResult, episode_metadata: dict[str, Any]
    ) -> str:
        """Generate YAML frontmatter.

        Args:
            result: ExtractionResult
            episode_metadata: Episode metadata

        Returns:
            YAML frontmatter block (with --- delimiters)
        """
        from datetime import timezone

        frontmatter_data = {
            "template": result.template_name,
            "podcast": episode_metadata.get("podcast_name", "Unknown"),
            "episode": episode_metadata.get("episode_title", "Unknown"),
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "extracted_with": result.provider,
            "cost_usd": round(result.cost_usd, 4),
        }

        # Add episode URL if available
        if "episode_url" in episode_metadata:
            frontmatter_data["url"] = episode_metadata["episode_url"]

        # Add custom tags based on template type
        tags = self._generate_tags(result.template_name)
        if tags:
            frontmatter_data["tags"] = tags

        yaml_str = yaml.dump(frontmatter_data, default_flow_style=False, sort_keys=False)
        return f"---\n{yaml_str}---"

    def _generate_tags(self, template_name: str) -> list[str]:
        """Generate tags based on template name.

        Args:
            template_name: Template name

        Returns:
            List of tags
        """
        tags = ["podcast", "inkwell"]

        # Add template-specific tags
        if "quote" in template_name.lower():
            tags.append("quotes")
        elif "summary" in template_name.lower():
            tags.append("summary")
        elif "concept" in template_name.lower():
            tags.append("concepts")
        elif "tool" in template_name.lower():
            tags.append("tools")
        elif "book" in template_name.lower():
            tags.append("books")

        return tags

    def _format_content(self, result: ExtractionResult) -> str:
        """Format extracted content as markdown.

        Args:
            result: ExtractionResult with content

        Returns:
            Formatted markdown content
        """
        if not result.extracted_content:
            return "# Error\n\nNo content extracted."

        content = result.extracted_content

        # Check if content is dict (structured data) or string (text)
        if isinstance(content.content, dict):
            return self._format_json_content(result.template_name, content)
        else:
            # String content - return as-is
            return self._format_text_content(content)

    def _format_json_content(self, template_name: str, content: ExtractedContent) -> str:
        """Format JSON content as markdown.

        Uses template-specific formatters for known templates.

        Args:
            template_name: Template name
            content: ExtractedContent with JSON data

        Returns:
            Formatted markdown
        """
        data = content.content if isinstance(content.content, dict) else {}

        # Use template-specific formatter if available
        if "quote" in template_name.lower():
            return self._format_quotes(data)
        elif "concept" in template_name.lower():
            return self._format_concepts(data)
        elif "tool" in template_name.lower():
            return self._format_tools(data)
        elif "book" in template_name.lower():
            return self._format_books(data)
        else:
            # Generic JSON formatting
            return self._format_generic_json(data)

    def _format_quotes(self, data: dict[str, Any]) -> str:
        """Format quotes as markdown list.

        Args:
            data: JSON data with quotes array

        Returns:
            Formatted markdown
        """
        if "quotes" not in data:
            return "No quotes found."

        lines = ["# Quotes\n"]

        for i, quote in enumerate(data["quotes"], 1):
            text = quote.get("text", "")
            speaker = quote.get("speaker", "Unknown")
            timestamp = quote.get("timestamp", "")

            # Format quote
            lines.append(f"## Quote {i}\n")
            lines.append(f"> {text}\n")
            lines.append(f"**Speaker:** {speaker}")

            if timestamp:
                lines.append(f"**Timestamp:** {timestamp}")

            lines.append("")  # Blank line between quotes

        return "\n".join(lines)

    def _format_concepts(self, data: dict[str, Any]) -> str:
        """Format key concepts as markdown.

        Args:
            data: JSON data with concepts array

        Returns:
            Formatted markdown
        """
        if "concepts" not in data:
            return "No concepts found."

        lines = ["# Key Concepts\n"]

        for concept in data["concepts"]:
            name = concept.get("name", "Unknown")
            explanation = concept.get("explanation", "")
            context = concept.get("context", "")

            lines.append(f"## {name}\n")
            if explanation:
                lines.append(f"{explanation}\n")
            if context:
                lines.append(f"**Context:** {context}\n")

        return "\n".join(lines)

    def _format_tools(self, data: dict[str, Any]) -> str:
        """Format tools/technologies as markdown table.

        Args:
            data: JSON data with tools array

        Returns:
            Formatted markdown
        """
        if "tools" not in data:
            return "No tools found."

        lines = ["# Tools & Technologies Mentioned\n"]
        lines.append("| Tool | Category | Context |")
        lines.append("|------|----------|---------|")

        for tool in data["tools"]:
            name = tool.get("name", "Unknown")
            category = tool.get("category", "N/A")
            context = tool.get("context", "")[:50]  # Truncate long context

            lines.append(f"| {name} | {category} | {context} |")

        return "\n".join(lines)

    def _format_books(self, data: dict[str, Any]) -> str:
        """Format books/publications as markdown list.

        Args:
            data: JSON data with books array

        Returns:
            Formatted markdown
        """
        if "books" not in data:
            return "No books found."

        lines = ["# Books & Publications\n"]

        for book in data["books"]:
            title = book.get("title", "Unknown")
            author = book.get("author", "Unknown")
            context = book.get("context", "")

            lines.append(f"## {title}\n")
            lines.append(f"**Author:** {author}\n")
            if context:
                lines.append(f"**Mentioned:** {context}\n")

        return "\n".join(lines)

    def _format_generic_json(self, data: dict[str, Any]) -> str:
        """Format generic JSON data as markdown.

        Args:
            data: JSON data

        Returns:
            Formatted markdown
        """
        lines = ["# Extracted Data\n"]

        # Pretty-print JSON as code block
        json_str = json.dumps(data, indent=2)
        lines.append("```json")
        lines.append(json_str)
        lines.append("```")

        return "\n".join(lines)

    def _format_markdown_content(self, content: ExtractedContent) -> str:
        """Format markdown content (already markdown).

        Args:
            content: ExtractedContent with markdown text

        Returns:
            Markdown content (as-is)
        """
        return str(content.content)

    def _format_yaml_content(self, content: ExtractedContent) -> str:
        """Format YAML content as markdown code block.

        Args:
            content: ExtractedContent with YAML data

        Returns:
            Formatted markdown
        """
        lines = ["# Extracted Data\n"]
        data = content.content if isinstance(content.content, dict) else {}
        yaml_str = yaml.dump(data, default_flow_style=False)
        lines.append("```yaml")
        lines.append(yaml_str)
        lines.append("```")
        return "\n".join(lines)

    def _format_text_content(self, content: ExtractedContent) -> str:
        """Format plain text content.

        Args:
            content: ExtractedContent with text

        Returns:
            Text content
        """
        return str(content.content)
