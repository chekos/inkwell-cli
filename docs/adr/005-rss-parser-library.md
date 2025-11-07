---
title: ADR 005 - RSS Parser Library Selection
adr:
  author: Claude
  created: 06-Nov-2025
  status: accepted
---

# ADR-005: RSS Parser Library Selection

**Status**: Accepted
**Date**: 2025-11-06
**Context**: Day 4 - RSS parser implementation

## Context

Inkwell needs to parse RSS and Atom podcast feeds to extract episode metadata. Podcast feeds follow various standards (RSS 2.0, Atom) and include iTunes-specific extensions for podcast metadata. We need a reliable parser that handles these variations.

## Decision

Use the **feedparser** library for RSS/Atom feed parsing.

## Options Considered

### 1. feedparser (Chosen)

**Pros**:
- Mature library (16+ years old)
- Handles both RSS 2.0 and Atom formats
- Parses iTunes podcast extensions (`itunes_duration`, `itunes_episode`, etc.)
- Lenient parsing (tolerates malformed XML)
- Returns normalized data structure
- Well-documented

**Cons**:
- Synchronous API (wraps in async function)
- Dependency on sgmllib3k (Python 3 port)
- Large dependency footprint

### 2. python-feedgen

**Pros**:
- Modern Python 3 library
- Good for feed generation

**Cons**:
- Primarily designed for feed *generation*, not parsing
- Less mature for parsing use case
- Less lenient with malformed feeds

### 3. atoma

**Pros**:
- Pure Python 3
- Type hints
- Modern API

**Cons**:
- Less mature (fewer years of development)
- Stricter parsing (fails on malformed XML)
- Limited iTunes extension support

### 4. Custom XML parsing (lxml/ElementTree)

**Pros**:
- Full control
- No additional dependencies (ElementTree)
- Can optimize for our specific use case

**Cons**:
- Need to handle RSS 2.0, Atom, iTunes extensions manually
- Need to write lenient parsing logic
- Significant development time
- More maintenance burden

## Rationale

feedparser is the clear choice because:

1. **Battle-tested**: Used by thousands of projects for 16+ years. Handles edge cases we haven't thought of.

2. **iTunes support**: Automatically parses iTunes podcast extensions, which are essential for podcast metadata (episode numbers, duration, season).

3. **Lenient parsing**: Real-world podcast feeds are often malformed. feedparser's lenient approach means we won't fail on minor XML issues.

4. **Normalized output**: Feedparser normalizes RSS and Atom into a consistent data structure, so we don't need separate code paths.

5. **Time to market**: Proven library lets us focus on Inkwell features instead of XML parsing edge cases.

The synchronous API is not a blocker - we wrap the parsing in an async HTTP client (httpx), so the HTTP fetch is async. Feed parsing itself is CPU-bound and fast enough to not need async.

## Implementation Details

```python
import feedparser
import httpx

class RSSParser:
    async def fetch_feed(self, url: str, auth: Optional[AuthConfig] = None):
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._build_auth_headers(auth))
            feed = feedparser.parse(response.content)
            return feed
```

The pattern: async HTTP fetch, sync parsing, return normalized feed.

## Consequences

**Positive**:
- Reliable feed parsing with minimal code
- iTunes podcast metadata extraction works out of the box
- Handles both RSS and Atom formats
- Tolerates malformed feeds from real-world sources

**Negative**:
- sgmllib3k dependency adds install complexity (requires `--use-pep517`)
- Larger dependency footprint than pure Python solution
- Synchronous parsing API (acceptable for our use case)

**Risks**:
- feedparser development has slowed in recent years (last major update 2020)
- If feedparser becomes unmaintained, we may need to migrate
- Mitigation: Well-isolated parser abstraction makes swapping libraries feasible

## References

- feedparser: https://github.com/kurtmckee/feedparser
- RSS 2.0 Specification: https://www.rssboard.org/rss-specification
- iTunes Podcast RSS: https://podcasters.apple.com/support/823-podcast-requirements
- Implementation: `src/inkwell/feeds/parser.py`

## Related ADRs

- ADR-002: Phase 1 Architecture (RSS parsing layer design)
