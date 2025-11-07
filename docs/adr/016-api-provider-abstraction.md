# ADR-016: API Provider Abstraction

**Date**: 2025-11-07
**Status**: Accepted
**Context**: Phase 3 Unit 4 - LLM Provider Implementation

---

## Context

Inkwell uses LLMs to extract structured information from podcast transcripts. Multiple LLM providers are available (Claude, Gemini), each with different:
- APIs and SDKs
- Pricing models
- Capabilities (JSON mode, function calling, etc.)
- Quality characteristics

We need a way to:
1. Support multiple providers with consistent interface
2. Make it easy to add new providers
3. Allow users to choose provider based on needs (quality vs. cost)
4. Estimate costs before making API calls

## Decision

**We will create an abstract `BaseExtractor` class that defines the interface for all LLM providers.**

All provider implementations (ClaudeExtractor, GeminiExtractor, etc.) must:

1. Inherit from `BaseExtractor`
2. Implement required abstract methods:
   - `async def extract()` - Perform extraction
   - `def estimate_cost()` - Calculate cost estimate
   - `def supports_structured_output()` - Report JSON mode support

3. Can override optional methods:
   - `build_prompt()` - Prompt rendering (default Jinja2 implementation provided)
   - `_count_tokens()` - Token estimation (default 4 chars/token approximation)

## Rationale

### Why Abstract Base Class?

**Alternatives considered:**
- Protocol (structural typing)
- Duck typing (no interface)
- Strategy pattern with separate classes

**Decision: ABC**

Pros:
- ✅ Explicit interface contract
- ✅ Runtime validation (can't instantiate without implementing required methods)
- ✅ IDE support and type checking
- ✅ Clear documentation of requirements

Cons:
- ❌ More verbose than Protocol
- ❌ Inheritance (composition might be cleaner)

**Verdict:** Benefits outweigh drawbacks for this use case.

### Why These Methods?

**`async def extract(template, transcript, metadata) -> str`**
- Primary functionality: perform extraction
- Async for non-blocking API calls
- Returns raw string (parsing happens elsewhere)
- Takes template, transcript, and metadata

**`def estimate_cost(template, transcript_length) -> float`**
- Users need to know costs before committing
- Returns USD cost estimate
- Allows cost-aware template selection

**`def supports_structured_output() -> bool`**
- Some providers have native JSON mode
- Others need prompting for JSON
- Enables optimization decisions

### Why Not Include Parsing?

Parsing happens in extraction engine (Unit 5), not in provider implementation.

Reasons:
- Parsing logic is provider-agnostic
- Easier to test separately
- Provider focuses on API communication
- Separation of concerns

### Provider Selection Strategy

**Current approach:** Manual selection via config/parameter

**Future considerations:**
- Auto-selection based on template requirements
- Fallback chain (try Claude, fall back to Gemini)
- A/B testing for quality comparison

## Implementation

### BaseExtractor (Abstract)

```python
class BaseExtractor(ABC):
    @abstractmethod
    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any]
    ) -> str:
        """Extract content using template."""
        pass

    @abstractmethod
    def estimate_cost(
        self,
        template: ExtractionTemplate,
        transcript_length: int
    ) -> float:
        """Estimate cost in USD."""
        pass

    @abstractmethod
    def supports_structured_output(self) -> bool:
        """Whether provider has native JSON mode."""
        pass

    def build_prompt(self, template, transcript, metadata) -> str:
        """Build prompt from template (default Jinja2)."""
        # Default implementation provided
        pass
```

### ClaudeExtractor

**Pricing (Nov 2024):**
- Input: $3.00/M tokens
- Output: $15.00/M tokens

**Features:**
- High quality (best for quotes, precise data)
- Native JSON mode (`response_format`)
- Expensive but accurate

**Use cases:**
- Quote extraction (precision critical)
- Complex structured data
- When budget allows

### GeminiExtractor

**Pricing (Nov 2024):**
- Input: $0.075/M tokens (<128K)
- Input: $0.15/M tokens (>128K)
- Output: $0.30/M tokens

**Features:**
- Good quality (85-90% of Claude quality)
- Native JSON mode (`response_mime_type`)
- 40x cheaper than Claude
- Long context (1M tokens)

**Use cases:**
- Summaries
- General extraction
- Cost-sensitive scenarios
- Long transcripts

## Cost Comparison

Example: 10K word transcript (40K tokens), 1K token output

| Provider | Input Cost | Output Cost | Total  | Relative |
|----------|------------|-------------|--------|----------|
| Claude   | $0.12      | $0.015      | $0.135 | 41x      |
| Gemini   | $0.003     | $0.0003     | $0.003 | 1x       |

**Gemini is ~41x cheaper** for typical workloads.

## Error Handling

### Error Hierarchy

```
ExtractionError (base)
├── ProviderError (API errors, rate limits, auth)
├── ValidationError (invalid output, schema mismatch)
└── TemplateError (template rendering issues)
```

### Retry Strategy

Not implemented in Unit 4. Future work:
- Exponential backoff for rate limits
- Automatic fallback to alternate provider
- Circuit breaker for persistent failures

## Testing Strategy

**Unit tests:**
- Mock API responses
- Test error handling
- Verify cost estimation
- Validate prompt building

**Integration tests (Unit 9):**
- Real API calls with test keys
- E2E extraction flow
- Cost tracking

## Future Enhancements

### 1. Additional Providers

Easy to add:
- OpenAI GPT-4
- Cohere
- Open-source models (Llama via Ollama)

### 2. Provider Auto-Selection

```python
def select_provider(template: ExtractionTemplate) -> BaseExtractor:
    if template.model_preference == "claude":
        return ClaudeExtractor()
    elif template.expected_format == "json" and template.max_tokens > 2000:
        return ClaudeExtractor()  # Complex structured data
    else:
        return GeminiExtractor()  # Default to cheaper
```

### 3. Caching & Rate Limiting

```python
class RateLimitedExtractor(BaseExtractor):
    def __init__(self, inner: BaseExtractor, max_rpm: int):
        self.inner = inner
        self.rate_limiter = RateLimiter(max_rpm)

    async def extract(self, ...):
        async with self.rate_limiter:
            return await self.inner.extract(...)
```

### 4. Cost Tracking

```python
class CostTrackingExtractor(BaseExtractor):
    def __init__(self, inner: BaseExtractor):
        self.inner = inner
        self.total_cost = 0.0

    async def extract(self, ...):
        estimated_cost = self.inner.estimate_cost(...)
        result = await self.inner.extract(...)
        self.total_cost += estimated_cost
        return result
```

## Consequences

### Positive

✅ Easy to add new providers (implement 3 methods)
✅ Consistent interface across providers
✅ Cost transparency for users
✅ Provider-agnostic template system
✅ Testable with mocks

### Negative

❌ Abstraction overhead (extra layer)
❌ Lowest common denominator (can't use provider-specific features easily)
❌ Cost estimation is approximate (actual costs may vary)

### Neutral

- Async all the way (required for good performance)
- Provider selection is manual (could be smarter)

## Related

- [ADR-013: LLM Provider Abstraction](./013-llm-provider-abstraction.md) - Initial decision
- [Research: LLM Extraction Comparison](../research/llm-extraction-comparison.md) - Quality vs. cost analysis
- [Unit 4 Devlog](../devlog/2025-11-07-phase-3-unit-4-provider-implementation.md) - Implementation details

---

## Revision History

- 2025-11-07: Initial ADR (Phase 3 Unit 4)
