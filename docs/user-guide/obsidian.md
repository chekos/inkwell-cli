# Obsidian Integration

Use Inkwell output with Obsidian for powerful knowledge management.

---

## Overview

Inkwell's output is designed for Obsidian with:

- **YAML frontmatter** - Dataview-compatible metadata
- **Wikilinks** - Connect concepts across episodes
- **Tags** - Easy filtering and search
- **Folder structure** - Works as vault or subfolder

---

## Setup

### Option 1: Use Output as Vault

Point Obsidian directly to Inkwell's output:

1. Open Obsidian
2. Click "Open folder as vault"
3. Select `~/inkwell-notes`

### Option 2: Add to Existing Vault

Copy episodes to your vault:

```bash
# Copy single episode
cp -r ~/inkwell-notes/podcast-2025-01-15-title ~/my-vault/podcasts/

# Or configure output to write directly to vault
inkwell config set default_output_dir ~/my-vault/podcasts
```

---

## Output Format

Each episode creates Obsidian-ready markdown:

```markdown
---
title: Summary
podcast: Lenny's Podcast
episode: Building a Growth Team
episode_date: 2025-11-10
duration_minutes: 45
rating: 4
status: inbox
tags: [podcast, growth, product-management, startups]
topics: [Growth Teams, A/B Testing, Experimentation]
has_wikilinks: true
cost_usd: 0.0055
---

# Building a Growth Team

## Overview

In this episode, Lenny discusses how to build a growth team with
[[Elena Verna]]. They cover [[Growth Loops]], [[A/B Testing]], and
[[Product-Led Growth]].

## Key Takeaways

- **[[Growth Teams]]** should be cross-functional
- **[[Experimentation Velocity]]** matters more than individual wins
- Start with [[Activation]] before [[Retention]]
```

---

## Wikilinks

Inkwell automatically creates wikilinks for:

- **People mentioned** - `[[Elena Verna]]`
- **Concepts** - `[[Growth Loops]]`, `[[A/B Testing]]`
- **Products/Tools** - `[[Amplitude]]`, `[[Mixpanel]]`
- **Books** - `[[Thinking, Fast and Slow]]`

### Building a Knowledge Graph

Click any wikilink to:

1. Create a new note for that topic
2. See backlinks from other episodes
3. Build connections over time

---

## Tags

Inkwell adds contextual tags:

```yaml
tags: [podcast, growth, product-management, startups]
```

Use Obsidian's tag pane to filter by topic.

---

## Dataview Queries

With the [Dataview plugin](https://github.com/blacksmithgu/obsidian-dataview), query your podcast notes.

### Recent Episodes

```dataview
TABLE podcast, episode_date, rating, duration_minutes
FROM "podcasts"
SORT episode_date DESC
LIMIT 10
```

### By Rating

```dataview
TABLE episode, podcast, duration_minutes
FROM "podcasts"
WHERE rating >= 4
SORT rating DESC
```

### By Topic

```dataview
TABLE episode, podcast
FROM "podcasts"
WHERE contains(topics, "growth")
SORT episode_date DESC
```

### Cost Tracking

```dataview
TABLE episode, cost_usd
FROM "podcasts"
SORT cost_usd DESC
LIMIT 10
```

### Unprocessed (Inbox)

```dataview
LIST
FROM "podcasts"
WHERE status = "inbox"
SORT episode_date DESC
```

---

## Frontmatter Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Note title (template name or summary) |
| `podcast` | string | Podcast name |
| `episode` | string | Episode title |
| `episode_date` | date | Episode publish date |
| `duration_minutes` | number | Episode length |
| `rating` | number | Your rating (1-5) |
| `status` | string | Processing status (inbox, reviewed, archived) |
| `tags` | list | Contextual tags |
| `topics` | list | Key topics discussed |
| `has_wikilinks` | boolean | Whether wikilinks are included |
| `cost_usd` | number | Extraction cost |
| `template` | string | Template that generated this file |
| `source` | string | Episode URL |

---

## Workflow Example

### Daily Processing

```bash
# Process latest episodes from favorite podcasts
inkwell fetch lennys --latest
inkwell fetch syntax --latest
```

### Weekly Review

In Obsidian, create a weekly review note:

```markdown
# Week of 2025-01-13

## New Episodes
```dataview
TABLE podcast, episode, rating
FROM "podcasts"
WHERE episode_date >= date(2025-01-13) AND episode_date <= date(2025-01-19)
SORT episode_date DESC
```

## Top Quotes This Week
![[lennys-2025-01-15-growth/quotes]]
![[syntax-2025-01-16-typescript/quotes]]
```

### Topic Deep Dive

Create a MOC (Map of Content) for a topic:

```markdown
# Growth

Episodes about growth:

```dataview
LIST
FROM "podcasts"
WHERE contains(topics, "growth") OR contains(tags, "growth")
SORT episode_date DESC
```

## Key Concepts
- [[Growth Loops]]
- [[Product-Led Growth]]
- [[Activation]]
```

---

## Custom Frontmatter

Configure additional fields in `config.yaml`:

```yaml
obsidian:
  extra_frontmatter:
    vault: podcasts
    type: podcast-note
    project: learning
```

---

## Tips

### Link Episodes Together

Add manual connections in your notes:

```markdown
This connects to [[other-podcast-2025-01-10-topic/summary]].
```

### Use Templates

Create an Obsidian template for manual notes:

```markdown
---
related_episodes: []
action_items: []
---

## My Thoughts

## Connections

## Action Items
```

### Rating System

Update ratings after reviewing:

```yaml
rating: 5  # Must listen
rating: 4  # Very good
rating: 3  # Good
rating: 2  # Okay
rating: 1  # Skip
```

Query for highly rated episodes later.

---

## Troubleshooting

### Wikilinks Not Working

Ensure wikilinks are enabled in Obsidian:

1. Settings → Files & Links
2. Enable "Use [[Wikilinks]]"

### Dataview Not Working

Install the Dataview plugin:

1. Settings → Community plugins
2. Browse → Search "Dataview"
3. Install and enable

### Tags Not Showing

Check your tag pane:

1. Click the tag icon in the left sidebar
2. Or use Cmd/Ctrl+Shift+T

---

## Next Steps

- [Configuration](configuration.md) - Obsidian-specific settings
- [Interview Mode](interview.md) - Create my-notes.md
