# Phase 4 Detailed Implementation Plan - Interview Mode

**Date**: 2025-11-08
**Status**: Planning
**Phase**: 4 of 5
**Related**: [PRD_v0.md](../PRD_v0.md), [Phase 3 Complete](../PHASE_3_COMPLETE.md)

## Overview

Phase 4 adds the **Interview Mode** to Inkwell, transforming passive note consumption into active knowledge building through interactive conversation. This is the differentiating feature that sets Inkwell apart—enabling users to capture not just *what was said* but *what they thought about it*.

After Phase 3's extraction pipeline generates structured notes, Phase 4 allows users to engage in a thoughtful conversation about the episode, guided by Claude. The system generates contextual questions based on extracted content, conducts a natural terminal-based interview, and saves the conversation as `my-notes.md`.

**Key Principle**: After each unit of work, we pause to document lessons learned, experiments, research, and architectural decisions. Documentation is not an afterthought—it's an integral part of our development process that ensures accessibility and maintainability.

---

## Phase 4 Scope (from PRD)

**Core Requirements:**
- Claude Agent SDK integration for conversational AI
- Context-aware question generation based on extracted content
- Terminal-based streaming interview interface
- Conversation state management and history
- Interview transcript formatting and saving
- Graceful exit and resume capabilities

**Professional Grade Additions:**
- Interview customization (question count, focus areas, depth)
- Multi-session interview support (pause/resume)
- Interview quality assessment and validation
- Rich terminal UI with conversation history view
- Interview analytics and insights tracking
- Template-based interview styles (reflective, analytical, creative)
- Export interview in multiple formats
- Interview caching and versioning
- Smart question adaptation based on user responses

---

## Architecture Overview

### Interview Flow

```
Episode Processed (Phase 3 complete)
    │
    ├─► Prepare Interview Context
    │     │
    │     ├─► Load extracted content (summary, quotes, concepts)
    │     ├─► Load user interview guidelines from config
    │     ├─► Load interview template (if specified)
    │     ├─► Prepare episode metadata
    │     └─► Build initial context prompt
    │
    ├─► Initialize Interview Session
    │     │
    │     ├─► Create Claude Agent SDK client
    │     ├─► Load conversation history (if resuming)
    │     ├─► Set up terminal UI (Rich)
    │     ├─► Initialize conversation state
    │     └─► Display interview introduction
    │
    ├─► Conduct Interactive Interview
    │     │
    │     ├─► Generate contextual question
    │     ├─► Display question in terminal
    │     ├─► Await user response (multiline input)
    │     ├─► Stream Claude's follow-up/next question
    │     ├─► Save exchange to conversation history
    │     ├─► Check for exit conditions (user quit, max questions)
    │     └─► Loop until interview complete
    │
    ├─► Process Interview Transcript
    │     │
    │     ├─► Format conversation as markdown
    │     ├─► Extract key themes and insights
    │     ├─► Generate action items (if requested)
    │     ├─► Create structured sections
    │     └─► Validate interview quality
    │
    └─► Save Interview Output
          │
          ├─► Write my-notes.md to episode directory
          ├─► Update .metadata.yaml with interview info
          ├─► Save raw conversation JSON (for resume)
          ├─► Update cost tracking
          └─► Display completion summary
```

### Module Structure

```
src/inkwell/
├── interview/
│   ├── __init__.py
│   ├── models.py              # InterviewSession, Question, Response data models
│   ├── context.py             # Context preparation from extracted content
│   ├── agent.py               # Claude Agent SDK wrapper
│   ├── session.py             # Interview session management
│   ├── questions.py           # Question generation and adaptation
│   ├── formatter.py           # Interview transcript formatting
│   ├── templates/
│   │   ├── __init__.py
│   │   ├── base.py           # Base interview template
│   │   ├── reflective.py     # Deep reflection interview
│   │   ├── analytical.py     # Critical analysis interview
│   │   └── creative.py       # Creative connections interview
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── terminal.py       # Rich terminal interface
│   │   ├── prompts.py        # User input handling
│   │   └─��── display.py       # Conversation display
│   └── manager.py             # High-level interview orchestrator
├── cli.py                     # Add --interview flag to fetch command
└── config/
    └── models.py              # Add interview configuration
```

### Configuration Schema Extension

```yaml
# ~/.config/inkwell/config.yaml

# ... existing config ...

interview:
  # Interview behavior
  enabled: true
  auto_start: false  # If true, always interview (no --interview flag needed)

  # Interview style
  default_template: "reflective"  # reflective, analytical, creative, custom
  question_count: 5  # Target number of questions (flexible)
  max_depth: 3  # How deep to go on follow-ups

  # User preferences
  guidelines: |
    Ask about how this applies to my work in software engineering.
    Probe for connections to past episodes I've listened to.
    Ask what surprised me or challenged my thinking.
    Keep questions open-ended and thoughtful.
    Focus on actionable insights.

  # Session management
  save_raw_transcript: true  # Save JSON for resume
  resume_enabled: true
  session_timeout_minutes: 60

  # Output preferences
  include_action_items: true
  include_key_insights: true
  format_style: "structured"  # structured, narrative, qa

  # Cost controls
  max_cost_per_interview: 0.50  # USD
  confirm_high_cost: true  # Prompt if estimated cost > threshold

  # Advanced
  model: "claude-sonnet-4-5"  # Override default model
  temperature: 0.7  # Creativity level
  streaming: true  # Stream responses in real-time
```

---

## Detailed Implementation Plan

### Unit 1: Research & Architecture Decision Making

**Duration**: 4-5 hours
**Goal**: Make informed decisions about Claude Agent SDK, interview patterns, and UX design

#### Tasks:

1. **Research Claude Agent SDK**
   - Review official documentation and examples
   - Test basic agent creation and conversation
   - Understand context management and memory
   - Test streaming response handling
   - Identify rate limits and cost implications
   - Document error scenarios and handling

2. **Research Interview Conversation Patterns**
   - Study effective interview question structures
   - Research conversation depth vs breadth tradeoffs
   - Evaluate question adaptation strategies
   - Test different prompting approaches for question generation
   - Research conversation exit and completion detection
   - Document best practices for contextual interviews

3. **Research Terminal UI Patterns**
   - Review Rich library capabilities for interactive UIs
   - Test multiline input collection methods
   - Evaluate conversation display patterns (chat-style, threaded)
   - Research progress indicators for streaming responses
   - Test conversation history display
   - Document accessibility considerations

4. **Research Conversation State Management**
   - Evaluate state persistence strategies (JSON, SQLite, pickle)
   - Test session resume capabilities
   - Research conversation versioning
   - Evaluate multi-session interview patterns
   - Test state recovery from interruptions
   - Document state consistency requirements

5. **Research Interview Quality Metrics**
   - Define what makes a "good" interview
   - Research conversation depth metrics
   - Evaluate insight extraction patterns
   - Test action item detection
   - Research user satisfaction indicators
   - Document quality assessment approach

#### Documentation Tasks:

**Create Research Document**: `docs/research/claude-agent-sdk-integration.md`
- Claude Agent SDK capabilities and limitations
- Context management patterns
- Streaming implementation details
- Cost estimation formulas
- Error handling strategies
- Rate limiting considerations
- Best practices for conversational agents
- Comparison with direct API usage

**Create Research Document**: `docs/research/interview-conversation-design.md`
- Effective interview question patterns
- Question sequencing strategies
- Follow-up question generation
- Context awareness techniques
- Conversation depth management
- Exit detection patterns
- Quality indicators for interviews
- User engagement strategies

**Create Research Document**: `docs/research/terminal-interview-ux.md`
- Terminal UI patterns for conversation
- Multiline input handling
- Streaming response display
- Conversation history visualization
- Progress indicators
- Accessibility considerations
- Keyboard shortcuts and commands
- Error display and recovery

**Create ADR**: `docs/adr/020-interview-framework-selection.md`
- **Decision**: Use Claude Agent SDK for interview mode
- **Alternatives**: Direct Anthropic API, LangChain agents, custom state machine
- **Rationale**: Purpose-built for conversational AI, handles state management, streaming support
- **Consequences**: Additional dependency, SDK learning curve, tied to Anthropic ecosystem

**Create ADR**: `docs/adr/021-interview-state-persistence.md`
- **Decision**: JSON-based state persistence with resume capability
- **Alternatives**: SQLite, in-memory only, pickle, custom binary format
- **Rationale**: Human-readable, debuggable, version-control friendly, portable
- **Consequences**: File I/O overhead, JSON size limitations, schema versioning needs

**Create ADR**: `docs/adr/022-interview-ui-framework.md`
- **Decision**: Rich library for terminal UI with streaming support
- **Alternatives**: Prompt_toolkit, Textual, curses, plain print/input
- **Rationale**: Already a dependency, excellent streaming support, beautiful output
- **Consequences**: Terminal-only (no GUI), requires modern terminal

**Create ADR**: `docs/adr/023-interview-template-system.md`
- **Decision**: Template-based interview styles (reflective, analytical, creative)
- **Alternatives**: Single interview style, fully custom per user, AI-determined style
- **Rationale**: Flexibility, user control, predictable experience, extensible
- **Consequences**: More templates to maintain, need template selection logic

**Create Devlog Entry**: `docs/devlog/2025-11-08-phase-4-unit-1-research.md`
- Document research findings
- Summarize key decisions
- Note surprises or gotchas discovered
- Link to research docs and ADRs
- Document experiment results
- Outline next steps

#### Experiments to Run:

**Create Experiment Log**: `docs/experiments/2025-11-08-claude-agent-sdk-streaming.md`
- Test streaming response latency and quality
- Compare streaming vs blocking for UX
- Measure token usage with different conversation lengths
- Test interruption and resume behavior
- Document optimal streaming chunk sizes
- Results inform streaming implementation

**Create Experiment Log**: `docs/experiments/2025-11-08-interview-question-quality.md`
- Generate questions with different prompting strategies
- Test zero-shot vs few-shot question generation
- Compare context-aware vs generic questions
- Evaluate question depth and relevance
- Test question adaptation based on responses
- Results inform question generation approach

**Create Experiment Log**: `docs/experiments/2025-11-08-terminal-multiline-input.md`
- Test different multiline input collection methods
- Compare Rich prompt vs custom input handler
- Test paste handling and text editing
- Evaluate user experience with different approaches
- Test signal handling (Ctrl+C, Ctrl+D)
- Results inform terminal UI implementation

#### Success Criteria:
- Claude Agent SDK integrated and tested
- Clear understanding of conversation patterns
- Terminal UI approach validated
- All ADRs created with rationale
- Research documents comprehensive
- Experiment results documented
- Ready to proceed with implementation

---

### Unit 2: Data Models & Interview Schema

**Duration**: 3-4 hours
**Goal**: Define type-safe models for interview system and conversation state

#### Tasks:

1. **Create Interview Models** (`interview/models.py`)
```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
from pathlib import Path

class InterviewGuidelines(BaseModel):
    """User's interview preferences and guidelines"""
    content: str  # Freeform guidelines text
    focus_areas: list[str] = Field(default_factory=list)  # e.g., ["work-applications", "connections"]
    question_style: Literal["open-ended", "specific", "mixed"] = "open-ended"
    depth_preference: Literal["shallow", "moderate", "deep"] = "moderate"

class InterviewTemplate(BaseModel):
    """Template for interview style"""
    name: str  # e.g., "reflective", "analytical"
    description: str
    system_prompt: str
    initial_question_prompt: str
    follow_up_prompt: str
    conclusion_prompt: str
    target_questions: int = 5
    max_depth: int = 3
    temperature: float = 0.7

class Question(BaseModel):
    """A single interview question"""
    id: str  # Unique question ID
    text: str
    question_number: int
    depth_level: int = 0  # 0 = top-level, 1+ = follow-up depth
    parent_question_id: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    context_used: dict = Field(default_factory=dict)  # What content informed this question

class Response(BaseModel):
    """User's response to a question"""
    question_id: str
    text: str
    word_count: int = 0
    responded_at: datetime = Field(default_factory=datetime.utcnow)
    thinking_time_seconds: float = 0.0

    @property
    def is_substantive(self) -> bool:
        """Check if response is meaningful (not just 'skip' or empty)"""
        return self.word_count >= 5 and self.text.strip().lower() not in ["skip", "pass", "next"]

class Exchange(BaseModel):
    """Question-response pair"""
    question: Question
    response: Response

    @property
    def depth_level(self) -> int:
        return self.question.depth_level

class InterviewSession(BaseModel):
    """Complete interview session state"""
    session_id: str
    episode_url: str
    episode_title: str
    podcast_name: str

    # Session metadata
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Session configuration
    template_name: str = "reflective"
    guidelines: Optional[InterviewGuidelines] = None
    max_questions: int = 5

    # Conversation state
    exchanges: list[Exchange] = Field(default_factory=list)
    current_question_number: int = 0
    status: Literal["active", "paused", "completed", "abandoned"] = "active"

    # Context
    extracted_content_summary: dict = Field(default_factory=dict)  # Key points from Phase 3

    # Metrics
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0

    @property
    def question_count(self) -> int:
        return len(self.exchanges)

    @property
    def substantive_response_count(self) -> int:
        return sum(1 for e in self.exchanges if e.response.is_substantive)

    @property
    def average_response_length(self) -> float:
        if not self.exchanges:
            return 0.0
        return sum(e.response.word_count for e in self.exchanges) / len(self.exchanges)

    @property
    def total_thinking_time(self) -> float:
        return sum(e.response.thinking_time_seconds for e in self.exchanges)

    @property
    def is_complete(self) -> bool:
        return self.status == "completed"

class InterviewResult(BaseModel):
    """Result of completed interview"""
    session: InterviewSession

    # Generated content
    formatted_transcript: str  # Markdown formatted interview
    key_insights: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)

    # Output files
    output_file: Optional[Path] = None  # my-notes.md
    raw_transcript_file: Optional[Path] = None  # session JSON

    # Quality metrics
    quality_score: Optional[float] = None  # 0-1 score
    quality_notes: list[str] = Field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(e.response.word_count for e in self.session.exchanges)

    @property
    def duration_minutes(self) -> float:
        if not self.session.completed_at:
            return 0.0
        delta = self.session.completed_at - self.session.started_at
        return delta.total_seconds() / 60.0
```

2. **Create Interview Context Model** (`interview/context.py` - model part)
```python
from pydantic import BaseModel, Field
from typing import Any

class InterviewContext(BaseModel):
    """Context provided to Claude Agent for interview"""
    # Episode information
    podcast_name: str
    episode_title: str
    episode_url: str
    duration_minutes: float

    # Extracted content (from Phase 3)
    summary: str
    key_quotes: list[dict] = Field(default_factory=list)  # {text, speaker, timestamp}
    key_concepts: list[str] = Field(default_factory=list)
    additional_extractions: dict[str, Any] = Field(default_factory=dict)  # tools, books, etc.

    # User context
    guidelines: Optional[InterviewGuidelines] = None
    previous_interviews: list[str] = Field(default_factory=list)  # For connection-making

    # Session context
    questions_asked: int = 0
    max_questions: int = 5
    depth_level: int = 0

    def to_prompt_context(self) -> str:
        """Convert to string suitable for LLM context"""
        context_parts = [
            f"# Episode: {self.episode_title}",
            f"Podcast: {self.podcast_name}",
            f"Duration: {self.duration_minutes:.0f} minutes",
            "",
            "## Summary",
            self.summary,
        ]

        if self.key_quotes:
            context_parts.extend([
                "",
                "## Notable Quotes",
            ])
            for quote in self.key_quotes[:5]:  # Top 5 quotes
                context_parts.append(f"- \"{quote.get('text', '')}\"")

        if self.key_concepts:
            context_parts.extend([
                "",
                "## Key Concepts",
            ])
            context_parts.extend([f"- {concept}" for concept in self.key_concepts])

        if self.guidelines:
            context_parts.extend([
                "",
                "## User's Interview Guidelines",
                self.guidelines.content,
            ])

        return "\n".join(context_parts)
```

3. **Create Interview Configuration Model** (extend `config/models.py`)
```python
class InterviewConfig(BaseModel):
    """Interview mode configuration"""
    enabled: bool = True
    auto_start: bool = False

    # Style
    default_template: str = "reflective"
    question_count: int = 5
    max_depth: int = 3

    # User preferences
    guidelines: str = ""

    # Session
    save_raw_transcript: bool = True
    resume_enabled: bool = True
    session_timeout_minutes: int = 60

    # Output
    include_action_items: bool = True
    include_key_insights: bool = True
    format_style: Literal["structured", "narrative", "qa"] = "structured"

    # Cost
    max_cost_per_interview: float = 0.50
    confirm_high_cost: bool = True

    # Advanced
    model: str = "claude-sonnet-4-5"
    temperature: float = 0.7
    streaming: bool = True
```

4. **Write Comprehensive Tests** (`tests/unit/test_interview_models.py`)
   - Test session state transitions
   - Test exchange creation and validation
   - Test response quality detection
   - Test session metrics calculation
   - Test context generation
   - Test edge cases (empty responses, long sessions)

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-08-phase-4-unit-2-data-models.md`
- Document model design decisions
- Explain session state machine
- Note challenges in modeling conversation state
- Document test coverage achieved
- Link to relevant code
- Discuss quality metrics rationale

**Create Research Document**: `docs/research/interview-quality-metrics.md`
- Define quality indicators for interviews
- Response substantiveness detection
- Conversation depth measurement
- Engagement metrics
- Actionable insights detection
- Best practices for quality assessment

**Update**: `CLAUDE.md` (if needed)
- Add conventions for interview module
- Document interview session patterns
- Note state management guidelines

#### Success Criteria:
- All models defined with comprehensive type hints
- Models validated with Pydantic
- Session state machine clear and testable
- 100% test coverage for model logic
- Clear documentation of model usage
- Devlog captures design decisions
- Quality metrics well-defined

---

### Unit 3: Interview Context Preparation

**Duration**: 3-4 hours
**Goal**: Build rich context from extracted content for intelligent question generation

#### Tasks:

1. **Implement Context Builder** (`interview/context.py`)
```python
from pathlib import Path
from typing import Optional
from inkwell.output.models import EpisodeOutput
from inkwell.extraction.models import ExtractedContent
from .models import InterviewContext, InterviewGuidelines

class InterviewContextBuilder:
    """Build interview context from extracted content"""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or self._get_config_dir()

    def build_context(
        self,
        episode_output: EpisodeOutput,
        guidelines: Optional[InterviewGuidelines] = None,
        max_questions: int = 5,
    ) -> InterviewContext:
        """Build interview context from episode output"""

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
        """Extract summary from output files"""
        summary_file = episode_output.get_file("summary")
        if summary_file:
            # Parse markdown and extract main content
            content = summary_file.content
            # Remove frontmatter and headers
            lines = content.split("\n")
            filtered_lines = []
            in_frontmatter = False
            for line in lines:
                if line.strip() == "---":
                    in_frontmatter = not in_frontmatter
                    continue
                if not in_frontmatter and not line.startswith("#"):
                    filtered_lines.append(line)
            return "\n".join(filtered_lines).strip()
        return ""

    def _extract_quotes(self, episode_output: EpisodeOutput) -> list[dict]:
        """Extract quotes from output files"""
        quotes_file = episode_output.get_file("quotes")
        if not quotes_file:
            return []

        # Parse quotes from markdown
        # Expected format:
        # > "Quote text"
        # > — Speaker [timestamp]

        quotes = []
        content = quotes_file.content
        lines = content.split("\n")

        current_quote = None
        for line in lines:
            if line.startswith(">") and '"' in line:
                # Extract quote text
                quote_text = line.strip("> ").strip('"')
                current_quote = {"text": quote_text}
            elif line.startswith(">") and "—" in line and current_quote:
                # Extract speaker and timestamp
                parts = line.strip("> — ").split("[")
                speaker = parts[0].strip()
                timestamp = ""
                if len(parts) > 1:
                    timestamp = parts[1].rstrip("]")

                current_quote["speaker"] = speaker
                current_quote["timestamp"] = timestamp
                quotes.append(current_quote)
                current_quote = None

        return quotes

    def _extract_concepts(self, episode_output: EpisodeOutput) -> list[str]:
        """Extract key concepts from output files"""
        concepts_file = episode_output.get_file("key-concepts")
        if not concepts_file:
            return []

        # Parse concepts from markdown (typically a list)
        concepts = []
        content = concepts_file.content
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                concept = line.lstrip("-*").strip()
                if concept and len(concept) > 3:  # Filter out very short items
                    concepts.append(concept)

        return concepts

    def _extract_additional_content(self, episode_output: EpisodeOutput) -> dict:
        """Extract any additional structured content (tools, books, etc.)"""
        additional = {}

        # Check for common additional templates
        for template_name in ["tools-mentioned", "books-mentioned", "people-mentioned"]:
            file = episode_output.get_file(template_name)
            if file:
                # Extract list items
                items = []
                lines = file.content.split("\n")
                for line in lines:
                    line = line.strip()
                    if line.startswith("-") or line.startswith("*"):
                        item = line.lstrip("-*").strip()
                        if item:
                            items.append(item)
                if items:
                    additional[template_name] = items

        return additional

    def _get_config_dir(self) -> Path:
        from inkwell.utils.paths import get_config_dir
        return get_config_dir()
```

2. **Implement Previous Interview Loader** (for connection-making)
```python
class PreviousInterviewLoader:
    """Load summaries of previous interviews for context"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def find_previous_interviews(
        self,
        podcast_name: Optional[str] = None,
        limit: int = 5,
    ) -> list[str]:
        """Find previous interviews for context"""

        # Find all episode directories with my-notes.md
        interview_summaries = []

        for episode_dir in self.output_dir.iterdir():
            if not episode_dir.is_dir():
                continue

            notes_file = episode_dir / "my-notes.md"
            if not notes_file.exists():
                continue

            # Filter by podcast if specified
            if podcast_name and podcast_name not in episode_dir.name:
                continue

            # Extract a brief summary (first few lines)
            content = notes_file.read_text()
            lines = [l for l in content.split("\n") if l.strip() and not l.startswith("#")]
            summary = " ".join(lines[:3])[:200] + "..."

            interview_summaries.append(f"- {episode_dir.name}: {summary}")

        # Return most recent
        return interview_summaries[-limit:]
```

3. **Write Comprehensive Tests** (`tests/unit/test_interview_context.py`)
   - Test context building from episode output
   - Test summary extraction
   - Test quote parsing
   - Test concept extraction
   - Test additional content extraction
   - Test previous interview loading
   - Test edge cases (missing files, malformed content)

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-08-phase-4-unit-3-context-preparation.md`
- Document context building approach
- Explain content extraction logic
- Show example contexts generated
- Document parsing strategies
- Note test coverage

**Create Lessons Learned**: `docs/lessons/2025-11-08-context-building.md`
- Markdown parsing challenges
- Context richness vs token limits
- Quote extraction techniques
- Connection-making strategies
- Best practices for context preparation

#### Success Criteria:
- Context builder fully functional
- Extracts all relevant content types
- Handles missing/malformed content gracefully
- Previous interview loading working
- 95%+ test coverage
- Clear, rich context generation

---

### Unit 4: Claude Agent SDK Integration

**Duration**: 5-6 hours
**Goal**: Integrate Claude Agent SDK for conversational interview

#### Tasks:

1. **Implement Agent Wrapper** (`interview/agent.py`)
```python
from typing import AsyncIterator, Optional
from anthropic import AsyncAnthropic
from .models import InterviewContext, Question, InterviewSession

class InterviewAgent:
    """Wrapper around Claude Agent SDK for interviews"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        temperature: float = 0.7,
    ):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.system_prompt = ""

    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt for the agent"""
        self.system_prompt = prompt

    async def generate_question(
        self,
        context: InterviewContext,
        session: InterviewSession,
        template_prompt: str,
    ) -> Question:
        """Generate next interview question"""

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
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )

        # Extract question text
        question_text = response.content[0].text.strip()

        # Create Question object
        import uuid
        question = Question(
            id=str(uuid.uuid4()),
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
        session.total_tokens_used += response.usage.input_tokens + response.usage.output_tokens
        session.total_cost_usd += self._calculate_cost(response.usage)

        return question

    async def generate_follow_up(
        self,
        question: Question,
        response_text: str,
        context: InterviewContext,
        template_prompt: str,
    ) -> Optional[Question]:
        """Generate follow-up question based on user's response"""

        # Decide if follow-up is warranted
        if context.depth_level >= 2:  # Max depth reached
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
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )

        follow_up_text = response.content[0].text.strip()

        import uuid
        follow_up = Question(
            id=str(uuid.uuid4()),
            text=follow_up_text,
            question_number=question.question_number,  # Same number, but deeper
            depth_level=question.depth_level + 1,
            parent_question_id=question.id,
        )

        return follow_up

    async def stream_response(
        self,
        prompt: str,
    ) -> AsyncIterator[str]:
        """Stream a response from Claude (for real-time display)"""

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=1000,
            temperature=self.temperature,
            system=self.system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def _build_question_prompt(
        self,
        context: InterviewContext,
        session: InterviewSession,
        template_prompt: str,
    ) -> str:
        """Build prompt for question generation"""

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
        prompt_parts.append(f"\nThis is question {session.question_count + 1} of approximately {context.max_questions}.")

        return "\n".join(prompt_parts)

    def _calculate_cost(self, usage) -> float:
        """Calculate cost based on token usage"""
        # Claude Sonnet 4.5 pricing (as of Nov 2024)
        input_cost_per_million = 3.00
        output_cost_per_million = 15.00

        input_cost = (usage.input_tokens / 1_000_000) * input_cost_per_million
        output_cost = (usage.output_tokens / 1_000_000) * output_cost_per_million

        return input_cost + output_cost
```

2. **Implement Interview Template Loader** (`interview/templates/base.py`)
```python
from pydantic import BaseModel
from typing import Literal

class InterviewTemplate(BaseModel):
    """Base template for interview styles"""
    name: str
    description: str

    system_prompt: str
    initial_question_prompt: str
    follow_up_prompt: str
    conclusion_prompt: str

    target_questions: int = 5
    max_depth: int = 3
    temperature: float = 0.7

# Reflective template
REFLECTIVE_TEMPLATE = InterviewTemplate(
    name="reflective",
    description="Deep personal reflection on episode content",
    system_prompt="""You are conducting a thoughtful interview to help the listener reflect deeply on a podcast episode they just heard. Your role is to ask open-ended questions that encourage personal connection, introspection, and actionable insights.

Guidelines:
- Ask about personal connections and applications
- Probe for surprising or challenging ideas
- Encourage connection-making to past experiences
- Focus on "what" and "how" rather than "why"
- Keep questions concise and open-ended
- Be curious and empathetic""",

    initial_question_prompt="""Generate the first interview question. This should be an open-ended question that helps the listener reflect on what resonated most with them from the episode. Draw from the summary and key concepts.""",

    follow_up_prompt="""Generate a follow-up question that goes deeper into their response. Build on what they said to explore their thinking further.""",

    conclusion_prompt="""Generate a final question that helps the listener identify concrete actions or next steps based on their reflections.""",
)

# Analytical template
ANALYTICAL_TEMPLATE = InterviewTemplate(
    name="analytical",
    description="Critical analysis and evaluation of episode arguments",
    system_prompt="""You are conducting an analytical interview to help the listener critically examine the ideas presented in a podcast episode. Your role is to ask questions that encourage critical thinking, argument evaluation, and intellectual engagement.

Guidelines:
- Ask about logical consistency and evidence
- Probe assumptions and implications
- Encourage comparison with alternative viewpoints
- Focus on "why" and "how" questions
- Challenge thinking constructively
- Maintain intellectual rigor""",

    initial_question_prompt="""Generate the first interview question. This should ask the listener to critically evaluate one of the main arguments or claims from the episode.""",

    follow_up_prompt="""Generate a follow-up question that challenges their analysis or asks them to consider alternative perspectives.""",

    conclusion_prompt="""Generate a final question that asks how this critical analysis changes their view on the topic.""",
)

# Creative template
CREATIVE_TEMPLATE = InterviewTemplate(
    name="creative",
    description="Creative connections and idea generation",
    system_prompt="""You are conducting a creative interview to help the listener make unexpected connections and generate new ideas inspired by the podcast episode. Your role is to ask questions that spark creativity, imagination, and novel thinking.

Guidelines:
- Ask about unexpected connections
- Encourage "what if" thinking
- Explore tangential ideas and metaphors
- Focus on possibility and potential
- Be playful and imaginative
- Avoid being too analytical""",

    initial_question_prompt="""Generate the first interview question. This should ask the listener to make an unexpected connection between the episode content and something else in their life or work.""",

    follow_up_prompt="""Generate a follow-up question that pushes their creative thinking further or explores an interesting tangent.""",

    conclusion_prompt="""Generate a final question that asks them to imagine a creative application or project inspired by the episode.""",
)

# Template registry
TEMPLATES = {
    "reflective": REFLECTIVE_TEMPLATE,
    "analytical": ANALYTICAL_TEMPLATE,
    "creative": CREATIVE_TEMPLATE,
}

def get_template(name: str) -> InterviewTemplate:
    """Get interview template by name"""
    if name not in TEMPLATES:
        raise ValueError(f"Unknown template: {name}")
    return TEMPLATES[name]
```

3. **Write Comprehensive Tests** (`tests/unit/test_interview_agent.py`)
   - Mock Claude API calls
   - Test question generation
   - Test follow-up generation
   - Test streaming responses
   - Test cost calculation
   - Test error handling
   - Test template loading

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-08-phase-4-unit-4-agent-integration.md`
- Document agent wrapper design
- Explain question generation approach
- Show example prompts and responses
- Document cost tracking
- Note API integration challenges

**Create Lessons Learned**: `docs/lessons/2025-11-08-agent-sdk-integration.md`
- Claude Agent SDK patterns
- Streaming implementation details
- Cost optimization strategies
- Error handling approaches
- Best practices for agent wrappers

**Create ADR**: `docs/adr/024-interview-question-generation.md`
- **Decision**: Template-based question generation with context
- **Alternatives**: Fully dynamic, scripted questions, user-provided
- **Rationale**: Flexibility, quality, personalization
- **Consequences**: Template maintenance, prompt engineering effort

#### Success Criteria:
- Agent wrapper fully functional
- Question generation working
- Follow-up generation working
- Templates implemented
- Cost tracking accurate
- 90%+ test coverage
- Clear error handling

---

### Unit 5: Interview Session Management

**Duration**: 4-5 hours
**Goal**: Orchestrate interview flow with state management and resume capability

#### Tasks:

1. **Implement Session Manager** (`interview/session.py`)
2. **Implement Session Persistence**
3. **Implement Resume Logic**
4. **Handle Interruptions and Exits**

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-08-phase-4-unit-5-session-management.md`

**Create Lessons Learned**: `docs/lessons/2025-11-08-session-state-management.md`

#### Success Criteria:
- Session creation and management working
- State persistence functional
- Resume capability working
- Graceful exit handling
- 95%+ test coverage

---

### Unit 6: Terminal UI Implementation

**Duration**: 5-6 hours
**Goal**: Build beautiful, interactive terminal interface for interviews

#### Tasks:

1. **Implement Rich Terminal Display** (`interview/ui/display.py`)
2. **Implement Multiline Input Handler** (`interview/ui/prompts.py`)
3. **Implement Streaming Response Display**
4. **Implement Conversation History View**
5. **Add Progress Indicators**

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-08-phase-4-unit-6-terminal-ui.md`

**Create Lessons Learned**: `docs/lessons/2025-11-08-terminal-ui-patterns.md`

#### Success Criteria:
- Terminal UI functional and beautiful
- Multiline input working
- Streaming display smooth
- Progress indicators clear
- Good UX (keyboard shortcuts, help text)

---

### Unit 7: Interview Transcript Formatting

**Duration**: 3-4 hours
**Goal**: Format interview conversation as structured markdown

#### Tasks:

1. **Implement Transcript Formatter** (`interview/formatter.py`)
2. **Extract Key Insights**
3. **Generate Action Items**
4. **Create Structured Sections**

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-08-phase-4-unit-7-transcript-formatting.md`

**Create ADR**: `docs/adr/025-interview-output-format.md`

#### Success Criteria:
- Transcript formatting working
- Insights extraction functional
- Action items generation working
- Multiple format styles supported
- 95%+ test coverage

---

### Unit 8: Interview Orchestration & CLI Integration

**Duration**: 4-5 hours
**Goal**: Tie everything together and expose via CLI

#### Tasks:

1. **Implement Interview Manager** (`interview/manager.py`)
2. **Add `--interview` Flag to `fetch` Command**
3. **Add `interview` Command for Resume**
4. **Add Cost Estimation and Confirmation**
5. **Integrate with Phase 3 Pipeline**

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-08-phase-4-unit-8-cli-integration.md`

**Update User Guide**: Document interview mode usage

#### Success Criteria:
- Interview manager orchestrates full flow
- CLI integration working
- Cost confirmation implemented
- Pipeline integration seamless
- Tests passing

---

### Unit 9: Testing, Polish & Documentation

**Duration**: 5-6 hours
**Goal**: Comprehensive testing, polish, and complete documentation

#### Tasks:

1. **End-to-End Integration Tests**
   - Test full interview flow
   - Test resume functionality
   - Test error scenarios
   - Test cost limits
   - Test different templates

2. **Manual Testing**
   - Real interview sessions
   - Test user experience
   - Verify output quality
   - Test edge cases

3. **Performance Testing**
   - Measure response latency
   - Test streaming performance
   - Verify cost estimates
   - Test with long sessions

4. **Polish**
   - Refine question quality
   - Improve error messages
   - Enhance terminal UI
   - Optimize token usage

5. **Documentation**
   - Complete all devlogs
   - Write comprehensive lessons learned
   - Create user guide
   - Document troubleshooting

#### Documentation Tasks:

**Create Final Phase 4 Summary**: `docs/PHASE_4_COMPLETE.md`
- Overview of what was built
- Statistics (LOC, tests, docs)
- Key achievements
- Lessons learned
- What's next

**Create Comprehensive Lessons**: `docs/lessons/2025-11-08-phase-4-complete.md`
- Technical insights
- Process insights
- Challenges overcome
- Best practices learned

**Update CLAUDE.md**
- Add interview mode conventions
- Document session management patterns
- Note UI patterns

**Create Architecture Diagram**: `docs/architecture/phase-4-interview.md`
- Interview flow diagram
- Component interaction
- State machine diagram

**Create User Guide**: `docs/guides/interview-mode.md`
- How to use interview mode
- Customizing interview templates
- Resuming sessions
- Tips for great interviews

#### Success Criteria:
- 90%+ test coverage
- All tests passing
- Manual testing successful
- Documentation complete
- User guide comprehensive
- Ready for real-world use

---

## Quality Gates

### Phase 4 is Complete When:

**Functionality:**
- [ ] Context building from Phase 3 output working
- [ ] Claude Agent SDK integrated
- [ ] Question generation working (multiple templates)
- [ ] Follow-up question generation working
- [ ] Interview session management working
- [ ] Terminal UI functional and polished
- [ ] Streaming responses working
- [ ] Session persistence and resume working
- [ ] Interview transcript formatting working
- [ ] CLI integration complete
- [ ] Cost tracking and limits working

**Code Quality:**
- [ ] 90%+ test coverage
- [ ] All tests passing
- [ ] No mypy errors
- [ ] No ruff warnings
- [ ] Pre-commit hooks passing
- [ ] Async patterns correct

**User Experience:**
- [ ] Terminal UI beautiful and intuitive
- [ ] Multiline input smooth
- [ ] Streaming responses feel natural
- [ ] Clear progress indicators
- [ ] Helpful prompts and instructions
- [ ] Graceful error handling
- [ ] Easy session resume
- [ ] Interview feels conversational

**Output Quality:**
- [ ] Questions are contextual and thoughtful
- [ ] Follow-ups build on responses
- [ ] Transcript is well-formatted
- [ ] Insights extraction meaningful
- [ ] Action items actionable
- [ ] Output integrates well with Phase 3 files

**Documentation:**
- [ ] All 4 ADRs created
- [ ] All 9 devlogs written
- [ ] All lessons learned documented
- [ ] 3 research docs complete
- [ ] 3 experiment logs complete
- [ ] User guide comprehensive
- [ ] PHASE_4_COMPLETE.md written
- [ ] Architecture diagrams created

---

## Architecture Decision Records to Create

1. **ADR-020: Interview Framework Selection** - Claude Agent SDK
2. **ADR-021: Interview State Persistence** - JSON-based
3. **ADR-022: Interview UI Framework** - Rich library
4. **ADR-023: Interview Template System** - Template-based styles
5. **ADR-024: Interview Question Generation** - Context-aware prompting
6. **ADR-025: Interview Output Format** - Structured markdown

---

## Timeline Estimate

**Total Duration**: 8-10 days

- Unit 1 (Research): 1 day
- Unit 2 (Data Models): 0.5 days
- Unit 3 (Context Preparation): 0.5 days
- Unit 4 (Agent Integration): 1.5 days
- Unit 5 (Session Management): 1 day
- Unit 6 (Terminal UI): 1.5 days
- Unit 7 (Transcript Formatting): 0.5 days
- Unit 8 (CLI Integration): 1 day
- Unit 9 (Testing & Docs): 1.5 days
- Buffer: 1 day

---

## Expected Code Metrics

### Production Code (Estimated)
| Component | Lines | Files |
|-----------|-------|-------|
| Models | ~400 | 1 |
| Context | ~300 | 1 |
| Agent | ~400 | 2 |
| Templates | ~200 | 4 |
| Session | ~350 | 1 |
| Terminal UI | ~500 | 3 |
| Formatter | ~300 | 1 |
| Manager | ~250 | 1 |
| **Total** | **~2700** | **~14** |

### Tests (Estimated)
| Component | Lines | Tests |
|-----------|-------|-------|
| Models | ~600 | 50 |
| Context | ~400 | 30 |
| Agent | ~600 | 40 |
| Session | ~500 | 35 |
| UI | ~400 | 25 |
| Formatter | ~400 | 30 |
| Integration | ~500 | 20 |
| **Total** | **~3400** | **~230** |

### Documentation (Estimated)
| Type | Lines | Count |
|------|-------|-------|
| ADRs | ~3000 | 6 |
| Devlogs | ~8000 | 9 |
| Research | ~2500 | 3 |
| Experiments | ~1500 | 3 |
| Lessons | ~2000 | 3 |
| Guides | ~2000 | 2 |
| **Total** | **~19000** | **26** |

---

## Notes for Implementation

1. **User Experience is Critical**: Interview mode is Inkwell's differentiator. The UX must be exceptional.

2. **Question Quality > Quantity**: Better to have 3 great questions than 10 mediocre ones.

3. **Respect User Time**: Keep interviews focused and valuable. Enable easy exit.

4. **Context is King**: Rich context from Phase 3 enables great questions.

5. **State Management Matters**: Users may get interrupted. Resume must work flawlessly.

6. **Cost Transparency**: Always show estimates. Confirm before high-cost operations.

7. **Streaming is Essential**: Real-time responses feel conversational.

8. **Test with Real Sessions**: Simulate actual interviews during development.

9. **Templates Enable Personalization**: Different users want different interview styles.

10. **Document the Magic**: Interview mode is complex. Documentation is essential.

---

## Key Success Metrics

### Technical Metrics:
- Average response latency < 2 seconds
- 90%+ test coverage
- Zero unhandled errors in interview flow
- Cost estimation accuracy within 10%

### User Experience Metrics:
- Average interview completion rate > 80%
- Average session length 10-20 minutes
- Average response length > 50 words
- User can resume paused session without confusion

### Output Quality Metrics:
- 80%+ of responses are substantive
- Action items generated for 70%+ of interviews
- Insights extracted for 90%+ of interviews
- Transcript is well-formatted and readable

---

## What Comes After Phase 4

**Phase 5: Obsidian Integration & Polish**
- Wikilink generation (link to people, tools, concepts)
- Tag system with LLM-suggested tags
- Dataview integration
- Batch processing multiple episodes
- Performance optimization
- Advanced template customization
- Search and query capabilities
- Publishing and sharing features

**Future Enhancements:**
- Multi-language support
- Voice input for responses
- Interview analytics dashboard
- Collaborative interviews (multiple users)
- Interview templates marketplace
- Integration with spaced repetition systems
- Interview quality scoring
- Automated follow-up questions based on interest signals

---

## Risk Assessment

### High Risk Areas:

1. **Claude Agent SDK Integration**
   - **Risk**: SDK may have limitations or bugs
   - **Mitigation**: Thorough research in Unit 1, fallback to direct API if needed

2. **Terminal UI Complexity**
   - **Risk**: Multiline input and streaming may have edge cases
   - **Mitigation**: Extensive testing, user testing, graceful degradation

3. **Session State Management**
   - **Risk**: State corruption could lose interview progress
   - **Mitigation**: Atomic writes, frequent saves, validation

4. **Cost Overruns**
   - **Risk**: Long interviews could be expensive
   - **Mitigation**: Hard limits, cost confirmation, streaming token tracking

5. **Question Quality**
   - **Risk**: Generic or repetitive questions
   - **Mitigation**: Template refinement, context richness, testing with real content

### Medium Risk Areas:

1. **Resume Functionality**
   - **Risk**: Edge cases in resuming sessions
   - **Mitigation**: Thorough testing, clear state machine

2. **Streaming Performance**
   - **Risk**: Network issues affecting streaming
   - **Mitigation**: Timeout handling, fallback to blocking

3. **Output Formatting**
   - **Risk**: Inconsistent or ugly output
   - **Mitigation**: Template-based formatting, validation

---

## Dependencies

### External Dependencies:
- `anthropic` (Claude Agent SDK) - Already in pyproject.toml
- `rich` - Already in pyproject.toml via typer[all]
- No additional dependencies needed!

### Internal Dependencies:
- Phase 3 extraction pipeline must be complete
- Output file structure from Phase 3
- Configuration system from Phase 1
- All existing infrastructure

---

## Example Usage (After Phase 4)

```bash
# Process episode with interview
inkwell fetch "my-podcast" --latest --interview

# Output:
# ✓ Episode found: "The Future of AI" (45 minutes)
# ✓ Transcript cached
# ✓ Extracted content: summary, quotes, key-concepts, tools-mentioned
#
# 🎙️  Starting interview...
#
# I've reviewed the episode "The Future of AI" from My Podcast.
# Let's reflect on what resonated with you.
#
# Question 1 of ~5:
# What aspect of the discussion about AI safety surprised you most,
# and how does it relate to your own work in software engineering?
#
# Your response (press Enter twice when done, or 'skip' to skip):
# > Well, I hadn't really thought about alignment problems at
# > the scale they discussed. It made me realize that even in
# > my day-to-day work, we often don't think carefully enough
# > about what we're optimizing for.
# >
# >
#
# That's a profound connection. Let's explore that further...
#
# Follow-up question:
# Can you think of a specific project where unclear optimization
# goals led to unexpected outcomes?
#
# Your response:
# > Actually yes! Last quarter we built a recommendation system...
# > [streaming response continues]
#
# [Interview continues for 4 more questions]
#
# ✓ Interview complete! (12 minutes, 5 questions, $0.18)
# ✓ Saved to: my-podcast-2025-11-08-the-future-of-ai/my-notes.md
#
# 📝 Key insights extracted:
# • Alignment problems exist at all scales
# • Optimization clarity is crucial in engineering
# • Three action items identified

# Resume a paused interview
inkwell interview resume my-podcast-2025-11-08-the-future-of-ai

# Use different interview template
inkwell fetch "my-podcast" --latest --interview --template analytical

# Configure interview settings
inkwell config set interview.question_count 8
inkwell config set interview.default_template creative
```

---

## Final Notes

Phase 4 is where Inkwell truly shines. The interview mode transforms the tool from a passive note-taker to an active learning partner. This is the feature that will make users love Inkwell.

Key focus areas:
1. **Exceptional UX** - Must feel natural and conversational
2. **Thoughtful Questions** - Context-aware and personally relevant
3. **Seamless Integration** - Works perfectly with Phase 3 output
4. **Reliable State** - Never lose an interview in progress
5. **Beautiful Output** - Interview notes are a joy to read

This phase is ambitious but achievable with the structured approach we've used in Phases 1-3. The documentation-first mindset will be especially important here, as interview mode is the most complex component yet.

---

**Ready to begin Phase 4 implementation! 🚀**

Let's transform podcast listening into active knowledge building.
