# Interview Mode

Capture your personal insights with AI-guided Q&A after processing an episode.

---

## Overview

Interview mode conducts a thoughtful conversation after extraction, generating questions based on episode content. Your responses are saved as `my-notes.md`, creating a personal knowledge base.

**Key features:**

- Context-aware questions based on episode content
- Multiple interview styles (reflective, analytical, creative)
- Pause and resume capability
- Pattern-based insight extraction
- Three output formats

---

## Basic Usage

Add the `--interview` flag to any `fetch` command:

```bash
inkwell fetch https://youtube.com/watch?v=xyz --interview
```

**Output:**

```
Step 5/5: Conducting interview...
✓ Interview complete
  Questions: 5
  Saved to: my-notes.md

Episode:         Episode from URL
Templates:       3
Extraction cost: $0.0090
Interview cost:  $0.1500
Total cost:      $0.1590
Interview:       ✓ Completed
```

---

## Requirements

Interview mode requires an Anthropic API key:

```bash
export ANTHROPIC_API_KEY="your-key-here"

# Or add to ~/.bashrc or ~/.zshrc
echo 'export ANTHROPIC_API_KEY=your-key' >> ~/.bashrc
```

Get a key at [console.anthropic.com](https://console.anthropic.com/)

---

## Interview Templates

Choose from three interview styles:

### Reflective (Default)

Focus on personal insights, connections, and applications.

```bash
inkwell fetch URL --interview
```

**Example questions:**

- "How does this idea connect to your own experience?"
- "What surprised you most in this episode?"
- "How might you apply this to your work?"

### Analytical

Deep critical thinking and evaluation.

```bash
inkwell fetch URL --interview --interview-template analytical
```

**Example questions:**

- "What assumptions underlie the main argument?"
- "What evidence supports or contradicts this view?"
- "What are the limitations of this approach?"

### Creative

Imaginative connections and new possibilities.

```bash
inkwell fetch URL --interview --interview-template creative
```

**Example questions:**

- "How could you combine this with other ideas?"
- "What would happen if you took this to an extreme?"
- "What analogies help explain this concept?"

---

## Command Options

| Option | Description | Default |
|--------|-------------|---------|
| `--interview` | Enable interview mode | `false` |
| `--interview-template` | Template: reflective, analytical, creative | From config |
| `--interview-format` | Format: structured, narrative, qa | From config |
| `--max-questions` | Number of questions | From config |
| `--no-resume` | Don't resume previous session | `false` |

---

## Interview Commands

During an interview, use these commands:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/skip` | Skip current question |
| `/done` | End interview early (save progress) |
| `/quit` | Exit interview without saving |
| `/history` | View conversation so far |

---

## Output Formats

### Structured (Default)

Organized by themes with extracted insights:

```markdown
# My Notes & Reflections

## Key Insights
- Insight 1 extracted from responses
- Insight 2 extracted from responses

## Action Items
- [ ] Action item 1
- [ ] Action item 2

## Themes
- Theme 1 (mentioned 3 times)
- Theme 2 (mentioned 2 times)

## Question 1: ...
My response...
```

### Narrative

Flowing text combining questions and responses:

```markdown
# My Notes & Reflections

When asked about X, I realized that...

This connects to Y because...

The most surprising aspect was...
```

### Q&A

Simple question-and-answer format:

```markdown
# My Notes & Reflections

**Q: Question 1**
A: My response...

**Q: Question 2**
A: My response...
```

---

## Session Management

### Pause and Resume

Press `Ctrl+C` during an interview to pause:

```
Interview paused. Resume with:
  inkwell interview resume <session-id>

Or abandon with:
  inkwell interview abandon <session-id>
```

Resume later:

```bash
inkwell interview resume abc123
```

### List Sessions

View all saved sessions:

```bash
inkwell interview sessions
```

### Cleanup

Remove old completed sessions:

```bash
inkwell interview cleanup --older-than 90d
```

---

## Configuration

Customize defaults in `~/.config/inkwell/config.yaml`:

```yaml
interview:
  enabled: true
  auto_start: false              # Set to true to always interview

  # Style preferences
  default_template: reflective   # reflective, analytical, creative
  question_count: 5              # Target number of questions
  format_style: structured       # structured, narrative, qa

  # Personal guidelines
  guidelines: |
    Focus on how this applies to my work as a software engineer.
    Ask about connections to previous episodes.
    Probe for actionable insights and blog post topics.

  # Cost control
  max_cost_per_interview: 0.50
  confirm_high_cost: true

  # Advanced
  model: claude-sonnet-4-5
  session_timeout_minutes: 60
```

---

## Cost Estimation

Interview mode uses Claude:

| Component | Cost |
|-----------|------|
| Extraction | ~$0.02 per episode |
| Interview (5 questions) | ~$0.15 per episode |
| **Total with interview** | **~$0.17 per episode** |

**Cost control:**

- Shorter interviews: `--max-questions 3` (~$0.09)
- Config limit: Set `max_cost_per_interview`
- Cache hit: $0 (cached extractions are free)

---

## Tips

### Custom Guidelines

Tailor questions to your interests:

```yaml
guidelines: |
  - Focus on practical applications for my startup
  - Ask about potential blog post angles
  - Probe connections to behavioral psychology
  - Challenge my assumptions when I'm too optimistic
```

### Interview Frequency

You don't need to interview every episode:

- **Do interview:** Complex topics, controversial ideas, personal relevance
- **Skip interview:** News updates, routine episodes, time-constrained

### Multi-Episode Patterns

Interview several related episodes together:

```bash
inkwell fetch URL1 --interview --max-questions 3
inkwell fetch URL2 --interview --max-questions 3
inkwell fetch URL3 --interview --max-questions 3
```

---

## Troubleshooting

### "ANTHROPIC_API_KEY not set"

```bash
export ANTHROPIC_API_KEY=your-key-here
```

### Interview Cost Too High

Use fewer questions:

```bash
inkwell fetch URL --interview --max-questions 3
```

Or set a config limit:

```yaml
interview:
  max_cost_per_interview: 0.20
```

### Questions Not Relevant

Add custom guidelines in config (see above).

---

## Next Steps

- [Obsidian Integration](obsidian.md) - Use interview notes in Obsidian
- [Configuration](configuration.md) - Interview settings
