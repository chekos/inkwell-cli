"""Claude Agent wrapper for interview question generation.

Provides async interface to Claude API for generating interview questions,
follow-ups, and handling streaming responses.
"""

from collections.abc import AsyncIterator
from uuid import uuid4

from anthropic import AsyncAnthropic
from anthropic.types import Usage

from .models import InterviewContext, InterviewSession, Question


class InterviewAgent:
    """Wrapper around Claude API for interview question generation.

    Handles question generation, follow-ups, streaming responses,
    and token/cost tracking.

    Example:
        >>> agent = InterviewAgent(api_key="sk-...")
        >>> agent.set_system_prompt(template.system_prompt)
        >>> question = await agent.generate_question(
        ...     context=context,
        ...     session=session,
        ...     template_prompt=template.initial_question_prompt
        ... )
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        temperature: float = 0.7,
    ):
        """Initialize the interview agent.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            temperature: Sampling temperature (0.0-1.0)
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.system_prompt = ""

    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt for the agent.

        Args:
            prompt: System prompt defining agent behavior
        """
        self.system_prompt = prompt

    async def generate_question(
        self,
        context: InterviewContext,
        session: InterviewSession,
        template_prompt: str,
    ) -> Question:
        """Generate next interview question.

        Args:
            context: Episode context with extracted content
            session: Current interview session
            template_prompt: Template-specific prompt for question generation

        Returns:
            Generated Question object
        """
        # Build prompt for question generation
        user_prompt = self._build_question_prompt(
            context,
            session,
            template_prompt,
        )

        # Call Claude
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            temperature=self.temperature,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract question text
        question_text = response.content[0].text.strip()

        # Create Question object
        question = Question(
            id=str(uuid4()),
            text=question_text,
            question_number=session.current_question_number + 1,
            depth_level=context.depth_level,
            context_used={
                "has_summary": bool(context.summary),
                "quote_count": len(context.key_quotes),
                "concept_count": len(context.key_concepts),
            },
        )

        # Track tokens/cost
        session.total_tokens_used += (
            response.usage.input_tokens + response.usage.output_tokens
        )
        session.total_cost_usd += self._calculate_cost(response.usage)

        return question

    async def generate_follow_up(
        self,
        question: Question,
        response_text: str,
        context: InterviewContext,
        template_prompt: str,
        max_depth: int = 2,
    ) -> Question | None:
        """Generate follow-up question based on user's response.

        Args:
            question: Original question
            response_text: User's response text
            context: Interview context
            template_prompt: Template-specific follow-up prompt
            max_depth: Maximum depth level for follow-ups

        Returns:
            Follow-up Question if warranted, None otherwise
        """
        # Decide if follow-up is warranted
        if question.depth_level >= max_depth:  # Max depth reached
            return None

        if len(response_text.split()) < 10:  # Response too brief
            return None

        # Build follow-up prompt
        user_prompt = f"""Based on this exchange:

Question: {question.text}
User Response: {response_text}

{template_prompt}

Generate a thoughtful follow-up question that goes deeper into their response.
Keep it concise and open-ended."""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            temperature=self.temperature,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        follow_up_text = response.content[0].text.strip()

        follow_up = Question(
            id=str(uuid4()),
            text=follow_up_text,
            question_number=question.question_number,  # Same number, but deeper
            depth_level=question.depth_level + 1,
            parent_question_id=question.id,
        )

        return follow_up

    async def stream_question(
        self,
        context: InterviewContext,
        session: InterviewSession,
        template_prompt: str,
    ) -> AsyncIterator[str]:
        """Generate question with streaming response.

        Yields text chunks as they arrive from the API.

        Args:
            context: Episode context
            session: Current session
            template_prompt: Template prompt

        Yields:
            Text chunks as they arrive
        """
        user_prompt = self._build_question_prompt(
            context,
            session,
            template_prompt,
        )

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=500,
            temperature=self.temperature,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def _build_question_prompt(
        self,
        context: InterviewContext,
        session: InterviewSession,
        template_prompt: str,
    ) -> str:
        """Build prompt for question generation.

        Args:
            context: Episode context
            session: Current session
            template_prompt: Template-specific prompt

        Returns:
            Complete prompt for question generation
        """
        # Include episode context
        prompt_parts = [context.to_prompt_context(), ""]

        # Include previous questions to avoid repetition
        if session.exchanges:
            prompt_parts.append("## Previous Questions Asked:")
            for exchange in session.exchanges[-3:]:  # Last 3
                prompt_parts.append(f"- {exchange.question.text}")
            prompt_parts.append("")

        # Add template-specific instructions
        prompt_parts.append(template_prompt)

        # Add progress context
        q_num = session.question_count + 1
        prompt_parts.append(
            f"\nThis is question {q_num} of approximately {context.max_questions}."
        )

        return "\n".join(prompt_parts)

    def _calculate_cost(self, usage: Usage) -> float:
        """Calculate cost based on token usage.

        Uses Claude Sonnet 4.5 pricing as of November 2024.

        Args:
            usage: Token usage from API response

        Returns:
            Cost in USD
        """
        # Claude Sonnet 4.5 pricing (as of Nov 2024)
        input_cost_per_million = 3.00
        output_cost_per_million = 15.00

        input_cost = (usage.input_tokens / 1_000_000) * input_cost_per_million
        output_cost = (usage.output_tokens / 1_000_000) * output_cost_per_million

        return input_cost + output_cost
