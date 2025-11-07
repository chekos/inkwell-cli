# Template Format Evaluation: YAML vs Alternatives

**Date**: 2025-11-07
**Author**: Phase 3 Research
**Status**: Complete
**Related**: [Phase 3 Plan](../devlog/2025-11-07-phase-3-detailed-plan.md)

## Overview

This document evaluates different formats for defining extraction templates. Templates control how content is extracted from transcripts and must be human-readable, validatable, and extensible. We compare YAML, TOML, JSON, and Python dataclasses.

---

## Requirements for Template Format

### Functional Requirements

1. **Human Readable**: Non-developers should be able to create templates
2. **Comments Support**: Document template purpose and variables
3. **Multi-line Strings**: Prompts can be long and complex
4. **Validation**: Schema validation for correctness
5. **Version Control Friendly**: Diffs should be readable
6. **Extensible**: Easy to add new fields without breaking old templates

### Non-Functional Requirements

1. **Parsing Speed**: Fast template loading
2. **Error Messages**: Clear validation errors
3. **Editor Support**: Syntax highlighting, autocomplete
4. **Standard Library**: Preferably no exotic dependencies
5. **Ecosystem**: Good tooling and examples

---

## Format Comparison

### 1. YAML (YAML Ain't Markup Language)

#### Example Template

```yaml
# Summary extraction template
name: summary
version: "1.0"
description: Generate a comprehensive episode summary

system_prompt: |
  You are an expert podcast analyst. Your task is to create
  a clear, concise summary of the podcast episode.

  Focus on:
  - Main topics discussed
  - Key takeaways
  - Notable insights

user_prompt_template: |
  Please summarize the following podcast transcript.

  Podcast: {{ metadata.podcast_name }}
  Episode: {{ metadata.episode_title }}
  Duration: {{ metadata.duration }}

  Transcript:
  {{ transcript }}

  Provide a 2-3 paragraph summary followed by 3-5 key takeaways.

expected_format: markdown
max_tokens: 2000
temperature: 0.3

# Category-specific configuration
applies_to:
  - all

priority: 0
```

#### Pros

✅ **Highly Readable**: Clear, clean syntax
✅ **Comments**: Native support with `#`
✅ **Multi-line Strings**: Excellent support with `|` and `>`
✅ **No Quotes Required**: Simple values don't need quotes
✅ **Wide Adoption**: Used by many tools (Docker, Kubernetes, GitHub Actions)
✅ **Editor Support**: Excellent syntax highlighting and validation
✅ **Complex Structures**: Easy nesting and lists

#### Cons

❌ **Indentation Sensitivity**: Whitespace matters (can cause errors)
❌ **Type Ambiguity**: `no` becomes `False`, `1.0` might be string or number
❌ **Security**: `yaml.unsafe_load()` can execute code (mitigated with `safe_load`)
❌ **Parsing Complexity**: More complex parser than JSON
❌ **Duplicate Keys**: Silently overwrites (YAML spec allows it)

#### Use Cases

✅ **Configuration files** (most common use)
✅ **CI/CD pipelines** (GitHub Actions, GitLab CI)
✅ **Kubernetes manifests**
✅ **Human-edited files**

#### Validation Example

```python
import yaml
from pydantic import BaseModel

# Load and validate
with open("template.yaml") as f:
    data = yaml.safe_load(f)
    template = ExtractionTemplate(**data)  # Pydantic validation
```

---

### 2. TOML (Tom's Obvious Minimal Language)

#### Example Template

```toml
# Summary extraction template
name = "summary"
version = "1.0"
description = "Generate a comprehensive episode summary"

system_prompt = """
You are an expert podcast analyst. Your task is to create
a clear, concise summary of the podcast episode.

Focus on:
- Main topics discussed
- Key takeaways
- Notable insights
"""

user_prompt_template = """
Please summarize the following podcast transcript.

Podcast: {{ metadata.podcast_name }}
Episode: {{ metadata.episode_title }}
Duration: {{ metadata.duration }}

Transcript:
{{ transcript }}

Provide a 2-3 paragraph summary followed by 3-5 key takeaways.
"""

expected_format = "markdown"
max_tokens = 2000
temperature = 0.3

applies_to = ["all"]
priority = 0
```

#### Pros

✅ **Type Safety**: Explicit types (strings, ints, floats, booleans)
✅ **Comments**: Native support with `#`
✅ **Multi-line Strings**: Triple quotes `"""`
✅ **No Indentation Issues**: Uses `[sections]` instead
✅ **Simple Parser**: Unambiguous syntax
✅ **Growing Adoption**: Python `pyproject.toml`, Rust `Cargo.toml`

#### Cons

❌ **Verbosity**: Requires quotes for all strings
❌ **Limited Nesting**: Awkward for deep hierarchies
❌ **Less Familiar**: Not as widely known as YAML/JSON
❌ **Editor Support**: Improving but not universal
❌ **Complex Lists**: Array of tables syntax is verbose

#### Use Cases

✅ **Python projects** (`pyproject.toml`)
✅ **Rust projects** (`Cargo.toml`)
✅ **Configuration with strict types**

#### Validation Example

```python
import tomli  # Python 3.11+ has tomllib in stdlib
from pydantic import BaseModel

with open("template.toml", "rb") as f:
    data = tomli.load(f)
    template = ExtractionTemplate(**data)
```

---

### 3. JSON (JavaScript Object Notation)

#### Example Template

```json
{
  "name": "summary",
  "version": "1.0",
  "description": "Generate a comprehensive episode summary",
  "system_prompt": "You are an expert podcast analyst. Your task is to create\na clear, concise summary of the podcast episode.\n\nFocus on:\n- Main topics discussed\n- Key takeaways\n- Notable insights",
  "user_prompt_template": "Please summarize the following podcast transcript.\n\nPodcast: {{ metadata.podcast_name }}\nEpisode: {{ metadata.episode_title }}\nDuration: {{ metadata.duration }}\n\nTranscript:\n{{ transcript }}\n\nProvide a 2-3 paragraph summary followed by 3-5 key takeaways.",
  "expected_format": "markdown",
  "max_tokens": 2000,
  "temperature": 0.3,
  "applies_to": ["all"],
  "priority": 0
}
```

#### Pros

✅ **Standardized**: RFC 8259 spec, universal support
✅ **Fast Parsing**: Very efficient parsers
✅ **No Ambiguity**: Strict syntax, no edge cases
✅ **Editor Support**: Universal syntax highlighting
✅ **Validation**: JSON Schema standard
✅ **Language Agnostic**: Works everywhere

#### Cons

❌ **No Comments**: Biggest limitation for templates
❌ **Verbose**: Requires quotes for keys and string values
❌ **Multi-line Strings**: Awkward with `\n` escapes
❌ **Trailing Commas**: Not allowed (causes errors)
❌ **Human Readability**: Less readable than YAML/TOML

#### Use Cases

✅ **API responses**
✅ **Configuration generated by machines**
✅ **Data interchange**
✅ **Strict validation needed**

#### Validation Example

```python
import json
from pydantic import BaseModel

with open("template.json") as f:
    data = json.load(f)
    template = ExtractionTemplate(**data)
```

---

### 4. Python Dataclasses / Pydantic

#### Example Template

```python
# templates/summary.py
from extraction.models import ExtractionTemplate

summary_template = ExtractionTemplate(
    name="summary",
    version="1.0",
    description="Generate a comprehensive episode summary",
    system_prompt="""
    You are an expert podcast analyst. Your task is to create
    a clear, concise summary of the podcast episode.

    Focus on:
    - Main topics discussed
    - Key takeaways
    - Notable insights
    """,
    user_prompt_template="""
    Please summarize the following podcast transcript.

    Podcast: {{ metadata.podcast_name }}
    Episode: {{ metadata.episode_title }}
    Duration: {{ metadata.duration }}

    Transcript:
    {{ transcript }}

    Provide a 2-3 paragraph summary followed by 3-5 key takeaways.
    """,
    expected_format="markdown",
    max_tokens=2000,
    temperature=0.3,
    applies_to=["all"],
    priority=0,
)
```

#### Pros

✅ **Type Safety**: Full Python type checking
✅ **IDE Support**: Autocomplete, refactoring, type hints
✅ **Comments**: Python docstrings and `#` comments
✅ **Validation**: Built-in with Pydantic
✅ **Programmatic**: Can compute values, import modules
✅ **No Parsing**: Native Python objects

#### Cons

❌ **Requires Python Knowledge**: Non-developers blocked
❌ **Security Risk**: Running user Python code is dangerous
❌ **Harder to Edit**: Need proper Python setup
❌ **Version Control**: Diffs less clear than declarative formats
❌ **Not Portable**: Can't easily share across languages

#### Use Cases

✅ **Built-in templates** (shipped with tool)
✅ **Developer-only templates**
✅ **Complex logic** (computed values)

#### Validation Example

```python
# Already validated at definition time
from templates.summary import summary_template
```

---

## Head-to-Head Comparison

### Readability (1-10 scale)

| Format | Score | Notes |
|--------|-------|-------|
| YAML | 9 | Clean, minimal syntax |
| TOML | 7 | More verbose but clear |
| JSON | 5 | Quoted keys/values, escaped newlines |
| Python | 8 | Familiar to developers |

### User-Friendliness (1-10 scale)

| Format | Score | Notes |
|--------|-------|-------|
| YAML | 9 | Easy for non-developers |
| TOML | 7 | Requires learning |
| JSON | 4 | Painful for multi-line strings |
| Python | 3 | Requires Python knowledge |

### Validation Support (1-10 scale)

| Format | Score | Notes |
|--------|-------|-------|
| YAML | 8 | Pydantic + PyYAML |
| TOML | 8 | Pydantic + tomli |
| JSON | 10 | JSON Schema standard |
| Python | 10 | Native Pydantic |

### Editor Support (1-10 scale)

| Format | Score | Notes |
|--------|-------|-------|
| YAML | 10 | Universal support |
| TOML | 7 | Growing support |
| JSON | 10 | Universal support |
| Python | 10 | Best IDE support |

### Safety (1-10 scale)

| Format | Score | Notes |
|--------|-------|-------|
| YAML | 7 | safe_load required |
| TOML | 9 | Very safe |
| JSON | 10 | Completely safe |
| Python | 3 | Code execution risk |

---

## Decision Matrix

### Weighted Scoring

| Criteria | Weight | YAML | TOML | JSON | Python |
|----------|--------|------|------|------|--------|
| Human Readable | 25% | 9 | 7 | 5 | 8 |
| User-Friendly | 25% | 9 | 7 | 4 | 3 |
| Comments Support | 15% | 10 | 10 | 0 | 10 |
| Multi-line Strings | 15% | 10 | 9 | 3 | 10 |
| Validation | 10% | 8 | 8 | 10 | 10 |
| Safety | 10% | 7 | 9 | 10 | 3 |
| **Total** | **100%** | **8.8** | **7.9** | **4.6** | **6.7** |

**Winner: YAML (8.8/10)**

---

## Real-World Template Examples

### YAML Template (Recommended)

```yaml
# tools-mentioned.yaml
name: tools-mentioned
version: "1.0"
description: Extract tools, frameworks, and libraries mentioned in tech podcasts

category: tech

system_prompt: |
  You are a technical expert analyzing a technology podcast.
  Extract all tools, frameworks, libraries, and technologies mentioned.

  For each tool, provide:
  - Name
  - Category (language, framework, library, tool, service)
  - Context (how it was discussed)
  - Timestamp (if mentioned)

user_prompt_template: |
  Analyze this tech podcast transcript and extract all mentioned tools.

  Transcript:
  {{ transcript }}

  Return a JSON array of tools with: name, category, context, timestamp.

expected_format: json
output_schema:
  type: object
  properties:
    tools:
      type: array
      items:
        type: object
        required: [name, category]
        properties:
          name:
            type: string
          category:
            type: string
            enum: [language, framework, library, tool, service, other]
          context:
            type: string
          timestamp:
            type: string
            pattern: "^\\d+:\\d+$"

applies_to:
  - tech
  - programming

priority: 5
model_preference: claude
max_tokens: 2000
temperature: 0.2
```

### Comparison: Same Template in JSON

```json
{
  "name": "tools-mentioned",
  "version": "1.0",
  "description": "Extract tools, frameworks, and libraries mentioned in tech podcasts",
  "category": "tech",
  "system_prompt": "You are a technical expert analyzing a technology podcast.\nExtract all tools, frameworks, libraries, and technologies mentioned.\n\nFor each tool, provide:\n- Name\n- Category (language, framework, library, tool, service)\n- Context (how it was discussed)\n- Timestamp (if mentioned)",
  "user_prompt_template": "Analyze this tech podcast transcript and extract all mentioned tools.\n\nTranscript:\n{{ transcript }}\n\nReturn a JSON array of tools with: name, category, context, timestamp.",
  "expected_format": "json",
  "output_schema": {
    "type": "object",
    "properties": {
      "tools": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["name", "category"],
          "properties": {
            "name": {"type": "string"},
            "category": {
              "type": "string",
              "enum": ["language", "framework", "library", "tool", "service", "other"]
            },
            "context": {"type": "string"},
            "timestamp": {
              "type": "string",
              "pattern": "^\\d+:\\d+$"
            }
          }
        }
      }
    }
  },
  "applies_to": ["tech", "programming"],
  "priority": 5,
  "model_preference": "claude",
  "max_tokens": 2000,
  "temperature": 0.2
}
```

**YAML is clearly more readable and maintainable.**

---

## Edge Cases and Gotchas

### YAML Edge Cases

**1. Type Coercion**
```yaml
# Problem: These all become booleans
no: false  # Becomes False
yes: true  # Becomes True
on: true   # Becomes True
off: false # Becomes False

# Solution: Quote strings
no: "no"
yes: "yes"
```

**2. Duplicate Keys**
```yaml
# Problem: Silently overwrites
name: first
name: second  # Wins, first is lost

# Solution: Use linter to detect
```

**3. Indentation**
```yaml
# Problem: Wrong indentation breaks parsing
prompt: |
  Line 1
   Line 2  # Extra space breaks it

# Solution: Use consistent indentation (2 or 4 spaces)
```

### Mitigation Strategies

1. **Use `yaml.safe_load()`** - Prevents code execution
2. **Validate with Pydantic** - Catch type errors early
3. **YAML Linter** - Pre-commit hook with `yamllint`
4. **Schema Validation** - Define expected structure
5. **Good Documentation** - Provide templates and examples

---

## Recommendation

### Primary Format: YAML

**Rationale:**
1. ✅ **Best user experience** - Non-developers can create templates
2. ✅ **Comments support** - Critical for documentation
3. ✅ **Multi-line strings** - Perfect for prompts
4. ✅ **Wide adoption** - Familiar to most developers
5. ✅ **Excellent tooling** - Linters, validators, editor support
6. ✅ **Validated safely** - Pydantic + safe_load

**Mitigations:**
- Use `yaml.safe_load()` for security
- Pydantic validation for correctness
- YAML linting in pre-commit hooks
- Clear documentation and examples
- Template validation CLI command

### Hybrid Approach

**Built-in templates**: Python (type-safe, version-controlled)
**User templates**: YAML (user-friendly, editable)

```python
# Load built-in template
from inkwell.templates.default import summary

# Load user template
loader.load_template("my-custom-template")  # Loads from ~/.config/inkwell/templates/
```

---

## Implementation Plan

### 1. Template Loading

```python
def load_template(path: Path) -> ExtractionTemplate:
    """Load and validate template from YAML file"""
    with open(path) as f:
        data = yaml.safe_load(f)

    # Pydantic validation
    template = ExtractionTemplate(**data)

    return template
```

### 2. Template Validation CLI

```bash
# Validate user template
inkwell template validate my-template.yaml

# Output:
# ✓ Template 'my-template' is valid
# - System prompt: 145 characters
# - User prompt template: 234 characters
# - Expected format: json
# - Output schema: valid
```

### 3. Template Creation Helper

```bash
# Create template from interactive prompt
inkwell template create tools-mentioned

# Guides user through:
# - Name, description
# - Category (optional)
# - System prompt
# - User prompt template
# - Expected format
# - Output schema (optional)
```

---

## Conclusion

**YAML is the clear winner** for user-defined extraction templates:
- Best balance of readability and functionality
- Excellent comment and multi-line string support
- Wide tooling and editor support
- Safe with proper loading and validation

**Implementation:**
1. Use YAML for all user-editable templates
2. Validate with Pydantic models
3. Provide good documentation and examples
4. Add CLI tools for validation and creation
5. Use pre-commit hooks to catch errors early

---

## References

- [YAML Specification](https://yaml.org/spec/)
- [TOML Specification](https://toml.io/)
- [JSON Specification](https://www.json.org/)
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation)
- [ADR-014: Template Format](../adr/014-template-format.md)
