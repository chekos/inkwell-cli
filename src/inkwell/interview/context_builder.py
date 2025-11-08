"""Context builder for interview preparation.

Extracts content from Phase 3 output files and builds rich context
for interview question generation.
"""

from pathlib import Path
from typing import Any

from inkwell.output.models import EpisodeOutput, OutputFile

from .models import InterviewContext, InterviewGuidelines


class InterviewContextBuilder:
    """Build interview context from extracted episode content.

    Takes Phase 3 output (summary, quotes, concepts, etc.) and constructs
    a rich context object that provides episode information and extracted
    content to the interview question generator.

    Example:
        >>> builder = InterviewContextBuilder()
        >>> context = builder.build_context(
        ...     episode_output=output,
        ...     guidelines=user_guidelines,
        ...     max_questions=5
        ... )
        >>> print(context.to_prompt_context())
    """

    def build_context(
        self,
        episode_output: EpisodeOutput,
        guidelines: InterviewGuidelines | None = None,
        max_questions: int = 5,
    ) -> InterviewContext:
        """Build interview context from episode output.

        Args:
            episode_output: Phase 3 output containing extracted content
            guidelines: Optional user interview preferences
            max_questions: Maximum number of questions to ask

        Returns:
            InterviewContext ready for question generation
        """
        # Extract key information from output files
        summary = self._extract_summary(episode_output)
        quotes = self._extract_quotes(episode_output)
        concepts = self._extract_concepts(episode_output)
        additional = self._extract_additional_content(episode_output)

        # Calculate duration
        duration_minutes = 0.0
        if episode_output.metadata.duration_seconds:
            duration_minutes = episode_output.metadata.duration_seconds / 60.0

        # Build context
        context = InterviewContext(
            podcast_name=episode_output.metadata.podcast_name,
            episode_title=episode_output.metadata.episode_title,
            episode_url=episode_output.metadata.episode_url,
            duration_minutes=duration_minutes,
            summary=summary,
            key_quotes=quotes,
            key_concepts=concepts,
            additional_extractions=additional,
            guidelines=guidelines,
            max_questions=max_questions,
        )

        return context

    def _extract_summary(self, episode_output: EpisodeOutput) -> str:
        """Extract summary from output files.

        Parses summary.md and extracts the main content, removing
        YAML frontmatter and markdown headers.

        Args:
            episode_output: Episode output with files

        Returns:
            Clean summary text
        """
        summary_file = episode_output.get_file("summary")
        if not summary_file:
            return ""

        # Get content (without frontmatter - use .content not .full_content)
        content = summary_file.content

        # Remove markdown headers to get just the prose
        lines = content.split("\n")
        filtered_lines = []
        for line in lines:
            # Skip header lines (# Summary, ## Key Points, etc.)
            if not line.strip().startswith("#"):
                filtered_lines.append(line)

        return "\n".join(filtered_lines).strip()

    def _extract_quotes(self, episode_output: EpisodeOutput) -> list[dict[str, Any]]:
        """Extract quotes from output files.

        Parses quotes.md for structured quote blocks. Supports formats:
        - > "Quote text"
        - > — Speaker [timestamp]
        - Standard markdown blockquotes

        Args:
            episode_output: Episode output with files

        Returns:
            List of quote dictionaries with text, speaker, timestamp
        """
        quotes_file = episode_output.get_file("quotes")
        if not quotes_file:
            return []

        quotes = []
        content = quotes_file.content
        lines = content.split("\n")

        current_quote: dict[str, Any] | None = None
        for line in lines:
            line = line.strip()

            # Quote text line: > "Quote text"
            if line.startswith(">") and '"' in line:
                # Save previous quote if exists
                if current_quote:
                    quotes.append(current_quote)

                # Extract quote text (remove > and quotes)
                quote_text = line.lstrip(">").strip().strip('"')
                current_quote = {"text": quote_text}

            # Attribution line: > — Speaker [timestamp]
            elif line.startswith(">") and "—" in line and current_quote:
                # Remove leading > and split on —
                after_quote = line.lstrip(">").strip()

                # Split on — to get attribution part
                if "—" in after_quote:
                    _, attribution = after_quote.split("—", 1)
                    attribution = attribution.strip()
                else:
                    attribution = after_quote

                # Split on [ to separate speaker and timestamp
                if "[" in attribution:
                    speaker, timestamp_part = attribution.split("[", 1)
                    timestamp = timestamp_part.rstrip("]").strip()
                    current_quote["speaker"] = speaker.strip()
                    current_quote["timestamp"] = timestamp
                else:
                    current_quote["speaker"] = attribution.strip()
                    current_quote["timestamp"] = ""

        # Add final quote if exists
        if current_quote:
            quotes.append(current_quote)

        return quotes

    def _extract_concepts(self, episode_output: EpisodeOutput) -> list[str]:
        """Extract key concepts from output files.

        Parses key-concepts.md for bulleted/numbered lists of concepts.

        Args:
            episode_output: Episode output with files

        Returns:
            List of key concepts
        """
        concepts_file = episode_output.get_file("key-concepts")
        if not concepts_file:
            return []

        concepts = []
        content = concepts_file.content
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            # Match bullet points (- or *) and numbered lists (1. 2. etc.)
            if line.startswith("-") or line.startswith("*"):
                concept = line.lstrip("-*").strip()
                # Filter out very short items and headers
                if concept and len(concept) > 3 and not concept.startswith("#"):
                    concepts.append(concept)
            elif line and line[0].isdigit() and "." in line:
                # Numbered list: "1. Concept"
                parts = line.split(".", 1)
                if len(parts) > 1:
                    concept = parts[1].strip()
                    if concept and len(concept) > 3:
                        concepts.append(concept)

        return concepts

    def _extract_additional_content(
        self, episode_output: EpisodeOutput
    ) -> dict[str, Any]:
        """Extract any additional structured content.

        Checks for common additional templates like tools-mentioned,
        books-mentioned, people-mentioned, etc.

        Args:
            episode_output: Episode output with files

        Returns:
            Dictionary mapping template name to extracted items
        """
        additional: dict[str, Any] = {}

        # Check for common additional templates
        additional_templates = [
            "tools-mentioned",
            "books-mentioned",
            "people-mentioned",
            "frameworks-mentioned",
            "companies-mentioned",
            "concepts-discussed",
        ]

        for template_name in additional_templates:
            file = episode_output.get_file(template_name)
            if file:
                items = self._extract_list_items(file)
                if items:
                    additional[template_name] = items

        return additional

    def _extract_list_items(self, file: OutputFile) -> list[str]:
        """Extract list items from markdown file.

        Parses bulleted and numbered lists from markdown content.

        Args:
            file: Output file to parse

        Returns:
            List of items extracted from lists
        """
        items = []
        lines = file.content.split("\n")

        for line in lines:
            line = line.strip()
            # Bullet points
            if line.startswith("-") or line.startswith("*"):
                item = line.lstrip("-*").strip()
                if item and not item.startswith("#"):
                    items.append(item)
            # Numbered lists
            elif line and line[0].isdigit() and "." in line:
                parts = line.split(".", 1)
                if len(parts) > 1:
                    item = parts[1].strip()
                    if item:
                        items.append(item)

        return items

    def load_previous_interviews(
        self, interview_dir: Path, limit: int = 3
    ) -> list[str]:
        """Load summaries from previous interviews.

        Finds previous interview session files and extracts key insights
        to help make connections across episodes.

        Args:
            interview_dir: Directory containing interview session files
            limit: Maximum number of previous interviews to include

        Returns:
            List of previous interview summaries
        """
        if not interview_dir.exists():
            return []

        # Look for previous interview session JSON files
        # Sort by modification time, then by name for stable ordering
        session_files = sorted(
            interview_dir.glob("session-*.json"),
            key=lambda p: (p.stat().st_mtime, p.name),
        )

        # Get most recent sessions
        recent_sessions = (
            session_files[-limit:] if len(session_files) > limit else session_files
        )

        summaries = []
        for session_file in recent_sessions:
            # TODO: Load session JSON and extract summary
            # For now, just note the file exists
            summaries.append(f"Previous interview: {session_file.name}")

        return summaries
