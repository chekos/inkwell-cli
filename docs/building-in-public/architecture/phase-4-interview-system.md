# Architecture: Phase 4 Interview System

**Date**: 2025-11-08
**Version**: 1.0
**Status**: Complete

## Overview

The Interview System is Inkwell's differentiating feature that transforms passive podcast listening into active knowledge building by conducting AI-powered conversations with users about episode content.

## System Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                     Interview Manager                           │
│                    (Orchestration Layer)                        │
└────────┬────────────────────────────────────────────┬───────────┘
         │                                            │
    ┌────▼─────────┐                           ┌────▼──────────┐
    │   Context    │                           │   Session     │
    │   Builder    │                           │   Manager     │
    └────┬─────────┘                           └────┬──────────┘
         │                                            │
    ┌────▼──────────┐                          ┌────▼──────────┐
    │  Interview    │                          │   Interview   │
    │   Context     │                          │   Session     │
    └───────────────┘                          └───────────────┘
         │                                            │
         │                                            │
    ┌────▼──────────────────────────────────────────▼───────────┐
    │              Interview Agent (Claude SDK)                 │
    └────────────────────────┬──────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Question      │
                    │  Generation     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Terminal UI    │
                    │  (Rich-based)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  User Response  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Transcript     │
                    │  Formatter      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Markdown       │
                    │  Output         │
                    └─────────────────┘
```

### Component Interaction

```
┌──────────────┐
│ Phase 3      │
│ Output       │──────┐
│ (Markdown)   │      │
└──────────────┘      │
                      │
                 ┌────▼──────────────┐
                 │ ContextBuilder    │
                 │ • Extract summary │
                 │ • Extract quotes  │
                 │ • Extract concepts│
                 └────┬──────────────┘
                      │
                 ┌────▼──────────────┐
                 │ InterviewContext  │
                 │ • Episode info    │
                 │ • Key content     │
                 │ • Guidelines      │
                 └────┬──────────────┘
                      │
                 ┌────▼──────────────┐
                 │ InterviewAgent    │
                 │ • Claude SDK      │
                 │ • Streaming       │
                 │ • Cost tracking   │
                 └────┬──────────────┘
                      │
                 ┌────▼──────────────┐
                 │ Question          │
                 │ • Text            │
                 │ • Depth level     │
                 │ • Question #      │
                 └────┬──────────────┘
                      │
                 ┌────▼──────────────┐
                 │ Terminal UI       │
                 │ • Display question│
                 │ • Get response    │
                 │ • Show progress   │
                 └────┬──────────────┘
                      │
                 ┌────▼──────────────┐
                 │ Response          │
                 │ • Text            │
                 │ • Word count      │
                 │ • Thinking time   │
                 └────┬──────────────┘
                      │
                 ┌────▼──────────────┐
                 │ Exchange          │
                 │ • Question        │
                 │ • Response        │
                 │ • Timestamp       │
                 └────┬──────────────┘
                      │
                 ┌────▼──────────────┐
                 │ InterviewSession  │
                 │ • All exchanges   │
                 │ • Metadata        │
                 │ • Statistics      │
                 └────┬──────────────┘
                      │
              ┌───────┴──────────┐
              │                  │
         ┌────▼───────────┐ ┌───▼──────────────┐
         │ SessionManager │ │ TranscriptFormat │
         │ • Save to JSON │ │ • 3 formats      │
         │ • XDG location │ │ • Extract insights│
         │ • Auto-save    │ │ • Extract actions│
         └────────────────┘ │ • Extract themes │
                            └───┬──────────────┘
                                │
                           ┌────▼──────────────┐
                           │ InterviewResult   │
                           │ • Formatted text  │
                           │ • Insights list   │
                           │ • Actions list    │
                           │ • Themes list     │
                           │ • Quality metrics │
                           └───┬───────────────┘
                               │
                          ┌────▼────────────┐
                          │ Markdown Files  │
                          │ • Transcript    │
                          │ • Metadata      │
                          │ • Frontmatter   │
                          └─────────────────┘
```

## Core Components

### 1. Interview Manager

**Location**: `src/inkwell/interview/manager.py`
**Responsibility**: Orchestrate complete interview flow
**Dependencies**: All other interview components

#### Key Methods

```python
async def conduct_interview(
    episode_url: str,
    episode_title: str,
    podcast_name: str,
    output_dir: Path,
    template_name: str = "reflective",
    max_questions: int = 5,
    guidelines: InterviewGuidelines | None = None,
    format_style: FormatStyle = "structured",
    resume_session_id: str | None = None,
) -> InterviewResult
```

**Workflow**:
1. Build context from output directory
2. Check for resumable session
3. Initialize agent with template
4. Run interview loop
5. Handle graceful interruption (Ctrl-C)
6. Format transcript with insights
7. Save to output directory
8. Return complete result

#### State Management

```python
# Session states during interview
ACTIVE → PAUSED (Ctrl-C with confirmation)
ACTIVE → COMPLETED (finished or /done)
ACTIVE → ABANDONED (timeout: 30min)
PAUSED → ACTIVE (resume)
```

### 2. Data Models

**Location**: `src/inkwell/interview/models.py`
**Responsibility**: Type-safe data structures with validation
**Technology**: Pydantic v2

#### Core Models

**Question**
```python
class Question(BaseModel):
    text: str                    # The question text
    question_number: int         # 1-indexed question number
    depth: int                   # Follow-up depth (0-3)
    follow_up_to: str | None     # Parent question ID
    created_at: datetime         # Generation timestamp
```

**Response**
```python
class Response(BaseModel):
    question_id: str             # UUID of question
    text: str                    # User's response
    word_count: int              # Computed from text
    thinking_time_seconds: float # Time to respond
    timestamp: datetime          # When submitted
```

**Exchange**
```python
class Exchange(BaseModel):
    question: Question
    response: Response
    depth_level: int             # From question.depth

    @property
    def is_substantive(self) -> bool:
        """Response has 10+ words"""
        return self.response.word_count >= 10
```

**InterviewSession**
```python
class InterviewSession(BaseModel):
    session_id: str              # UUID
    episode_url: str             # Unique identifier
    podcast_name: str
    episode_title: str
    template_name: str           # reflective/analytical/creative
    max_questions: int           # Target question count
    status: SessionStatus        # active/paused/completed/abandoned
    started_at: datetime
    ended_at: datetime | None
    updated_at: datetime
    guidelines: InterviewGuidelines | None
    exchanges: list[Exchange]    # All Q&A pairs
    total_input_tokens: int      # For cost tracking
    total_output_tokens: int

    @property
    def question_count(self) -> int
    @property
    def substantive_response_count(self) -> int
    @property
    def average_response_length(self) -> float
    @property
    def total_thinking_time(self) -> float
    @property
    def duration(self) -> timedelta | None
```

**InterviewContext**
```python
class InterviewContext(BaseModel):
    episode_title: str
    podcast_name: str
    summary: str                  # From summary.md
    quotes: list[str]             # From quotes.md
    key_concepts: list[str]       # From key-concepts.md
    additional_content: dict[str, list[str]]  # books, tools, etc.
    episode_url: str
    duration_minutes: int | None

    def to_prompt_context(self, guidelines: InterviewGuidelines | None) -> str:
        """Format as context for AI prompt"""
```

**InterviewResult**
```python
class InterviewResult(BaseModel):
    session: InterviewSession
    formatted_transcript: str     # Markdown
    output_file: Path | None      # Where saved
    insights: list[str]           # Extracted patterns
    action_items: list[str]       # Extracted todos
    themes: list[str]             # Recurring topics

    @property
    def word_count(self) -> int
    @property
    def duration_minutes(self) -> float
    @property
    def quality_metrics(self) -> dict
```

### 3. Context Builder

**Location**: `src/inkwell/interview/context_builder.py`
**Responsibility**: Extract episode content from Phase 3 output
**Input**: Output directory with markdown files
**Output**: `InterviewContext` for question generation

#### Extraction Logic

```python
def build_context(
    output_dir: Path,
    episode_url: str,
    guidelines: InterviewGuidelines | None = None,
) -> InterviewContext:
    """
    Reads:
    - summary.md → main episode summary
    - quotes.md → noteworthy quotes
    - key-concepts.md → main concepts discussed
    - *.md → additional content (books, tools, people, etc.)

    Returns:
    - InterviewContext with all extracted content
    """
```

**Content Detection**:
- `books-mentioned.md` → additional_content["books"]
- `tools-mentioned.md` → additional_content["tools"]
- `people-mentioned.md` → additional_content["people"]
- etc.

### 4. Interview Agent

**Location**: `src/inkwell/interview/agent.py`
**Responsibility**: Generate questions using Claude Agent SDK
**Technology**: `claude-agent-sdk` via `anthropic` library

#### Configuration

```python
class InterviewAgent:
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 500  # Per question
    temperature: float = 0.7

    # Cost tracking (per 1000 tokens)
    INPUT_COST: float = 0.015
    OUTPUT_COST: float = 0.075
```

#### Question Generation

```python
async def generate_question(
    context: InterviewContext,
    session: InterviewSession,
    prompt_type: str = "initial",  # initial/follow_up/conclusion
) -> Question:
    """
    1. Build prompt with episode context + previous exchanges
    2. Call Claude Agent SDK
    3. Track tokens for cost estimation
    4. Return structured Question
    """
```

**Prompt Structure**:
```
System: {template.system_prompt}

Context:
Episode: {episode_title}
Summary: {summary}
Quotes: {quotes}
Concepts: {concepts}

Previous Questions:
1. {previous_question_1}
2. {previous_question_2}
...

User: {template.initial_prompt / follow_up_prompt / conclusion_prompt}
```

#### Follow-Up Logic

```python
async def generate_follow_up(
    question: Question,
    response: Response,
    context: InterviewContext,
) -> Question | None:
    """
    Generate follow-up if:
    - Response is substantive (10+ words)
    - Depth limit not reached (max depth = 3)
    - Follow-up would add value

    Returns:
    - Question with incremented depth
    - None if no follow-up warranted
    """
```

#### Streaming Support

```python
async def stream_question(prompt: str) -> AsyncIterator[str]:
    """
    Stream question generation for real-time display.

    Yields:
    - Text chunks as they arrive from Claude

    Usage:
    async for chunk in agent.stream_question(prompt):
        display_chunk(chunk)
    """
```

### 5. Session Manager

**Location**: `src/inkwell/interview/session_manager.py`
**Responsibility**: Persist and manage interview sessions
**Storage**: JSON files in XDG-compliant directory

#### File Structure

```
$XDG_DATA_HOME/inkwell/interview/sessions/
├── 3a7f9c2e-1234-5678-9abc-def012345678.json
├── 8b2e1d3f-2345-6789-abcd-ef0123456789.json
└── ...
```

#### Session Operations

```python
def save_session(session: InterviewSession) -> None:
    """
    Atomic write with temp + rename:
    1. Write to {session_id}.tmp
    2. Rename to {session_id}.json (atomic!)

    Auto-saves after every exchange.
    """

def load_session(session_id: str) -> InterviewSession:
    """Load session from JSON file"""

def find_resumable_session(episode_url: str) -> InterviewSession | None:
    """
    Find active or paused session for episode.
    Prefers active over paused.
    Returns None if only completed sessions exist.
    """

def list_sessions(
    episode_url: str | None = None,
    podcast_name: str | None = None,
    status: SessionStatus | None = None,
) -> list[InterviewSession]:
    """Filter and list sessions"""

def cleanup_old_sessions(days: int = 90) -> int:
    """Delete completed sessions older than N days"""

def detect_timeout(session: InterviewSession) -> bool:
    """Check if session timed out (30min since last update)"""
```

### 6. Terminal UI

**Location**: `src/inkwell/interview/ui/`
**Technology**: `rich` library for beautiful terminal output
**Components**: Display functions + input prompts

#### Display Components (`display.py`)

```python
def display_welcome(
    episode_title: str,
    podcast_name: str,
    template_name: str,
    max_questions: int,
) -> None:
    """Beautiful welcome screen with episode info"""

async def display_streaming_question(
    stream: AsyncIterator[str],
    question_number: int,
    is_follow_up: bool = False,
) -> None:
    """
    Live-updating panel showing question as it streams.
    Uses Rich Live context manager for flicker-free updates.
    """

def display_conversation_summary(exchanges: list[Exchange]) -> None:
    """
    Table showing conversation history:
    Q1 | What surprised you? | 45 words
    Q2 | Tell me more...    | 67 words
    """

def display_completion_summary(
    session: InterviewSession,
    output_file: Path | None,
) -> None:
    """
    Final summary with:
    - Questions asked
    - Total time
    - Average response length
    - Where transcript saved
    """

def display_pause_message(session: InterviewSession) -> None:
    """Instructions for resuming paused session"""
```

#### Input Components (`prompts.py`)

```python
def get_multiline_input(
    prompt: str = "Your response",
    show_instructions: bool = True,
) -> str:
    """
    Multiline input with:
    - Double-enter to submit
    - Ctrl-D also submits
    - Ctrl-C raises KeyboardInterrupt
    - Commands: /skip, /done, /quit, /help

    Commands only work on first line.
    """

def get_single_line_input(
    prompt: str,
    default: str | None = None,
) -> str:
    """Simple single-line input"""

def get_choice(
    prompt: str,
    choices: list[str],
    default: str | None = None,
) -> str:
    """
    Select from list:
    1. Option A
    2. Option B
    3. Option C

    Enter choice (1-3):
    """

def confirm_action(
    message: str,
    default: bool = False,
) -> bool:
    """Yes/no confirmation with default"""

def display_help() -> None:
    """Show available commands and usage"""
```

### 7. Interview Templates

**Location**: `src/inkwell/interview/templates.py`
**Responsibility**: Define interview styles and prompts

#### Template Structure

```python
class InterviewTemplate(BaseModel):
    name: str                          # reflective/analytical/creative
    description: str                   # User-facing description
    system_prompt: str                 # AI behavior instruction
    initial_prompt: str                # First question prompt
    follow_up_prompt: str              # Deeper questions
    conclusion_prompt: str             # Wrap-up question
    guidelines: InterviewGuidelines    # Constraints
    model_parameters: dict             # temperature, etc.
```

#### Available Templates

**Reflective Template**
- Focus: Personal insights and connections
- Tone: Thoughtful, introspective
- Questions: "What surprised you?", "How does this relate to..."
- Temperature: 0.7

**Analytical Template**
- Focus: Critical evaluation and deep thinking
- Tone: Intellectual, probing
- Questions: "What assumptions...", "How would you evaluate..."
- Temperature: 0.8

**Creative Template**
- Focus: Imaginative applications and new ideas
- Tone: Exploratory, divergent
- Questions: "What if...", "How might you apply..."
- Temperature: 0.9

### 8. Transcript Formatter

**Location**: `src/inkwell/interview/formatter.py`
**Responsibility**: Convert session to markdown with insights
**Output**: Structured markdown with frontmatter

#### Format Styles

**Structured Format**
```markdown
---
interview_date: 2025-11-08
template: reflective
questions_asked: 5
---

# Interview: Episode Title

## Statistics
- Questions: 5
- Duration: 12.5 minutes
- Avg response: 45 words

## Conversation

### Question 1
What surprised you most about this episode?

**Your Response:**
I was surprised by...

### Question 2
...

## Insights
- I realize that sleep is more important than I thought
- I learned that consistency beats intensity

## Action Items
- [ ] I should track my sleep for a week
- [ ] I want to implement a morning routine

## Themes
- sleep quality
- consistent habits
- morning routines
```

**Narrative Format**
```markdown
# My Conversation with Inkwell

On November 8th, 2025, I reflected on "Episode Title" from Podcast Name...

When asked what surprised me, I shared that...

Diving deeper, I explored how...

## Key Takeaways
...
```

**Q&A Format**
```markdown
# Interview Transcript

**Q**: What surprised you most?
**A**: I was surprised by...

**Q**: Tell me more about that.
**A**: Well, thinking deeper...
```

#### Pattern-Based Extraction

**Insights** (statements of learning/realization):
```python
PATTERNS = [
    r"\bI realize\b",
    r"\bI learned\b",
    r"\bThis made me think\b",
    r"\bI never thought\b",
    r"\bIt\'s interesting that\b",
]
```

**Action Items** (intended behaviors):
```python
PATTERNS = [
    r"\bI should\b",
    r"\bI need to\b",
    r"\bI want to\b",
    r"\bI will\b",
    r"\bI\'m going to\b",
]
```

**Themes** (recurring topics):
- Extract 2-3 word ngrams from all responses
- Count occurrences
- Themes = phrases appearing 2+ times

## Data Flow

### Complete Interview Flow

```
1. User triggers interview mode:
   inkwell process <url> --interview

2. InterviewManager.conduct_interview() starts:

   a. ContextBuilder extracts content from output_dir/
      - Reads summary.md, quotes.md, key-concepts.md
      - Builds InterviewContext

   b. Check for existing session:
      - SessionManager.find_resumable_session(episode_url)
      - If found, ask user to resume
      - If yes, load session and skip to step 3

   c. Create new session:
      - SessionManager.create_session(...)
      - Initialize with template (reflective/analytical/creative)
      - Save initial state

   d. Initialize InterviewAgent:
      - Load template (system prompt, guidelines)
      - Set model parameters

3. Interview loop (_interview_loop):

   while session.question_count < session.max_questions:
       a. Generate question:
          - Agent.generate_question(context, session, prompt_type)
          - Prompt includes episode context + previous Q&A
          - Stream to terminal with display_streaming_question()

       b. Get user response:
          - get_multiline_input()
          - Handle commands: /skip, /done, /quit
          - Record thinking time

       c. Process response:
          - Create Response object
          - Validate (not empty, substantive check)
          - Create Exchange (question + response)

       d. Update session:
          - session.add_exchange(exchange)
          - Track tokens for cost
          - SessionManager.save_session() (auto-save!)

       e. Decide next step:
          - If substantive response + depth < 3: generate follow-up
          - Else: continue to next main question
          - If question_count == max_questions: conclusion question

   # Graceful interruption (Ctrl-C):
   except KeyboardInterrupt:
       - Confirm: "Pause this interview?"
       - If yes: session.pause(), save, display resume info
       - Return partial result

4. Format transcript:

   a. TranscriptFormatter.format_session(session, style="structured")
   b. Extract insights (pattern matching)
   c. Extract action items (pattern matching)
   d. Extract themes (ngram repetition)
   e. Generate markdown with frontmatter

5. Save output:

   a. TranscriptFormatter.save_transcript(output_dir)
   b. Write markdown file: my-interview.md or my-notes.md
   c. Update session status: completed
   d. Final save

6. Display summary:

   a. display_completion_summary(session, output_file)
   b. Show statistics (questions, time, avg length)
   c. Show where transcript saved

7. Return InterviewResult:

   return InterviewResult(
       session=session,
       formatted_transcript=markdown,
       output_file=output_path,
       insights=insights,
       action_items=actions,
       themes=themes,
   )
```

### State Persistence

```
Every exchange auto-saves:

1. User submits response
2. Create Exchange(question, response)
3. session.add_exchange(exchange)
4. SessionManager.save_session(session)
   ├─ Serialize to JSON: session.model_dump_json()
   ├─ Write to temp: {session_id}.tmp
   └─ Atomic rename: .tmp → .json

Benefits:
- No data loss on crash
- Can resume from any point
- Graceful Ctrl-C works safely
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **AI Engine** | Claude Agent SDK | Simplifies conversational flow, manages history |
| **Data Models** | Pydantic v2 | Type safety, validation, serialization |
| **Terminal UI** | Rich library | Beautiful output with minimal code |
| **Input** | prompt_toolkit | Multiline editing, command support |
| **Persistence** | JSON files | Simple, human-readable, version-controllable |
| **Storage** | platformdirs | XDG compliance, cross-platform |
| **Testing** | pytest + AsyncMock | Async support, clean fixtures |
| **Type Checking** | mypy (via Pydantic) | IDE autocomplete, refactoring safety |

## Performance Characteristics

### Latency

| Operation | Typical Time | Notes |
|-----------|-------------|-------|
| Context building | 50-200ms | Depends on file count |
| Question generation | 2-5 seconds | Claude API call |
| Streaming display | Real-time | Chunks appear as generated |
| Session save | 5-20ms | Atomic write to JSON |
| Pattern extraction | 10-50ms | Regex on all responses |

### Cost Estimation

```
Per interview session (5 questions):
- Context: ~500 tokens input (one-time)
- Question 1: ~700 tokens in, ~50 tokens out
- Question 2-5: ~800 tokens in (includes history), ~50 tokens out
- Total: ~3800 input, ~250 output

Cost:
- Input: 3.8K × $0.015/1K = $0.057
- Output: 0.25K × $0.075/1K = $0.019
- Total: ~$0.076 per interview

20-question interview: ~$0.30
```

### Storage

```
Per session:
- JSON file: 5-20 KB (depends on response length)
- Transcript markdown: 2-10 KB

100 interviews:
- Session data: ~1.5 MB
- Transcripts: ~600 KB
- Total: ~2 MB

Negligible storage footprint.
```

## Error Handling

### API Errors

```python
# Claude API failures
try:
    question = await agent.generate_question(...)
except APIError as e:
    display_error(f"API error: {e}")
    # Session is already saved up to this point
    # User can resume later
    raise
```

### File System Errors

```python
# Missing content files
if not summary_path.exists():
    # Use empty string, continue gracefully
    summary = ""

# Session save failure
try:
    save_session(session)
except OSError as e:
    display_error(f"Failed to save session: {e}")
    # Continue interview, try again next exchange
```

### User Input Errors

```python
# Empty response
if not response_text.strip():
    # Treat as /skip command
    continue

# Invalid command
if response_text.startswith("/"):
    if response_text not in VALID_COMMANDS:
        display_info("Unknown command. Type /help for options.")
        continue
```

## Security Considerations

### API Key Storage

- API key passed via environment variable: `ANTHROPIC_API_KEY`
- Never stored in session files
- Never logged to console
- Manager fails gracefully if missing

### Session Data Privacy

- Sessions stored locally in user's data directory
- No data sent to external services (except Claude API)
- JSON files are world-readable by default (relies on file system permissions)
- Users can encrypt home directory for privacy

### Input Validation

- All user input validated via Pydantic
- Prevents injection attacks (no `eval`, no shell execution)
- Text sanitized before markdown output (no XSS risk)
- File paths validated to prevent directory traversal

## Future Enhancements

### Near-Term

1. **Resume UI Improvement**: Show last few exchanges when resuming
2. **Cost Limits**: Hard limit on tokens per session
3. **Export Formats**: PDF, HTML generation
4. **Analytics**: Track patterns across multiple interviews

### Long-Term

1. **Voice Input**: Speech-to-text for hands-free
2. **Multi-language**: Support international podcasts
3. **Collaborative**: Multiple participants in one interview
4. **Smart Adaptation**: Learn question preferences over time
5. **Obsidian Plugin**: Deep integration with note-taking

## References

- [Claude Agent SDK Documentation](https://docs.anthropic.com/en/agent-sdk)
- [Rich Library Documentation](https://rich.readthedocs.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/)

## Related Documentation

- **ADR-021**: Interview State Persistence (JSON vs SQLite)
- **ADR-022**: Interview UI Framework (Rich vs Textual)
- **ADR-023**: Interview Template System (Template-based styles)
- **ADR-024**: Interview Question Generation (Context-aware prompting)
- **ADR-025**: Interview Output Format (Markdown with extraction)

- **Research**: `docs/research/claude-agent-sdk-integration.md`
- **Research**: `docs/research/interview-conversation-design.md`
- **Research**: `docs/research/terminal-ux-patterns.md`

- **Devlogs**: `docs/devlog/2025-11-08-phase-4-unit-*.md` (Units 1-8)
- **Lessons**: `docs/lessons/2025-11-08-phase-4-complete.md`

---

**Last Updated**: 2025-11-08
**Status**: Complete and production-ready
