# Template Authoring Guide

**Date**: 2025-11-07
**Version**: 1.0
**Related**: [Template Schema Design](../research/template-schema-design.md), [ADR-014: Template Format](../adr/014-template-format.md)

---

## Overview

This guide teaches you how to write custom extraction templates for Inkwell. Templates define how content is extracted from podcast transcripts using LLM prompts.

**What you'll learn:**
- Template structure and required fields
- Writing effective system and user prompts
- Using variables and few-shot examples
- Validating outputs with JSON Schema
- Best practices for different extraction types

---

## Quick Start

### Your First Template

Create a file `~/.config/inkwell/templates/my-template.yaml`:

```yaml
name: my-template
version: "1.0"
description: "Extract action items from podcast episodes"

system_prompt: |
  You are an expert at identifying actionable tasks and recommendations
  from podcast discussions.

user_prompt_template: |
  Extract action items from this podcast transcript.

  Transcript:
  {{ transcript }}

  For each action item:
  - Brief description
  - Why it was recommended
  - Timestamp (MM:SS format)

  Return as JSON:
  {
    "action_items": [
      {
        "action": "description",
        "reason": "why recommended",
        "timestamp": "12:34"
      }
    ]
  }

expected_format: json
max_tokens: 2000
temperature: 0.3
```

**Use it:**
```bash
inkwell fetch <url> --templates my-template
```

That's it! Now let's dive deeper.

---

## Template Structure

### Required Fields

Every template must have these fields:

```yaml
name: template-name           # Unique identifier (alphanumeric, hyphens, underscores)
version: "1.0"                # Semantic version for cache invalidation
description: "What it does"  # Human-readable description
system_prompt: "..."          # LLM system message
user_prompt_template: "..."  # Jinja2 template for user message
expected_format: json         # json, markdown, yaml, or text
```

### Optional Fields

Enhance your template with these optional fields:

```yaml
output_schema: {...}          # JSON Schema for validation
category: tech                # Template category
applies_to: [tech, general]   # When to apply this template
priority: 10                  # Execution order (lower = earlier)
model_preference: claude      # claude, gemini, or auto
max_tokens: 2000              # Maximum response length
temperature: 0.3              # 0.0 (deterministic) to 1.0 (creative)
variables: [...]              # Custom variables
few_shot_examples: [...]      # Example inputs/outputs
```

---

## Writing Prompts

### System Prompt

The system prompt sets context and defines the LLM's role.

**Best practices:**
- Define role clearly ("You are an expert...")
- Specify what to focus on
- Set quality expectations
- Keep it concise (2-5 sentences)

**Example:**
```yaml
system_prompt: |
  You are an expert podcast analyst specialized in extracting technical
  discussions and code-related insights.

  Focus on accuracy - only extract information explicitly mentioned in
  the transcript. Do not infer or add information.
```

### User Prompt Template

The user prompt template is a Jinja2 template with access to:
- `{{ transcript }}` - Full transcript text
- `{{ metadata.podcast_name }}` - Podcast name
- `{{ metadata.episode_title }}` - Episode title
- `{{ metadata.duration }}` - Episode duration
- Custom variables (if defined)

**Best practices:**
- Be explicit about requirements
- Show the expected output format
- Include examples (few-shot prompting)
- Specify constraints (length, count, etc.)

**Example:**
```yaml
user_prompt_template: |
  Extract notable quotes from this podcast.

  Podcast: {{ metadata.podcast_name }}
  Episode: {{ metadata.episode_title }}

  Transcript:
  {{ transcript }}

  Requirements:
  - Extract 5-10 most memorable quotes
  - Must be exact quotes (no paraphrasing)
  - Include speaker name and timestamp

  Return JSON matching this structure:
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

---

## Output Formats

### JSON Format

Best for structured data extraction.

**Example:**
```yaml
expected_format: json

user_prompt_template: |
  Extract tools mentioned.

  Return JSON:
  {
    "tools": [
      {
        "name": "Tool Name",
        "category": "type",
        "context": "how discussed"
      }
    ]
  }

output_schema:
  type: object
  required: [tools]
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
            enum: [language, framework, library, tool, database, other]
          context: {type: string}
```

**Always include `output_schema` for JSON format** to validate LLM output.

### Markdown Format

Best for narrative content like summaries.

**Example:**
```yaml
expected_format: markdown

user_prompt_template: |
  Summarize this podcast episode.

  Transcript:
  {{ transcript }}

  Provide:
  1. A 2-3 paragraph summary
  2. A list of 3-5 key takeaways

  Format as markdown with clear headings.
```

### Text Format

Best for simple, unformatted output.

**Example:**
```yaml
expected_format: text

user_prompt_template: |
  Extract the main thesis of this episode in 2-3 sentences.

  Transcript:
  {{ transcript }}
```

---

## JSON Schema Validation

For `json` format, define an `output_schema` to validate LLM responses.

### Basic Schema

```yaml
output_schema:
  type: object
  required: [quotes]        # Required fields
  properties:
    quotes:
      type: array
      items:
        type: object
        required: [text]
        properties:
          text: {type: string}
          speaker: {type: string}
```

### Advanced Schema

```yaml
output_schema:
  type: object
  required: [tools]
  properties:
    tools:
      type: array
      minItems: 1            # At least 1 tool
      maxItems: 20           # Max 20 tools
      items:
        type: object
        required: [name, category]
        properties:
          name:
            type: string
            minLength: 1
          category:
            type: string
            enum: [language, framework, library, tool, database, platform, other]
          url:
            type: string
            format: uri     # Validates URL format
          timestamp:
            type: string
            pattern: "^\\d+:\\d+$"  # Matches MM:SS
```

**Common validations:**
- `minLength` / `maxLength` - String length constraints
- `minItems` / `maxItems` - Array size constraints
- `enum` - Restrict to specific values
- `pattern` - Regex validation
- `format` - Built-in formats (uri, email, date, etc.)

See [JSON Schema docs](https://json-schema.org/) for complete reference.

---

## Few-Shot Examples

Few-shot examples dramatically improve extraction quality and consistency.

**Structure:**
```yaml
few_shot_examples:
  - input: "Sample transcript snippet"
    output: {expected: "output"}
  - input: "Another example"
    output: {more: "data"}
```

**Full example:**
```yaml
name: quotes
expected_format: json

user_prompt_template: |
  Extract quotes from the transcript.

  {{ transcript }}

  Return JSON with quotes array.

few_shot_examples:
  - input: "[00:05:30] John: I think focus is the key to productivity."
    output:
      quotes:
        - text: "I think focus is the key to productivity."
          speaker: "John"
          timestamp: "00:05:30"

  - input: "[00:12:45] Sarah: As Cal says, 'Deep work matters.'"
    output:
      quotes:
        - text: "Deep work matters."
          speaker: "Cal Newport (quoted by Sarah)"
          timestamp: "00:12:45"
```

**Best practices:**
- Include 1-3 examples (more is not always better)
- Show edge cases in examples
- Match the expected output format exactly
- Keep examples concise

---

## Template Parameters

### Priority

Controls execution order. Lower numbers run first.

```yaml
name: summary
priority: 0         # Runs first

---
name: detailed-analysis
priority: 10        # Runs after summary
```

**Use cases:**
- Run summary before detailed extractions
- Execute cheap extractions before expensive ones
- Order dependencies (if one template uses another's output)

### Temperature

Controls randomness. Range: 0.0 to 1.0

```yaml
temperature: 0.2    # Quote extraction (very deterministic)
temperature: 0.3    # Summary generation (balanced)
temperature: 0.5    # Creative analysis (more varied)
```

**Guidelines:**
- **0.0-0.2**: Factual extraction (quotes, entities, data)
- **0.3-0.4**: Summaries and analysis
- **0.5-0.7**: Creative or exploratory tasks
- **0.8-1.0**: Not recommended for extraction

### Max Tokens

Maximum response length. Range: 1 to ~8000

```yaml
max_tokens: 1000    # Short summary
max_tokens: 2000    # Standard extraction (default)
max_tokens: 4000    # Detailed analysis
```

**Estimate tokens:**
- ~4 characters = 1 token
- 100 words ≈ 133 tokens
- 1 page text ≈ 500 tokens

### Model Preference

Choose LLM provider for this template.

```yaml
model_preference: claude    # High quality, expensive
model_preference: gemini    # Good quality, cheap
model_preference: auto      # Use system default (recommended)
```

**When to specify:**
- `claude`: Precision critical (quotes, exact data)
- `gemini`: Cost-sensitive, quality sufficient
- `auto`: Most templates (default)

---

## Category Templates

Category templates apply only to specific podcast types.

### Creating Category Templates

```yaml
name: tools-mentioned
category: tech
applies_to: [tech, programming]

system_prompt: |
  You are a technical expert analyzing technology podcasts.
  Extract all tools, frameworks, and libraries mentioned.
```

**Built-in categories:**
- `tech` - Technology and programming podcasts
- `interview` - Interview-style podcasts
- `general` - General content (default)

### Category Detection

Inkwell auto-detects categories using keyword matching:

**Tech indicators:**
- programming, code, software, framework, library
- python, javascript, react, docker, api
- developer, engineering, technical

**Interview indicators:**
- guest, interview, book, author, welcome
- background, experience, story, conversation

**Add custom detection** by using explicit categories:
```bash
inkwell fetch <url> --category tech
```

---

## Custom Variables

Define reusable variables for your templates.

```yaml
variables:
  - name: language
    description: "Podcast language"
    default: "en"
    required: false

  - name: max_quotes
    description: "Maximum quotes to extract"
    default: "10"
    required: false

user_prompt_template: |
  Extract up to {{ max_quotes }} quotes in {{ language }} language.

  {{ transcript }}
```

**Usage:**
```bash
inkwell fetch <url> --template-vars language=es max_quotes=5
```

---

## Complete Examples

### Example 1: Action Items

```yaml
name: action-items
version: "1.0"
description: "Extract actionable tasks and recommendations"

category: general
applies_to: [all]
priority: 15

system_prompt: |
  You are an expert at identifying actionable recommendations
  from podcast discussions. Focus on specific, concrete actions.

user_prompt_template: |
  Extract action items from this podcast.

  Transcript:
  {{ transcript }}

  For each action item:
  - Clear, actionable description
  - Why it was recommended
  - Timestamp in MM:SS format

  Return JSON matching the schema.

expected_format: json
output_schema:
  type: object
  required: [action_items]
  properties:
    action_items:
      type: array
      items:
        type: object
        required: [action, reason]
        properties:
          action:
            type: string
            minLength: 10
          reason:
            type: string
          timestamp:
            type: string
            pattern: "^\\d+:\\d+$"

max_tokens: 2000
temperature: 0.3
model_preference: auto

few_shot_examples:
  - input: "[15:30] You should definitely read 'Deep Work' by Cal Newport."
    output:
      action_items:
        - action: "Read 'Deep Work' by Cal Newport"
          reason: "Recommended by host"
          timestamp: "15:30"
```

### Example 2: Technical Concepts

```yaml
name: technical-concepts
version: "1.0"
description: "Extract and explain technical concepts discussed"

category: tech
applies_to: [tech, programming]
priority: 12

system_prompt: |
  You are a technical educator who explains programming concepts clearly.
  Extract technical concepts and provide brief, accessible explanations.

user_prompt_template: |
  Identify technical concepts discussed in this podcast.

  Transcript:
  {{ transcript }}

  For each concept:
  - Name (official term)
  - Brief explanation (1-2 sentences)
  - How it was discussed

  Return JSON.

expected_format: json
output_schema:
  type: object
  required: [concepts]
  properties:
    concepts:
      type: array
      maxItems: 15
      items:
        type: object
        required: [name, explanation]
        properties:
          name: {type: string}
          explanation: {type: string}
          context: {type: string}

max_tokens: 3000
temperature: 0.3
model_preference: claude
```

### Example 3: Episode Summary

```yaml
name: detailed-summary
version: "1.0"
description: "Generate comprehensive episode summary with sections"

category: general
applies_to: [all]
priority: 0

system_prompt: |
  You are an expert podcast summarizer. Create clear, well-structured
  summaries that capture the essence without unnecessary detail.

user_prompt_template: |
  Summarize this podcast episode.

  Podcast: {{ metadata.podcast_name }}
  Episode: {{ metadata.episode_title }}
  Duration: {{ metadata.duration }}

  Transcript:
  {{ transcript }}

  Provide:

  ## Summary
  A comprehensive 3-4 paragraph summary of the main discussion.

  ## Key Takeaways
  - 5-7 bullet points of key insights

  ## Topics Covered
  - List of main topics discussed

  ## Notable Moments
  - 2-3 highlights with timestamps

  Format as markdown.

expected_format: markdown
max_tokens: 3000
temperature: 0.3
model_preference: auto
```

---

## Best Practices

### 1. Start Simple

Begin with minimal templates and add complexity as needed.

✅ **Good:**
```yaml
name: simple-summary
system_prompt: "Summarize podcasts clearly."
user_prompt_template: "Summarize: {{ transcript }}"
expected_format: text
```

❌ **Bad:**
```yaml
# Don't add complexity until you need it
name: over-engineered-summary
variables: [...]        # Not needed yet
few_shot_examples: [...] # Add after testing
output_schema: {...}    # Only for JSON format
```

### 2. Test Incrementally

1. Start with basic prompt
2. Test on sample transcript
3. Add few-shot examples
4. Refine based on results
5. Add schema validation
6. Adjust temperature/tokens

### 3. Be Explicit

LLMs need clear instructions.

✅ **Good:**
```yaml
user_prompt_template: |
  Extract 5-10 quotes.

  Requirements:
  - Exact quotes only (no paraphrasing)
  - Include speaker name
  - Include timestamp in MM:SS format

  Return JSON: {"quotes": [...]}
```

❌ **Bad:**
```yaml
user_prompt_template: |
  Get the quotes from the transcript.
  # Too vague - what format? how many? what fields?
```

### 4. Use Few-Shot Examples

Include 1-2 examples for consistent results.

✅ **Good:**
```yaml
few_shot_examples:
  - input: "[12:00] John: Focus is key."
    output:
      quotes:
        - text: "Focus is key."
          speaker: "John"
          timestamp: "12:00"
```

### 5. Validate JSON Output

Always use `output_schema` for `json` format.

✅ **Good:**
```yaml
expected_format: json
output_schema:
  type: object
  required: [quotes]
  properties: {...}
```

❌ **Bad:**
```yaml
expected_format: json
# No schema - LLM might return invalid JSON
```

### 6. Choose Right Temperature

Match temperature to task.

✅ **Good:**
```yaml
# Quotes (factual)
temperature: 0.2

# Summary (balanced)
temperature: 0.3

# Analysis (creative)
temperature: 0.5
```

❌ **Bad:**
```yaml
# Quotes with high temperature
temperature: 0.8  # May paraphrase or invent quotes
```

### 7. Version Your Templates

Increment version when changing prompts.

✅ **Good:**
```yaml
version: "1.1"  # Changed prompt
# Cache automatically invalidated
```

❌ **Bad:**
```yaml
version: "1.0"  # Didn't update version
# Old cached results used despite prompt changes
```

---

## Testing Templates

### Validation

Validate template syntax:

```bash
inkwell template validate my-template.yaml
```

### Preview

Preview rendered prompt:

```bash
inkwell template preview my-template.yaml \
  --transcript sample.txt
```

### Test Extraction

Test on sample transcript:

```bash
inkwell template test my-template.yaml \
  --transcript sample.txt \
  --output test-output/
```

### Dry Run

Test without making API calls:

```bash
inkwell fetch <url> \
  --templates my-template \
  --dry-run
```

---

## Common Patterns

### Pattern 1: Entity Extraction

Extract specific entities (people, tools, books).

```yaml
name: entities
expected_format: json
system_prompt: "Extract named entities."
user_prompt_template: |
  Extract entities:
  {{ transcript }}

  Return JSON: {"entities": [{"name": "...", "type": "..."}]}

output_schema:
  type: object
  properties:
    entities:
      type: array
      items:
        properties:
          name: {type: string}
          type: {type: string, enum: [person, organization, product, tool]}
```

### Pattern 2: Timestamped Extraction

Extract content with timestamps.

```yaml
user_prompt_template: |
  Extract quotes with timestamps.

  Format timestamps as MM:SS.

  {{ transcript }}

output_schema:
  properties:
    quotes:
      items:
        properties:
          timestamp:
            type: string
            pattern: "^\\d+:\\d+$"
```

### Pattern 3: Hierarchical Data

Extract nested/structured data.

```yaml
output_schema:
  properties:
    sections:
      type: array
      items:
        properties:
          topic: {type: string}
          subtopics:
            type: array
            items: {type: string}
          key_points:
            type: array
            items: {type: string}
```

### Pattern 4: Conditional Extraction

Extract based on content presence.

```yaml
user_prompt_template: |
  If the transcript contains code examples, extract them.
  Otherwise, return empty array.

  {{ transcript }}

  Return: {"code_examples": [...]}
```

---

## Troubleshooting

### Problem: LLM Returns Wrong Format

**Solution:** Add few-shot examples showing exact format.

```yaml
few_shot_examples:
  - input: "sample"
    output: {"expected": "format"}
```

### Problem: Extraction Quality Poor

**Solutions:**
1. Lower temperature (0.2 instead of 0.5)
2. Add more specific instructions
3. Use `model_preference: claude`
4. Add few-shot examples

### Problem: Validation Errors

**Solution:** Check `output_schema` matches expected output exactly.

```bash
inkwell template test my-template.yaml --verbose
```

### Problem: Missing Data

**Solution:** Be explicit about what to include.

```yaml
user_prompt_template: |
  Extract ALL quotes, even brief ones.
  Include speaker name (required).
  Include timestamp (required).
```

### Problem: Inconsistent Results

**Solutions:**
1. Lower temperature to 0.2
2. Add few-shot examples
3. Be more specific in prompt
4. Use stricter `output_schema`

---

## Resources

### Documentation

- [Template Schema Reference](../research/template-schema-design.md) - Complete field reference
- [ADR-014: Template Format](../adr/014-template-format.md) - Why YAML?
- [Prompt Engineering Effectiveness](../experiments/2025-11-07-prompt-engineering-effectiveness.md) - Research findings

### External Resources

- [Jinja2 Template Designer](https://jinja.palletsprojects.com/templates/)
- [JSON Schema Specification](https://json-schema.org/)
- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Anthropic Prompt Engineering](https://docs.anthropic.com/claude/docs/prompt-engineering)

### Examples

See built-in templates for reference:
- `src/inkwell/templates/default/` - Default templates
- `src/inkwell/templates/categories/` - Category-specific templates

---

## Next Steps

1. **Create your first template** using the Quick Start example
2. **Test it** on a sample podcast
3. **Refine** based on results
4. **Share** your templates with the community

**Need help?** Open an issue or discussion on GitHub.

---

## Revision History

- 2025-11-07: Initial authoring guide (Phase 3 Unit 3)
