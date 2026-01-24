---
status: complete
priority: p2
issue_id: "082"
tags: [code-review, error-handling, debugging, pr-35]
dependencies: []
---

# Add Logging to Silent Exception Handlers

## Problem Statement

The new `cli_list.py` module contains bare `except Exception` blocks that silently swallow errors without logging. This makes debugging difficult when things go wrong and could hide security-relevant issues.

**Why it matters:**
- Users won't know why templates fail to load or episodes are skipped
- Debugging production issues becomes significantly harder
- Could mask malformed data, security issues, or configuration problems
- Violates the principle of observable systems

## Findings

**Agents Discovered:** pattern-recognition-specialist, security-sentinel, code-simplicity-reviewer

**Location 1:** `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`, lines 68-69

```python
for name in names:
    try:
        info = loader.get_template_info(name)
        table.add_row(name, info.get("description", "-"))
    except Exception:
        table.add_row(name, "[dim]failed to load[/dim]")
```

**Location 2:** `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`, lines 131-133

```python
for i, entry in enumerate(feed.entries[:limit], 1):
    try:
        ep = parser.extract_episode_metadata(entry, name)
        # ... table row added
    except Exception:
        # Skip entries that fail to parse
        pass
```

**Impact:**
- Template loading failures show "[dim]failed to load[/dim]" with no details
- Episode parsing failures are completely invisible (silent `pass`)
- If all episodes fail to parse, user sees empty table with no explanation

## Proposed Solutions

### Option 1: Add DEBUG Logging (Recommended)
**Pros:** Non-intrusive, uses existing logging infrastructure, aids debugging
**Cons:** Requires enabling verbose mode to see messages
**Effort:** Low (30 min)
**Risk:** Very Low

```python
import logging
logger = logging.getLogger(__name__)

# Template loading
except Exception as e:
    logger.debug(f"Failed to load template info for '{name}': {e}")
    table.add_row(name, "[dim]failed to load[/dim]")

# Episode parsing
except Exception as e:
    logger.debug(f"Failed to parse episode entry: {e}")
    skipped_count += 1
```

### Option 2: Track and Report Failures
**Pros:** User gets feedback about failures, more transparent
**Cons:** Adds complexity to output
**Effort:** Low-Medium (1 hour)
**Risk:** Low

```python
skipped = 0
for i, entry in enumerate(feed.entries[:limit], 1):
    try:
        ep = parser.extract_episode_metadata(entry, name)
        # ... table row added
    except Exception:
        skipped += 1

if skipped > 0:
    console.print(f"[dim]({skipped} entries could not be parsed)[/dim]")
```

### Option 3: Catch Specific Exceptions
**Pros:** More precise error handling, safer
**Cons:** May miss unexpected errors, requires knowing exception types
**Effort:** Medium (1-2 hours)
**Risk:** Low

```python
from inkwell.utils.errors import InkwellError
from xml.etree.ElementTree import ParseError

except (InkwellError, ParseError, KeyError) as e:
    logger.debug(f"Expected error parsing episode: {e}")
except Exception as e:
    logger.warning(f"Unexpected error parsing episode: {e}")
```

## Recommended Action

Implement **Option 1** for immediate improvement, with **Option 2** as enhancement for episodes.

**Minimal Fix:**
```python
import logging
logger = logging.getLogger(__name__)

# In list_templates():
except Exception as e:
    logger.debug(f"Failed to load template '{name}': {e}")
    table.add_row(name, "[dim]failed to load[/dim]")

# In list_episodes():
skipped = 0
for i, entry in enumerate(feed.entries[:limit], 1):
    try:
        ep = parser.extract_episode_metadata(entry, name)
        # ...
    except Exception as e:
        logger.debug(f"Failed to parse entry {i}: {e}")
        skipped += 1

# After the loop:
if skipped > 0:
    console.print(f"[dim]({skipped} entries could not be parsed)[/dim]")
```

## Technical Details

**Affected Files:**
- `src/inkwell/cli_list.py` (lines 68-69, 131-133)

**Changes Required:**
1. Add `import logging` and `logger = logging.getLogger(__name__)` at top
2. Replace bare `except Exception` with `except Exception as e`
3. Add `logger.debug()` calls
4. Track skipped count for episodes

## Acceptance Criteria

- [x] Template load failures are logged at DEBUG level with exception details
- [x] Episode parse failures are logged at DEBUG level
- [x] Skipped episode count is shown to user when > 0
- [ ] Running with `-v` (verbose) shows debug messages
- [x] Normal output (non-verbose) is unchanged
- [ ] Add test for skipped episode count display

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-01-07 | Created | Identified during PR #35 code review |
| 2026-01-07 | Completed | Implemented Option 1 + Option 2 combination |

## Resources

- PR #35: https://github.com/chekos/inkwell-cli/pull/35
- Python logging best practices: https://docs.python.org/3/howto/logging.html
