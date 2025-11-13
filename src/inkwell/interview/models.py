"""Interview data models for conversation state and session management."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from inkwell.utils.datetime import now_utc


class InterviewGuidelines(BaseModel):
    """User's interview preferences and guidelines."""

    content: str  # Freeform guidelines text
    focus_areas: list[str] = Field(default_factory=list)  # e.g., ["work-applications"]
    question_style: Literal["open-ended", "specific", "mixed"] = "open-ended"
    depth_preference: Literal["shallow", "moderate", "deep"] = "moderate"


class InterviewTemplate(BaseModel):
    """Template for interview style (reflective, analytical, creative)."""

    name: str  # e.g., "reflective", "analytical"
    description: str

    # System prompt defines interview character and approach
    system_prompt: str

    # Guidance for different question types
    initial_question_prompt: str
    follow_up_prompt: str
    conclusion_prompt: str

    # Interview parameters
    target_questions: int = 5
    max_depth: int = 3
    temperature: float = 0.7

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure template name is alphanumeric."""
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"Template name must be alphanumeric: {v}")
        return v


class Question(BaseModel):
    """A single interview question."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    question_number: int  # 1-indexed
    depth_level: int = 0  # 0 = top-level, 1+ = follow-up depth
    parent_question_id: str | None = None
    generated_at: datetime = Field(default_factory=now_utc)
    context_used: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Ensure question is not empty."""
        if not v.strip():
            raise ValueError("Question text cannot be empty")
        return v.strip()

    @field_validator("question_number")
    @classmethod
    def validate_question_number(cls, v: int) -> int:
        """Ensure question number is positive."""
        if v < 1:
            raise ValueError("Question number must be >= 1")
        return v

    @field_validator("depth_level")
    @classmethod
    def validate_depth_level(cls, v: int) -> int:
        """Ensure depth level is non-negative."""
        if v < 0:
            raise ValueError("Depth level must be >= 0")
        return v


class Response(BaseModel):
    """User's response to a question."""

    question_id: str
    text: str
    word_count: int = 0
    responded_at: datetime = Field(default_factory=now_utc)
    thinking_time_seconds: float = 0.0

    def __init__(self, **data: Any) -> None:
        """Initialize and calculate word count."""
        super().__init__(**data)
        if not self.word_count:
            self.word_count = len(self.text.split())

    @property
    def is_substantive(self) -> bool:
        """Check if response is meaningful (not just 'skip' or empty)."""
        skip_words = {"skip", "pass", "next", "done", "quit"}
        return self.word_count >= 5 and self.text.strip().lower() not in skip_words

    @property
    def is_skip(self) -> bool:
        """Check if response is a skip command."""
        skip_words = {"skip", "pass", "next"}
        return self.text.strip().lower() in skip_words

    @property
    def is_exit(self) -> bool:
        """Check if response is an exit command."""
        exit_words = {"done", "quit", "exit", "finish", "end", "stop"}
        return self.text.strip().lower() in exit_words


class Exchange(BaseModel):
    """Question-response pair."""

    question: Question
    response: Response

    @property
    def depth_level(self) -> int:
        """Return depth level of this exchange."""
        return self.question.depth_level

    @property
    def is_substantive(self) -> bool:
        """Check if exchange has substantive response."""
        return self.response.is_substantive


class InterviewSession(BaseModel):
    """Complete interview session state."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    episode_url: str
    episode_title: str
    podcast_name: str

    # Session metadata
    started_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    completed_at: datetime | None = None

    # Session configuration
    template_name: str = "reflective"
    guidelines: InterviewGuidelines | None = None
    max_questions: int = 5

    @field_validator("started_at", "updated_at", "completed_at", mode="before")
    @classmethod
    def ensure_timezone_aware_timestamps(cls, v: datetime | None) -> datetime | None:
        """Ensure all timestamps are timezone-aware."""
        if v is None:
            return None
        if isinstance(v, datetime) and v.tzinfo is None:
            # Assume UTC for naive datetimes during deserialization
            return v.replace(tzinfo=timezone.utc)
        return v

    # Conversation state
    exchanges: list[Exchange] = Field(default_factory=list)
    current_question_number: int = 0
    status: Literal["active", "paused", "completed", "abandoned"] = "active"

    # Context (summary of extracted content)
    extracted_content_summary: dict[str, Any] = Field(default_factory=dict)

    # Metrics
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0

    @property
    def question_count(self) -> int:
        """Return number of questions asked."""
        return len(self.exchanges)

    @property
    def substantive_response_count(self) -> int:
        """Return number of substantive responses."""
        return sum(1 for e in self.exchanges if e.response.is_substantive)

    @property
    def average_response_length(self) -> float:
        """Return average response length in words."""
        if not self.exchanges:
            return 0.0
        return sum(e.response.word_count for e in self.exchanges) / len(self.exchanges)

    @property
    def total_thinking_time(self) -> float:
        """Return total thinking time in seconds."""
        return sum(e.response.thinking_time_seconds for e in self.exchanges)

    @property
    def is_complete(self) -> bool:
        """Check if session is completed."""
        return self.status == "completed"

    @property
    def duration(self) -> timedelta:
        """Return session duration."""
        end = self.completed_at if self.completed_at else now_utc()
        return end - self.started_at

    def mark_updated(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = now_utc()

    def add_exchange(self, question: Question, response: Response) -> None:
        """Add a question-response exchange to the session."""
        exchange = Exchange(question=question, response=response)
        self.exchanges.append(exchange)
        self.current_question_number = question.question_number
        self.mark_updated()

    def complete(self) -> None:
        """Mark session as completed."""
        self.status = "completed"
        self.completed_at = now_utc()
        self.mark_updated()

    def pause(self) -> None:
        """Mark session as paused."""
        self.status = "paused"
        self.mark_updated()

    def resume(self) -> None:
        """Resume a paused session."""
        if self.status == "paused":
            self.status = "active"
            self.mark_updated()

    def abandon(self) -> None:
        """Mark session as abandoned."""
        self.status = "abandoned"
        self.mark_updated()


class InterviewContext(BaseModel):
    """Context provided to LLM for interview question generation."""

    # Episode information
    podcast_name: str
    episode_title: str
    episode_url: str
    duration_minutes: float

    # Extracted content (from Phase 3)
    summary: str
    key_quotes: list[dict[str, Any]] = Field(default_factory=list)
    key_concepts: list[str] = Field(default_factory=list)
    additional_extractions: dict[str, Any] = Field(default_factory=dict)

    # User context
    guidelines: InterviewGuidelines | None = None
    previous_interviews: list[str] = Field(default_factory=list)

    # Session context
    questions_asked: int = 0
    max_questions: int = 5
    depth_level: int = 0

    def to_prompt_context(self) -> str:
        """Convert to string suitable for LLM context."""
        context_parts = [
            f"# Episode: {self.episode_title}",
            f"Podcast: {self.podcast_name}",
            f"Duration: {self.duration_minutes:.0f} minutes",
            "",
            "## Summary",
            self.summary,
        ]

        if self.key_quotes:
            context_parts.extend(["", "## Notable Quotes"])
            for quote in self.key_quotes[:5]:  # Top 5 quotes
                quote_text = quote.get("text", "")
                context_parts.append(f"- \"{quote_text}\"")

        if self.key_concepts:
            context_parts.extend(["", "## Key Concepts"])
            context_parts.extend([f"- {concept}" for concept in self.key_concepts])

        if self.previous_interviews:
            context_parts.extend(["", "## Previous Interview Sessions", ""])
            for i, session_summary in enumerate(self.previous_interviews, 1):
                context_parts.append(session_summary)
                if i < len(self.previous_interviews):
                    context_parts.append("")  # Add blank line between sessions

        if self.guidelines:
            context_parts.extend(
                ["", "## User's Interview Guidelines", self.guidelines.content]
            )

        return "\n".join(context_parts)


class InterviewResult(BaseModel):
    """Result of completed interview."""

    session: InterviewSession

    # Generated content
    formatted_transcript: str
    key_insights: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)

    # Output files
    output_file: Path | None = None  # my-notes.md
    raw_transcript_file: Path | None = None  # session JSON

    # Quality metrics
    quality_score: float | None = None  # 0-1 score
    quality_notes: list[str] = Field(default_factory=list)

    @property
    def word_count(self) -> int:
        """Return total word count from all responses."""
        return sum(e.response.word_count for e in self.session.exchanges)

    @property
    def duration_minutes(self) -> float:
        """Return session duration in minutes."""
        if not self.session.completed_at:
            return 0.0
        delta = self.session.completed_at - self.session.started_at
        return delta.total_seconds() / 60.0
