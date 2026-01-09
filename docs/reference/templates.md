# Templates

Available extraction templates and their outputs.

---

## Overview

Templates define what information to extract from podcast transcripts. Each template produces a separate markdown file.

---

## Available Templates

### summary

**Purpose:** Episode overview and key takeaways

**Output file:** `summary.md`

**Best for:** All episodes

**Extracted content:**

- Episode overview
- Key takeaways (3-5 bullet points)
- Main themes discussed
- Practical applications

**Example output:**

```markdown
# Summary

## Overview
In this episode, the host discusses productivity systems
with a focus on time-blocking and deep work.

## Key Takeaways
- Time-blocking increases focus by 40%
- Deep work requires 90-minute blocks minimum
- Context switching is the enemy of productivity

## Main Themes
- Productivity, Focus, Time Management

## Practical Applications
- Block 2 hours each morning for deep work
- Use a physical calendar for time-blocking
```

---

### quotes

**Purpose:** Notable quotes with speaker attribution

**Output file:** `quotes.md`

**Best for:** Interview podcasts, thought leadership

**Extracted content:**

- Direct quotes from speakers
- Speaker attribution
- Timestamp (if available)
- Context for the quote

**Example output:**

```markdown
# Notable Quotes

> "The quality of your attention determines the quality of your life."
> — Cal Newport

> "Most people overestimate what they can do in a day and underestimate what they can do in a year."
> — Guest Speaker

> "Focus is not about saying yes. It's about saying no."
> — Host
```

---

### key-concepts

**Purpose:** Main ideas and concepts explained

**Output file:** `key-concepts.md`

**Best for:** Educational content, complex topics

**Extracted content:**

- Concept names
- Definitions/explanations
- Examples given
- Related concepts

**Example output:**

```markdown
# Key Concepts

## Deep Work
**Definition:** Professional activities performed in a state of distraction-free concentration.

**Key points:**
- Requires extended, uninterrupted time
- Produces high-value output
- Is a skill that must be trained

**Related:** [[Shallow Work]], [[Flow State]]

---

## Time Blocking
**Definition:** Scheduling every minute of your day in advance.

**Key points:**
- Reduces decision fatigue
- Creates accountability
- Makes time visible
```

---

### tools-mentioned

**Purpose:** Software, apps, and products referenced

**Output file:** `tools-mentioned.md`

**Best for:** Tech podcasts, productivity shows

**Extracted content:**

- Tool/product name
- Category
- What it's used for
- URL (if mentioned)

**Example output:**

```markdown
# Tools Mentioned

## Productivity
- **Notion** - All-in-one workspace for notes and projects
- **Todoist** - Task management app
- **Forest** - Focus timer with gamification

## Development
- **VS Code** - Code editor
- **GitHub Copilot** - AI pair programming

## Communication
- **Slack** - Team messaging
- **Loom** - Async video messaging
```

---

### books-mentioned

**Purpose:** Books and reading recommendations

**Output file:** `books-mentioned.md`

**Best for:** Any podcast with book references

**Extracted content:**

- Book title
- Author
- Why it was mentioned
- Key ideas from the book

**Example output:**

```markdown
# Books Mentioned

## Deep Work
**Author:** Cal Newport

**Why mentioned:** Foundation for the episode's discussion on focus

**Key ideas:**
- Shallow work is the enemy of productivity
- Deep work is a skill that requires practice
- Schedule every minute of your day

---

## Atomic Habits
**Author:** James Clear

**Why mentioned:** Building systems over goals

**Key ideas:**
- 1% better every day compounds
- Environment design beats willpower
```

---

## Template Selection

### Automatic Selection

Templates are auto-selected based on episode category:

| Category | Templates |
|----------|-----------|
| `tech` | summary, quotes, tools-mentioned |
| `business` | summary, quotes, key-concepts |
| `interview` | summary, quotes |
| `education` | summary, key-concepts |
| Default | summary, quotes, key-concepts |

### Manual Selection

Override with `--templates`:

```bash
inkwell fetch URL --templates summary,quotes,books-mentioned
```

---

## Provider Assignment

Different templates use different providers by default:

| Template | Default Provider | Reason |
|----------|-----------------|--------|
| summary | Gemini | Cost-effective, good quality |
| quotes | Claude | Precision matters for attribution |
| key-concepts | Gemini | Good for explanations |
| tools-mentioned | Gemini | Straightforward extraction |
| books-mentioned | Claude | Accuracy in titles/authors |

Override with `--provider`:

```bash
inkwell fetch URL --provider gemini  # All templates use Gemini
```

---

## Template Versioning

Templates include version numbers for cache invalidation:

```yaml
name: summary
version: 2
```

When a template is updated:

1. Version number increases
2. Cache is invalidated for that template
3. New extractions use updated prompt

---

## Cost by Template

Approximate costs per template (1-hour episode):

| Template | Gemini | Claude |
|----------|--------|--------|
| summary | $0.003 | $0.04 |
| quotes | $0.003 | $0.04 |
| key-concepts | $0.003 | $0.04 |
| tools-mentioned | $0.002 | $0.03 |
| books-mentioned | $0.002 | $0.03 |

---

## Custom Templates

Custom templates are planned for a future release. Currently, only built-in templates are available.

---

## Next Steps

- [Content Extraction](../user-guide/extraction.md) - Using templates
- [Configuration](../user-guide/configuration.md) - Default settings
