# Content Extraction

Configure templates, providers, and costs for AI-powered content extraction.

---

## How It Works

Inkwell uses AI to extract structured information from podcast transcripts:

```
Transcript → Template Selection → AI Extraction → Markdown Output
```

Each template defines what to extract (quotes, summary, concepts, etc.) and produces a separate markdown file.

---

## Available Templates

| Template | Description | Output |
|----------|-------------|--------|
| `summary` | Episode overview and key takeaways | `summary.md` |
| `quotes` | Notable quotes with speaker attribution | `quotes.md` |
| `key-concepts` | Main ideas and concepts discussed | `key-concepts.md` |
| `tools-mentioned` | Software, apps, products mentioned | `tools-mentioned.md` |
| `books-mentioned` | Books and resources referenced | `books-mentioned.md` |

---

## Template Selection

### Automatic (Default)

Templates are auto-selected based on episode category:

| Category | Templates |
|----------|-----------|
| `tech` | summary, quotes, tools-mentioned |
| `business` | summary, quotes, key-concepts |
| `interview` | summary, quotes |

### Manual Selection

Override with `--templates`:

```bash
# Specific templates
inkwell fetch URL --templates summary,quotes

# All templates
inkwell fetch URL --templates summary,quotes,key-concepts,tools-mentioned,books-mentioned
```

### Category Override

Force a category to change auto-selection:

```bash
inkwell fetch URL --category tech
```

---

## Providers

Inkwell supports two AI providers for extraction:

### Gemini (Default)

- **Cost:** ~$0.003 per template
- **Quality:** Good for most use cases
- **Speed:** Fast

### Claude

- **Cost:** ~$0.12 per template (40x more expensive)
- **Quality:** Best for precision tasks
- **Speed:** Moderate

### Smart Selection (Default)

Inkwell automatically chooses based on template:

- **Gemini:** summary, key-concepts, tools-mentioned
- **Claude:** quotes, books-mentioned (precision matters)

### Force Provider

```bash
# Use Gemini for everything (lowest cost)
inkwell fetch URL --provider gemini

# Use Claude for everything (highest quality)
inkwell fetch URL --provider claude
```

---

## Costs

### Cost Estimation

Check costs before processing:

```bash
inkwell fetch URL --dry-run
```

Output:
```
Estimated cost: $0.0090
  • summary (gemini): $0.0030
  • quotes (claude): $0.0045
  • key-concepts (gemini): $0.0015
```

### Typical Costs

| Episode Size | Templates | Provider | Cost |
|--------------|-----------|----------|------|
| 30 min (~5k words) | 3 | Gemini | ~$0.003 |
| 30 min (~5k words) | 3 | Claude | ~$0.045 |
| 120 min (~20k words) | 5 | Gemini | ~$0.012 |
| 120 min (~20k words) | 5 | Claude | ~$0.180 |

### Track Spending

```bash
inkwell costs
```

Output:
```
┌ Overall ─────────────────────┐
│ Total Operations:  15         │
│ Total Cost:        $0.0825    │
│                               │
│ By Provider:                  │
│   gemini    $0.0525           │
│   claude    $0.0300           │
│                               │
│ By Operation:                 │
│   extraction    $0.0825       │
└───────────────────────────────┘
```

---

## Caching

Extractions are cached to save time and money.

### How It Works

- Cache key = transcript hash + template version
- Default cache duration: 30 days
- Cache location: `~/.cache/inkwell/`

### Cache Behavior

| Scenario | Result |
|----------|--------|
| Same transcript, same template | Cache hit ($0) |
| Same transcript, different template | New extraction |
| Template version updated | Cache invalidated |

### Skip Cache

Force fresh extraction:

```bash
inkwell fetch URL --skip-cache
```

---

## Concurrency

Templates are extracted in parallel for faster processing:

- Default: 5 concurrent extractions
- ~5x speedup compared to sequential

---

## Template Versioning

Templates include version numbers:

```yaml
# templates/summary.yaml
name: summary
version: 2  # Incremented when prompt changes
expected_format: text
```

When a template is updated:

1. New version number invalidates cache
2. Next extraction uses updated prompt
3. Old cached results are ignored

---

## Cost Optimization Tips

1. **Use YouTube transcripts** - They're free
2. **Default to Gemini** - 40x cheaper than Claude
3. **Select fewer templates** - Only extract what you need
4. **Leverage caching** - Don't re-process unnecessarily
5. **Check with --dry-run** - Know costs before committing

---

## Next Steps

- [Interview Mode](interview.md) - Capture personal insights
- [Templates Reference](../reference/templates.md) - Template details
- [Configuration](configuration.md) - Cost limits and defaults
