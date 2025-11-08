# ADR-014: Template Format Selection

**Date**: 2025-11-07
**Status**: Accepted
**Deciders**: Phase 3 Team
**Related**: [Template Format Evaluation](../research/template-format-evaluation.md)

## Context

Phase 3's extraction system requires a template format for defining how content is extracted from transcripts. Templates must specify:
- System and user prompts
- Output format and schema
- LLM configuration (model, temperature, tokens)
- Metadata (name, category, priority)

**Key Requirements:**
1. **Human-readable**: Non-developers should be able to create templates
2. **Comments**: Documentation within templates
3. **Multi-line strings**: Prompts can be long and complex
4. **Validation**: Catch errors before runtime
5. **Version control friendly**: Clean diffs

**Candidate formats:**
- YAML (widely used for config)
- TOML (Python ecosystem standard)
- JSON (universal, structured)
- Python dataclasses (programmatic)

## Decision

**We will use YAML as the template format for user-editable extraction templates.**

### Template Structure

```yaml
# Summary extraction template
name: summary
version: "1.0"
description: Generate a comprehensive episode summary

# LLM prompts
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

  Transcript:
  {{ transcript }}

  Provide a 2-3 paragraph summary followed by 3-5 key takeaways.

# Output configuration
expected_format: markdown
output_schema: null  # Optional JSON schema

# Template metadata
category: null
applies_to:
  - all
priority: 0

# LLM configuration
model_preference: auto
max_tokens: 2000
temperature: 0.3
```

### Loading and Validation

```python
import yaml
from pydantic import BaseModel

def load_template(path: Path) -> ExtractionTemplate:
    """Load and validate template from YAML"""
    with open(path) as f:
        data = yaml.safe_load(f)  # Use safe_load for security

    # Pydantic validation ensures correctness
    template = ExtractionTemplate(**data)

    return template
```

### Template Locations

1. **Built-in templates**: `src/inkwell/templates/default/*.yaml`
2. **Category templates**: `src/inkwell/templates/categories/{tech,interview}/*.yaml`
3. **User templates**: `~/.config/inkwell/templates/*.yaml`

**Priority**: User templates override built-in templates with same name

## Alternatives Considered

### Alternative 1: TOML

**Example:**
```toml
name = "summary"
version = "1.0"
description = "Generate a comprehensive episode summary"

system_prompt = """
You are an expert podcast analyst.
"""

applies_to = ["all"]
```

**Pros:**
- Type-safe (explicit strings, ints, booleans)
- No indentation issues
- Python ecosystem (pyproject.toml)

**Cons:**
- More verbose (quotes required)
- Less familiar to non-Python users
- Awkward for nested structures
- Limited editor support

**Rejected because**: Verbosity and unfamiliarity outweigh type safety

### Alternative 2: JSON

**Example:**
```json
{
  "name": "summary",
  "system_prompt": "You are an expert...\n\nFocus on:\n- Topics\n- Takeaways",
  "applies_to": ["all"]
}
```

**Pros:**
- Universal standard
- Fast parsing
- Strict syntax (no ambiguity)
- Excellent validation (JSON Schema)

**Cons:**
- **No comments** (deal-breaker for templates)
- Multi-line strings require `\n` escapes
- Verbose (quoted keys)
- Poor human readability

**Rejected because**: Lack of comments makes templates hard to document

### Alternative 3: Python Dataclasses

**Example:**
```python
# templates/summary.py
summary_template = ExtractionTemplate(
    name="summary",
    version="1.0",
    system_prompt="""
    You are an expert podcast analyst.
    """,
    applies_to=["all"],
)
```

**Pros:**
- Full type safety
- IDE support (autocomplete, refactoring)
- Programmatic (can compute values)
- No parsing needed

**Cons:**
- **Requires Python knowledge** (blocks non-developers)
- **Security risk** (executing user code)
- Not portable across languages
- Harder to edit without IDE

**Rejected because**: Non-developers must be able to create templates

## Rationale

### Why YAML Won

1. **Best Human Readability** (9/10)
   - Clean, minimal syntax
   - No quotes required for simple values
   - Easy to scan and understand

2. **Excellent Comment Support** (10/10)
   - Native `#` comments
   - Document template purpose
   - Explain prompt choices
   - Guide template authors

3. **Multi-line String Support** (10/10)
   ```yaml
   prompt: |
     Line 1
     Line 2
   ```
   - Perfect for long prompts
   - Preserves formatting
   - No escape characters

4. **Wide Adoption** (10/10)
   - Used by Docker, Kubernetes, GitHub Actions
   - Familiar to developers
   - Good editor support
   - Many examples available

5. **Validation Support** (8/10)
   - Pydantic models validate structure
   - YAML linters catch errors
   - Schema validation possible
   - Clear error messages

### Trade-offs Accepted

**Indentation Sensitivity**
- **Issue**: Wrong indentation breaks parsing
- **Mitigation**:
  - Use 2-space indentation consistently
  - YAML linter in pre-commit hooks
  - Clear error messages
  - Template examples

**Type Ambiguity**
- **Issue**: `no` becomes `False`, `1.0` ambiguous
- **Mitigation**:
  - Quote strings when ambiguous: `name: "no"`
  - Pydantic validation catches type errors
  - Document gotchas in template guide

**Security Concerns**
- **Issue**: `yaml.unsafe_load()` can execute code
- **Mitigation**:
  - **Always use `yaml.safe_load()`**
  - Never load untrusted templates
  - Pydantic validation layer
  - File permission checks

## Consequences

### Positive

✅ **User-Friendly**: Non-developers can create templates
✅ **Well-Documented**: Comments explain template design
✅ **Clean Prompts**: Multi-line strings read naturally
✅ **Familiar**: Most developers know YAML
✅ **Validated**: Pydantic catches errors early
✅ **Maintainable**: Easy to update and version

### Negative

❌ **Indentation Errors**: Whitespace matters
❌ **Type Confusion**: Some values ambiguous
❌ **Parsing Complexity**: More complex than JSON
❌ **Security**: Need safe_load() always

### Mitigations

1. **YAML Linting**
   ```yaml
   # .yamllint
   rules:
     indentation:
       spaces: 2
       indent-sequences: true
     line-length:
       max: 100
   ```

2. **Template Validation CLI**
   ```bash
   # Validate before using
   inkwell template validate my-template.yaml

   # Output:
   # ✓ Valid YAML syntax
   # ✓ All required fields present
   # ✓ Prompts are valid Jinja2
   # ✓ Schema is valid JSON Schema
   ```

3. **Template Creation Helper**
   ```bash
   # Interactive template creator
   inkwell template create

   # Creates properly formatted YAML
   # Validates as you go
   # Provides examples
   ```

4. **Comprehensive Documentation**
   - Template authoring guide
   - Common pitfalls
   - Best practices
   - Many examples

## Implementation

### Template Schema (Pydantic)

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional

class ExtractionTemplate(BaseModel):
    """Template for extracting content from transcript"""

    # Required fields
    name: str
    version: str
    description: str
    system_prompt: str
    user_prompt_template: str
    expected_format: Literal["json", "markdown", "yaml", "text"]

    # Optional fields
    output_schema: Optional[dict] = None
    category: Optional[str] = None
    applies_to: list[str] = Field(default_factory=lambda: ["all"])
    priority: int = 0
    model_preference: Optional[str] = None
    max_tokens: int = 2000
    temperature: float = 0.3

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure template name is filesystem-safe"""
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"Template name must be alphanumeric: {v}")
        return v

    @field_validator("user_prompt_template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        """Ensure Jinja2 template is valid"""
        from jinja2 import Template
        try:
            Template(v)
        except Exception as e:
            raise ValueError(f"Invalid Jinja2 template: {e}")
        return v
```

### Loading System

```python
class TemplateLoader:
    """Load and manage extraction templates"""

    def load_template(self, name: str) -> ExtractionTemplate:
        """Load template from YAML file"""
        path = self._find_template(name)

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise TemplateLoadError(f"Invalid YAML in {path}: {e}")

        try:
            template = ExtractionTemplate(**data)
        except ValidationError as e:
            raise TemplateValidationError(f"Invalid template {name}: {e}")

        return template
```

### Error Handling

```python
# Friendly error messages
try:
    template = loader.load_template("my-template")
except yaml.YAMLError as e:
    console.print(f"[red]✗ YAML syntax error in my-template.yaml[/red]")
    console.print(f"Line {e.problem_mark.line}: {e.problem}")
    console.print("\n[yellow]Tip: Check indentation (use 2 spaces)[/yellow]")
except ValidationError as e:
    console.print(f"[red]✗ Template validation failed[/red]")
    for error in e.errors():
        console.print(f"  - {error['loc'][0]}: {error['msg']}")
```

## Validation

### Success Criteria

✅ Can load built-in YAML templates
✅ Can load user YAML templates
✅ Pydantic validation catches errors
✅ Clear error messages for common mistakes
✅ Template validation CLI command works
✅ YAML linting in pre-commit hooks
✅ Documentation complete with examples

### Example Templates

**Default templates ship as YAML:**
- `summary.yaml`
- `quotes.yaml`
- `key-concepts.yaml`

**Category templates:**
- `tech/tools-mentioned.yaml`
- `tech/frameworks-mentioned.yaml`
- `interview/books-mentioned.yaml`
- `interview/people-mentioned.yaml`

## Related Decisions

- [ADR-013: LLM Provider Abstraction](013-llm-provider-abstraction.md)
- [Template Format Evaluation](../research/template-format-evaluation.md)

## References

- [YAML Specification](https://yaml.org/spec/)
- [PyYAML Documentation](https://pyyaml.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [yamllint](https://yamllint.readthedocs.io/)

## Revision History

- 2025-11-07: Initial decision (Phase 3 Unit 1)
