---
status: resolved
priority: p3
issue_id: "014"
tags: [code-review, performance, optimization, api]
dependencies: []
---

# Batch API Requests for Template Extraction

## Problem Statement

Template extraction makes separate API calls for each template (4-5 calls per episode). Batching these into a single API call would reduce network overhead by 75% and improve processing speed by 30-40%.

**Severity**: LOW (Performance Optimization)

## Findings

- Discovered during performance analysis by performance-oracle agent
- Location: `src/inkwell/extraction/engine.py:162-167`
- Templates processed concurrently but not batched
- Each template = separate API round trip
- Network latency compounds (4 × 50ms = 200ms overhead)

**Current Behavior**:
```python
# 4 separate API calls (concurrent but not batched)
tasks = [
    self.extract(template, transcript, metadata)
    for template in templates
]
results = await asyncio.gather(*tasks)

# Result: 4 API calls, 4 × network latency
```

**Performance Impact**:
- Short episode (15min): 4 templates × ~2.5s = 10s extraction
- Long episode (90min): 4 templates × ~16s = 65s extraction
- Network overhead: ~200ms per episode (4 × 50ms)

## Proposed Solutions

### Option 1: Batch Multiple Templates in Single API Call (Recommended)
**Pros**:
- 75% reduction in API calls (4 → 1)
- 30-40% faster extraction
- Lower cost (fewer request charges)

**Cons**:
- More complex prompt engineering
- Single point of failure
- Requires response parsing changes

**Effort**: Medium (3-4 hours)
**Risk**: Medium

**Implementation**:

```python
# src/inkwell/extraction/engine.py

async def extract_all_batched(
    self,
    templates: list[ExtractionTemplate],
    transcript: str,
    metadata: dict[str, Any],
    use_cache: bool = True,
) -> list[ExtractionResult]:
    """Extract all templates in a single batched API call.

    Args:
        templates: List of extraction templates
        transcript: Episode transcript
        metadata: Episode metadata
        use_cache: Whether to use cache

    Returns:
        List of extraction results (one per template)

    Example:
        >>> results = await engine.extract_all_batched(
        ...     [summary_template, quotes_template, concepts_template],
        ...     transcript,
        ...     metadata
        ... )
    """
    # Check cache for each template
    cached_results = {}
    uncached_templates = []

    if use_cache:
        for template in templates:
            cached = await self._get_from_cache(template, transcript)
            if cached:
                cached_results[template.name] = cached
            else:
                uncached_templates.append(template)
    else:
        uncached_templates = templates

    # If all cached, return early
    if not uncached_templates:
        return [cached_results[t.name] for t in templates]

    # Build batched prompt
    batched_prompt = self._create_batch_prompt(uncached_templates, transcript, metadata)

    # Single API call for all templates
    try:
        response = await self._call_llm_batched(batched_prompt)
        batch_results = self._parse_batch_response(response, uncached_templates)

        # Cache individual results
        for template, result in zip(uncached_templates, batch_results):
            if result.success and use_cache:
                await self._save_to_cache(template, transcript, result)

    except Exception as e:
        logger.error(f"Batch extraction failed: {e}")
        # Fallback to individual extraction
        batch_results = await self._extract_individually(uncached_templates, transcript, metadata)

    # Combine cached and new results
    all_results = []
    for template in templates:
        if template.name in cached_results:
            all_results.append(cached_results[template.name])
        else:
            # Find in batch results
            result = next(
                (r for r, t in zip(batch_results, uncached_templates) if t.name == template.name),
                None
            )
            all_results.append(result)

    return all_results


def _create_batch_prompt(
    self,
    templates: list[ExtractionTemplate],
    transcript: str,
    metadata: dict[str, Any],
) -> str:
    """Create combined prompt for multiple templates.

    Args:
        templates: Templates to extract
        transcript: Episode transcript
        metadata: Episode metadata

    Returns:
        Combined prompt string

    Example:
        Prompt format:
        '''
        Analyze this podcast transcript and provide multiple extractions:

        1. SUMMARY:
        [template instructions]

        2. QUOTES:
        [template instructions]

        3. KEY CONCEPTS:
        [template instructions]

        TRANSCRIPT:
        [full transcript]

        Provide your response as JSON:
        {
            "summary": "...",
            "quotes": [...],
            "key_concepts": [...]
        }
        '''
    """
    # Build combined instructions
    instructions = []
    for i, template in enumerate(templates, 1):
        instructions.append(f"{i}. {template.name.upper().replace('-', ' ')}:")
        instructions.append(template.user_prompt)
        instructions.append("")

    # Build JSON schema
    schema = {
        template.name: "..."
        for template in templates
    }

    prompt = f"""
Analyze this podcast transcript and provide multiple extractions.

PODCAST INFORMATION:
- Title: {metadata.get('title', 'Unknown')}
- Podcast: {metadata.get('podcast', 'Unknown')}
- Duration: {metadata.get('duration', 'Unknown')}

EXTRACTION TASKS:
{'\\n'.join(instructions)}

TRANSCRIPT:
{transcript}

Provide your response as JSON with the following structure:
{json.dumps(schema, indent=2)}

Each field should contain the extracted information for that task.
""".strip()

    return prompt


def _parse_batch_response(
    self,
    response: str,
    templates: list[ExtractionTemplate],
) -> list[ExtractionResult]:
    """Parse batched LLM response into individual results.

    Args:
        response: LLM response text
        templates: Templates that were batched

    Returns:
        List of extraction results

    Raises:
        ValueError: If response cannot be parsed
    """
    try:
        # Extract JSON from response
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        json_str = response[json_start:json_end]
        data = json.loads(json_str)

        # Create results for each template
        results = []
        for template in templates:
            template_data = data.get(template.name)
            if template_data is None:
                # Template not in response
                results.append(ExtractionResult(
                    success=False,
                    error=f"Missing {template.name} in batch response"
                ))
            else:
                # Convert to expected format
                formatted = self._format_template_output(template, template_data)
                results.append(ExtractionResult(
                    success=True,
                    content=formatted
                ))

        return results

    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse batch response: {e}")
        raise ValueError(f"Invalid batch response format: {e}")


async def _extract_individually(
    self,
    templates: list[ExtractionTemplate],
    transcript: str,
    metadata: dict[str, Any],
) -> list[ExtractionResult]:
    """Fallback: extract templates individually if batch fails.

    Args:
        templates: Templates to extract
        transcript: Episode transcript
        metadata: Episode metadata

    Returns:
        List of extraction results
    """
    logger.warning("Batch extraction failed, falling back to individual extraction")

    tasks = [
        self.extract(template, transcript, metadata, use_cache=False)
        for template in templates
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)


# Update CLI to use batched extraction:
# src/inkwell/cli.py

async def process_episode(...):
    # ... existing code ...

    # OLD: Individual extraction (concurrent but not batched)
    # results = await engine.extract_all(templates, transcript, metadata)

    # NEW: Batched extraction
    results = await engine.extract_all_batched(templates, transcript, metadata)

    # ... rest of code ...
```

**Expected Improvement**:
- API calls: 4 → 1 (75% reduction)
- Network overhead: 200ms → 50ms (75% reduction)
- Processing time: 10-65s → 7-45s (30-40% faster)
- Cost: Minimal savings (token count similar)

### Option 2: Keep Current Approach
**Pros**:
- Simpler implementation
- Individual failures don't affect others
- Easier to cache

**Cons**:
- 4× network overhead
- Slower processing

**Effort**: None
**Risk**: None

## Recommended Action

Consider Option 1 for v1.1. Current performance is acceptable (2x realtime), but batching would improve UX significantly.

## Technical Details

**Affected Files**:
- `src/inkwell/extraction/engine.py:162-167` (extract_all method)
- `src/inkwell/cli.py` (process_episode function)

**New Files**:
None (changes to existing files)

**Related Components**:
- LLM API calls
- Caching layer
- Cost tracking

**Database Changes**: No

## Resources

- API Batching Best Practices: https://cloud.google.com/apis/design/design_patterns#batch_operations
- Gemini Batch API: https://ai.google.dev/gemini-api/docs/caching

## Acceptance Criteria

- [ ] Batch extraction method implemented
- [ ] Prompt engineering for multiple templates
- [ ] JSON response parsing for batched results
- [ ] Fallback to individual extraction on batch failure
- [ ] Cache integration maintained
- [ ] Cost tracking updated for batched calls
- [ ] Unit tests for batch extraction
- [ ] Unit tests for response parsing
- [ ] Integration tests comparing batch vs individual
- [ ] Performance benchmarks showing improvement
- [ ] Documentation updated
- [ ] All existing tests pass

## Work Log

### 2025-11-13 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during performance analysis
- Analyzed by performance-oracle agent
- Calculated network overhead impact
- Categorized as LOW priority (optimization)

**Learnings**:
- Batching reduces network round trips
- Single API call more efficient than concurrent calls
- Prompt engineering can handle multiple tasks
- Fallback important for reliability

## Notes

**Why Batching Helps**:

Current (4 separate API calls):
```
Time 0ms:   Send template 1 ────→ LLM
Time 0ms:   Send template 2 ────→ LLM
Time 0ms:   Send template 3 ────→ LLM
Time 0ms:   Send template 4 ────→ LLM
Time 50ms:  ←──── Response 1
Time 50ms:  ←──── Response 2
Time 50ms:  ←──── Response 3
Time 50ms:  ←──── Response 4

Total network time: 100ms (50ms each way)
Total API calls: 4
```

Batched (1 API call):
```
Time 0ms:   Send batch ────────→ LLM
Time 50ms:  ←──────── Batch response

Total network time: 100ms (50ms each way)
Total API calls: 1
Network overhead saved: 150ms
```

**Trade-offs**:

**Advantages**:
- Fewer API calls = faster
- Less network overhead
- Simpler cost tracking

**Disadvantages**:
- Single point of failure (all or nothing)
- Harder to cache (must parse batch response first)
- More complex error handling
- Larger prompt = more expensive

**When to Batch**:
- Multiple similar operations
- Network latency significant
- Operations can share context

**When Not to Batch**:
- Operations very different
- Individual caching important
- Failure isolation critical

**Prompt Engineering Challenge**:

Must clearly separate tasks:
```
BAD (confusing):
"Provide a summary and quotes and key concepts"

GOOD (structured):
"Provide three separate extractions:
1. SUMMARY: [instructions]
2. QUOTES: [instructions]
3. KEY CONCEPTS: [instructions]"
```

**Testing Strategy**:
```python
@pytest.mark.asyncio
async def test_batch_extraction():
    """Test batched extraction produces same results as individual."""
    engine = ExtractionEngine(...)
    templates = [summary_template, quotes_template, concepts_template]
    transcript = "..."

    # Batch extraction
    batch_results = await engine.extract_all_batched(templates, transcript, {})

    # Individual extraction (for comparison)
    individual_results = []
    for template in templates:
        result = await engine.extract(template, transcript, {})
        individual_results.append(result)

    # Should produce similar results
    assert len(batch_results) == len(individual_results)
    for batch, individual in zip(batch_results, individual_results):
        assert batch.success == individual.success
        # Content should be similar (not exact due to LLM randomness)
```

**Source**: Code review performed on 2025-11-13
**Review command**: /review #9
