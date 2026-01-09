## Template Schema Design and Field Reference

**Date**: 2025-11-07
**Status**: Reference Documentation
**Related**: [ADR-014: Template Format](../adr/014-template-format.md), [Phase 3 Plan](../devlog/2025-11-07-phase-3-detailed-plan.md)

## Overview

This document provides comprehensive documentation for the extraction template schema. Templates are YAML files that define how content should be extracted from podcast transcripts using LLM prompts.

---

## Template Schema Reference

### Required Fields

#### `name` (string)

**Description**: Unique identifier for the template. Must be filesystem-safe.

**Validation**: Alphanumeric characters, hyphens, and underscores only

**Examples**:
```yaml
name: summary              # Good
name: tools-mentioned      # Good
name: key_concepts         # Good
name: invalid@name         # Bad - special characters not allowed
```

#### `version` (string)

**Description**: Template version using semantic versioning

**Format**: `MAJOR.MINOR.PATCH` or `MAJOR.MINOR`

**Purpose**: Used for cache invalidation - changing version invalidates cached extractions

**Examples**:
```yaml
version: "1.0"        # Initial version
version: "1.1.0"      # Minor update (improved prompt)
version: "2.0.0"      # Major update (breaking changes)
```

#### `description` (string)

**Description**: Human-readable description of what this template extracts

**Best Practice**: Be specific about what the template does

**Examples**:
```yaml
description: "Generate a comprehensive 2-3 paragraph summary with key takeaways"
description: "Extract notable quotes with exact wording, speakers, and timestamps"
description: "Identify all tools, frameworks, and libraries mentioned in tech podcasts"
```

#### `system_prompt` (string, multi-line)

**Description**: System message sent to the LLM to set context and behavior

**Best Practices**:
- Define the LLM's role clearly
- Specify what to focus on
- Set quality expectations
- Use multi-line YAML for readability

**Examples**:
```yaml
system_prompt: |
  You are an expert podcast analyst specialized in extracting key information.

  Your task is to generate accurate, concise summaries that capture:
  - Main topics discussed
  - Key takeaways and insights
  - Notable quotes or statements

  Focus on factual accuracy. Do not add information not present in the transcript.
```

#### `user_prompt_template` (string, multi-line Jinja2)

**Description**: User prompt template with variables for transcript and metadata

**Available Variables**:
- `{{ transcript }}` - Full transcript text
- `{{ metadata.podcast_name }}` - Podcast name
- `{{ metadata.episode_title }}` - Episode title
- `{{ metadata.duration }}` - Episode duration
- Custom variables defined in `variables` field

**Best Practices**:
- Be explicit about output format
- Include examples (few-shot prompting)
- Specify constraints (length, structure)
- Use clear instructions

**Example**:
```yaml
user_prompt_template: |
  Analyze this podcast transcript and extract notable quotes.

  Podcast: {{ metadata.podcast_name }}
  Episode: {{ metadata.episode_title }}

  Transcript:
  {{ transcript }}

  Extract 5-10 notable quotes that are:
  - Memorable or insightful
  - Representative of key ideas
  - Exact quotes (no paraphrasing)

  For each quote, provide:
  - Exact quote text
  - Speaker name
  - Timestamp in MM:SS format

  Return as JSON with this structure:
  {
    "quotes": [
      {
        "text": "exact quote here",
        "speaker": "Speaker Name",
        "timestamp": "12:34"
      }
    ]
  }
```

#### `expected_format` (enum)

**Description**: Expected output format from LLM

**Options**:
- `json` - Structured JSON response
- `markdown` - Formatted markdown text
- `yaml` - YAML formatted output
- `text` - Plain text response

**Recommendation**: Use `json` for structured data, `markdown` for narrative content

**Examples**:
```yaml
expected_format: json       # For quotes, entities, structured data
expected_format: markdown   # For summaries, narratives
expected_format: text       # For simple text extraction
```

---

### Optional Fields

#### `output_schema` (dict, JSON Schema)

**Description**: JSON Schema for validating extracted content

**Purpose**: Ensures LLM output matches expected structure

**When to use**: Always for `json` format, especially with critical extractions

**Example**:
```yaml
output_schema:
  type: object
  required: [quotes]
  properties:
    quotes:
      type: array
      items:
        type: object
        required: [text, speaker, timestamp]
        properties:
          text:
            type: string
            minLength: 10
          speaker:
            type: string
          timestamp:
            type: string
            pattern: "^\\d+:\\d+$"
```

#### `category` (string)

**Description**: Category this template belongs to

**Purpose**: Templates can be grouped by category for organization

**Examples**:
```yaml
category: tech          # For tech podcast templates
category: interview     # For interview podcast templates
category: general       # For general-purpose templates
```

#### `applies_to` (list of strings)

**Description**: Conditions under which this template should be applied

**Default**: `["all"]` - applies to all episodes

**Use Cases**:
- Category-specific templates
- Conditional template application
- Template routing logic

**Examples**:
```yaml
applies_to: [all]                    # Apply to all episodes
applies_to: [tech, programming]      # Only tech/programming podcasts
applies_to: [interview]              # Only interview podcasts
```

#### `priority` (integer)

**Description**: Execution order (lower numbers run first)

**Default**: `0`

**Purpose**: Control which templates run first (useful for dependencies)

**Examples**:
```yaml
# Summary runs first
name: summary
priority: 0

# Quotes runs second
name: quotes
priority: 5

# Custom analysis runs last
name: custom-analysis
priority: 10
```

#### `model_preference` (string)

**Description**: Preferred LLM provider for this template

**Options**:
- `claude` - Use Claude Sonnet
- `gemini` - Use Gemini Flash
- `auto` or `null` - Use system default

**When to specify**:
- `claude` for quote extraction (precision critical)
- `gemini` for cost-sensitive extractions
- `auto` for most templates

**Examples**:
```yaml
model_preference: claude    # High quality needed
model_preference: gemini    # Cost-sensitive
model_preference: auto      # Use default
```

#### `max_tokens` (integer)

**Description**: Maximum tokens for LLM response

**Default**: `2000`

**Range**: `1` to model-specific limit (typically 4000-8000)

**Guidelines**:
- Summary: 1000-2000
- Quotes: 1500-2500
- Concepts: 1000-1500
- Detailed extraction: 3000-4000

**Examples**:
```yaml
max_tokens: 1000    # Short summary
max_tokens: 2000    # Standard extraction
max_tokens: 4000    # Detailed analysis
```

#### `temperature` (float)

**Description**: LLM temperature (controls randomness)

**Default**: `0.3`

**Range**: `0.0` to `1.0`

**Guidelines**:
- `0.0-0.2`: Deterministic (quotes, facts)
- `0.3-0.5`: Balanced (summaries, concepts)
- `0.6-1.0`: Creative (not recommended for extraction)

**Examples**:
```yaml
temperature: 0.2    # Quote extraction (precision)
temperature: 0.3    # Summary generation (balanced)
temperature: 0.5    # Ideation (creative)
```

#### `variables` (list of TemplateVariable)

**Description**: Custom variables for prompt templates

**Use Case**: Define reusable variables with defaults

**Structure**:
```yaml
variables:
  - name: language
    description: "Podcast language"
    default: "en"
    required: false
  - name: focus_area
    description: "Specific area to focus on"
    required: true
```

#### `few_shot_examples` (list of dicts)

**Description**: Few-shot examples to improve extraction quality

**Purpose**: Show LLM exactly what output format is expected

**Best Practices**:
- Include 1-2 examples
- Show edge cases in examples
- Match expected_format

**Structure**:
```yaml
few_shot_examples:
  - input: "[00:05:30] John: Focus is key to productivity."
    output:
      quotes:
        - text: "Focus is key to productivity."
          speaker: "John"
          timestamp: "00:05:30"

  - input: "[00:12:45] Sarah: As Cal says, 'Deep work matters.'"
    output:
      quotes:
        - text: "Deep work matters."
          speaker: "Cal Newport (quoted by Sarah)"
          timestamp: "00:12:45"
```

---

## Complete Template Examples

### Example 1: Summary Template

```yaml
name: summary
version: "1.0"
description: "Generate a comprehensive episode summary with key takeaways"

system_prompt: |
  You are an expert podcast analyst. Create clear, concise summaries
  that capture the essence of the episode without unnecessary detail.

user_prompt_template: |
  Summarize the following podcast episode.

  Podcast: {{ metadata.podcast_name }}
  Episode: {{ metadata.episode_title }}
  Duration: {{ metadata.duration }}

  Transcript:
  {{ transcript }}

  Provide:
  1. A 2-3 paragraph summary of the main discussion
  2. A list of 3-5 key takeaways

  Format as markdown with clear headings.

expected_format: markdown
max_tokens: 2000
temperature: 0.3
priority: 0
applies_to: [all]
```

### Example 2: Quotes Template (JSON with Schema)

```yaml
name: quotes
version: "1.0"
description: "Extract notable quotes with speakers and timestamps"

system_prompt: |
  You are an expert at identifying and extracting memorable quotes
  from podcast transcripts. Focus on insightful, representative statements.

user_prompt_template: |
  Extract notable quotes from this transcript.

  Transcript:
  {{ transcript }}

  Requirements:
  - Exact quotes (no paraphrasing)
  - Speaker names
  - Timestamps in MM:SS format
  - 5-10 quotes maximum

  Return JSON matching the schema.

expected_format: json
output_schema:
  type: object
  required: [quotes]
  properties:
    quotes:
      type: array
      maxItems: 10
      items:
        type: object
        required: [text, speaker, timestamp]
        properties:
          text: {type: string}
          speaker: {type: string}
          timestamp: {type: string, pattern: "^\\d+:\\d+$"}

max_tokens: 2500
temperature: 0.2
priority: 5
model_preference: claude
applies_to: [all]

few_shot_examples:
  - input: "[00:05:30] John: I think focus is the key to productivity."
    output:
      quotes:
        - text: "I think focus is the key to productivity."
          speaker: "John"
          timestamp: "00:05:30"
```

### Example 3: Tools Mentioned (Tech Category)

```yaml
name: tools-mentioned
version: "1.0"
description: "Extract tools, frameworks, and libraries mentioned in tech podcasts"

category: tech

system_prompt: |
  You are a technical expert analyzing technology podcasts.
  Extract all tools, frameworks, libraries, and technologies mentioned.

user_prompt_template: |
  Identify all technical tools mentioned in this podcast.

  Transcript:
  {{ transcript }}

  For each tool, provide:
  - Name (official name)
  - Category (language, framework, library, tool, service, database, etc.)
  - Context (brief description of how it was discussed)
  - Timestamp (if mentioned at specific time)

  Return as JSON.

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
          name: {type: string}
          category:
            type: string
            enum: [language, framework, library, tool, service, database, platform, other]
          context: {type: string}
          timestamp: {type: string}

max_tokens: 3000
temperature: 0.2
priority: 10
applies_to: [tech, programming]
model_preference: claude
```

---

## Validation Rules

Templates are validated using Pydantic models with the following rules:

### Name Validation
```python
# Valid names
✅ "summary"
✅ "quotes"
✅ "tools-mentioned"
✅ "key_concepts"

# Invalid names
❌ "invalid@name"     # Special characters
❌ "my template"      # Spaces
❌ "quotes/summary"   # Slashes
```

### Jinja2 Template Validation
```python
# Valid templates
✅ "Summarize: {{ transcript }}"
✅ "Episode: {{ metadata.episode_title }}"

# Invalid templates
❌ "{{ unclosed"              # Unclosed tag
❌ "{{ undefined.field }}"    # Will error at runtime
```

### Temperature Validation
```python
# Valid temperatures
✅ 0.0
✅ 0.3
✅ 1.0

# Invalid temperatures
❌ -0.1    # Below 0
❌ 1.5     # Above 1
```

### Max Tokens Validation
```python
# Valid max_tokens
✅ 100
✅ 2000
✅ 8000

# Invalid max_tokens
❌ 0       # Must be >= 1
❌ -100    # Negative not allowed
```

---

## Best Practices

### 1. Use Few-Shot Examples

**Always include 1-2 examples** to dramatically improve quality and consistency.

### 2. Be Explicit About Format

Don't assume the LLM knows your format. Show examples and specify structure clearly.

### 3. Validate with Schemas

For `json` format, always include `output_schema` for validation.

### 4. Set Appropriate Temperature

- Quotes, facts: 0.1-0.2
- Summaries, analysis: 0.3-0.4
- Creative tasks: 0.5-0.7 (rarely needed)

### 5. Version Templates

Increment version when changing prompts to invalidate cache.

### 6. Choose Right Model

- Claude for quotes (precision)
- Either for summaries
- Gemini for cost-sensitive tasks

### 7. Test Templates

Test with real transcripts before deploying.

---

## Template Development Workflow

1. **Define Purpose**: What should this template extract?
2. **Choose Format**: JSON for structured, markdown for narrative
3. **Write System Prompt**: Define LLM role and expectations
4. **Write User Prompt**: Be specific about requirements
5. **Add Schema**: Validate JSON output structure
6. **Add Examples**: 1-2 few-shot examples
7. **Set Parameters**: temperature, max_tokens, model_preference
8. **Test**: Run on sample transcripts
9. **Iterate**: Refine based on results
10. **Version**: Increment version for changes

---

## Common Pitfalls

### Pitfall 1: Vague Prompts

❌ "Extract the important stuff"
✅ "Extract 5-10 notable quotes with exact wording, speakers, and timestamps"

### Pitfall 2: Missing Schema

❌ `expected_format: json` without `output_schema`
✅ Include schema for all JSON outputs

### Pitfall 3: No Examples

❌ No `few_shot_examples`
✅ Include 1-2 examples showing expected format

### Pitfall 4: Wrong Temperature

❌ `temperature: 0.8` for quote extraction
✅ `temperature: 0.2` for factual extraction

### Pitfall 5: Forgetting Version

❌ Change prompt without updating version
✅ Increment version to invalidate cache

---

## Template Testing

Test templates before deploying:

```bash
# Validate template syntax
inkwell template validate my-template.yaml

# Test on sample transcript
inkwell template test my-template.yaml --transcript sample.txt

# Preview output
inkwell template preview my-template.yaml
```

---

## References

- [ADR-014: Template Format](../adr/014-template-format.md)
- [Template Format Evaluation](./template-format-evaluation.md)
- [Prompt Engineering Effectiveness](../experiments/2025-11-07-prompt-engineering-effectiveness.md)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)
- [JSON Schema Specification](https://json-schema.org/)

## Revision History

- 2025-11-07: Initial template schema documentation (Phase 3 Unit 2)
