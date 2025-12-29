# ADR-013: LLM Provider Abstraction

**Date**: 2025-11-07
**Status**: Accepted
**Deciders**: Phase 3 Team
**Related**: [ADR-016](016-default-llm-provider.md), [LLM Comparison Research](../research/llm-extraction-comparison.md)

## Context

Phase 3 requires LLM integration for content extraction from podcast transcripts. Multiple LLM providers are available (Claude, Gemini, GPT-4, local models), each with different:
- APIs and interfaces
- Pricing models
- Quality characteristics
- Structured output support
- Rate limits

We need to decide whether to:
1. Hard-code a single provider
2. Support multiple providers via abstraction
3. Build a pluggable provider system

Users have different priorities:
- Some prioritize quality (willing to pay for Claude)
- Some prioritize cost (prefer Gemini)
- Some want privacy (local models)
- Some want flexibility (switch providers)

## Decision

**We will implement an abstract `BaseExtractor` interface with concrete implementations for multiple LLM providers, starting with Claude and Gemini.**

### Architecture

```python
# Abstract base
class BaseExtractor(ABC):
    @abstractmethod
    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict,
    ) -> ExtractedContent:
        """Extract content using template and transcript"""
        pass

    @abstractmethod
    def estimate_cost(self, template: ExtractionTemplate, transcript_length: int) -> float:
        """Estimate extraction cost in USD"""
        pass

    @abstractmethod
    def supports_structured_output(self) -> bool:
        """Whether provider supports structured output (JSON mode)"""
        pass

# Concrete implementations
class ClaudeExtractor(BaseExtractor):
    """Claude API extractor"""
    ...

class GeminiExtractor(BaseExtractor):
    """Gemini API extractor"""
    ...

# Future
class LocalExtractor(BaseExtractor):
    """Local model extractor (Ollama, llama.cpp)"""
    ...

# Factory
class ExtractorFactory:
    @staticmethod
    def create(provider: str, api_key: str, **kwargs) -> BaseExtractor:
        if provider == "claude":
            return ClaudeExtractor(api_key, **kwargs)
        elif provider == "gemini":
            return GeminiExtractor(api_key, **kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider}")
```

### Configuration

```yaml
# Global default
default_llm_provider: claude

# Provider API keys (via environment or config)
anthropic_api_key: ${ANTHROPIC_API_KEY}
google_api_key: ${GOOGLE_API_KEY}

# Provider-specific settings
llm_providers:
  claude:
    model: claude-sonnet-4-5-20250929
    default_temperature: 0.3
    default_max_tokens: 2000
  gemini:
    model: gemini-2.0-flash-exp
    default_temperature: 0.3
    default_max_tokens: 2000
```

### Template-Level Override

```yaml
# Template can specify preferred provider
name: quotes
model_preference: claude  # Use Claude for this template

# Or let system decide
name: summary
model_preference: auto  # Use default provider
```

### CLI Override

```bash
# Use specific provider
inkwell fetch "podcast" --latest --llm-provider gemini

# Use default
inkwell fetch "podcast" --latest
```

## Alternatives Considered

### Alternative 1: Hard-code Claude Only

**Pros:**
- Simplest implementation
- Best quality (Claude excels at extraction)
- No abstraction overhead
- Fewer edge cases

**Cons:**
- No flexibility for users
- Vendor lock-in
- Higher costs for all users
- Can't use free Gemini tier
- No path to local models

**Rejected because**: Users need cost/quality trade-offs

### Alternative 2: Hard-code Gemini Only

**Pros:**
- Cheapest option
- Generous free tier
- Good for experimentation
- Large context window

**Cons:**
- Lower quality extractions
- Less consistent structured output
- Professional users need better quality
- Quote accuracy issues

**Rejected because**: Quality matters for production use

### Alternative 3: User Must Choose (No Default)

**Pros:**
- Forces conscious choice
- No opinionated defaults
- Clear cost implications

**Cons:**
- Poor user experience (friction)
- Requires understanding of providers
- Extra configuration burden
- Decision paralysis

**Rejected because**: Defaults should work out-of-box

### Alternative 4: Always Ask at Runtime

**Pros:**
- User control every time
- Cost visibility

**Cons:**
- Annoying for repeated use
- Breaks automation
- Poor CLI UX

**Rejected because**: Too much friction

## Rationale

### Why Abstraction?

1. **User Flexibility**: Different users have different priorities
   - Budget-conscious → Gemini
   - Quality-focused → Claude
   - Privacy-focused → Local models (future)

2. **Template-Specific Needs**: Different templates have different requirements
   - Quotes → Claude (precision critical)
   - Summary → Either (both work well)
   - Experiments → Gemini (cheap iteration)

3. **Future-Proofing**: New providers will emerge
   - GPT-4 structured output
   - Local models (Ollama, llama.cpp)
   - Specialized models

4. **Cost Optimization**: Smart provider selection
   - Auto-route based on template complexity
   - Fallback to cheaper provider if quality sufficient
   - Batch processing with cost-effective provider

5. **Vendor Independence**: Avoid lock-in
   - Provider pricing changes
   - Service availability
   - API changes

### Why Not Full Plugin System?

**Considered but deferred:**
- Full plugin architecture with external providers
- User-written provider plugins
- Dynamic provider loading

**Reasons:**
- Over-engineering for current needs
- Security risk (running user code)
- Complexity not justified yet
- Can add later if needed

**Current approach:**
- Built-in providers (Claude, Gemini)
- Clean interface for adding more
- Extensible without plugins

## Consequences

### Positive

✅ **User Choice**: Users select cost/quality trade-off
✅ **Flexibility**: Easy to add new providers
✅ **Testing**: Can mock providers for tests
✅ **Cost Control**: Users can optimize costs
✅ **Future-Proof**: Ready for new models

### Negative

❌ **Complexity**: More code than single provider
❌ **Maintenance**: Must update multiple integrations
❌ **Testing Burden**: Test all providers
❌ **Documentation**: Explain provider differences
❌ **Configuration**: More settings to manage

### Mitigations

1. **Good Defaults**: Claude default works well
2. **Clear Docs**: Explain when to use which provider
3. **Shared Code**: Abstract common logic
4. **Comprehensive Tests**: Mock all providers
5. **Provider Recommendations**: Guide users to right choice

## Implementation Plan

### Phase 1: Core Abstraction (Unit 4)
- Define `BaseExtractor` interface
- Implement `ClaudeExtractor`
- Implement `GeminiExtractor`
- Create `ExtractorFactory`

### Phase 2: Configuration (Unit 4)
- Add provider configuration to config schema
- Environment variable support
- Template-level override
- CLI flag support

### Phase 3: Testing (Unit 4-5)
- Mock extractor for tests
- Test each provider implementation
- Integration tests with real APIs
- Cost estimation tests

### Phase 4: Documentation (Unit 4)
- Provider comparison guide
- Configuration examples
- When to use which provider
- Cost optimization tips

## Validation

### Success Criteria

✅ Can switch providers via config
✅ Templates can specify preferred provider
✅ CLI can override provider
✅ Costs estimated accurately per provider
✅ Tests pass with mocked providers
✅ Clear error messages when API key missing

### Testing Strategy

```python
# Unit tests with mock
def test_extract_with_claude(mock_anthropic):
    extractor = ClaudeExtractor(api_key="test")
    result = await extractor.extract(template, transcript, metadata)
    assert result.content is not None

# Integration tests (marked slow)
@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="API key required")
def test_real_claude_extraction():
    extractor = ClaudeExtractor(api_key=os.getenv("ANTHROPIC_API_KEY"))
    result = await extractor.extract(sample_template, sample_transcript, {})
    assert result.confidence > 0.8
```

## Related Decisions

- [ADR-016: Default LLM Provider](016-default-llm-provider.md) - Which provider to default to
- [LLM Extraction Comparison](../research/llm-extraction-comparison.md) - Provider comparison research
- [Structured Extraction Patterns](../research/structured-extraction-patterns.md) - How to prompt each provider

## References

- [Anthropic Claude API](https://docs.anthropic.com/)
- [Google Gemini API](https://ai.google.dev/)
- [Abstract Factory Pattern](https://refactoring.guru/design-patterns/abstract-factory)

## Revision History

- 2025-11-07: Initial decision (Phase 3 Unit 1)
