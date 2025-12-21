"""Simplified interview implementation - minimal complexity, maximum value.

This module provides a streamlined interview experience for podcast episodes,
replacing the previous 2,500+ LOC implementation with a focused 200 LOC approach.

Key simplifications:
- No session management (no pause/resume)
- Single template (reflective, hardcoded)
- Single format (markdown)
- No metrics tracking
- Simple string concatenation for context building
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from anthropic import AsyncAnthropic
from rich.console import Console
from rich.prompt import Prompt

if TYPE_CHECKING:
    from inkwell.utils.costs import CostTracker

logger = logging.getLogger(__name__)


@dataclass
class SimpleInterviewResult:
    """Minimal result object for simple interview.

    Provides compatibility with orchestrator expectations while
    keeping implementation simple.
    """

    transcript: str
    exchanges: list[dict[str, str]]
    total_cost: float
    total_tokens: int

    def __len__(self) -> int:
        """Return number of exchanges for compatibility."""
        return len(self.exchanges)


class SimpleInterviewer:
    """Minimal interview implementation - single template, no sessions.

    Conducts a simple, focused interview using Claude to generate thoughtful
    reflection questions about a podcast episode. Questions are based on
    episode content (summary, quotes, concepts) and user responses build
    on previous answers.

    Example:
        >>> interviewer = SimpleInterviewer(api_key="sk-...")
        >>> markdown = await interviewer.conduct_interview(
        ...     episode_title="The Future of AI",
        ...     podcast_name="Tech Talks",
        ...     summary="Discussion about AI trends...",
        ...     key_quotes=["Quote 1", "Quote 2"],
        ...     key_concepts=["AGI", "Neural Networks"],
        ...     max_questions=5
        ... )
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        cost_tracker: CostTracker | None = None,
    ):
        """Initialize the simple interviewer.

        Args:
            api_key: Anthropic API key
            model: Claude model to use (default: claude-sonnet-4-5)
            cost_tracker: Optional cost tracker for recording API usage
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.console = Console()
        self.cost_tracker = cost_tracker
        self.total_tokens = 0
        self.total_cost = 0.0

    async def conduct_interview(
        self,
        episode_title: str,
        podcast_name: str,
        summary: str,
        key_quotes: list[str] | None = None,
        key_concepts: list[str] | None = None,
        max_questions: int = 5,
    ) -> SimpleInterviewResult:
        """Conduct simple interview with fixed reflective template.

        Args:
            episode_title: Title of the episode
            podcast_name: Name of the podcast
            summary: Episode summary text
            key_quotes: Optional list of key quotes from episode
            key_concepts: Optional list of key concepts from episode
            max_questions: Maximum number of questions to ask (default: 5)

        Returns:
            SimpleInterviewResult with transcript, exchanges, and cost info
        """
        # Normalize inputs
        key_quotes = key_quotes or []
        key_concepts = key_concepts or []

        # Build context
        context = self._build_context(
            episode_title=episode_title,
            podcast_name=podcast_name,
            summary=summary,
            key_quotes=key_quotes,
            key_concepts=key_concepts,
        )

        # Display welcome
        self._display_welcome(
            episode_title=episode_title,
            podcast_name=podcast_name,
            max_questions=max_questions,
        )

        # Collect exchanges
        exchanges: list[dict[str, str]] = []

        try:
            for i in range(max_questions):
                # Generate question
                self.console.print(f"\n[dim]Generating question {i + 1}/{max_questions}...[/dim]")
                question = await self._generate_question(context, exchanges)

                # Display question
                self.console.print(f"\n[bold blue]Question {i + 1}:[/bold blue] {question}")

                # Get user response
                self.console.print("[dim]Type your response (or 'quit' to end early):[/dim]")
                response = Prompt.ask("[green]>>[/green]", default="")

                # Handle early exit
                if response.lower() in ["quit", "exit", "done", "q"]:
                    self.console.print("[yellow]Ending interview early.[/yellow]")
                    break

                # Skip empty responses
                if not response.strip():
                    self.console.print("[yellow]Skipping empty response.[/yellow]")
                    continue

                # Record exchange
                exchanges.append({"question": question, "response": response})

        except KeyboardInterrupt:
            self.console.print(
                "\n[yellow]Interview interrupted. Saving partial results...[/yellow]"
            )

        # Format output
        markdown = self._format_markdown(
            episode_title=episode_title,
            podcast_name=podcast_name,
            exchanges=exchanges,
        )

        # Display completion
        self._display_completion(len(exchanges), max_questions)

        return SimpleInterviewResult(
            transcript=markdown,
            exchanges=exchanges,
            total_cost=self.total_cost,
            total_tokens=self.total_tokens,
        )

    def _build_context(
        self,
        episode_title: str,
        podcast_name: str,
        summary: str,
        key_quotes: list[str],
        key_concepts: list[str],
    ) -> str:
        """Build interview context using simple string concatenation.

        Args:
            episode_title: Episode title
            podcast_name: Podcast name
            summary: Episode summary
            key_quotes: Key quotes
            key_concepts: Key concepts

        Returns:
            Context string for LLM
        """
        parts = [
            f"Podcast: {podcast_name}",
            f"Episode: {episode_title}",
            "",
            "Summary:",
            summary,
        ]

        if key_quotes:
            parts.extend(["", "Key Quotes:"])
            parts.extend(f"- {quote}" for quote in key_quotes[:5])  # Max 5 quotes

        if key_concepts:
            parts.extend(["", "Key Concepts:"])
            parts.extend(f"- {concept}" for concept in key_concepts[:5])  # Max 5

        return "\n".join(parts)

    async def _generate_question(self, context: str, exchanges: list[dict[str, str]]) -> str:
        """Generate next interview question using Claude.

        Args:
            context: Episode context
            exchanges: Previous Q&A exchanges

        Returns:
            Generated question text
        """
        # Build system prompt (reflective template, hardcoded)
        system_prompt = """You are conducting a thoughtful interview to help someone \
reflect on a podcast episode they listened to.

Your role:
- Ask open-ended questions that encourage deep reflection
- Build on previous responses to go deeper
- Help them connect the episode to their own experiences and thoughts
- Keep questions concise and focused

Guidelines:
- One question at a time
- Make it personal and reflective
- Avoid yes/no questions
- Build on what they've already shared"""

        # Build user prompt
        user_parts = [context, ""]

        if exchanges:
            user_parts.append("Previous conversation:")
            for ex in exchanges[-3:]:  # Last 3 exchanges for context
                user_parts.append(f"Q: {ex['question']}")
                user_parts.append(f"A: {ex['response']}")
                user_parts.append("")

        user_parts.append(
            "Generate the next thought-provoking question. Ask ONE question only, no preamble."
        )

        user_prompt = "\n".join(user_parts)

        # Call Claude
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=200,
            temperature=0.7,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Track costs
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        self.total_tokens += input_tokens + output_tokens

        # Calculate cost (Claude Sonnet 4.5 pricing)
        cost = (input_tokens / 1_000_000 * 3.00) + (output_tokens / 1_000_000 * 15.00)
        self.total_cost += cost

        # Track in CostTracker if available
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                provider="claude",
                model=self.model,
                operation="interview",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        return response.content[0].text.strip()

    def _format_markdown(
        self,
        episode_title: str,
        podcast_name: str,
        exchanges: list[dict[str, str]],
    ) -> str:
        """Format interview as markdown.

        Args:
            episode_title: Episode title
            podcast_name: Podcast name
            exchanges: Q&A exchanges

        Returns:
            Formatted markdown string
        """
        lines = [
            f"# My Notes: {episode_title}",
            "",
            f"**Podcast:** {podcast_name}",
            "",
            "## Interview Reflections",
            "",
        ]

        for i, ex in enumerate(exchanges, 1):
            lines.append(f"### Q{i}: {ex['question']}")
            lines.append("")
            lines.append(ex["response"])
            lines.append("")

        return "\n".join(lines)

    def _display_welcome(self, episode_title: str, podcast_name: str, max_questions: int) -> None:
        """Display welcome message.

        Args:
            episode_title: Episode title
            podcast_name: Podcast name
            max_questions: Max number of questions
        """
        self.console.print("\n[bold cyan]Interview Mode[/bold cyan]")
        self.console.print(f"[dim]Podcast:[/dim] {podcast_name}")
        self.console.print(f"[dim]Episode:[/dim] {episode_title}")
        self.console.print(f"[dim]I'll ask up to {max_questions} reflection questions.[/dim]\n")

    def _display_completion(self, questions_answered: int, max_questions: int) -> None:
        """Display completion message.

        Args:
            questions_answered: Number of questions answered
            max_questions: Maximum questions
        """
        self.console.print(
            f"\n[bold green]Interview complete![/bold green] "
            f"({questions_answered}/{max_questions} questions)"
        )
        self.console.print(
            f"[dim]Total cost: ${self.total_cost:.4f} ({self.total_tokens:,} tokens)[/dim]"
        )


async def conduct_interview_from_output(
    output_dir: Path,
    episode_title: str,
    podcast_name: str,
    api_key: str,
    max_questions: int = 5,
    cost_tracker: CostTracker | None = None,
) -> SimpleInterviewResult:
    """Convenience function to conduct interview from episode output directory.

    Loads content from output files (summary.md, quotes.md, key-concepts.md)
    and conducts interview.

    Args:
        output_dir: Directory containing episode output files
        episode_title: Episode title
        podcast_name: Podcast name
        api_key: Anthropic API key
        max_questions: Maximum number of questions (default: 5)
        cost_tracker: Optional cost tracker

    Returns:
        SimpleInterviewResult with transcript, exchanges, and cost info

    Raises:
        FileNotFoundError: If output directory or required files don't exist
    """
    # Load summary
    summary_path = output_dir / "summary.md"
    summary = summary_path.read_text() if summary_path.exists() else ""

    # Load quotes
    quotes: list[str] = []
    quotes_path = output_dir / "quotes.md"
    if quotes_path.exists():
        content = quotes_path.read_text()
        # Extract quote text (simple parsing - look for lines starting with >)
        quotes = [
            line.strip(">\t ").strip()
            for line in content.split("\n")
            if line.strip().startswith(">")
        ]

    # Load concepts
    concepts: list[str] = []
    concepts_path = output_dir / "key-concepts.md"
    if concepts_path.exists():
        content = concepts_path.read_text()
        # Extract concept names (simple parsing - look for lines starting with ##)
        concepts = [
            line.strip("#\t ").strip()
            for line in content.split("\n")
            if line.strip().startswith("##") and not line.strip().startswith("###")
        ]

    # Conduct interview
    interviewer = SimpleInterviewer(api_key=api_key, cost_tracker=cost_tracker)
    return await interviewer.conduct_interview(
        episode_title=episode_title,
        podcast_name=podcast_name,
        summary=summary,
        key_quotes=quotes,
        key_concepts=concepts,
        max_questions=max_questions,
    )
