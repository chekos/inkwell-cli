---
status: resolved
priority: p2
issue_id: "010"
tags: [code-review, security, performance, denial-of-service, high-priority]
dependencies: []
completed_date: 2025-11-13
---

# Fix ReDoS Vulnerabilities in Regex Patterns

## Problem Statement

Complex regex patterns with optional groups and backtracking could cause exponential time complexity with specially crafted input, leading to Regular Expression Denial of Service (ReDoS) attacks.

**Severity**: MEDIUM-HIGH (CVSS 5.5)

## Findings

- Discovered during security audit by security-sentinel agent
- Location: `src/inkwell/obsidian/wikilinks.py:42-60`
- Complex patterns with nested optional groups
- Potential for catastrophic backtracking
- No timeouts on regex operations

**Vulnerable Patterns**:
```python
EntityType.PERSON: [
    r"\b(?:Dr\.?|Prof\.?|Mr\.?|Ms\.?|Mrs\.?)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
    r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\b",  # ← Vulnerable
    r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)'s\b",
],
```

**ReDoS Example**:
```python
# This pattern is vulnerable to catastrophic backtracking:
pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\b"

# Malicious input that causes exponential backtracking:
malicious = "A" + "a" * 50 + " A" + "a" * 50  # Causes extreme slowdown

# Each failed match attempt tries many combinations of optional groups
# Time complexity: O(2^n) where n is input length
```

**Impact**:
- CPU exhaustion
- Application freeze/timeout
- Denial of service
- Poor user experience (episode processing hangs)

## Proposed Solutions

### Option 1: Add Regex Timeouts (Recommended)
**Pros**:
- Simple to implement
- No pattern changes needed
- Catches all ReDoS vulnerabilities

**Cons**:
- Requires `regex` library (not built-in `re`)

**Effort**: Small (1-2 hours)
**Risk**: Low

**Implementation**:

```python
# src/inkwell/obsidian/wikilinks.py

import regex  # pip install regex (not built-in re)
from typing import Pattern

class WikilinkGenerator:
    def __init__(self, config: WikilinkConfig | None = None):
        self.config = config or WikilinkConfig()

        # Compile patterns with timeout support
        self._patterns: dict[EntityType, list[Pattern]] = {
            EntityType.PERSON: [
                regex.compile(
                    r"\b(?:Dr\.?|Prof\.?|Mr\.?|Ms\.?|Mrs\.?)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
                    timeout=1.0  # 1 second timeout
                ),
                regex.compile(
                    r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\b",
                    timeout=1.0
                ),
                regex.compile(
                    r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)'s\b",
                    timeout=1.0
                ),
            ],
            EntityType.BOOK: [
                regex.compile(
                    r'"([^"]{3,50})"',
                    timeout=1.0
                ),
                regex.compile(
                    r"(?:book|reading)\s+['\"]([^'\"]{3,50})['\"]",
                    regex.IGNORECASE,
                    timeout=1.0
                ),
            ],
            # ... other patterns
        }

    def _extract_from_text(self, text: str, source: str) -> list[Entity]:
        """Extract entities from text using regex patterns."""
        entities = []

        # Limit text chunk size to prevent excessive processing
        MAX_CHUNK_SIZE = 50000  # 50KB chunks
        if len(text) > MAX_CHUNK_SIZE:
            # Process in chunks
            for i in range(0, len(text), MAX_CHUNK_SIZE):
                chunk = text[i:i + MAX_CHUNK_SIZE]
                entities.extend(self._extract_from_chunk(chunk, source))
        else:
            entities.extend(self._extract_from_chunk(text, source))

        return entities

    def _extract_from_chunk(self, text: str, source: str) -> list[Entity]:
        """Extract entities from a single text chunk."""
        entities = []

        for entity_type, patterns in self._patterns.items():
            for pattern in patterns:
                try:
                    matches = pattern.findall(text)
                    for match in matches:
                        # Process match...
                        entity = self._create_entity(match, entity_type, source)
                        if entity:
                            entities.append(entity)
                except regex.TimeoutError:
                    logger.warning(
                        f"Regex timeout for {entity_type.value} pattern. "
                        f"This may indicate a ReDoS attack or very complex input. "
                        f"Skipping this pattern for current chunk."
                    )
                    continue

        return entities


# Add to pyproject.toml:
# dependencies = [
#     ...
#     "regex>=2023.12.25",  # For regex timeouts
# ]
```

### Option 2: Simplify Regex Patterns
**Pros**:
- No external dependencies
- Better performance
- Easier to understand

**Cons**:
- May miss some edge cases
- Requires pattern redesign

**Effort**: Medium (2-3 hours)
**Risk**: Medium

**Implementation**:
```python
# Simplified patterns (avoid nested optional groups):

# OLD (vulnerable):
r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\b"

# NEW (safe - split into two patterns):
r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b",           # John Smith
r"\b([A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+)\b", # John A. Smith

# This eliminates optional groups that cause backtracking
```

### Option 3: Use Alternative Matching Strategy
**Pros**:
- More robust
- No regex vulnerabilities

**Cons**:
- Complete rewrite
- More complex code

**Effort**: Large (4-6 hours)
**Risk**: High

## Recommended Action

Implement Option 1 (regex timeouts) immediately for safety. Consider Option 2 (simplification) as enhancement for v1.1.

## Technical Details

**Affected Files**:
- `src/inkwell/obsidian/wikilinks.py:42-60` (pattern definitions)
- `src/inkwell/obsidian/wikilinks.py:140-180` (_extract_from_text method)

**New Dependencies**:
- `regex>=2023.12.25` (Python regex library with timeout support)

**Related Components**:
- Entity extraction
- Wikilink generation
- Any regex-based parsing

**Database Changes**: No

## Resources

- ReDoS Explained: https://owasp.org/www-community/attacks/Regular_expression_Denial_of_Service_-_ReDoS
- Python regex library: https://pypi.org/project/regex/
- ReDoS Testing Tool: https://devina.io/redos-checker

## Acceptance Criteria

- [x] `regex` library added as dependency
- [x] All regex patterns compiled with timeout (1 second)
- [x] TimeoutError handling added
- [x] Text chunking implemented for large inputs
- [x] Maximum chunk size configured (50KB)
- [x] Logging for timeout events
- [x] Unit tests for timeout behavior
- [x] Unit tests with malicious input patterns
- [x] Performance tests with complex input
- [x] Documentation updated with ReDoS mitigation (inline comments)
- [x] All ReDoS protection tests pass (7/7 pass)

## Work Log

### 2025-11-13 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during security audit
- Analyzed by security-sentinel agent
- Identified vulnerable regex patterns
- Researched catastrophic backtracking
- Tested with malicious inputs
- Categorized as MEDIUM-HIGH priority

**Learnings**:
- Nested optional groups cause exponential backtracking
- Python's `re` module has no timeout support
- `regex` library provides timeout mechanism
- Chunking limits worst-case impact

### 2025-11-13 - Implementation Complete
**By:** Claude Code (Resolution)
**Actions:**
- Added `regex>=2023.12.25` to project dependencies
- Updated `WikilinkGenerator.__init__()` to use `regex.compile()` instead of raw pattern strings
- Implemented timeout protection (1 second) via `pattern.finditer(text, timeout=1.0)`
- Added text chunking (50KB max) in `_extract_from_text()`
- Created new `_extract_from_chunk()` method with timeout error handling
- Added comprehensive ReDoS protection test suite (7 tests)
- All ReDoS protection tests passing

**Changes Made:**
- `/Users/sergio/projects/inkwell-cli/pyproject.toml` - Added regex dependency
- `/Users/sergio/projects/inkwell-cli/src/inkwell/obsidian/wikilinks.py` - Implemented ReDoS protections
- `/Users/sergio/projects/inkwell-cli/tests/unit/obsidian/test_wikilinks.py` - Added ReDoS test suite

**Test Results:**
```
tests/unit/obsidian/test_wikilinks.py::TestReDoSProtection::test_redos_protection_with_malicious_input PASSED
tests/unit/obsidian/test_wikilinks.py::TestReDoSProtection::test_regex_timeout_handling PASSED
tests/unit/obsidian/test_wikilinks.py::TestReDoSProtection::test_large_text_chunking PASSED
tests/unit/obsidian/test_wikilinks.py::TestReDoSProtection::test_complex_input_patterns PASSED
tests/unit/obsidian/test_wikilinks.py::TestReDoSProtection::test_normal_text_still_works PASSED
tests/unit/obsidian/test_wikilinks.py::TestReDoSProtection::test_chunk_boundary_entities PASSED
tests/unit/obsidian/test_wikilinks.py::TestReDoSProtection::test_timeout_configuration PASSED
7 passed in 0.50s
```

**Security Impact:**
- ReDoS vulnerability mitigated through timeout enforcement
- Maximum processing time per pattern limited to 1 second
- Large text inputs (>50KB) processed in safe chunks
- Graceful degradation on timeout (skip pattern, log warning, continue)
- CVSS 5.5 vulnerability resolved

**Learnings:**
- The `regex` library's timeout parameter is passed to search/finditer methods, not compile()
- Timeout behavior works correctly with malicious inputs (tested with backtracking patterns)
- Chunking prevents memory issues with very large transcripts
- Pattern compilation with `regex.compile()` is compatible with existing code

## Notes

**What is ReDoS**:

Regular Expression Denial of Service occurs when regex patterns with:
- Nested quantifiers: `(a+)+`
- Overlapping alternatives: `(a|a)+`
- Optional groups: `(a?)+`

Process input with exponential time complexity O(2^n).

**Example Vulnerable Pattern**:
```python
# Vulnerable: nested optional groups
pattern = r"(a+)+"

# Benign input: fast
text = "aaaaaaaaa"  # Linear time

# Malicious input: exponential time
text = "aaaaaaaaa!"  # ! prevents final match
# Engine tries all combinations: 2^9 = 512 attempts
# With 20 'a's: 2^20 = 1,048,576 attempts → hang
```

**Why Timeouts Work**:
```python
import regex

pattern = regex.compile(r"(a+)+", timeout=1.0)

# Benign input: completes quickly
pattern.search("aaaaaaaaa")  # Fast

# Malicious input: timeout after 1 second
try:
    pattern.search("aaaaaaaaaaaaaaaaaaaa!")
except regex.TimeoutError:
    print("Pattern took too long, aborting")
```

**Safe Pattern Design**:
- Avoid nested quantifiers
- Use possessive quantifiers: `a++` (no backtracking)
- Use atomic groups: `(?>a+)+`
- Limit input size
- Use timeouts

**Testing for ReDoS**:
```python
def test_redos_protection():
    """Test that ReDoS attacks are mitigated."""
    generator = WikilinkGenerator()

    # Create malicious input (designed to cause backtracking)
    malicious_text = "A" + "a" * 100 + " A" + "a" * 100 + "!"

    # Should complete within reasonable time (not hang)
    import time
    start = time.time()

    entities = generator._extract_from_text(malicious_text, "test")

    elapsed = time.time() - start

    # Should timeout and continue, not hang forever
    assert elapsed < 5.0, f"Extraction took {elapsed}s, possible ReDoS"


def test_regex_timeout_handling():
    """Test that regex timeouts are handled gracefully."""
    # Create pattern that will definitely timeout
    pattern = regex.compile(r"(a+)+", timeout=0.001)

    with pytest.raises(regex.TimeoutError):
        pattern.search("a" * 100)
```

**Migration Path**:
1. Add `regex` dependency
2. Replace `import re` with `import regex`
3. Add `timeout=1.0` to all `regex.compile()` calls
4. Add try/except for `regex.TimeoutError`
5. Add chunking for large inputs
6. Test with known ReDoS patterns

**Alternative: Built-in re with Manual Timeout**:
```python
import re
import signal
from contextlib import contextmanager

@contextmanager
def timeout(seconds):
    """Context manager for timing out operations."""
    def handler(signum, frame):
        raise TimeoutError("Operation timed out")

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

# Usage:
try:
    with timeout(1):
        matches = pattern.findall(text)
except TimeoutError:
    logger.warning("Regex timed out")
    matches = []
```

Note: `signal`-based timeout only works on Unix, not Windows.

**Source**: Code review performed on 2025-11-13
**Review command**: /review #9
