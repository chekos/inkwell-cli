# feat: Agent-Native Interview Mode

## Enhancement Summary

**Deepened on:** 2026-01-09
**Research agents used:** kieran-python-reviewer, code-simplicity-reviewer, architecture-strategist, agent-native-reviewer, performance-oracle, security-sentinel, Context7 (Anthropic SDK, Pydantic)

### Key Improvements
1. **Simplified Architecture Option**: Single callback parameter instead of 3-class hierarchy
2. **Agent-Native Gaps Fixed**: Added `skip_question()`, `cancel()`, `get_state()` methods
3. **Crash Safety**: Incremental persistence after each exchange
4. **Security Hardening**: Response length validation, prompt injection defenses

### New Considerations Discovered
- Current plan scores **62% (8/13)** on agent-native audit - needs 5 more capabilities
- Consider callback-based design for simplicity over adapter pattern
- Explicit `InterviewState` enum prevents invalid state transitions
- Streaming recommended for perceived performance

---

## Overview

Transform the `--interview` feature from a human-only CLI interaction into an **agent-native** implementation where agents are first-class citizens. This means:

1. **Tool-Agent Parity**: Agents can do everything users can do through tools
2. **Visibility Parity**: Agents can see everything users can see (structured data, not just markdown)
3. **Atomic Tools**: Small, composable operations that agents can orchestrate

## Problem Statement

The current `SimpleInterviewer` implementation (`src/inkwell/interview/simple_interviewer.py:49-354`) has critical limitations:

| Issue | Impact |
|-------|--------|
| Uses `Prompt.ask()` blocking stdin | Agents cannot provide responses - hangs indefinitely |
| Returns markdown transcript only | Agents must parse free-form text |
| No structured input/output | Cannot be called as MCP tool |
| No partial save on error | API failure loses all progress |
| Dead CLI flags (`--resume-session`) | User confusion, code bloat |
| 15+ unused config options | Maintenance burden |

**Current Flow (Broken for Agents):**
```
Agent calls conduct_interview_from_output()
  → SimpleInterviewer.conduct_interview()
    → Prompt.ask() ← BLOCKS FOREVER
```

## Proposed Solution

Implement a **dual-mode interview system**:

1. **Interactive Mode** (default): Rich terminal UI for humans
2. **Programmatic Mode**: Async generator API for agents

Both modes share the same core logic but differ in I/O handling.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    InterviewEngine                          │
│  (Core logic: question generation, context building)        │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────────┐
│   InteractiveAdapter    │     │   ProgrammaticAdapter       │
│   (Rich console I/O)    │     │   (Async generator API)     │
│   - Prompt.ask()        │     │   - next_question()         │
│   - Console.print()     │     │   - submit_response()       │
│   - Live streaming      │     │   - Returns structured data │
└─────────────────────────┘     └─────────────────────────────┘
```

### Research Insights: Architecture

**Simplicity Review Finding:**
The 3-class architecture (Engine + Interactive + Programmatic) may be over-engineered. A simpler alternative:

```python
# Single class with callback injection
class Interview:
    async def run(
        self,
        response_provider: Callable[[str], Awaitable[str]] | None = None,
    ) -> InterviewResult:
        """
        If response_provider is None: use stdin (interactive mode)
        If response_provider is given: use callback (programmatic mode)
        """
```

**Recommendation**: Start with the callback-based design. Only split into adapters if the complexity justifies it during implementation.

**Architecture Strategist Validation:**
- ✅ Hexagonal architecture (ports and adapters) is appropriate
- ✅ Engine as core domain logic is correct
- 🔧 Add explicit `InterviewState` enum to prevent invalid state transitions

```python
class InterviewState(Enum):
    NOT_STARTED = "not_started"
    AWAITING_RESPONSE = "awaiting_response"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
```

## Technical Approach

### Phase 1: Core Refactoring (Foundation)

Extract I/O-agnostic interview logic into `InterviewEngine`.

**Files to modify:**
- `src/inkwell/interview/engine.py` (new)
- `src/inkwell/interview/simple_interviewer.py` (refactor)
- `src/inkwell/interview/__init__.py` (update exports)

**InterviewEngine responsibilities:**
```python
# src/inkwell/interview/engine.py

class InterviewEngine:
    """I/O-agnostic interview logic."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        cost_tracker: CostTracker | None = None,
    ):
        self.client = AsyncAnthropic(api_key=api_key)
        self.exchanges: list[Exchange] = []
        self.context: InterviewContext | None = None

    def load_context(self, output_dir: Path, episode_title: str, podcast_name: str) -> InterviewContext:
        """Load episode content from output files."""
        ...

    async def generate_question(self, question_number: int) -> str:
        """Generate next question based on context and history."""
        ...

    def record_exchange(self, question: str, response: str) -> Exchange:
        """Record a Q&A exchange."""
        ...

    def to_result(self) -> InterviewResult:
        """Convert session to structured result."""
        ...
```

**Structured models:**
```python
# src/inkwell/interview/models.py

class Exchange(BaseModel):
    """Single Q&A exchange."""
    question: str
    response: str
    timestamp: datetime
    question_number: int

class InterviewContext(BaseModel):
    """Context for interview generation."""
    episode_title: str
    podcast_name: str
    summary: str
    quotes: list[str]
    concepts: list[str]

class InterviewResult(BaseModel):
    """Structured interview result - agent-readable."""
    session_id: str
    status: Literal["completed", "interrupted", "failed"]
    exchanges: list[Exchange]
    total_cost: float
    total_tokens: int
    markdown: str  # For human consumption

    def to_agent_context(self) -> dict:
        """Return all state an agent would need."""
        return {
            "session_id": self.session_id,
            "status": self.status,
            "question_count": len(self.exchanges),
            "exchanges": [e.model_dump() for e in self.exchanges],
            "cost_usd": self.total_cost,
        }
```

#### Research Insights: Models

**Python Review (Kieran) Recommendations:**
```python
# 1. Add model_config for JSON serialization consistency
class Exchange(BaseModel):
    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
        ser_json_bytes="base64",
    )

# 2. Use typed return over dict
def to_agent_context(self) -> "AgentContext":
    """Return typed object instead of dict."""
    return AgentContext(...)

# 3. Add validation for response length (Security)
class Exchange(BaseModel):
    response: str = Field(..., max_length=50_000)  # Prevent DoS
```

**Security Sentinel Recommendations:**
- Add `max_length` constraints on user input fields
- Validate response content doesn't contain prompt injection patterns
- Consider rate limiting on question generation

**Performance Oracle Recommendations:**
```python
# Use sliding window for context to prevent token explosion
class InterviewEngine:
    MAX_CONTEXT_EXCHANGES = 5  # Only last 5 Q&A pairs in prompt

    def _build_context_window(self) -> list[Exchange]:
        return self.exchanges[-self.MAX_CONTEXT_EXCHANGES:]
```

### Phase 2: Programmatic Mode (Agent-Native)

Create async generator interface for agents.

**Files to create:**
- `src/inkwell/interview/programmatic.py` (new)

```python
# src/inkwell/interview/programmatic.py

class ProgrammaticInterviewer:
    """Non-blocking interview interface for agents."""

    def __init__(self, engine: InterviewEngine):
        self.engine = engine
        self._current_question: str | None = None

    async def start(
        self,
        output_dir: Path,
        episode_title: str,
        podcast_name: str,
    ) -> InterviewContext:
        """Initialize interview, return context."""
        return self.engine.load_context(output_dir, episode_title, podcast_name)

    async def next_question(self) -> str | None:
        """
        Generate and return next question.
        Returns None if max questions reached.
        """
        if self.engine.question_count >= self.max_questions:
            return None
        self._current_question = await self.engine.generate_question(
            self.engine.question_count + 1
        )
        return self._current_question

    def submit_response(self, response: str) -> Exchange:
        """
        Submit response to current question.
        Returns the recorded exchange.
        """
        if not self._current_question:
            raise ValueError("No pending question. Call next_question() first.")
        exchange = self.engine.record_exchange(self._current_question, response)
        self._current_question = None
        return exchange

    def finish(self) -> InterviewResult:
        """Complete interview and return structured result."""
        return self.engine.to_result()

    # === AGENT-NATIVE AUDIT: Missing capabilities (add these) ===

    def skip_question(self) -> None:
        """Skip current question without recording. Agent parity with /skip command."""
        self._current_question = None

    def cancel(self) -> InterviewResult:
        """
        Explicit cancel with partial results.
        Agent parity with Ctrl-C interrupt.
        """
        return self.engine.to_result(status="cancelled")

    def get_state(self) -> InterviewState:
        """
        Return current interview state for agent visibility.
        Visibility parity: agents see what humans see.
        """
        if not self._started:
            return InterviewState.NOT_STARTED
        if self._current_question:
            return InterviewState.AWAITING_RESPONSE
        if len(self.engine.exchanges) >= self.max_questions:
            return InterviewState.COMPLETED
        return InterviewState.PROCESSING

    def get_progress(self) -> dict:
        """
        Return progress info for agent visibility.
        """
        return {
            "current_question": self.engine.question_count,
            "max_questions": self.max_questions,
            "exchanges_completed": len(self.engine.exchanges),
            "state": self.get_state().value,
        }

    # Convenience async generator
    async def interview_loop(
        self,
        response_provider: Callable[[str], Awaitable[str]],
    ) -> InterviewResult:
        """
        Run full interview loop with custom response provider.

        Example:
            async def my_responses(question: str) -> str:
                return await my_llm.answer(question)

            result = await interviewer.interview_loop(my_responses)
        """
        while (question := await self.next_question()):
            response = await response_provider(question)
            if response.lower() in ("done", "quit", "exit"):
                break
            self.submit_response(response)
        return self.finish()
```

**Agent usage:**
```python
# Example: Agent using interview programmatically

from inkwell.interview import ProgrammaticInterviewer, InterviewEngine

engine = InterviewEngine(api_key=os.environ["ANTHROPIC_API_KEY"])
interviewer = ProgrammaticInterviewer(engine)

# Start interview
context = await interviewer.start(
    output_dir=Path("./output/my-podcast-2024-01-15-episode"),
    episode_title="The Future of AI",
    podcast_name="Tech Talks",
)

# Agent-driven loop
while (question := await interviewer.next_question()):
    print(f"Q: {question}")

    # Agent generates response (or gets from user via different channel)
    response = await my_agent.generate_response(question, context)

    exchange = interviewer.submit_response(response)
    print(f"A: {exchange.response}")

# Get structured result
result = interviewer.finish()
print(f"Completed {len(result.exchanges)} exchanges, cost: ${result.total_cost:.4f}")

# Agent can read all data
agent_data = result.to_agent_context()
```

#### Research Insights: Programmatic Mode

**Agent-Native Audit Results:**
| Capability | Original Plan | After Enhancement |
|------------|---------------|-------------------|
| Start interview | ✅ `start()` | ✅ |
| Get questions | ✅ `next_question()` | ✅ |
| Submit responses | ✅ `submit_response()` | ✅ |
| Read results | ✅ `to_agent_context()` | ✅ |
| Skip question | ❌ Missing | ✅ `skip_question()` |
| Cancel interview | ❌ Missing | ✅ `cancel()` |
| Get state | ❌ Missing | ✅ `get_state()` |
| Get progress | ❌ Missing | ✅ `get_progress()` |

**Score: 62% → 100%** (with enhancements)

**Performance Oracle: Streaming Pattern**
```python
# Context7: Anthropic SDK streaming for perceived performance
async def generate_question_streaming(self) -> AsyncIterator[str]:
    """Stream question generation for real-time display."""
    async with self.client.messages.stream(
        model=self.model,
        max_tokens=500,
        system=self.system_prompt,
        messages=self._build_messages(),
    ) as stream:
        async for text in stream.text_stream:
            yield text
```

**Crash Safety: Incremental Persistence**
```python
def record_exchange(self, question: str, response: str) -> Exchange:
    exchange = Exchange(question=question, response=response, ...)
    self.exchanges.append(exchange)

    # Save after EVERY exchange (ADR-021 pattern)
    self._persist_session()  # Atomic write to .interview_session.json

    return exchange
```

### Phase 3: Interactive Mode (Refactored)

Refactor existing `SimpleInterviewer` to use `InterviewEngine`.

**Files to modify:**
- `src/inkwell/interview/interactive.py` (rename from simple_interviewer.py)

```python
# src/inkwell/interview/interactive.py

class InteractiveInterviewer:
    """Rich terminal UI for human interviews."""

    def __init__(self, engine: InterviewEngine):
        self.engine = engine
        self.console = Console()

    async def conduct_interview(
        self,
        output_dir: Path,
        episode_title: str,
        podcast_name: str,
        max_questions: int = 5,
    ) -> InterviewResult:
        """Run interactive interview with Rich UI."""

        # Load context
        context = self.engine.load_context(output_dir, episode_title, podcast_name)

        # Display welcome
        self._display_welcome(episode_title, podcast_name)

        try:
            for i in range(max_questions):
                # Generate question
                question = await self.engine.generate_question(i + 1)
                self._display_question(question, i + 1, max_questions)

                # Get response (blocking for humans)
                response = self._get_user_response()

                # Handle commands
                if response.startswith("/"):
                    if self._handle_command(response):
                        break
                    continue

                # Record exchange
                self.engine.record_exchange(question, response)

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Interview interrupted.[/yellow]")

        result = self.engine.to_result()
        self._display_completion(result)
        return result

    def _get_user_response(self) -> str:
        """Multiline input with double-enter to submit."""
        self.console.print("[dim](Press Enter twice to submit, /done to finish)[/dim]")
        lines = []
        empty_count = 0

        while empty_count < 2:
            try:
                line = input()
                if not lines and line.startswith("/"):
                    return line
                if not line.strip():
                    empty_count += 1
                else:
                    empty_count = 0
                lines.append(line)
            except EOFError:
                break

        return "\n".join(lines).strip()

    def _handle_command(self, cmd: str) -> bool:
        """Handle /commands. Returns True if should exit."""
        cmd = cmd.lower().strip()
        if cmd in ("/done", "/quit", "/exit"):
            return True
        if cmd == "/help":
            self._display_help()
            return False
        if cmd == "/skip":
            self.console.print("[dim]Skipping question...[/dim]")
            return False
        self.console.print(f"[red]Unknown command: {cmd}[/red]")
        return False
```

### Phase 4: Pipeline Integration

Update orchestrator to use new interface.

**Files to modify:**
- `src/inkwell/pipeline/orchestrator.py` (update `_conduct_interview`)

```python
# In orchestrator.py, update _conduct_interview method

async def _conduct_interview(
    self,
    episode_output: EpisodeOutput,
    options: PipelineOptions,
    progress_callback: ProgressCallback,
) -> InterviewResult | None:
    """Conduct interview using appropriate adapter."""

    from inkwell.interview import InterviewEngine, InteractiveInterviewer

    engine = InterviewEngine(
        api_key=self._get_api_key("anthropic"),
        cost_tracker=self.cost_tracker,
    )

    # Use interactive mode (programmatic mode for agents via direct API)
    interviewer = InteractiveInterviewer(engine)

    result = await interviewer.conduct_interview(
        output_dir=episode_output.directory,
        episode_title=episode_output.metadata.title,
        podcast_name=episode_output.metadata.podcast_name,
        max_questions=options.max_questions or 5,
    )

    # Write both markdown and structured output
    (episode_output.directory / "my-notes.md").write_text(result.markdown)
    (episode_output.directory / ".interview.json").write_text(
        result.model_dump_json(indent=2)
    )

    return result
```

### Phase 5: Cleanup Dead Code

Remove unused CLI flags and config options.

**Files to modify:**
- `src/inkwell/cli.py` - Remove `--resume-session`, `--no-resume` flags
- `src/inkwell/config/schema.py` - Mark unused fields as deprecated or remove

```python
# cli.py - Remove these parameters from fetch_command

# REMOVE:
# resume_session: str | None = typer.Option(None, "--resume-session", ...)
# no_resume: bool = typer.Option(False, "--no-resume", ...)

# config/schema.py - Simplify InterviewConfig

class InterviewConfig(BaseModel):
    """Interview configuration - only implemented options."""
    enabled: bool = True
    auto_start: bool = False
    question_count: int = Field(default=5, ge=1, le=20)
    model: str = Field(default="claude-sonnet-4-5")
    # Remove: template, max_depth, guidelines, format_style,
    #         save_raw_transcript, resume_enabled, session_timeout_minutes,
    #         include_action_items, include_key_insights, streaming,
    #         temperature, confirm_high_cost
```

## Acceptance Criteria

### Functional Requirements

- [ ] **Agent can start interview programmatically** via `ProgrammaticInterviewer.start()`
- [ ] **Agent can get questions one-by-one** via `next_question()` (non-blocking)
- [ ] **Agent can submit responses** via `submit_response()` (non-blocking)
- [ ] **Agent can read structured results** via `InterviewResult.to_agent_context()`
- [ ] **Human CLI works unchanged** via `inkwell fetch --interview <url>`
- [ ] **Ctrl-C gracefully interrupts** and returns partial result
- [ ] **Commands supported**: `/done`, `/quit`, `/help`, `/skip`
- [ ] **Structured output saved** alongside markdown (`.interview.json`)

### Non-Functional Requirements

- [ ] **No breaking changes** to existing CLI interface
- [ ] **Remove dead code**: `--resume-session`, `--no-resume` flags
- [ ] **Clean config**: Remove or deprecate unused `InterviewConfig` fields
- [ ] **Test coverage**: Unit tests for `InterviewEngine`, `ProgrammaticInterviewer`

### Agent-Native Audit Criteria (Enhanced)

| Principle | Implementation | Status |
|-----------|----------------|--------|
| **Tool-Agent Parity** | `ProgrammaticInterviewer` provides same capabilities as CLI | ✅ |
| **Visibility Parity** | `get_state()`, `get_progress()`, `to_agent_context()` | ✅ |
| **Atomic Tools** | `start()`, `next_question()`, `submit_response()`, `skip_question()`, `cancel()`, `finish()` | ✅ |
| **Structured Data** | Pydantic models with `model_dump_json()` | ✅ |
| **Interrupt Handling** | `cancel()` returns partial result, same as Ctrl-C | ✅ |
| **State Visibility** | `InterviewState` enum exposed via `get_state()` | ✅ |

**Full Capability Matrix:**

| Human Can... | Agent Can... | Method |
|--------------|--------------|--------|
| Start interview | ✅ | `start()` |
| See questions | ✅ | `next_question()` returns string |
| Submit responses | ✅ | `submit_response()` |
| Skip question (`/skip`) | ✅ | `skip_question()` |
| Quit early (`/done`) | ✅ | `finish()` |
| Ctrl-C interrupt | ✅ | `cancel()` |
| See progress | ✅ | `get_progress()` |
| See current state | ✅ | `get_state()` |
| Read final results | ✅ | `to_agent_context()` |

## Success Metrics

- [ ] Agent can complete full interview loop without human intervention
- [ ] All interview data accessible via structured API (no markdown parsing needed)
- [ ] No regressions in existing `inkwell fetch --interview` behavior
- [ ] Code reduced by ~30% (removing dead code and unused config)

## Dependencies & Risks

### Dependencies
- Anthropic SDK `>=0.72.0` (already installed)
- No new dependencies required

### Risks

| Risk | Mitigation |
|------|------------|
| Breaking existing CLI | Keep `InteractiveInterviewer` behavior identical to current |
| API changes mid-project | Pin Anthropic SDK version |
| Scope creep | Explicit "not in scope" list below |

#### Research Insights: Security & Reliability

**Security Sentinel Assessment: LOW-MEDIUM Risk**

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Response DoS (huge inputs) | Medium | Low | Add `max_length=50_000` on response field |
| Prompt injection in responses | Low | Medium | Sanitize before including in context |
| API key exposure in logs | Low | High | Never log API keys; use env vars |
| Cost explosion | Medium | Medium | Implement cost ceiling per interview |

**Recommended Validations:**
```python
# Add to Exchange model
response: str = Field(..., max_length=50_000)

# Add to InterviewEngine
MAX_COST_USD = 2.00  # Stop if cost exceeds this

async def generate_question(self, ...) -> str:
    if self.total_cost >= self.MAX_COST_USD:
        raise InterviewCostLimitExceeded(self.total_cost)
```

**Error Handling Hierarchy (Kieran Python Review):**
```python
class InterviewError(Exception):
    """Base class for interview errors."""

class InterviewCostLimitExceeded(InterviewError):
    """Raised when cost ceiling is hit."""

class InterviewStateError(InterviewError):
    """Raised for invalid state transitions."""

class InterviewAPIError(InterviewError):
    """Raised for Anthropic API failures."""
```

### Not In Scope (Future Work)

- Claude Agent SDK migration (requires MCP server setup)
- Session persistence/resume (can add later if users request)
- Multiple interview templates (single "reflective" template for now)
- Follow-up questions / adaptive depth
- Streaming responses with Rich Live (current token-based display works)

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/inkwell/interview/models.py` | Create | Pydantic models for structured data |
| `src/inkwell/interview/engine.py` | Create | I/O-agnostic interview logic |
| `src/inkwell/interview/programmatic.py` | Create | Agent-native interface |
| `src/inkwell/interview/interactive.py` | Rename + Refactor | Human CLI interface (was simple_interviewer.py) |
| `src/inkwell/interview/__init__.py` | Update | Export new classes |
| `src/inkwell/pipeline/orchestrator.py` | Update | Use new interview interface |
| `src/inkwell/cli.py` | Update | Remove dead flags |
| `src/inkwell/config/schema.py` | Update | Clean unused config |
| `tests/interview/test_engine.py` | Create | Unit tests |
| `tests/interview/test_programmatic.py` | Create | Agent integration tests |

## References

### Internal
- Current implementation: `src/inkwell/interview/simple_interviewer.py:49-354`
- CLI flags: `src/inkwell/cli.py:727-748`
- Config schema: `src/inkwell/config/schema.py:110-176`
- Orchestrator hook: `src/inkwell/pipeline/orchestrator.py:623-669`
- ADR-020: `docs/building-in-public/adr/020-interview-framework-selection.md`
- ADR-021: `docs/building-in-public/adr/021-interview-state-persistence.md`

### External
- [Agent-native Architectures - Every.to](https://every.to/guides/agent-native)
- [Claude Agent SDK Documentation](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Anthropic SDK Python](https://github.com/anthropics/anthropic-sdk-python)

### Related PRs/Issues
- TODO-034: Simplify interview system (completed)
- Phase 4 Architecture: `docs/building-in-public/architecture/phase-4-interview-system.md`
