# ADR-012: Gemini API Cost Management

**Date**: 2025-11-07
**Status**: Accepted
**Context**: Phase 2 - Transcription Layer
**Related**: [ADR-009: Transcription Strategy](./009-transcription-strategy.md), [ADR-010: Caching](./010-transcript-caching.md)

---

## Context

Gemini transcription costs ~$0.01 per minute (~$0.60/hour of audio). While this is reasonable for occasional use, costs can accumulate:
- Processing 100 one-hour episodes: **$60**
- Accidentally processing wrong episode: **wasted $0.60**
- Re-processing without cache: **doubled costs**

Users need visibility and control over API costs to avoid bill shock.

---

## Decision

Implement **transparent cost management** with the following measures:

### 1. Pre-Transcription Cost Estimates
Show estimated cost before starting Gemini transcription:
```
⚠️  Transcription Cost Estimate
Duration: 67.5 minutes
Estimated cost: $0.68

Continue with Gemini transcription? [y/N]:
```

### 2. Cost Confirmation Thresholds
- **< $0.50**: Auto-approve (no prompt)
- **$0.50 - $1.00**: Show estimate, ask for confirmation
- **> $1.00**: **Require explicit confirmation**

### 3. Cost Tracking
Track cumulative costs per session and display at end:
```
✓ Transcription complete!
Cost this session: $2.40
Total episodes processed: 4
```

### 4. Cost Display
Always show cost in transcription results:
```bash
$ inkwell transcribe "https://episode.url"

✓ Transcription complete!
Source: gemini
Duration: 67.5 minutes
Cost: $0.68
```

### 5. Cache Awareness
Clearly indicate when cache saves money:
```bash
$ inkwell transcribe "https://episode.url"

✓ Using cached transcript (source: gemini)
Original cost: $0.68 | This request: $0.00
```

---

## Alternatives Considered

### Alternative 1: No Cost Management (Let Users Track Manually)

**Approach**: Users monitor their Google Cloud billing

**Pros**:
- Simplest implementation
- No code needed

**Cons**:
- Bill shock risk
- Poor user experience
- Users can't predict costs
- Easy to accidentally overspend

**Verdict**: ❌ Rejected - Unacceptable UX

---

### Alternative 2: Hard Budget Limits

**Approach**: Set monthly budget, refuse to transcribe when exceeded

**Pros**:
- Prevents overspending
- Clear cost control

**Cons**:
- Requires persistent state (budget tracking)
- Breaks user workflow arbitrarily
- One tool can't manage multiple API key users
- Too restrictive

**Verdict**: ❌ Rejected - Too rigid, consider for v0.4+

---

### Alternative 3: Require Confirmation for Every Transcription

**Approach**: Always prompt, regardless of cost

**Pros**:
- Maximum user awareness
- No surprise costs

**Cons**:
- Annoying for small costs
- Interrupts workflow
- Reduces automation potential

**Verdict**: ❌ Rejected - Threshold-based approach better

---

### Alternative 4: Post-Transcription Cost Reporting Only

**Approach**: Show cost after transcription completes

**Pros**:
- Simple implementation
- No workflow interruption

**Cons**:
- Too late (cost already incurred)
- No chance to cancel
- Bill shock still possible

**Verdict**: ❌ Rejected - Must show cost *before* spending

---

## Rationale

### Why Threshold-Based Confirmation?

**Small costs (< $0.50)**: Auto-approve
- Typical 30-45 minute podcast
- User knows they're transcribing
- Prompt would be annoying

**Medium costs ($0.50-$1.00)**: Show and confirm
- 50-100 minute episode
- User should be aware
- One-click confirmation (not burdensome)

**Large costs (> $1.00)**: Require explicit confirmation
- 100+ minute episode or multiple episodes
- Significant API spend
- User must actively confirm

### Why $1.00 Threshold?

**Balance point**:
- Small enough: Catches most "expensive" episodes
- Large enough: Doesn't prompt on every episode

**100-minute episode** = $1.00
- Long but not unusual for podcasts
- Clear psychological boundary
- Round number (easy to remember)

**User can override**:
- `--force`: Skip confirmation for automation
- `--no-confirm`: Disable all prompts (future feature)

---

## Consequences

### Positive

1. **Prevents Bill Shock**
   - Users see cost before spending
   - Clear warning for expensive operations
   - Can cancel before charge

2. **Cost Awareness**
   - Session cost tracking visible
   - Cache savings highlighted
   - Users understand value of caching

3. **Trust Building**
   - Transparent pricing
   - No hidden costs
   - Users feel in control

4. **Workflow Friendly**
   - Small costs don't interrupt
   - Only prompts when significant
   - Can be overridden for automation

### Negative

1. **Implementation Complexity**
   - Need audio duration before transcription
   - Cost calculation logic
   - Session state management

2. **Workflow Interruption**
   - Confirmation prompts break automation
   - But: necessary trade-off for cost control

3. **Estimation Inaccuracy**
   - Actual cost may differ slightly
   - But: close enough for decision-making

---

## Implementation Details

### Cost Calculation

```python
class GeminiTranscriber:
    COST_PER_MINUTE = 0.01  # $0.01/min

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate transcription cost in USD."""
        minutes = duration_seconds / 60
        return minutes * self.COST_PER_MINUTE

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration using ffprobe."""
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
             str(audio_path)],
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())
```

### Confirmation Prompt

```python
from rich.console import Console
from rich.prompt import Confirm

def confirm_transcription_cost(
    duration_seconds: float,
    cost: float,
    threshold: float = 1.0
) -> bool:
    """Prompt user to confirm expensive transcription."""

    if cost < threshold:
        return True  # Auto-approve small costs

    console = Console()
    console.print(f"\n[yellow]⚠️  Transcription Cost Warning[/yellow]")
    console.print(f"Duration: {duration_seconds / 60:.1f} minutes")
    console.print(f"Estimated cost: ${cost:.2f}\n")

    return Confirm.ask(
        "Continue with Gemini transcription?",
        default=False,
    )
```

### Session Cost Tracking

```python
class TranscriptionManager:
    def __init__(self):
        self.session_cost = 0.0
        self.episodes_processed = 0

    async def transcribe(self, url: str) -> TranscriptionResult:
        # ... transcription logic ...

        if result.cost_usd > 0:
            self.session_cost += result.cost_usd
            self.episodes_processed += 1

        return result

    def get_session_summary(self) -> str:
        return f"Cost this session: ${self.session_cost:.2f} ({self.episodes_processed} episodes)"
```

### Cost Display in CLI

```python
@app.command()
def transcribe(url: str, force: bool = False):
    result = asyncio.run(manager.transcribe(url))

    if result.success:
        console.print(f"\n[green]✓[/green] Transcription complete!")
        console.print(f"Source: {result.transcript.source}")

        if result.cost_usd > 0:
            if result.from_cache:
                console.print(f"Original cost: ${result.cost_usd:.2f} | This request: $0.00")
            else:
                console.print(f"Cost: ${result.cost_usd:.2f}")
```

---

## Validation

### User Scenarios

#### Scenario 1: Small Podcast (30 min)
```
$ inkwell transcribe URL

[No prompt - auto-approved]

✓ Transcription complete!
Cost: $0.30
```

#### Scenario 2: Medium Podcast (75 min)
```
$ inkwell transcribe URL

⚠️  Transcription Cost Warning
Duration: 75.0 minutes
Estimated cost: $0.75

Continue with Gemini transcription? [y/N]: y

✓ Transcription complete!
Cost: $0.75
```

#### Scenario 3: Long Podcast (120 min)
```
$ inkwell transcribe URL

⚠️  Transcription Cost Warning
Duration: 120.0 minutes
Estimated cost: $1.20

Continue with Gemini transcription? [y/N]: n

❌ Transcription cancelled by user
```

#### Scenario 4: Cached Episode
```
$ inkwell transcribe URL

✓ Using cached transcript (source: gemini)
Original cost: $0.60 | This request: $0.00
```

### Cost Estimation Accuracy

**Expected accuracy**: ±10%
- Gemini billing rounds to nearest minute
- Network overhead negligible
- Good enough for user decision

---

## Future Enhancements

### Phase 3+

1. **Budget Tracking** (v0.3+)
   - Set monthly budget: `inkwell config set monthly_budget 20.00`
   - Warn when approaching limit
   - Refuse when exceeded (with override)

2. **Cost Analytics** (v0.4+)
   - Cost per podcast feed
   - Cost trends over time
   - Most expensive episodes

3. **Configurable Thresholds** (v0.4+)
   - User sets their own threshold
   - Per-feed overrides (e.g., "always confirm for expensive podcasts")

4. **Batch Processing Estimates** (v0.5+)
   - Show total cost for batch operations
   - One confirmation for multiple episodes

---

## References

- [Google Gemini API Pricing](https://ai.google.dev/pricing)
- [ADR-009: Transcription Strategy](./009-transcription-strategy.md)
- [ADR-010: Transcript Caching](./010-transcript-caching.md)
- [Phase 2 Implementation Plan](../devlog/2025-11-07-phase-2-detailed-plan.md)

---

## Approval

**Status**: ✅ Accepted

**Date**: 2025-11-07

**Reviewers**: Claude (Phase 2 architect)

**Next steps**:
1. Implement cost calculation in GeminiTranscriber (Unit 5)
2. Add confirmation prompt to TranscriptionManager (Unit 7)
3. Implement session cost tracking (Unit 7)
4. Add cost display to CLI (Unit 8)
5. Test with various episode lengths (Unit 9)

---

## Notes

**User Experience Philosophy**:
*Cost transparency builds trust. Users should never be surprised by API charges. Show costs early, often, and clearly.*
