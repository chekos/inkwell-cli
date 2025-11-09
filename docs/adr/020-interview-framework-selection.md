# ADR-020: Interview Framework Selection

**Status**: Accepted
**Date**: 2025-11-08
**Deciders**: Development Team
**Related**: Phase 4 Unit 1, [Research: Claude Agent SDK Integration](../research/claude-agent-sdk-integration.md)

## Context

Phase 4 adds Interview Mode to Inkwell, enabling conversational reflection on podcast episodes. We need to choose how to implement the conversational AI component that will generate contextual questions and conduct natural interviews with users.

### Requirements

1. **Natural Conversation** - Multi-turn dialogue with context awareness
2. **Streaming Responses** - Real-time text display for better UX
3. **State Management** - Track conversation history and session state
4. **Cost Efficiency** - Minimize API costs while maintaining quality
5. **Error Handling** - Robust error recovery for network issues
6. **Testability** - Easy to mock and test
7. **Maintainability** - Simple, clear implementation

### Constraints

- Must use Claude models (Anthropic) for question quality
- Already have `anthropic` package installed (v0.72.0+)
- Want to minimize new dependencies
- Need async support for responsive UI

## Decision

**Use the Anthropic Python SDK directly**, building conversation management ourselves rather than using an agent framework or custom abstraction.

### Implementation Approach

```python
from anthropic import AsyncAnthropic

class InterviewAgent:
    """Thin wrapper around Anthropic SDK for interviews"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate_question(
        self,
        context: str,
        conversation_history: list[dict],
        system_prompt: str,
    ) -> str:
        """Generate next interview question"""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            system=system_prompt,
            messages=conversation_history
        )

        return response.content[0].text

    async def stream_response(
        self,
        messages: list[dict],
        system_prompt: str,
    ) -> AsyncIterator[str]:
        """Stream response for real-time display"""

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=500,
            system=system_prompt,
            messages=messages
        ) as stream:
            async for text in stream.text_stream:
                yield text
```

**Conversation State Management**:
- Maintain message list in `InterviewSession` Pydantic model
- Append user/assistant messages after each exchange
- Persist to JSON for resume capability
- No framework-specific state management

## Alternatives Considered

### Alternative 1: LangChain Agents

**Description**: Use LangChain's conversation agent framework

**Pros**:
- Built-in conversation memory management
- Tool-calling capabilities (future extensions)
- State persistence helpers
- Well-documented patterns

**Cons**:
- Heavy additional dependency (`langchain`, `langchain-anthropic`)
- Adds ~50MB to installation size
- Framework overhead and complexity
- Less control over exact prompt structure
- Harder to debug conversation flow
- Overkill for our simple Q&A use case
- Learning curve for framework

**Why Rejected**: Too much complexity and dependency weight for what is essentially structured conversation management we can easily implement ourselves.

### Alternative 2: Custom Agent Framework

**Description**: Build our own agent abstraction with memory, tools, etc.

**Pros**:
- Perfect fit for our needs
- Full control over architecture
- No external dependencies
- Can evolve as needed

**Cons**:
- More code to write and maintain
- Reinventing wheels (message history, state)
- Risk of over-engineering
- Testing burden increases
- Longer initial implementation time

**Why Rejected**: While appealing, the complexity isn't justified. Our needs are simple enough that a thin wrapper over the SDK is sufficient.

### Alternative 3: OpenAI-style Direct API Calls

**Description**: Use raw HTTP requests to Anthropic API

**Pros**:
- Maximum control
- No SDK dependency
- Minimal overhead

**Cons**:
- Have to implement request/response handling
- Manual error handling and retries
- No streaming helpers
- Type safety concerns
- Already have SDK installed anyway

**Why Rejected**: The Anthropic SDK is already a dependency and provides excellent async/streaming support. No benefit to going lower-level.

### Alternative 4: Claude Agent SDK (Hypothetical)

**Description**: Use a purpose-built "Claude Agent SDK" if it existed

**Note**: During research, we discovered there isn't a separate "Claude Agent SDK" from Anthropic. The standard Python SDK (`anthropic`) is the official way to build agent-like applications.

## Decision Rationale

### Why Direct SDK Usage is Best

1. **Already a Dependency**
   - `anthropic` already in pyproject.toml
   - No new packages to add
   - Zero dependency bloat

2. **Simple Use Case**
   - Interview = structured Q&A conversation
   - No complex tools or workflows needed
   - Message history is straightforward list

3. **Full Control**
   - Complete control over prompts and conversation flow
   - Easy to customize for our exact needs
   - Can optimize costs precisely
   - Clear debugging and testing

4. **Excellent SDK Features**
   - Async/await support out of the box
   - Streaming via `messages.stream()`
   - Token usage tracking included
   - Good error handling and retries

5. **Testing & Debugging**
   - Can easily mock `AsyncAnthropic`
   - Clear request/response flow
   - No framework magic to debug
   - Simple stack traces

6. **Performance**
   - No framework overhead
   - Direct API calls
   - Streaming fully supported
   - Minimal latency

7. **Maintainability**
   - Small, focused codebase
   - Easy for contributors to understand
   - No framework version coupling
   - Can upgrade SDK independently

### What We're Building

**Thin `InterviewAgent` Wrapper**:
- Encapsulates Anthropic SDK client
- Provides convenience methods for interview-specific patterns
- Handles cost tracking and token counting
- Manages system prompts and message formatting
- No complex state management or memory

**Separate State Management**:
- `InterviewSession` Pydantic model holds conversation state
- Messages list managed explicitly
- JSON serialization for persistence
- Simple, transparent, testable

## Consequences

### Positive

- ✅ **No new dependencies** - Uses existing `anthropic` package
- ✅ **Simple implementation** - Thin wrapper, ~300 lines of code
- ✅ **Easy to test** - Mock AsyncAnthropic, test wrapper methods
- ✅ **Full control** - Every prompt is explicit and customizable
- ✅ **Transparent costs** - Token usage directly from API response
- ✅ **Easy debugging** - Clear request/response flow
- ✅ **Streaming support** - Native SDK streaming works great
- ✅ **Maintainable** - Small codebase, easy to understand

### Negative

- ⚠️ **Manual state management** - We implement conversation history ourselves
  - *Mitigation*: Use Pydantic model for type safety, simple list append
- ⚠️ **Manual prompt engineering** - No framework templates
  - *Mitigation*: Create our own template system (more flexibility anyway)
- ⚠️ **No built-in retries** - Have to implement error handling
  - *Mitigation*: SDK has good errors, we add retry logic in wrapper
- ⚠️ **Future extensibility** - If we want complex agent features later
  - *Mitigation*: Can always refactor to framework if needs grow

### Trade-offs Accepted

- **Simplicity over Features** - We're building for our specific use case, not a general agent framework
- **Code over Configuration** - Explicit Python code rather than framework config
- **Control over Convenience** - More control at cost of some boilerplate

## Implementation Plan

1. **Create `InterviewAgent` class** (`interview/agent.py`)
   - Wrap `AsyncAnthropic` client
   - Methods: `generate_question()`, `stream_response()`
   - Cost tracking and token counting

2. **Create `InterviewSession` model** (`interview/models.py`)
   - Pydantic model with messages list
   - Serialization to/from JSON
   - State machine for conversation flow

3. **Create Template System** (`interview/templates/`)
   - System prompts for different interview styles
   - Load from YAML or Python constants
   - User-customizable via config

4. **Testing Strategy**
   - Mock `AsyncAnthropic` with `respx`
   - Unit test wrapper methods
   - Integration test with real API (opt-in)

## Monitoring & Review

### Success Criteria

- Interview conversations feel natural
- Question quality is high (context-aware, thoughtful)
- Cost per interview < $0.50
- Streaming responses work smoothly
- Easy to add new interview templates
- Tests cover 90%+ of agent code

### Review Trigger

Consider revisiting this decision if:
- We need complex multi-agent orchestration
- Tool-calling becomes essential feature
- State management complexity grows significantly
- Community requests LangChain integration

## References

- [Anthropic Python SDK Documentation](https://github.com/anthropics/anthropic-sdk-python)
- [Claude API Messages](https://docs.anthropic.com/en/api/messages)
- [Streaming Messages](https://docs.anthropic.com/en/api/messages-streaming)
- [Research: Claude Agent SDK Integration](../research/claude-agent-sdk-integration.md)

## Related Decisions

- ADR-021: Interview State Persistence (JSON-based)
- ADR-023: Interview Template System
- ADR-024: Interview Question Generation

---

**Decision**: Use Anthropic Python SDK directly with thin wrapper
**Rationale**: Simple, no new dependencies, full control, perfect for our use case
**Status**: ✅ Accepted
