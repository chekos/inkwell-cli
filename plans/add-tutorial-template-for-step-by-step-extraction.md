# feat: Add Tutorial Template for Step-by-Step Plan Extraction

## Overview

Add a new "tutorial" template category for Inkwell that extracts step-by-step plans from podcast/video transcripts. This enables users to process tutorial content (like 2-hour coding walkthroughs) and get structured, actionable guides they can follow.

**Goal:** Transform tutorial/how-to video content into structured markdown guides with ordered steps, prerequisites, timestamps, and tips.

## Problem Statement / Motivation

Currently, Inkwell supports:
- `tech` category: extracts tools mentioned
- `interview` category: extracts books mentioned

But users processing tutorial content (coding walkthroughs, tool demos, how-to guides) lose the most valuable information: **the sequential steps to accomplish the goal**.

A user watching a 2-hour Python tutorial wants to save:
1. What the tutorial teaches (the goal)
2. What they need before starting (prerequisites)
3. The exact steps in order with timestamps
4. Common mistakes to avoid

This is currently not captured by any existing template.

## Proposed Solution

Create a new template category `tutorial/` with a `step-by-step-plan.yaml` template that extracts structured tutorial content.

### Template Structure

Create `src/inkwell/templates/categories/tutorial/step-by-step-plan.yaml`:

```yaml
name: step-by-step-plan
version: "1.0"
description: "Extract step-by-step plans from tutorial and how-to content"
category: tutorial

system_prompt: |
  You are an expert technical writer who excels at extracting and
  structuring instructional content from podcast/video transcripts.

  Your task is to identify and extract tutorials, guides, and
  step-by-step procedures.

  Focus on:
  - Sequential instructions with clear ordering
  - Prerequisites mentioned (tools, knowledge, accounts needed)
  - Code snippets and exact commands
  - Expected outcomes after each step
  - Common pitfalls and tips mentioned

  CRITICAL Guidelines:
  - ONLY extract content actually discussed - NEVER invent or add steps
  - Use imperative voice for instructions (start with action verbs)
  - Preserve exact code/commands when provided
  - Note when code is described but not shown: "[code described]"
  - If unsure about a step, omit it rather than guess

user_prompt_template: |
  Extract step-by-step tutorials from this transcript.

  Podcast: {{ metadata.podcast_name }}
  Episode: {{ metadata.episode_title }}
  {% if metadata.duration %}Duration: {{ metadata.duration }}{% endif %}

  <transcript>
  {{ transcript }}
  </transcript>

  For each tutorial found, extract:

  ## [Tutorial Title]

  **Goal:** What the learner will accomplish

  **Difficulty:** beginner | intermediate | advanced

  **Estimated Time:** (if mentioned)

  ### Prerequisites
  - Tools/software needed
  - Knowledge assumed
  - Accounts/access required

  ### Steps

  1. **[Step Title]** [MM:SS timestamp if available]
     - What to do (clear instruction)
     - Code/command: `exact code here`
     - Expected result: What you should see

  2. **[Next Step]** [MM:SS]
     ...continue for all steps...

  ### Tips & Common Pitfalls
  - Things to watch out for
  - Pro tips mentioned

  ### Key Takeaways
  - Main learning points

  ---

  If multiple tutorials are discussed, extract each as a separate section.
  If no tutorial content is found, state: "No step-by-step tutorial content found in this episode."

expected_format: markdown
temperature: 0.2
priority: 15
applies_to: [tutorial]
model_preference: auto

few_shot_examples:
  - input: |
      [05:30] Okay so first thing you want to do is open your terminal.
      Navigate to your project folder, that's cd followed by the path.
      [06:00] Then you run npm init dash y to create your package.json.
      You should see a success message saying it created the file.
      [06:30] A common mistake here is running this in the wrong directory,
      so double check you're in your project folder first.
    output: |
      ## Initialize an npm Project

      **Goal:** Create a new Node.js project with package.json

      **Difficulty:** beginner

      ### Prerequisites
      - Node.js installed
      - Terminal access

      ### Steps

      1. **Open your terminal** [05:30]
         - Navigate to your project folder
         - `cd /path/to/project`
         - Expected result: You're in the correct directory

      2. **Initialize the project** [06:00]
         - Create package.json with defaults
         - `npm init -y`
         - Expected result: Success message, package.json file created

      ### Tips & Common Pitfalls
      - Double check you're in your project folder before running npm init

      ### Key Takeaways
      - npm init -y creates package.json with default values
```

### Directory Structure

```
src/inkwell/templates/
├── default/
│   ├── summary.yaml
│   ├── quotes.yaml
│   └── key-concepts.yaml
└── categories/
    ├── tech/
    │   └── tools-mentioned.yaml
    ├── interview/
    │   └── books-mentioned.yaml
    └── tutorial/              # NEW
        └── step-by-step-plan.yaml
```

## Technical Considerations

### No Code Changes Required for MVP

The existing template system fully supports this feature:
- `TemplateLoader` automatically discovers templates in category directories
- `ExtractionEngine` processes any valid template
- `MarkdownGenerator` handles markdown format output
- CLI already supports `--templates` flag for explicit selection

**MVP approach:** Users specify template explicitly:
```bash
inkwell fetch <url> --templates step-by-step-plan
inkwell fetch <url> --templates summary,quotes,step-by-step-plan
```

### Optional Enhancement: Auto-Detection

For Phase 2, update `TemplateSelector.detect_category()` in `template_selector.py` to recognize tutorial content:

```python
# Add to template_selector.py around line 150
tutorial_keywords = [
    "tutorial", "how to", "step by step", "guide", "walkthrough",
    "let me show you", "first we'll", "next we", "then we",
    "install", "setup", "configure", "build", "deploy"
]
```

**Decision:** This is deferred to Phase 2 to keep MVP simple.

### Template Settings Rationale

| Setting | Value | Rationale |
|---------|-------|-----------|
| `temperature` | 0.2 | Low for factual precision - tutorials need exact commands/steps |
| `expected_format` | markdown | Tutorials need narrative structure, not strict JSON |
| `priority` | 15 | Same as other category templates |
| `applies_to` | [tutorial] | Only triggers for tutorial category - users can always use `--templates` flag explicitly |
| `few_shot_examples` | 1 example | Demonstrates expected output format to improve consistency |

Note: No `max_tokens` is set - this allows the model to use defaults and handle very long tutorials (1-2 hours) without arbitrary truncation.

### Handling Edge Cases

1. **No tutorial content:** Template explicitly handles with "No step-by-step tutorial content found"
2. **Multiple tutorials:** Template extracts each as separate section with `---` dividers
3. **Missing timestamps:** Uses "timestamp if available" - gracefully omits
4. **Code described but not shown:** Uses "[code described]" marker

## Acceptance Criteria

### Functional Requirements

- [ ] Create `src/inkwell/templates/categories/tutorial/` directory
- [ ] Create `step-by-step-plan.yaml` with valid template structure
- [ ] Template loads successfully via `TemplateLoader`
- [ ] Template can be selected via `--templates step-by-step-plan`
- [ ] Extraction produces markdown output with expected sections
- [ ] Output includes: title, goal, prerequisites, numbered steps, tips

### Quality Requirements

- [ ] Template passes YAML validation
- [ ] Template passes Pydantic model validation (`ExtractionTemplate`)
- [ ] Jinja2 template syntax is valid
- [ ] Existing tests continue to pass

### Documentation

- [ ] Update `docs/user-guide/templates.md` with tutorial template info
- [ ] Add example output to documentation

## MVP Implementation Plan

### Phase 1: Template Creation (MVP)

**Files to create:**

1. `src/inkwell/templates/categories/tutorial/step-by-step-plan.yaml`
   - Full template as specified above

**Files to update:**

None required - template auto-discovery handles this.

**Testing:**

```bash
# Verify template loads
uv run python -c "from inkwell.extraction.templates import TemplateLoader; t = TemplateLoader(); print(t.load_template('step-by-step-plan'))"

# Test with real content
inkwell fetch <youtube-tutorial-url> --templates step-by-step-plan
```

**Add to `tests/unit/test_template_loader.py`:**

```python
def test_load_tutorial_template(self) -> None:
    """Test loading tutorial category template."""
    loader = TemplateLoader()

    template = loader.load_template("step-by-step-plan")
    assert template.name == "step-by-step-plan"
    assert template.category == "tutorial"
    assert template.expected_format == "markdown"
    assert template.temperature == 0.2
    assert len(template.few_shot_examples) >= 1
```

**Add to `tests/unit/test_template_selector.py`:**

```python
def test_list_templates_includes_tutorial(self) -> None:
    """Test that tutorial template appears in template list."""
    loader = TemplateLoader()
    templates = loader.list_templates()

    assert "step-by-step-plan" in templates
```

### Phase 2: Auto-Detection (Future)

**Files to update:**

1. `src/inkwell/extraction/template_selector.py`
   - Add tutorial keyword matching in `detect_category()`
   - Add tutorial to category priority logic

## Success Metrics

- Template successfully extracts steps from tutorial content
- Output is useful for following along with original video
- Markdown renders correctly in Obsidian and other tools

## Dependencies & Prerequisites

**No external dependencies.** Uses existing:
- Template loading infrastructure
- Extraction engine
- Markdown output generation

**Requires:**
- No code changes for MVP
- Just one new YAML file

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM invents/hallucinates steps | Medium | High | Temperature 0.2, explicit "NEVER invent steps" in prompt, few-shot example |
| LLM extracts poor quality steps | Medium | Medium | Low temperature, clear prompts, few-shot example |
| Long tutorials exceed token limits | Low | Low | No max_tokens limit set - uses model defaults |
| Users expect auto-detection | Medium | Low | Document manual `--templates` usage clearly |

## Example Output

Processing a Python tutorial video would produce `step-by-step-plan.md`:

*Note: This is an idealized example. Real LLM output may vary in quality and formatting.*

```markdown
---
template: step-by-step-plan
version: "1.0"
extracted_at: 2026-01-05T10:30:00Z
---

## Setting Up a Python Virtual Environment

**Goal:** Create an isolated Python environment for your project

**Difficulty:** beginner

**Estimated Time:** 5 minutes

### Prerequisites
- Python 3.8+ installed on your system
- Terminal/command line access

### Steps

1. **Open your terminal** [00:30]
   - Navigate to your project directory
   - `cd ~/projects/my-project`
   - Expected result: You're in your project folder

2. **Create the virtual environment** [01:15]
   - Run the venv module
   - `python -m venv .venv`
   - Expected result: A `.venv` folder appears in your project

3. **Activate the environment** [02:00]
   - On Mac/Linux:
   - `source .venv/bin/activate`
   - On Windows:
   - `.venv\Scripts\activate`
   - Expected result: Your prompt shows `(.venv)` prefix

4. **Verify activation** [02:45]
   - Check Python location
   - `which python`
   - Expected result: Path points to `.venv/bin/python`

### Tips & Common Pitfalls
- Always activate before installing packages
- Add `.venv` to your `.gitignore`
- Use `deactivate` command to exit the environment

### Key Takeaways
- Virtual environments isolate project dependencies
- The `.venv` folder contains a complete Python installation
- Each project should have its own virtual environment

---
```

## References

### Internal

- `src/inkwell/extraction/models.py:49-136` - ExtractionTemplate model
- `src/inkwell/extraction/templates.py:21-283` - TemplateLoader
- `src/inkwell/extraction/template_selector.py:17-206` - TemplateSelector
- `docs/building-in-public/adr/014-template-format.md` - Template format ADR
- `docs/_internal/templates/AUTHORING_GUIDE.md` - Template authoring guide

### Existing Templates (Examples)

- `src/inkwell/templates/default/summary.yaml`
- `src/inkwell/templates/default/quotes.yaml`
- `src/inkwell/templates/categories/tech/tools-mentioned.yaml`

### External

- [Anthropic Prompt Engineering Guide](https://claude.com/blog/best-practices-for-prompt-engineering)
- [Instructor Library - Action Items](https://python.useinstructor.com/examples/action_items/)
