---
status: completed
priority: p2
issue_id: "020"
tags: [reliability, error-handling, user-experience, extraction]
dependencies: []
---

# Improve Error Handling for Extraction Failures

## Problem Statement

The extraction engine's `extract_all()` method has basic error handling for failed extractions, but needs improvement. Currently it logs warnings and filters out exceptions, but doesn't provide clear user feedback about which templates failed or why. Users may not notice missing output files when partial failures occur.

**Severity**: IMPORTANT (Reliability / User Experience)

## Findings

- Discovered during code triage session on 2025-11-13
- Location: `src/inkwell/extraction/engine.py:177`
- TODO comment: `# TODO: Better error handling - log failures, allow partial success`
- Current implementation filters exceptions but provides minimal feedback
- No tracking of which specific templates failed
- No retry mechanism for transient failures

**Current Implementation**:
```python
async def extract_all(
    self,
    templates: list[ExtractionTemplate],
    transcript: str,
    metadata: dict[str, Any],
    use_cache: bool = True,
) -> list[ExtractionResult]:
    """Extract all templates concurrently."""
    import asyncio

    # Extract concurrently
    tasks = [
        self.extract(template, transcript, metadata, use_cache)
        for template in templates
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions (return successful results only)
    # TODO: Better error handling - log failures, allow partial success
    successful_results = []
    for result in results:
        if isinstance(result, ExtractionResult):
            successful_results.append(result)
        elif isinstance(result, Exception):
            # Log error but continue
            logger.warning("Extraction failed: %s", result, exc_info=True)

    return successful_results
```

**Problem Scenario**:
1. User processes an episode with 4 templates: summary, quotes, key-concepts, tools-mentioned
2. Network timeout occurs during quotes extraction
3. Other 3 templates succeed
4. Current behavior:
   - Logs warning: "Extraction failed: TimeoutError"
   - Returns 3 successful results
   - Creates 3 output files (summary.md, key-concepts.md, tools-mentioned.md)
   - Missing: quotes.md
5. User sees output directory with 3 files
6. **Problem**: User may not notice quotes.md is missing
7. **Problem**: No clear feedback about what failed
8. **Problem**: No guidance on how to retry just the failed extraction

**Impact**:
- Silent partial failures
- Incomplete episode processing without clear indication
- Poor user experience when errors occur
- Difficult to troubleshoot extraction issues
- No way to retry failed extractions without reprocessing everything

## Proposed Solutions

### Option 1: Extraction Summary with Detailed Reporting (Recommended)

**Pros**:
- Clear visibility into what succeeded/failed
- Detailed error messages per template
- User-facing summary after extraction
- Helps troubleshooting
- Better UX

**Cons**:
- More code complexity
- Need to design summary format

**Effort**: Medium (2-3 hours)
**Risk**: Low

**Implementation**:

```python
# src/inkwell/extraction/models.py

from dataclasses import dataclass
from enum import Enum

class ExtractionStatus(str, Enum):
    """Status of an extraction attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    CACHED = "cached"

@dataclass
class ExtractionAttempt:
    """Record of a single extraction attempt."""
    template_name: str
    status: ExtractionStatus
    result: ExtractionResult | None = None
    error: Exception | None = None
    error_message: str | None = None
    duration_seconds: float | None = None

@dataclass
class ExtractionSummary:
    """Summary of all extraction attempts."""
    total: int
    successful: int
    failed: int
    cached: int
    attempts: list[ExtractionAttempt]

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total == 0:
            return 0.0
        return (self.successful / self.total) * 100

    @property
    def failed_templates(self) -> list[str]:
        """Get list of failed template names."""
        return [
            attempt.template_name
            for attempt in self.attempts
            if attempt.status == ExtractionStatus.FAILED
        ]

    def format_summary(self) -> str:
        """Format summary for user display."""
        lines = [
            f"\nExtraction Summary:",
            f"  Total: {self.total}",
            f"  Successful: {self.successful}",
            f"  Failed: {self.failed}",
            f"  Cached: {self.cached}",
            f"  Success Rate: {self.success_rate:.1f}%",
        ]

        if self.failed > 0:
            lines.append("\nFailed Templates:")
            for attempt in self.attempts:
                if attempt.status == ExtractionStatus.FAILED:
                    error_msg = attempt.error_message or str(attempt.error)
                    lines.append(f"  - {attempt.template_name}: {error_msg}")

        return "\n".join(lines)


# src/inkwell/extraction/engine.py

import time
from inkwell.extraction.models import (
    ExtractionAttempt,
    ExtractionSummary,
    ExtractionStatus
)

async def extract_all(
    self,
    templates: list[ExtractionTemplate],
    transcript: str,
    metadata: dict[str, Any],
    use_cache: bool = True,
) -> tuple[list[ExtractionResult], ExtractionSummary]:
    """Extract all templates concurrently.

    Args:
        templates: List of extraction templates
        transcript: Episode transcript
        metadata: Episode metadata
        use_cache: Whether to use cache

    Returns:
        Tuple of (successful results, extraction summary)
    """
    import asyncio

    # Track timing for each extraction
    start_times = {}

    async def extract_with_tracking(template: ExtractionTemplate):
        """Extract and track timing."""
        start_times[template.name] = time.time()
        return await self.extract(template, transcript, metadata, use_cache)

    # Extract concurrently
    tasks = [extract_with_tracking(template) for template in templates]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Build detailed summary
    attempts = []
    successful_results = []

    for template, result in zip(templates, results):
        duration = time.time() - start_times.get(template.name, time.time())

        if isinstance(result, ExtractionResult):
            if result.success:
                # Determine if from cache
                status = (ExtractionStatus.CACHED
                         if result.from_cache
                         else ExtractionStatus.SUCCESS)

                attempts.append(ExtractionAttempt(
                    template_name=template.name,
                    status=status,
                    result=result,
                    duration_seconds=duration,
                ))
                successful_results.append(result)
            else:
                # ExtractionResult with success=False
                attempts.append(ExtractionAttempt(
                    template_name=template.name,
                    status=ExtractionStatus.FAILED,
                    error_message=result.error,
                    duration_seconds=duration,
                ))
                logger.warning(
                    f"Extraction failed for template '{template.name}': {result.error}"
                )

        elif isinstance(result, Exception):
            # Exception during extraction
            attempts.append(ExtractionAttempt(
                template_name=template.name,
                status=ExtractionStatus.FAILED,
                error=result,
                error_message=str(result),
                duration_seconds=duration,
            ))
            logger.error(
                f"Extraction failed for template '{template.name}': {result}",
                exc_info=result
            )

    # Build summary
    summary = ExtractionSummary(
        total=len(templates),
        successful=sum(1 for a in attempts if a.status == ExtractionStatus.SUCCESS),
        failed=sum(1 for a in attempts if a.status == ExtractionStatus.FAILED),
        cached=sum(1 for a in attempts if a.status == ExtractionStatus.CACHED),
        attempts=attempts,
    )

    # Log summary
    logger.info(
        f"Extraction complete: {summary.successful}/{summary.total} successful, "
        f"{summary.failed} failed, {summary.cached} cached"
    )

    return successful_results, summary


# src/inkwell/cli.py - Update to use summary

async def process_episode(...):
    # ... existing code ...

    # Extract content
    results, summary = await engine.extract_all(templates, transcript, metadata)

    # Show summary to user
    if summary.failed > 0:
        console.print(summary.format_summary(), style="yellow")
        console.print(
            f"\n[yellow]⚠[/yellow] {summary.failed} template(s) failed. "
            f"Check logs for details."
        )
    else:
        console.print(
            f"[green]✓[/green] All {summary.total} templates extracted successfully"
        )

    # ... continue with successful results ...
```

**User Experience Improvement**:
```
Before:
[Generic progress bar]
✓ Episode processed successfully
[User doesn't realize quotes.md is missing]

After:
Processing episode...
[Progress bar]

Extraction Summary:
  Total: 4
  Successful: 3
  Failed: 1
  Cached: 0
  Success Rate: 75.0%

Failed Templates:
  - quotes: TimeoutError: Request timed out after 30s

⚠ 1 template(s) failed. Check logs for details.
✓ Episode processed with 3/4 templates
```

### Option 2: Retry Failed Extractions

**Pros**:
- Automatic recovery from transient failures
- Better success rate
- Improved reliability

**Cons**:
- More complex logic
- Longer processing time
- May retry non-recoverable errors

**Effort**: Medium (3-4 hours)
**Risk**: Medium

**Implementation**:
```python
async def extract_all_with_retry(
    self,
    templates: list[ExtractionTemplate],
    transcript: str,
    metadata: dict[str, Any],
    use_cache: bool = True,
    max_retries: int = 2,
) -> tuple[list[ExtractionResult], ExtractionSummary]:
    """Extract all templates with automatic retry for failures."""

    # First attempt
    results, summary = await self.extract_all(...)

    # Retry failed templates
    if summary.failed > 0 and max_retries > 0:
        failed_templates = [
            template for template in templates
            if template.name in summary.failed_templates
        ]

        logger.info(f"Retrying {len(failed_templates)} failed templates...")

        retry_results, retry_summary = await self.extract_all(
            failed_templates,
            transcript,
            metadata,
            use_cache=False,  # Don't use cache for retries
        )

        # Merge results
        # ... combine results and update summary ...

    return results, summary
```

### Option 3: Save Failure Info to Metadata

**Pros**:
- Persistent record of failures
- Can check later what failed
- Helps troubleshooting

**Cons**:
- Requires metadata format change
- More disk I/O

**Effort**: Small (1 hour)
**Risk**: Low

**Implementation**:
```python
# Add to .metadata.yaml:
extraction_failures:
  - template: quotes
    error: "TimeoutError: Request timed out after 30s"
    timestamp: "2025-11-13T15:30:00Z"
```

## Recommended Action

Implement Option 1 (Extraction Summary with Detailed Reporting) first. Consider Option 2 (Retry) as an enhancement in a follow-up. Option 3 (Metadata) can be added easily to Option 1.

## Technical Details

**Affected Files**:
- `src/inkwell/extraction/engine.py:177` - Update `extract_all()` method
- `src/inkwell/extraction/models.py` - Add `ExtractionSummary`, `ExtractionAttempt`, `ExtractionStatus`
- `src/inkwell/cli.py` - Update to display extraction summary

**New Models**:
- `ExtractionStatus` enum
- `ExtractionAttempt` dataclass
- `ExtractionSummary` dataclass

**Related Components**:
- Episode processing pipeline
- Error logging
- User feedback

**Database Changes**: No (unless implementing Option 3)

## Resources

- Error handling best practices: https://docs.python.org/3/tutorial/errors.html
- asyncio.gather with exceptions: https://docs.python.org/3/library/asyncio-task.html#asyncio.gather

## Acceptance Criteria

- [ ] `ExtractionStatus` enum defined
- [ ] `ExtractionAttempt` dataclass defined
- [ ] `ExtractionSummary` dataclass defined with helper methods
- [ ] `extract_all()` returns tuple of (results, summary)
- [ ] Track duration for each extraction attempt
- [ ] Distinguish between SUCCESS, FAILED, and CACHED
- [ ] Detailed error messages captured per template
- [ ] Summary formatted for user display
- [ ] CLI displays summary after extraction
- [ ] Warning shown if any templates failed
- [ ] Success message if all succeeded
- [ ] Failed template names listed in output
- [ ] Detailed errors logged at ERROR level (not just WARNING)
- [ ] Unit tests for ExtractionSummary
- [ ] Unit tests for success_rate calculation
- [ ] Unit tests for failed_templates list
- [ ] Integration test with mixed success/failure
- [ ] Documentation updated

## Work Log

### 2025-11-13 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code triage session
- Found TODO comment in engine.py:177
- Current error handling identified as insufficient
- Categorized as P2 (Important - reliability)
- Estimated effort: Medium (2-3 hours)

**Learnings:**
- Partial failures are silently ignored
- Users don't get clear feedback about what failed
- Missing output files may go unnoticed
- Better error reporting would significantly improve UX
- Summary/tracking pattern common in production systems

## Notes

**Why This Matters**:

Real-world scenario where this helps:
1. User processes 10 episodes overnight
2. One episode has a network issue during quotes extraction
3. Without improvement: User sees 10 "successful" episodes, doesn't notice one is incomplete
4. With improvement: Clear summary shows "Episode 5: quotes template failed (TimeoutError)"
5. User can easily identify and reprocess just the failed extraction

**Error Categories to Handle Better**:
- Network timeouts (transient - good retry candidate)
- API rate limits (transient - need backoff)
- Invalid JSON responses (permanent - need user notification)
- Missing API keys (permanent - need clear error)
- Malformed templates (permanent - need template fix)

**Testing Strategy**:
```python
def test_extraction_summary_tracks_failures():
    """Test that extraction summary properly tracks failures."""
    # Create templates that will fail
    templates = [
        good_template,
        failing_template,
        another_good_template,
    ]

    results, summary = await engine.extract_all(templates, ...)

    assert summary.total == 3
    assert summary.successful == 2
    assert summary.failed == 1
    assert summary.success_rate == pytest.approx(66.67)
    assert "failing_template" in summary.failed_templates
```

**Source**: Code triage session on 2025-11-13
**Original TODO**: engine.py:177
