# Phase 5 Unit 7: Cost Tracking System

**Date**: 2025-11-13
**Phase**: 5 - Obsidian Integration
**Unit**: 7 - Cost Tracking System
**Status**: ✅ Complete

## Objective

Implement comprehensive cost tracking for API usage with:
- Real-time cost tracking for all API operations
- Persistent storage of usage history
- CLI command to view and analyze costs
- Filtering by provider, operation, episode, and date

## Implementation Summary

Built complete cost tracking system:
- ✅ Cost tracking models (`APIUsage`, `CostSummary`)
- ✅ Persistent storage (`CostTracker` with JSON file)
- ✅ Pricing calculation utilities
- ✅ `inkwell costs` CLI command with rich formatting
- ✅ 25 unit tests (100% passing)

## Code Structure

### 1. Cost Tracking Module (`src/inkwell/utils/costs.py`, ~350 lines)

**Provider Pricing**:
```python
class ProviderPricing(BaseModel):
    provider: str
    model: str
    input_price_per_m: float  # Per million tokens
    output_price_per_m: float

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = (input_tokens / 1_000_000) * self.input_price_per_m
        output_cost = (output_tokens / 1_000_000) * self.output_price_per_m
        return input_cost + output_cost

# Current pricing (as of Nov 2024)
PROVIDER_PRICING = {
    "gemini-flash": ProviderPricing(..., input_price_per_m=0.075, output_price_per_m=0.30),
    "gemini-flash-long": ProviderPricing(..., input_price_per_m=0.15, output_price_per_m=0.30),
    "claude-sonnet": ProviderPricing(..., input_price_per_m=3.00, output_price_per_m=15.00),
}
```

**API Usage Model**:
```python
class APIUsage(BaseModel):
    provider: Literal["gemini", "claude", "youtube"]
    model: str
    operation: Literal["transcription", "extraction", "tag_generation", "interview"]

    input_tokens: int
    output_tokens: int
    total_tokens: int  # Auto-calculated

    cost_usd: float

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    episode_title: str | None
    template_name: str | None
```

**Cost Summary**:
```python
class CostSummary(BaseModel):
    total_operations: int
    total_tokens: int
    total_cost_usd: float

    costs_by_provider: dict[str, float]
    costs_by_operation: dict[str, float]
    costs_by_episode: dict[str, float]

    @classmethod
    def from_usage_list(cls, usage_list: list[APIUsage]) -> "CostSummary":
        # Aggregate usage from list
```

**Cost Tracker**:
```python
class CostTracker:
    """Track and persist API costs to disk."""

    def __init__(self, costs_file: Path | None = None):
        # Default: ~/.config/inkwell/costs.json
        self.usage_history: list[APIUsage] = []
        self._load()

    def track(self, usage: APIUsage) -> None:
        """Track new API usage and persist."""
        self.usage_history.append(usage)
        self._save()

    def get_summary(
        self,
        provider: str | None = None,
        operation: str | None = None,
        episode_title: str | None = None,
        since: datetime | None = None,
    ) -> CostSummary:
        """Get filtered cost summary."""

    def get_total_cost(self) -> float:
        """Get total cost across all usage."""

    def get_recent_usage(self, limit: int = 10) -> list[APIUsage]:
        """Get most recent operations."""

    def clear(self) -> None:
        """Clear all cost history."""
```

**Helper Functions**:
```python
def calculate_cost_from_usage(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate cost from token usage.

    Automatically handles:
    - Gemini tiered pricing (<128K vs >128K tokens)
    - Provider-specific pricing
    """
```

### 2. CLI Command (`src/inkwell/cli.py`, ~180 lines added)

**Command Signature**:
```python
@app.command("costs")
def costs_command(
    provider: str | None = Option(None, help="Filter by provider"),
    operation: str | None = Option(None, help="Filter by operation"),
    episode: str | None = Option(None, help="Filter by episode"),
    days: int | None = Option(None, help="Show last N days"),
    recent: int | None = Option(None, help="Show N recent operations"),
    clear: bool = Option(False, help="Clear history"),
):
    """View API cost tracking and usage statistics."""
```

**Display Modes**:

1. **Recent Operations** (`--recent 10`):
```
Recent 10 Operations:

Date         Provider  Operation      Episode                 Tokens   Cost
2025-11-13   gemini    extraction     Building Software       6,500    $0.0065
2025-11-13   gemini    tag_generati…  Building Software       2,000    $0.0020
...

Total: $0.0450
```

2. **Summary View** (default):
```
API Cost Summary

┌ Overall ─────────────────────┐
│ Total Operations:  15          │
│ Total Tokens:      125,000     │
│ Input Tokens:      100,000     │
│ Output Tokens:     25,000      │
│ Total Cost:        $0.1250     │
└──────────────────────────────┘

By Provider:
  gemini    $0.0850
  claude    $0.0400

By Operation:
  extraction        $0.0900
  tag_generation    $0.0200
  interview         $0.0150

By Episode (Top 10):
  Building Better Software    $0.0350
  Deep Work Strategies        $0.0300
  ...
```

3. **Filtered View** (`--provider gemini --days 7`):
```
API Cost Summary
(filtered by provider=gemini, days=7)

...
```

4. **Clear History** (`--clear`):
```
$ inkwell costs --clear
Are you sure you want to clear all cost history? [y/N]: y
✓ Cost history cleared
```

### 3. Test Suite (`tests/unit/utils/test_costs.py`, ~500 lines, 25 tests)

**Test Coverage**:
```
✅ TestProviderPricing (3 tests)
   - Gemini Flash pricing calculation
   - Claude pricing calculation
   - Zero tokens edge case

✅ TestAPIUsage (3 tests)
   - Usage record creation
   - Auto-calculated total_tokens
   - Auto-set timestamp

✅ TestCostSummary (3 tests)
   - Empty summary
   - Single usage aggregation
   - Multiple usage aggregation

✅ TestCostTracker (12 tests)
   - Tracker creation
   - Usage tracking
   - Persistence (save/load)
   - Total cost calculation
   - Summary generation (no filter)
   - Filtering (provider, operation, episode, since)
   - Recent usage retrieval
   - Clear history
   - Corrupt file handling

✅ TestCalculateCostFromUsage (4 tests)
   - Gemini short context (<128K tokens)
   - Gemini long context (>128K tokens)
   - Claude pricing
   - Unsupported provider error
```

**All tests passing** in 0.21 seconds.

## Implementation Journey

### Phase 1: Design (30 minutes)

**Key Design Decisions**:

1. **Storage Format**: JSON file in config directory
   - **Alternative**: SQLite database
   - **Why JSON**: Simpler, human-readable, sufficient for usage patterns
   - **Trade-off**: No SQL queries, but filtering in Python is fast enough

2. **Pricing Model**: Per-million-tokens with provider constants
   - **Challenge**: Gemini has tiered pricing (<128K vs >128K)
   - **Solution**: Detect context size and apply correct pricing

3. **CLI Interface**: Typer command with rich formatting
   - **Alternative**: JSON output for scripting
   - **Why rich tables**: Better UX for human consumption
   - **Future**: Add `--json` flag for programmatic use

4. **Cost Source**: Track actual usage, not estimates
   - **Note**: For Phase 5, we're setting up the infrastructure
   - **Next**: Update extractors to return actual token usage from API responses
   - **Current**: Framework ready, actual integration in Phase 6

### Phase 2: Models & Persistence (45 minutes)

**APIUsage Model Design**:
- Provider, model, operation for categorization
- Input/output/total tokens for analysis
- Cost in USD for reporting
- Timestamp for time-based filtering
- Episode/template for context

**CostTracker Design**:
```python
# File: ~/.config/inkwell/costs.json
[
  {
    "provider": "gemini",
    "model": "gemini-1.5-flash-latest",
    "operation": "extraction",
    "input_tokens": 5000,
    "output_tokens": 1000,
    "total_tokens": 6000,
    "cost_usd": 0.0065,
    "timestamp": "2025-11-13T10:30:00Z",
    "episode_title": "Building Better Software",
    "template_name": "summary"
  },
  ...
]
```

**Benefits**:
- Human-readable (can inspect manually)
- Version control friendly (can track in git if needed)
- Easy backup/restore (just copy file)
- Simple migration path (can convert to SQLite later)

### Phase 3: Cost Calculation (30 minutes)

**Challenge**: Gemini has tiered pricing

**Solution**:
```python
def calculate_cost_from_usage(provider, model, input_tokens, output_tokens):
    if provider == "gemini":
        if input_tokens >= 128_000:
            pricing_key = "gemini-flash-long"  # $0.15/M
        else:
            pricing_key = "gemini-flash"  # $0.075/M
    elif provider == "claude":
        pricing_key = "claude-sonnet"  # $3.00/M input, $15.00/M output

    pricing = PROVIDER_PRICING[pricing_key]
    return pricing.calculate_cost(input_tokens, output_tokens)
```

**Example Calculations**:
```
Gemini Flash (50K input, 2K output):
  Input:  (50,000 / 1M) * $0.075 = $0.00375
  Output: (2,000 / 1M) * $0.30 = $0.00060
  Total:  $0.00435

Claude Sonnet (10K input, 2K output):
  Input:  (10,000 / 1M) * $3.00 = $0.03000
  Output: (2,000 / 1M) * $15.00 = $0.03000
  Total:  $0.06000
```

### Phase 4: CLI Command (60 minutes)

**Display Requirements**:
1. Summary view: Overall stats + breakdowns
2. Recent view: Table of recent operations
3. Filtering: By provider, operation, episode, date
4. Clear: With confirmation prompt

**Rich Formatting**:
```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Overall stats in a panel
console.print(Panel(stats_table, title="Overall", border_style="blue"))

# Breakdowns in tables
provider_table = Table(show_header=False, box=None, padding=(0, 2))
provider_table.add_column("Provider", style="magenta")
provider_table.add_column("Cost", style="yellow", justify="right")
```

**User Experience**:
- Color-coded output (providers, operations, costs)
- Right-aligned numbers for easy scanning
- Compact layout (no unnecessary whitespace)
- Clear labels and units

### Phase 5: Testing (45 minutes)

**Testing Strategy**:
- Unit tests for all models and functions
- Use tmp_path fixture for file operations
- Test filtering logic thoroughly
- Test edge cases (empty data, corrupt files)

**Test Performance**: 25 tests in 0.21 seconds

## Integration Points

### Current State (Phase 5)
- ✅ Cost tracking infrastructure ready
- ✅ CLI command functional
- ✅ Persistent storage working
- ⏳ Actual API usage tracking (pending Phase 6)

### Future Integration (Phase 6+)

**Update Extractors**:
```python
# src/inkwell/extraction/extractors/gemini.py
async def extract(self, ...) -> tuple[str, APIUsage]:
    response = await self._generate_async(...)

    # Capture actual usage from response
    usage = APIUsage(
        provider="gemini",
        model=self.MODEL,
        operation="extraction",
        input_tokens=response.usage_metadata.prompt_token_count,
        output_tokens=response.usage_metadata.candidates_token_count,
        cost_usd=calculate_cost_from_usage(...),
        episode_title=metadata["episode_title"],
        template_name=template.name,
    )

    return response.text, usage
```

**Update Extraction Engine**:
```python
# Track costs as operations complete
tracker = CostTracker()

for template in templates:
    result, usage = await extractor.extract(template, transcript, metadata)
    tracker.track(usage)
```

## Key Decisions

### 1. JSON Storage vs SQLite
**Decision**: JSON file for v1.0
**Rationale**: Simpler, human-readable, sufficient performance
**Future**: Can migrate to SQLite if needed

### 2. Actual Usage vs Estimates
**Decision**: Track actual usage from API responses
**Rationale**: More accurate, better for billing transparency
**Implementation**: Phase 6 (extractors need to return usage)

### 3. CLI-First Interface
**Decision**: Rich terminal UI, no JSON export yet
**Rationale**: Focus on human UX for v1.0
**Future**: Add `--json` flag for scripting

### 4. Persistent History
**Decision**: Keep all history, provide `--clear` command
**Rationale**: Users may want to analyze trends over time
**Trade-off**: File size grows, but JSON compression is good

## Usage Examples

### View all costs
```bash
$ inkwell costs
```

### Filter by provider
```bash
$ inkwell costs --provider gemini
```

### Show costs from last week
```bash
$ inkwell costs --days 7
```

### Show recent operations
```bash
$ inkwell costs --recent 20
```

### Filter by episode
```bash
$ inkwell costs --episode "Building Better Software"
```

### Clear history
```bash
$ inkwell costs --clear
```

## Lessons Learned

See: [docs/lessons/2025-11-13-phase-5-unit-7-cost-tracking.md](../lessons/2025-11-13-phase-5-unit-7-cost-tracking.md)

## Next Steps

### Unit 8: E2E Testing
- Implement end-to-end test framework
- Test with 5 real podcast episodes
- Validate cost tracking in real scenarios
- Benchmark performance

### Future Enhancements

1. **Export to CSV**: For spreadsheet analysis
2. **Cost Alerts**: Notify when costs exceed threshold
3. **Budget Tracking**: Set monthly budgets per podcast
4. **Cost Forecasting**: Predict monthly costs based on usage
5. **Provider Comparison**: "How much would this cost with Claude?"

## References

- [Gemini Pricing](https://ai.google.dev/pricing)
- [Claude Pricing](https://www.anthropic.com/pricing)
- [EpisodeMetadata Model](../../src/inkwell/output/models.py)

## Time Log

- Design: 30 minutes
- Models & persistence: 45 minutes
- Cost calculation: 30 minutes
- CLI command: 60 minutes
- Testing: 45 minutes
- Documentation: 30 minutes
- **Total: ~3.5 hours**
