"""Interview orchestrator that coordinates the entire interview flow.

This module integrates all interview components (context, agent, session, UI, formatter)
to provide a complete interview experience.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from inkwell.interview.agent import InterviewAgent
from inkwell.interview.context_builder import InterviewContextBuilder
from inkwell.interview.formatter import FormatStyle, TranscriptFormatter
from inkwell.interview.models import (
    InterviewContext,
    InterviewGuidelines,
    InterviewResult,
    InterviewSession,
    Response,
)
from inkwell.interview.session_manager import SessionManager
from inkwell.interview.templates import get_template
from inkwell.interview.ui import (
    ProcessingIndicator,
    UserCommand,
    confirm_action,
    display_completion_summary,
    display_info,
    display_pause_message,
    display_question,
    display_thinking,
    display_welcome,
    get_multiline_input,
)
from inkwell.output.models import EpisodeOutput

logger = logging.getLogger(__name__)


class InterviewManager:
    """Orchestrate complete interview flow from start to finish."""

    def __init__(
        self,
        api_key: str | None = None,
        session_dir: Path | None = None,
        model: str = "claude-sonnet-4-5",
    ):
        """Initialize interview manager.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            session_dir: Directory for session storage (defaults to XDG)
            model: Claude model to use
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required (ANTHROPIC_API_KEY env var or parameter)")

        self.session_manager = SessionManager(session_dir=session_dir)
        self.context_builder = InterviewContextBuilder()
        self.model = model

    async def conduct_interview(
        self,
        episode_url: str,
        episode_title: str,
        podcast_name: str,
        output_dir: Path,
        template_name: str = "reflective",
        max_questions: int = 5,
        guidelines: InterviewGuidelines | None = None,
        format_style: FormatStyle = "structured",
        resume_session_id: str | None = None,
    ) -> InterviewResult:
        """Conduct complete interview for an episode.

        Args:
            episode_url: URL of the episode
            episode_title: Title of the episode
            podcast_name: Name of the podcast
            output_dir: Directory containing Phase 3 output
            template_name: Interview template (reflective, analytical, creative)
            max_questions: Target number of questions
            guidelines: Optional user guidelines
            format_style: Transcript format style
            resume_session_id: Optional session ID to resume

        Returns:
            InterviewResult with transcript and extractions

        Example:
            >>> manager = InterviewManager()
            >>> result = await manager.conduct_interview(
            ...     episode_url="https://example.com/ep1",
            ...     episode_title="The Future of AI",
            ...     podcast_name="Tech Talks",
            ...     output_dir=Path("output/tech-talks-2025-11-08-future-of-ai"),
            ...     template_name="reflective",
            ... )
        """
        # Resume or create new session
        if resume_session_id:
            session = self._resume_session(resume_session_id)
        else:
            # Check for existing resumable session
            existing = self.session_manager.find_resumable_session(episode_url)
            if existing:
                session_preview = existing.session_id[:8]
                message = (
                    f"Found existing interview for this episode (Session: {session_preview}...). "
                    "Resume it?"
                )
                should_resume = confirm_action(message, default=True)
                session = existing if should_resume else None
            else:
                session = None

            # Create new if not resuming
            if not session:
                session = self.session_manager.create_session(
                    episode_url=episode_url,
                    episode_title=episode_title,
                    podcast_name=podcast_name,
                    template_name=template_name,
                    max_questions=max_questions,
                    guidelines=guidelines,
                )

        # Build context from Phase 3 output
        with ProcessingIndicator("Building interview context..."):
            context = self._build_context_from_output(
                output_dir=output_dir,
                episode_url=episode_url,
                episode_title=episode_title,
                podcast_name=podcast_name,
                guidelines=guidelines,
                max_questions=max_questions,
            )

        # Create agent
        agent = InterviewAgent(
            api_key=self.api_key,
            model=self.model,
            temperature=get_template(template_name).temperature,
        )
        agent.set_system_prompt(get_template(template_name).system_prompt)

        # Display welcome
        display_welcome(
            episode_title=episode_title,
            podcast_name=podcast_name,
            template_name=template_name,
            max_questions=max_questions,
        )

        # Run interview loop
        try:
            await self._interview_loop(agent, context, session, template_name)
        except KeyboardInterrupt:
            # User pressed Ctrl-C during interview
            if confirm_action("Pause this interview?", default=True):
                session.pause()
                self.session_manager.save_session(session)
                display_pause_message(session)
                # Return partial result
                return self._create_partial_result(session, output_dir, format_style)
            else:
                # User wants to continue, but we're in a bad state
                # Save and exit gracefully
                self.session_manager.save_session(session)
                raise

        # Mark session as completed
        session.complete()
        self.session_manager.save_session(session)

        # Format transcript
        with ProcessingIndicator("Formatting transcript..."):
            result = self._format_transcript(session, output_dir, format_style)

        # Display completion
        display_completion_summary(session, result.output_file)

        return result

    async def resume_interview(
        self,
        session_id: str,
        output_dir: Path | None = None,
        format_style: FormatStyle = "structured",
    ) -> InterviewResult:
        """Resume a paused interview session.

        Args:
            session_id: Session ID to resume
            output_dir: Output directory (inferred if not provided)
            format_style: Transcript format style

        Returns:
            InterviewResult with transcript

        Raises:
            FileNotFoundError: If session not found
            ValueError: If session is not resumable (completed/abandoned)
        """
        session = self.session_manager.load_session(session_id)

        if session.status not in ["active", "paused"]:
            raise ValueError(
                f"Cannot resume {session.status} session. "
                "Only active/paused sessions can be resumed."
            )

        # Infer output directory if not provided
        if not output_dir:
            # Construct from episode info
            # Format: podcast-name-YYYY-MM-DD-episode-title
            date_str = session.started_at.strftime("%Y-%m-%d")
            safe_podcast = session.podcast_name.lower().replace(" ", "-")
            safe_title = session.episode_title.lower().replace(" ", "-")
            dir_name = f"{safe_podcast}-{date_str}-{safe_title}"
            output_dir = Path("output") / dir_name

        # Resume session
        session.resume()
        self.session_manager.save_session(session)

        # Build context (will be from cached extracted content)
        with ProcessingIndicator("Loading interview context..."):
            context = self._build_context_from_output(
                output_dir=output_dir,
                episode_url=session.episode_url,
                episode_title=session.episode_title,
                podcast_name=session.podcast_name,
                guidelines=session.guidelines,
                max_questions=session.max_questions,
            )

        # Create agent
        template = get_template(session.template_name)
        agent = InterviewAgent(
            api_key=self.api_key,
            model=self.model,
            temperature=template.temperature,
        )
        agent.set_system_prompt(template.system_prompt)

        # Show resume info
        display_info(
            f"Resuming interview for '{session.episode_title}'\n"
            f"Questions answered so far: {session.question_count}",
            title="Resume Interview",
        )

        # Continue interview loop
        try:
            await self._interview_loop(agent, context, session, session.template_name)
        except KeyboardInterrupt:
            if confirm_action("Pause again?", default=True):
                session.pause()
                self.session_manager.save_session(session)
                display_pause_message(session)
                return self._create_partial_result(session, output_dir, "structured")
            else:
                self.session_manager.save_session(session)
                raise

        # Complete
        session.complete()
        self.session_manager.save_session(session)

        # Format
        with ProcessingIndicator("Formatting transcript..."):
            result = self._format_transcript(session, output_dir, format_style)

        display_completion_summary(session, result.output_file)

        return result

    def list_sessions(
        self,
        episode_url: str | None = None,
        podcast_name: str | None = None,
        status: str | None = None,
    ) -> list[InterviewSession]:
        """List interview sessions.

        Args:
            episode_url: Filter by episode URL
            podcast_name: Filter by podcast name
            status: Filter by status

        Returns:
            List of matching sessions
        """
        return self.session_manager.list_sessions(
            episode_url=episode_url,
            podcast_name=podcast_name,
            status=status,
        )

    async def _interview_loop(
        self,
        agent: InterviewAgent,
        context: InterviewContext,
        session: InterviewSession,
        template_name: str,
    ) -> None:
        """Run the main interview question/response loop.

        Args:
            agent: Interview agent for question generation
            context: Episode context
            session: Current session
            template_name: Template name for prompts
        """
        template = get_template(template_name)

        while session.question_count < session.max_questions:
            # Generate question
            with ProcessingIndicator("Generating question..."):
                if session.question_count == 0:
                    # First question
                    prompt = template.initial_question_prompt
                else:
                    prompt = template.initial_question_prompt  # Regular question

                question = await agent.generate_question(context, session, prompt)

            # Display question
            display_question(
                question_number=question.question_number,
                total_questions=session.max_questions,
                question_text=question.text,
                is_follow_up=(question.depth_level > 0),
            )

            # Get user response
            response_text = get_multiline_input()

            # Handle special commands
            if response_text is None:
                # User cancelled (Ctrl-C handled in outer try/except)
                break

            if response_text == UserCommand.DONE or response_text == UserCommand.QUIT:
                # User wants to end early
                break

            if response_text == UserCommand.SKIP:
                # Skip this question (don't add exchange)
                continue

            if response_text == UserCommand.HELP:
                from inkwell.interview.ui import display_help

                display_help()
                # Re-ask the same question
                continue

            # Create response
            response = Response(
                question_id=question.id,
                text=response_text,
                thinking_time_seconds=0.0,  # Not tracking for now
            )

            # Add exchange
            session.add_exchange(question, response)

            # Save session after each exchange
            self.session_manager.save_session(session)

            # Check if should generate follow-up
            if response.is_substantive and question.depth_level < template.max_depth:
                should_follow_up = len(response_text.split()) >= 10  # Heuristic
                if should_follow_up:
                    display_thinking("Interesting response. Let me dig deeper...")

                    # Generate follow-up
                    with ProcessingIndicator("Generating follow-up..."):
                        follow_up = await agent.generate_follow_up(
                            question=question,
                            response_text=response_text,
                            context=context,
                            template_prompt=template.follow_up_prompt,
                        )

                    if follow_up:
                        # Display follow-up
                        display_question(
                            question_number=follow_up.question_number,
                            total_questions=session.max_questions,
                            question_text=follow_up.text,
                            is_follow_up=True,
                        )

                        # Get follow-up response
                        follow_up_response_text = get_multiline_input()

                        # Handle commands
                        if follow_up_response_text is None:
                            break
                        if follow_up_response_text in [UserCommand.DONE, UserCommand.QUIT]:
                            break
                        if follow_up_response_text == UserCommand.SKIP:
                            continue

                        # Create follow-up response
                        follow_up_response = Response(
                            question_id=follow_up.id,
                            text=follow_up_response_text,
                        )

                        # Add follow-up exchange
                        session.add_exchange(follow_up, follow_up_response)
                        self.session_manager.save_session(session)

            # Update context with progress
            context.questions_asked = session.question_count

    def _build_context_from_output(
        self,
        output_dir: Path,
        episode_url: str,
        episode_title: str,
        podcast_name: str,
        guidelines: InterviewGuidelines | None,
        max_questions: int,
    ) -> InterviewContext:
        """Build interview context from Phase 3 output directory.

        Loads episode output files (summary.md, quotes.md, key-concepts.md, etc.)
        and extracts content to build rich interview context.

        Args:
            output_dir: Directory containing extracted content
            episode_url: Episode URL
            episode_title: Episode title
            podcast_name: Podcast name
            guidelines: User guidelines
            max_questions: Max questions

        Returns:
            InterviewContext ready for agent with actual episode content
        """
        try:
            # Load episode output from directory
            episode_output = EpisodeOutput.from_directory(output_dir)

            # Use context builder to extract content from files
            context = self.context_builder.build_context(
                episode_output=episode_output,
                guidelines=guidelines,
                max_questions=max_questions,
            )

            return context

        except FileNotFoundError as e:
            # Output files don't exist yet - return minimal context
            logger.warning(
                f"Episode output not found at {output_dir}, using minimal context: {e}"
            )
            return InterviewContext(
                podcast_name=podcast_name,
                episode_title=episode_title,
                episode_url=episode_url,
                duration_minutes=0.0,  # Unknown duration
                summary=f"Episode: {episode_title}",
                key_quotes=[],
                key_concepts=[],
                guidelines=guidelines,
                max_questions=max_questions,
            )

        except Exception as e:
            # Other error - log and return minimal context
            logger.error(f"Failed to build context from output: {e}", exc_info=True)
            return InterviewContext(
                podcast_name=podcast_name,
                episode_title=episode_title,
                episode_url=episode_url,
                duration_minutes=0.0,  # Unknown duration
                summary=f"Episode: {episode_title}",
                key_quotes=[],
                key_concepts=[],
                guidelines=guidelines,
                max_questions=max_questions,
            )

    def _format_transcript(
        self,
        session: InterviewSession,
        output_dir: Path,
        format_style: FormatStyle,
    ) -> InterviewResult:
        """Format interview transcript.

        Args:
            session: Completed session
            output_dir: Output directory
            format_style: Format style

        Returns:
            InterviewResult with formatted transcript
        """
        formatter = TranscriptFormatter(format_style=format_style)
        result = formatter.format_session(
            session,
            extract_insights=True,
            extract_actions=True,
            extract_themes=True,
        )

        # Save transcript
        formatter.save_transcript(result, output_dir, filename="my-notes.md")

        return result

    def _create_partial_result(
        self,
        session: InterviewSession,
        output_dir: Path,
        format_style: FormatStyle,
    ) -> InterviewResult:
        """Create partial result for paused interview.

        Args:
            session: Paused session
            output_dir: Output directory
            format_style: Format style

        Returns:
            InterviewResult (without saving)
        """
        formatter = TranscriptFormatter(format_style=format_style)
        result = formatter.format_session(
            session,
            extract_insights=True,
            extract_actions=True,
            extract_themes=True,
        )
        return result

    def _resume_session(self, session_id: str) -> InterviewSession:
        """Load and validate session for resume.

        Args:
            session_id: Session ID

        Returns:
            Loaded session

        Raises:
            FileNotFoundError: If session not found
            ValueError: If session not resumable
        """
        session = self.session_manager.load_session(session_id)

        if session.status not in ["active", "paused"]:
            raise ValueError(
                f"Cannot resume {session.status} session. "
                "Only active/paused sessions can be resumed."
            )

        session.resume()
        return session
