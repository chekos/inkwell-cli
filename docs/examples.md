# Inkwell Examples & Workflows

Common use cases and workflows for Inkwell.

## Table of Contents

1. [Daily Podcast Processing](#daily-podcast-processing)
2. [Learning & Research](#learning--research)
3. [Building a Knowledge Base](#building-a-knowledge-base)
4. [Cost Optimization](#cost-optimization)
5. [Batch Operations](#batch-operations)
6. [Custom Workflows](#custom-workflows)

## Daily Podcast Processing

### Morning Routine: Process Overnight Releases

```bash
#!/bin/bash
# save as: ~/bin/process-podcasts.sh

# Process latest episodes from your regular podcasts
uv run inkwell fetch syntax --latest
uv run inkwell fetch huberman --latest
uv run inkwell fetch tim-ferriss --latest

# Show cost summary
uv run inkwell costs --days 1
```

Make it executable:
```bash
chmod +x ~/bin/process-podcasts.sh
```

Run daily:
```bash
crontab -e
# Add: 0 9 * * * ~/bin/process-podcasts.sh
```

### Selective Processing with Interview

```bash
# Only do interview for high-value episodes
uv run inkwell fetch tim-ferriss --latest  # Quick processing
# Review the summary first
cat output/tim-ferriss-*/summary.md

# If interesting, do full interview
uv run inkwell fetch tim-ferriss --latest --interview --overwrite
```

## Learning & Research

### Learning Path: Master a Topic

**Goal**: Learn about AI and Machine Learning

```bash
# 1. Add relevant podcasts
uv run inkwell add "https://lexfridman.com/feed/podcast/" --name lex-fridman
uv run inkwell add "https://twimlai.com/feed/" --name twiml

# 2. Process recent AI-focused episodes
uv run inkwell fetch lex-fridman --count 10
uv run inkwell fetch twiml --count 5

# 3. In Obsidian, create AI dashboard
```

**Obsidian Dashboard** (`AI-Learning.md`):
```markdown
# AI Learning Path

## Recent Episodes
```dataview
TABLE episode, podcast, rating
FROM "podcasts"
WHERE contains(topics, "ai") OR contains(topics, "machine-learning")
SORT episode_date DESC
LIMIT 20
```

## Key Concepts to Study
```dataview
LIST FROM [[AI]] OR [[Machine Learning]] OR [[Neural Networks]]
WHERE file.name != "AI Learning Path"
```

## People to Follow
```dataview
LIST
FROM "podcasts"
WHERE contains(people, "Andrew Ng") OR contains(people, "Yann LeCun")
```
```

### Research Project: Compile Expert Insights

**Goal**: Research "Future of Remote Work"

```bash
# 1. Process relevant episodes
uv run inkwell fetch all-in --count 20  # Tech business discussions
uv run inkwell fetch tim-ferriss --count 10  # Productivity insights

# 2. Extract relevant notes
grep -r "remote work" output/*/summary.md
grep -r "distributed teams" output/*/key-concepts.md

# 3. Create research note in Obsidian
```

**Research Note** (`Future-of-Remote-Work.md`):
```markdown
# Future of Remote Work - Research

## Sources
- [[All-In Podcast - Remote Work Discussion]]
- [[Tim Ferriss - Digital Nomad Lifestyle]]
- [[Huberman Lab - Productivity Science]]

## Key Insights

### Productivity
From [[All-In Episode 123]]:
> "Async communication is the future. Zoom fatigue is real."

### Tools
Mentioned across episodes:
- [[Notion]] - Knowledge management
- [[Slack]] - Team communication
- [[Loom]] - Async video

### Challenges
- Timezone coordination
- Company culture
- Work-life boundaries
```

## Building a Knowledge Base

### Personal Wiki: Connect Everything

```bash
# Process your podcast library
uv run inkwell fetch --all

# Let wikilinks build connections automatically
```

**Obsidian Graph View** will show:
- **Books** mentioned across episodes
- **People** referenced multiple times
- **Concepts** that appear frequently
- **Tools** recommended by different hosts

### Topic Clustering

**Dataview Query** (`Topic-Clusters.md`):
```markdown
# Topic Clusters

## Most Referenced Books
```dataview
TABLE count(rows) as "Mentions", list(episode) as "Episodes"
FROM "podcasts"
FLATTEN books as book
GROUP BY book
SORT count(rows) DESC
LIMIT 10
```

## Most Discussed People
```dataview
TABLE count(rows) as "Mentions"
FROM "podcasts"
FLATTEN people as person
GROUP BY person
SORT count(rows) DESC
LIMIT 10
```

## Tool Recommendations
```dataview
TABLE count(rows) as "Mentions", list(podcast) as "Recommended By"
FROM "podcasts"
FLATTEN tools as tool
GROUP BY tool
SORT count(rows) DESC
```
```

### Book Reading List

```markdown
# Books to Read (From Podcasts)

## High Priority (Mentioned 3+ times)
```dataview
TABLE count(rows) as mentions, list(episode) as "Mentioned In"
FROM "podcasts"
FLATTEN books as book
WHERE book != null
GROUP BY book
HAVING count(rows) >= 3
SORT count(rows) DESC
```

## By Topic: Productivity
```dataview
LIST
FROM "podcasts"
FLATTEN books as book
WHERE contains(topics, "productivity") AND book != null
```
```

## Cost Optimization

### Strategy 1: Prioritize Free Transcripts

```bash
# Check if YouTube transcript available before processing
# Inkwell does this automatically, but you can check manually:

# Process episode (uses YouTube if available)
uv run inkwell fetch syntax --latest

# Check cost breakdown
uv run inkwell costs --recent 1
# If transcription cost is $0.00, it used YouTube (free!)
```

### Strategy 2: Batch Processing

```bash
# Process multiple episodes at once (shares setup overhead)
uv run inkwell fetch syntax --count 10

# More efficient than:
# for i in {1..10}; do inkwell fetch syntax --episode $i; done
```

### Strategy 3: Selective Templates

Edit config to only extract what you need:

```yaml
# ~/.config/inkwell/config.yaml
templates_enabled:
  - summary      # Always useful
  - quotes       # Great for reviews
  # - key-concepts  # Skip if not needed
  # - tools-mentioned  # Skip to save $0.002
```

### Strategy 4: Use Gemini (Not Claude)

```yaml
default_provider: "gemini"  # 5x cheaper than Claude
```

**Cost Comparison**:
- Gemini: $0.005-0.025 per episode
- Claude: $0.025-0.125 per episode

Use Claude only for premium content where quality matters most.

### Strategy 5: Set Budget Limits

```yaml
max_cost_per_episode: 0.20
monthly_budget: 10.00
```

```bash
# Monitor monthly spending
uv run inkwell costs --days 30

# Get breakdown
uv run inkwell costs --provider gemini --days 30
uv run inkwell costs --provider claude --days 30
```

## Batch Operations

### Weekly Catch-Up

```bash
#!/bin/bash
# weekly-podcasts.sh

# Get list of podcasts
PODCASTS=("syntax" "huberman" "tim-ferriss" "all-in" "lex-fridman")

# Process last week's episodes
for podcast in "${PODCASTS[@]}"; do
  echo "Processing $podcast..."
  uv run inkwell fetch "$podcast" --count 3
done

# Generate report
echo "\n=== Weekly Summary ==="
uv run inkwell costs --days 7
```

### Archive Entire Podcast

```bash
# Process all episodes from a podcast
# Note: This can be expensive for large podcasts!

# Estimate cost first
uv run inkwell list syntax
# Shows: 250 episodes

# Cost estimate: 250 episodes × $0.01 avg = $2.50

# Process in batches
for i in {1..250..10}; do
  uv run inkwell fetch syntax --episode $i
  sleep 2  # Rate limiting
done
```

### Export for Sharing

```bash
#!/bin/bash
# export-favorites.sh

# Export your favorite episodes as standalone markdown
EPISODES=(
  "tim-ferriss-2025-11-01-naval"
  "huberman-2025-10-15-sleep"
  "syntax-2025-09-20-react"
)

mkdir -p exports

for episode in "${EPISODES[@]}"; do
  cp -r "output/$episode" "exports/"
done

# Create index
cat > exports/INDEX.md << EOF
# My Favorite Podcast Episodes

$(for episode in "${EPISODES[@]}"; do
  echo "- [$episode](./$episode/summary.md)"
done)
EOF

echo "Exports ready in ./exports"
```

## Custom Workflows

### Workflow 1: Interview-First Approach

```bash
# Process with interview immediately (capture fresh thoughts)
uv run inkwell fetch podcast-name --latest --interview

# Result: More personal insights in my-notes.md
```

### Workflow 2: Review-Then-Interview

```bash
# 1. Quick processing
uv run inkwell fetch podcast-name --latest

# 2. Review summary
cat output/podcast-name-*/summary.md

# 3. If valuable, do interview
uv run inkwell fetch podcast-name --latest --interview --overwrite
```

### Workflow 3: Spaced Repetition

```bash
# Day 1: Process episode
uv run inkwell fetch podcast-name --latest

# Day 3: Review and add thoughts
# In Obsidian, add your own notes to the episode

# Day 7: Interview yourself about key concepts
uv run inkwell fetch podcast-name --latest --interview --overwrite
```

### Workflow 4: Team Knowledge Sharing

```bash
# 1. Process episode
uv run inkwell fetch podcast-name --latest

# 2. Add team-specific insights
# Edit output/*/summary.md and add:
# ## Team Applications
# - How we can apply this to Project X
# - Relevant for Q4 goals

# 3. Commit to shared repo
git add output/
git commit -m "Add: Podcast notes on [topic]"
git push
```

### Workflow 5: Content Creation

Use podcast notes as research for blog posts:

```bash
# 1. Process related episodes
uv run inkwell fetch podcast-1 --latest
uv run inkwell fetch podcast-2 --latest
uv run inkwell fetch podcast-3 --latest

# 2. In Obsidian, create outline
# - Combine insights from multiple episodes
# - Add your commentary
# - Link to original notes

# 3. Export to blog post
```

## Pro Tips

### Tip 1: Use Aliases for Common Operations

```bash
# Add to ~/.bashrc or ~/.zshrc
alias ink='uv run inkwell'
alias ink-fetch='uv run inkwell fetch'
alias ink-costs='uv run inkwell costs'

# Usage:
ink-fetch syntax --latest
ink-costs --days 7
```

### Tip 2: Quick Episode Review

```bash
# View summary without opening full file
tail -n +20 output/podcast-name-*/summary.md | head -n 30
```

### Tip 3: Find Episodes by Topic

```bash
# Search across all summaries
grep -r "machine learning" output/*/summary.md

# Search key concepts
grep -r "neural networks" output/*/key-concepts.md
```

### Tip 4: Cost Tracking

```bash
# Set up cost alerting
if [ $(uv run inkwell costs --days 30 | grep "Total" | awk '{print $NF}' | tr -d '$') -gt 10 ]; then
  echo "Warning: Monthly cost exceeded $10"
fi
```

### Tip 5: Obsidian Templates

Create template for new podcast notes:

```markdown
---
template: podcast-review
status: inbox
rating:
---

# {{title}}

## My Thoughts

## Action Items

## Related Notes
```

## Community Examples

### Example 1: Developer's Setup

```yaml
# Optimized for technical podcasts
templates_enabled:
  - summary
  - key-concepts
  - tools-mentioned
  - code-snippets  # Custom template

podcasts:
  - syntax (daily updates)
  - changelog (weekly)
  - shop-talk-show (weekly)
```

### Example 2: Business Professional's Setup

```yaml
# Optimized for business/strategy content
templates_enabled:
  - summary
  - quotes
  - actionable-advice  # Custom template
  - frameworks  # Custom template

podcasts:
  - all-in (weekly)
  - tim-ferriss (weekly)
  - a16z (weekly)
```

### Example 3: Researcher's Setup

```yaml
# Optimized for research and citations
templates_enabled:
  - summary
  - quotes
  - key-concepts
  - studies-mentioned  # Custom template
  - citations  # Custom template

podcasts:
  - huberman-lab (weekly)
  - lex-fridman (bi-weekly)
  - twiml (weekly)
```

## Conclusion

These examples show the flexibility of Inkwell for:
- Personal knowledge management
- Research and learning
- Team collaboration
- Content creation
- Cost-effective processing

**Start Simple**:
1. Pick 2-3 favorite podcasts
2. Process latest episodes
3. Explore in Obsidian
4. Add complexity as needed

**Remember**:
- Quality > Quantity (process what you'll actually read)
- Use interview mode for high-value episodes
- Monitor costs regularly
- Build connections through wikilinks

## More Resources

- [User Guide](./user-guide.md) - Complete reference
- [Tutorial](./tutorial.md) - Step-by-step walkthrough
- [Dataview Queries](../dataview-queries.md) - 27 example queries
- [Custom Templates](./custom-templates.md) - Create your own

Happy note-taking! 🎧📝
