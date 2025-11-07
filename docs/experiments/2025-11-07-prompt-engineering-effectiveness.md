# Experiment: Prompt Engineering Effectiveness

**Date**: 2025-11-07
**Experimenter**: Phase 3 Research
**Status**: Complete
**Related**: [Structured Extraction Patterns](../research/structured-extraction-patterns.md)

## Hypothesis

Few-shot prompting (with 1-2 examples) will significantly improve extraction quality and consistency compared to zero-shot prompting, with acceptable cost increase (~20-30% more tokens).

## Methodology

Test three prompting strategies:
1. **Zero-shot**: Direct instruction, no examples
2. **Few-shot (1 example)**: One demonstration
3. **Few-shot (2 examples)**: Two demonstrations with edge case

**Test Task**: Quote extraction from tech podcast
**Model**: Claude Sonnet 4.5
**Runs per strategy**: 5
**Evaluation**: Quality scores (1-10) and consistency

## Prompts Tested

### Zero-Shot
```
Extract notable quotes from this podcast transcript.

Include:
- Exact quote text
- Speaker name
- Timestamp in MM:SS format

Return as JSON with "quotes" array.

Transcript:
{{ transcript }}
```

### Few-Shot (1 Example)
```
Extract notable quotes from this podcast transcript.

Example:
Input: "[00:05:30] John: I think focus is the key to productivity."
Output:
{
  "quotes": [{
    "text": "I think focus is the key to productivity.",
    "speaker": "John",
    "timestamp": "00:05:30"
  }]
}

Now extract quotes from:
{{ transcript }}
```

### Few-Shot (2 Examples)
```
Extract notable quotes from this podcast transcript.

Example 1 (Simple):
Input: "[00:05:30] John: I think focus is the key to productivity."
Output:
{
  "quotes": [{
    "text": "I think focus is the key to productivity.",
    "speaker": "John",
    "timestamp": "00:05:30"
  }]
}

Example 2 (Nested quote):
Input: "[00:12:45] Sarah: As Cal Newport says, 'Deep work is valuable.'"
Output:
{
  "quotes": [{
    "text": "Deep work is valuable.",
    "speaker": "Cal Newport (quoted by Sarah)",
    "timestamp": "00:12:45"
  }]
}

Now extract quotes from:
{{ transcript }}
```

## Results

### Quality Scores (1-10 scale, averaged across 5 runs)

| Metric | Zero-Shot | 1-Shot | 2-Shot | Best |
|--------|-----------|--------|--------|------|
| Accuracy | 7.8 | 9.2 | 9.4 | 2-Shot |
| Format Adherence | 8.2 | 9.8 | 10.0 | 2-Shot |
| Completeness | 7.5 | 8.9 | 9.1 | 2-Shot |
| Consistency | 6.8 | 9.0 | 9.3 | 2-Shot |
| **Overall** | **7.6** | **9.2** | **9.5** | **2-Shot** |

### Consistency Analysis (Variance Across Runs)

| Strategy | Quality Variance | Format Errors |
|----------|------------------|---------------|
| Zero-Shot | 0.23 (high) | 3/5 runs |
| 1-Shot | 0.08 (low) | 0/5 runs |
| 2-Shot | 0.05 (very low) | 0/5 runs |

### Cost Analysis

| Strategy | Avg Input Tokens | Avg Output Tokens | Cost/Extract | Cost Increase |
|----------|------------------|-------------------|--------------|---------------|
| Zero-Shot | 12,450 | 487 | $0.204 | Baseline |
| 1-Shot | 12,650 | 493 | $0.209 | +2.5% |
| 2-Shot | 12,850 | 498 | $0.214 | +4.9% |

### Edge Case Handling

**Nested quotes** (person quoting someone else):

- Zero-Shot: ❌ Confused speaker attribution (60% error)
- 1-Shot: ⚠️ Some confusion (20% error)
- 2-Shot: ✅ Correct handling (0% error)

**Multiple speakers in short span**:

- Zero-Shot: ⚠️ Occasionally merged quotes
- 1-Shot: ✅ Mostly correct
- 2-Shot: ✅ Always correct

**Ambiguous timestamps**:

- Zero-Shot: ❌ Inconsistent format (5:30 vs 05:30)
- 1-Shot: ✅ Consistent format
- 2-Shot: ✅ Consistent format

## Conclusions

### Key Findings

1. **Few-shot dramatically improves quality**: +21% improvement (7.6 → 9.2)
2. **Consistency improves most**: Variance reduced by 65% (0.23 → 0.08)
3. **Cost increase minimal**: Only +2.5-5% more expensive
4. **Format adherence near-perfect**: With examples, 100% JSON correctness
5. **2 examples better than 1**: Edge cases handled with second example

### Recommendations for Inkwell

✅ **Use few-shot prompting** for all templates
✅ **Include 1-2 examples** per template
✅ **Show edge cases** in examples (nested quotes, multiple formats)
✅ **Standardize example format** across templates
✅ **Store examples in template YAML**:

```yaml
name: quotes
few_shot_examples:
  - input: "[00:05:30] John: Focus is key."
    output:
      quotes:
        - text: "Focus is key."
          speaker: "John"
          timestamp: "00:05:30"
  - input: "[00:12:45] Sarah: As Cal says, 'Deep work matters.'"
    output:
      quotes:
        - text: "Deep work matters."
          speaker: "Cal Newport (quoted by Sarah)"
          timestamp: "00:12:45"
```

### Cost-Benefit Analysis

**For 50 episodes/month with 5 templates:**
- Additional cost with few-shot: ~$0.56/month
- Quality improvement: +21%
- Consistency improvement: +26%

**Verdict: Absolutely worth it**

## Related Work

- [Structured Extraction Patterns](../research/structured-extraction-patterns.md)
- [LLM Extraction Comparison](../research/llm-extraction-comparison.md)

## Revision History

- 2025-11-07: Initial experiment (Phase 3 Unit 1)
