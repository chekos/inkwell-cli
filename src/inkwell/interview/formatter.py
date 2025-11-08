"""Interview transcript formatter for generating structured markdown output.

This module converts interview sessions into beautifully formatted markdown transcripts
with extracted insights, action items, and themes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from inkwell.interview.models import Exchange, InterviewResult, InterviewSession

FormatStyle = Literal["structured", "narrative", "qa"]


class TranscriptFormatter:
    """Format interview sessions as structured markdown transcripts."""

    def __init__(self, format_style: FormatStyle = "structured"):
        """Initialize transcript formatter.

        Args:
            format_style: Output format style (structured, narrative, or qa)
        """
        self.format_style = format_style

    def format_session(
        self,
        session: InterviewSession,
        extract_insights: bool = True,
        extract_actions: bool = True,
        extract_themes: bool = True,
    ) -> InterviewResult:
        """Format interview session as markdown transcript.

        Args:
            session: Completed interview session
            extract_insights: Whether to extract key insights
            extract_actions: Whether to extract action items
            extract_themes: Whether to identify themes

        Returns:
            InterviewResult with formatted transcript and extractions

        Example:
            >>> formatter = TranscriptFormatter(format_style="structured")
            >>> result = formatter.format_session(session)
            >>> print(result.formatted_transcript)
        """
        # Generate formatted transcript
        if self.format_style == "structured":
            transcript = self._format_structured(session)
        elif self.format_style == "narrative":
            transcript = self._format_narrative(session)
        else:  # qa
            transcript = self._format_qa(session)

        # Extract insights, actions, themes
        insights = self._extract_insights(session) if extract_insights else []
        actions = self._extract_action_items(session) if extract_actions else []
        themes = self._extract_themes(session) if extract_themes else []

        return InterviewResult(
            session=session,
            formatted_transcript=transcript,
            key_insights=insights,
            action_items=actions,
            themes=themes,
        )

    def _format_structured(self, session: InterviewSession) -> str:
        """Format as structured markdown with clear sections.

        Args:
            session: Interview session

        Returns:
            Formatted markdown transcript
        """
        parts = []

        # Header
        parts.append(self._format_header(session))
        parts.append("")

        # Metadata
        parts.append(self._format_metadata(session))
        parts.append("")

        # Conversation
        parts.append("## Conversation")
        parts.append("")

        for exchange in session.exchanges:
            parts.append(self._format_exchange_structured(exchange))
            parts.append("")

        # Statistics
        parts.append(self._format_statistics(session))
        parts.append("")

        return "\n".join(parts)

    def _format_narrative(self, session: InterviewSession) -> str:
        """Format as flowing narrative text.

        Args:
            session: Interview session

        Returns:
            Formatted markdown transcript
        """
        parts = []

        # Header
        parts.append(self._format_header(session))
        parts.append("")

        # Introduction
        parts.append(self._format_narrative_intro(session))
        parts.append("")

        # Conversation as narrative
        for i, exchange in enumerate(session.exchanges, 1):
            parts.append(self._format_exchange_narrative(exchange, i))
            parts.append("")

        # Closing
        parts.append(self._format_narrative_closing(session))
        parts.append("")

        return "\n".join(parts)

    def _format_qa(self, session: InterviewSession) -> str:
        """Format as simple Q&A pairs.

        Args:
            session: Interview session

        Returns:
            Formatted markdown transcript
        """
        parts = []

        # Header
        parts.append(self._format_header(session))
        parts.append("")

        # Simple Q&A
        for exchange in session.exchanges:
            parts.append(self._format_exchange_qa(exchange))
            parts.append("")

        return "\n".join(parts)

    def _format_header(self, session: InterviewSession) -> str:
        """Format transcript header.

        Args:
            session: Interview session

        Returns:
            Formatted header text
        """
        return f"# Interview Notes: {session.episode_title}"

    def _format_metadata(self, session: InterviewSession) -> str:
        """Format session metadata.

        Args:
            session: Interview session

        Returns:
            Formatted metadata section
        """
        duration_minutes = session.duration.total_seconds() / 60.0
        date_str = session.started_at.strftime("%Y-%m-%d")

        parts = [
            "---",
            "",
            "**Podcast**: " + session.podcast_name,
            f"**Episode**: {session.episode_title}",
            f"**Interview Date**: {date_str}",
            f"**Template**: {session.template_name}",
            f"**Questions**: {session.question_count}",
            f"**Duration**: {duration_minutes:.1f} minutes",
            "",
            "---",
        ]

        return "\n".join(parts)

    def _format_exchange_structured(self, exchange: Exchange) -> str:
        """Format exchange in structured style.

        Args:
            exchange: Question/response exchange

        Returns:
            Formatted exchange text
        """
        q_num = exchange.question.question_number
        is_followup = exchange.question.depth_level > 0

        parts = []

        # Question
        if is_followup:
            parts.append(f"### Follow-up {q_num}")
        else:
            parts.append(f"### Question {q_num}")

        parts.append("")
        parts.append(f"**Q**: {exchange.question.text}")
        parts.append("")

        # Response
        parts.append(f"**A**: {exchange.response.text}")

        return "\n".join(parts)

    def _format_exchange_narrative(self, exchange: Exchange, number: int) -> str:
        """Format exchange in narrative style.

        Args:
            exchange: Question/response exchange
            number: Sequential number for flow

        Returns:
            Formatted exchange text
        """
        parts = []

        # Flowing text
        parts.append(f"_{exchange.question.text}_")
        parts.append("")
        parts.append(exchange.response.text)

        return "\n".join(parts)

    def _format_exchange_qa(self, exchange: Exchange) -> str:
        """Format exchange as simple Q&A.

        Args:
            exchange: Question/response exchange

        Returns:
            Formatted exchange text
        """
        parts = [
            f"**Q**: {exchange.question.text}",
            "",
            f"**A**: {exchange.response.text}",
        ]

        return "\n".join(parts)

    def _format_narrative_intro(self, session: InterviewSession) -> str:
        """Format narrative introduction.

        Args:
            session: Interview session

        Returns:
            Formatted intro text
        """
        date_str = session.started_at.strftime("%B %d, %Y")

        return (
            f"On {date_str}, I reflected on **{session.episode_title}** "
            f"from {session.podcast_name}. Here are my thoughts from that conversation."
        )

    def _format_narrative_closing(self, session: InterviewSession) -> str:
        """Format narrative closing.

        Args:
            session: Interview session

        Returns:
            Formatted closing text
        """
        return (
            f"This reflection covered {session.question_count} questions "
            f"and helped me think more deeply about the episode's ideas."
        )

    def _format_statistics(self, session: InterviewSession) -> str:
        """Format session statistics.

        Args:
            session: Interview session

        Returns:
            Formatted statistics section
        """
        duration_minutes = session.duration.total_seconds() / 60.0

        parts = [
            "## Session Statistics",
            "",
            f"- **Questions asked**: {session.question_count}",
            f"- **Substantive responses**: {session.substantive_response_count}",
            f"- **Total time**: {duration_minutes:.1f} minutes",
            f"- **Tokens used**: {session.total_tokens_used:,}",
            f"- **Cost**: ${session.total_cost_usd:.4f}",
        ]

        return "\n".join(parts)

    def _extract_insights(self, session: InterviewSession) -> list[str]:
        """Extract key insights from interview exchanges.

        Insights are substantive realizations or connections the user made.

        Args:
            session: Interview session

        Returns:
            List of extracted insights
        """
        insights = []

        # Insight indicators (words/phrases that signal insights)
        insight_patterns = [
            r"i realize",
            r"i've realized",
            r"i learned",
            r"i discovered",
            r"this made me think",
            r"this makes me think",
            r"i hadn't considered",
            r"i never thought",
            r"the connection is",
            r"the key insight",
            r"what struck me",
            r"it's interesting that",
            r"i'm starting to see",
            r"now i understand",
        ]

        pattern = re.compile("|".join(insight_patterns), re.IGNORECASE)

        for exchange in session.exchanges:
            if not exchange.response.is_substantive:
                continue

            # Look for insight indicators
            text = exchange.response.text
            if pattern.search(text):
                # Extract the sentence containing the insight
                sentences = re.split(r"[.!?]+", text)
                for sentence in sentences:
                    if pattern.search(sentence):
                        insight = sentence.strip()
                        if len(insight) >= 20:  # Must be substantive
                            insights.append(insight)

        # Deduplicate similar insights
        return self._deduplicate_items(insights)[:5]  # Top 5

    def _extract_action_items(self, session: InterviewSession) -> list[str]:
        """Extract action items from interview exchanges.

        Action items are things the user wants to do or try.

        Args:
            session: Interview session

        Returns:
            List of extracted action items
        """
        actions = []

        # Action indicators
        action_patterns = [
            r"i should",
            r"i'll",
            r"i will",
            r"i want to",
            r"i need to",
            r"i plan to",
            r"i'm going to",
            r"next step",
            r"my goal",
            r"i could try",
            r"worth trying",
            r"i'd like to",
        ]

        pattern = re.compile("|".join(action_patterns), re.IGNORECASE)

        for exchange in session.exchanges:
            if not exchange.response.is_substantive:
                continue

            text = exchange.response.text
            if pattern.search(text):
                # Extract sentences with action indicators
                sentences = re.split(r"[.!?]+", text)
                for sentence in sentences:
                    if pattern.search(sentence):
                        action = sentence.strip()
                        if len(action) >= 15:  # Must be substantive
                            # Clean up action text
                            action = self._clean_action_text(action)
                            actions.append(action)

        return self._deduplicate_items(actions)[:10]  # Top 10

    def _extract_themes(self, session: InterviewSession) -> list[str]:
        """Extract recurring themes from interview exchanges.

        Themes are topics or concepts that appear multiple times.

        Args:
            session: Interview session

        Returns:
            List of identified themes
        """
        # Collect all substantial responses
        all_text = " ".join(
            exchange.response.text
            for exchange in session.exchanges
            if exchange.response.is_substantive
        )

        # Look for repeated important concepts
        # Extract noun phrases and multi-word concepts
        words = all_text.lower().split()

        # Count 2-3 word phrases
        phrase_counts: dict[str, int] = {}

        for i in range(len(words) - 1):
            # 2-word phrases
            phrase = " ".join(words[i : i + 2])
            if self._is_meaningful_phrase(phrase):
                phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

            # 3-word phrases
            if i < len(words) - 2:
                phrase = " ".join(words[i : i + 3])
                if self._is_meaningful_phrase(phrase):
                    phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

        # Get phrases that appear 2+ times
        themes = [phrase for phrase, count in phrase_counts.items() if count >= 2]

        # Sort by frequency
        themes.sort(key=lambda p: phrase_counts[p], reverse=True)

        # Capitalize and return top 8
        return [theme.title() for theme in themes[:8]]

    def _is_meaningful_phrase(self, phrase: str) -> bool:
        """Check if phrase is meaningful (not stop words).

        Args:
            phrase: Phrase to check

        Returns:
            True if phrase is meaningful
        """
        # Common stop words to exclude
        stop_words = {
            "i am",
            "i was",
            "i have",
            "i had",
            "i do",
            "i did",
            "it is",
            "it was",
            "that is",
            "that was",
            "to be",
            "and the",
            "in the",
            "of the",
            "to the",
            "for the",
            "on the",
            "at the",
        }

        return phrase not in stop_words and len(phrase) > 5

    def _clean_action_text(self, action: str) -> str:
        """Clean action item text for readability.

        Args:
            action: Raw action text

        Returns:
            Cleaned action text
        """
        # Remove leading conjunctions
        action = re.sub(r"^(and|but|so)\s+", "", action, flags=re.IGNORECASE)

        # Capitalize first letter
        if action:
            action = action[0].upper() + action[1:]

        return action.strip()

    def _deduplicate_items(self, items: list[str]) -> list[str]:
        """Remove duplicate or very similar items.

        Args:
            items: List of items to deduplicate

        Returns:
            Deduplicated list
        """
        if not items:
            return []

        # Simple deduplication: keep first occurrence
        seen = set()
        unique = []

        for item in items:
            item_lower = item.lower().strip()
            if item_lower not in seen and len(item_lower) > 0:
                seen.add(item_lower)
                unique.append(item)

        return unique

    def save_transcript(
        self, result: InterviewResult, output_dir: Path, filename: str = "my-notes.md"
    ) -> Path:
        """Save formatted transcript to file.

        Args:
            result: Interview result with formatted transcript
            output_dir: Directory to save transcript
            filename: Output filename

        Returns:
            Path to saved file
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / filename

        # Build complete markdown
        content_parts = [result.formatted_transcript]

        # Add insights section if present
        if result.key_insights:
            content_parts.extend(["", "## Key Insights", ""])
            for insight in result.key_insights:
                content_parts.append(f"- {insight}")

        # Add action items if present
        if result.action_items:
            content_parts.extend(["", "## Action Items", ""])
            for action in result.action_items:
                content_parts.append(f"- [ ] {action}")

        # Add themes if present
        if result.themes:
            content_parts.extend(["", "## Recurring Themes", ""])
            for theme in result.themes:
                content_parts.append(f"- {theme}")

        # Write to file
        output_file.write_text("\n".join(content_parts))

        # Update result with file path
        result.output_file = output_file

        return output_file
