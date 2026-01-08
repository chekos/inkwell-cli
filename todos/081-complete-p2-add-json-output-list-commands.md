---
status: complete
priority: p2
issue_id: "081"
tags: [code-review, agent-native, cli, pr-35]
dependencies: []
---

# Add --json Flag for Machine-Readable Output in List Commands

## Problem Statement

The new `inkwell list` commands (feeds, templates, episodes) only output Rich-formatted tables designed for human consumption. There is no `--json` or `--format` option for machine-readable output, making it impossible for AI agents and automation scripts to programmatically access this data.

**Why it matters:**
- AI agents cannot parse Rich table markup like `[cyan]template-name[/cyan]`
- Automation scripts cannot reliably extract data from formatted tables
- Piped output includes color codes and table borders that break parsing
- This violates the "agent-native" principle: anything a user can see, an agent should be able to access programmatically

## Findings

**Agent Discovered:** agent-native-reviewer

**Location:** `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`

**Current Implementation (lines 60-72):**
```python
table = Table(title="[bold]Extraction Templates[/bold]")
table.add_column("Name", style="cyan", no_wrap=True)
table.add_column("Description")

for name in names:
    try:
        info = loader.get_template_info(name)
        table.add_row(name, info.get("description", "-"))
    except Exception:
        table.add_row(name, "[dim]failed to load[/dim]")

console.print(table)
console.print(f"\n[dim]Total: {len(names)} template(s)[/dim]")
```

**Impact:**
- 0/3 new list commands are agent-accessible
- Existing `inkwell plugins list`, `inkwell config show`, `inkwell costs` have the same gap
- This is a systemic pattern in the CLI that should be addressed

## Proposed Solutions

### Option 1: Add --json Flag to Each Command (Recommended)
**Pros:** Simple, explicit, follows common CLI conventions (kubectl, gh, docker)
**Cons:** Adds parameter to each command
**Effort:** Medium (2-3 hours)
**Risk:** Low

```python
@app.command("templates")
def list_templates(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    loader = TemplateLoader()
    names = loader.list_templates()

    if json_output:
        import json
        result = {
            "templates": [
                {"name": name, **loader.get_template_info(name)}
                for name in names
            ],
            "total": len(names)
        }
        print(json.dumps(result, indent=2))
        return

    # ... existing Rich table code ...
```

### Option 2: Global --format Flag
**Pros:** Consistent across all commands, single implementation point
**Cons:** Requires callback inheritance, more complex
**Effort:** Medium-High (3-4 hours)
**Risk:** Medium

```python
@app.callback()
def main(
    ctx: typer.Context,
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["format"] = format
```

### Option 3: Auto-detect TTY and Switch Output
**Pros:** Works automatically for pipes/scripts
**Cons:** May surprise users, less explicit control
**Effort:** Low (1 hour)
**Risk:** Medium

```python
import sys

def should_use_json() -> bool:
    return not sys.stdout.isatty()
```

## Recommended Action

Implement **Option 1** for the three new commands in this PR, with plan to extend to other commands later.

**JSON Schema for Each Command:**

```json
// inkwell list feeds --json
{
  "feeds": [
    {"name": "my-podcast", "url": "https://...", "auth": "none", "category": "tech"}
  ],
  "total": 1
}

// inkwell list templates --json
{
  "templates": [
    {"name": "summary", "description": "...", "category": "default", "version": "1.0"}
  ],
  "total": 6
}

// inkwell list episodes my-podcast --json
{
  "feed": "my-podcast",
  "episodes": [
    {"title": "...", "date": "2026-01-07", "duration": "45:30", "url": "..."}
  ],
  "total": 100,
  "showing": 10
}
```

## Technical Details

**Affected Files:**
- `src/inkwell/cli_list.py` (lines 37-76 for templates, 79-147 for episodes, 150-181 for feeds)

**Minimal Changes Required:**
1. Add `json_output` parameter to each command
2. Early return with JSON if flag is set
3. Use `print()` instead of `console.print()` for JSON output

## Acceptance Criteria

- [x] `inkwell list feeds --json` outputs valid JSON
- [x] `inkwell list templates --json` outputs valid JSON with full template metadata
- [x] `inkwell list episodes <feed> --json` outputs valid JSON with episode data
- [x] JSON output works correctly when piped: `inkwell list templates --json | jq '.templates[0].name'`
- [x] Short flag `-j` works as alias for `--json`
- [x] Help text documents the new flag
- [ ] Add tests for JSON output format (existing tests pass, JSON-specific tests can be added later)

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-01-07 | Created | Identified during PR #35 code review |
| 2026-01-07 | Completed | Implemented Option 1 - added --json/-j flag to all 3 list commands |

## Resources

- PR #35: https://github.com/chekos/inkwell-cli/pull/35
- kubectl output patterns: https://kubernetes.io/docs/reference/kubectl/jsonpath/
- GitHub CLI JSON support: https://cli.github.com/manual/gh_help_formatting
