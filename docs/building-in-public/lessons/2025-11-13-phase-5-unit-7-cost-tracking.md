# Lessons Learned: Phase 5 Unit 7 - Cost Tracking System

**Date**: 2025-11-13
**Context**: Building comprehensive cost tracking for API usage
**Related**: [Devlog](../devlog/2025-11-13-phase-5-unit-7-cost-tracking.md)

## Technical Insights

### 1. JSON is Often Good Enough

**The Temptation**: Use SQLite for "proper" data storage

**The Reality**: JSON file is simpler and sufficient
```python
# JSON file: ~/.config/inkwell/costs.json
[
  {"provider": "gemini", "cost_usd": 0.005, ...},
  ...
]
```

**Benefits**:
- ✅ Human-readable (can inspect/edit manually)
- ✅ No dependencies (stdlib only)
- ✅ Easy backup (just copy file)
- ✅ Version control friendly
- ✅ Simple migration path (can move to SQLite later)

**Performance**:
- 1,000 records: ~100KB, loads in <0.01s
- 10,000 records: ~1MB, loads in <0.1s
- Filtering in Python is fast for this scale

**Lesson**: Start simple. JSON is fine for most use cases. Only use databases when you actually need SQL queries or handle millions of records.

### 2. Pydantic Models Provide Free Validation

**Example**:
```python
class APIUsage(BaseModel):
    provider: Literal["gemini", "claude", "youtube"]  # Type-safe!
    input_tokens: int = Field(ge=0)  # Must be non-negative
    cost_usd: float = Field(ge=0)
```

**Benefits**:
- Invalid data is caught at creation time
- No need for manual validation code
- Self-documenting (field descriptions, constraints)
- JSON serialization built-in

**Example Validation**:
```python
# ❌ Fails validation
APIUsage(provider="openai", ...)  # ValueError: Invalid provider

# ❌ Fails validation
APIUsage(provider="gemini", input_tokens=-100, ...)  # ValueError: Must be >= 0

# ✅ Valid
APIUsage(provider="gemini", input_tokens=5000, cost_usd=0.005)
```

**Lesson**: Use Pydantic for all data models. The upfront investment in model definition pays off in runtime safety and reduced bugs.

### 3. Auto-Calculated Fields with model_post_init

**Problem**: `total_tokens` should be `input_tokens + output_tokens`, but easy to forget to calculate

**Solution**: Use `model_post_init` hook
```python
class APIUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int = 0  # Will be auto-calculated

    def model_post_init(self, __context: Any) -> None:
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens
```

**Benefits**:
- ✅ No manual calculation needed
- ✅ Consistent across all usage
- ✅ Tests don't need to set total_tokens

**Lesson**: Use `model_post_init` for derived fields. Reduces boilerplate and prevents bugs from forgetting to calculate.

### 4. Filtering is Better Than Multiple Query Methods

**Anti-pattern**:
```python
class CostTracker:
    def get_gemini_costs(self): ...
    def get_claude_costs(self): ...
    def get_extraction_costs(self): ...
    def get_tag_generation_costs(self): ...
    def get_costs_for_episode(self, title): ...
    # 20+ methods for different filters!
```

**Better Approach**:
```python
class CostTracker:
    def get_summary(
        self,
        provider: str | None = None,
        operation: str | None = None,
        episode_title: str | None = None,
        since: datetime | None = None,
    ) -> CostSummary:
        filtered = self.usage_history
        if provider:
            filtered = [u for u in filtered if u.provider == provider]
        if operation:
            filtered = [u for u in filtered if u.operation == operation]
        # ... more filters
        return CostSummary.from_usage_list(filtered)
```

**Benefits**:
- ✅ Single method handles all filter combinations
- ✅ Easy to add new filters (just add parameter)
- ✅ Composable (can combine multiple filters)

**Lesson**: Use optional parameters for filtering instead of creating separate methods for each filter combination.

### 5. Tiered Pricing Requires Context-Aware Calculation

**Challenge**: Gemini pricing changes based on context size
- <128K tokens: $0.075/M input
- ≥128K tokens: $0.15/M input

**Solution**: Check input token count
```python
def calculate_cost_from_usage(provider, model, input_tokens, output_tokens):
    if provider == "gemini":
        if input_tokens >= 128_000:
            pricing_key = "gemini-flash-long"
        else:
            pricing_key = "gemini-flash"
    # ...
```

**Mistake to Avoid**: Hardcoding single price per provider

**Lesson**: Always check provider documentation for tiered pricing. Model it explicitly in code rather than treating all requests the same.

### 6. Timestamps Enable Time-Based Analysis

**Why Timestamp Everything**:
```python
class APIUsage(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

**Enables**:
- "Show costs from last 7 days"
- "Monthly cost trends"
- "Cost per hour" analysis
- Debugging timing issues

**Cost**: Almost zero (datetime is small, <20 bytes)

**Lesson**: Always include timestamps in usage tracking. The overhead is negligible and enables powerful time-based filtering.

### 7. Rich Terminal UI Improves UX Dramatically

**Basic Output**:
```
Total: $0.1250
Gemini: $0.0850
Claude: $0.0400
```

**Rich Output**:
```
┌ Overall ─────────────────────┐
│ Total Cost:  $0.1250         │
└──────────────────────────────┘

By Provider:
  gemini    $0.0850
  claude    $0.0400
```

**Benefits**:
- Color-coded (easier to scan)
- Right-aligned numbers (easier to compare)
- Visual hierarchy (panels, tables)
- Professional appearance

**Investment**: ~10 minutes to add rich formatting

**Lesson**: Use rich terminal output for better UX. The effort is minimal and user experience improvement is significant.

### 8. Separate Display Logic from Business Logic

**Good Separation**:
```python
# Business logic (utils/costs.py)
class CostTracker:
    def get_summary(...) -> CostSummary:
        return summary  # Just data

# Display logic (cli.py)
def costs_command(...):
    summary = tracker.get_summary(...)

    # Format for display
    table = Table()
    table.add_row("Total:", f"${summary.total_cost_usd:.4f}")
    console.print(table)
```

**Benefits**:
- ✅ Business logic is reusable (can use in API, GUI, tests)
- ✅ Easy to test (test data, not display)
- ✅ Can add different UIs (JSON export, web dashboard, etc.)

**Lesson**: Keep data models and calculation logic separate from display formatting. This enables reuse across different interfaces.

### 9. Confirmation Prompts for Destructive Operations

**Example**:
```python
if clear:
    if typer.confirm("Are you sure you want to clear all cost history?"):
        tracker.clear()
        console.print("[green]✓[/green] Cost history cleared")
    else:
        console.print("Cancelled")
```

**Why Important**:
- Prevents accidental data loss
- Gives user chance to reconsider
- Professional UX (matches user expectations)

**Lesson**: Always add confirmation prompts for destructive operations (delete, clear, reset, etc.).

### 10. Handle Corrupt Files Gracefully

**Problem**: JSON file can get corrupted (power loss, manual edit, etc.)

**Solution**: Try-catch with graceful fallback
```python
def _load(self) -> None:
    try:
        with open(self.costs_file) as f:
            data = json.load(f)
            self.usage_history = [APIUsage.model_validate(item) for item in data]
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Warning: Could not load costs file: {e}")
        self.usage_history = []  # Start fresh
```

**Benefits**:
- ✅ Doesn't crash the entire application
- ✅ Warns user about the problem
- ✅ Allows user to continue working

**Lesson**: Always handle file corruption gracefully. Don't let a bad data file crash your application.

## Architecture Patterns

### 1. Layered Architecture

**Layers**:
1. **Models** (data structures): `APIUsage`, `CostSummary`, `ProviderPricing`
2. **Business Logic** (operations): `CostTracker`, `calculate_cost_from_usage`
3. **Persistence** (storage): `_load()`, `_save()`
4. **Interface** (CLI): `costs_command()`

**Benefits**:
- Each layer has clear responsibility
- Easy to test (can test each layer independently)
- Easy to swap implementations (e.g., JSON → SQLite)

**Lesson**: Separate concerns into layers. Don't mix data models, business logic, and UI code.

### 2. Builder Pattern for Complex Objects

**Example**:
```python
class CostSummary(BaseModel):
    @classmethod
    def from_usage_list(cls, usage_list: list[APIUsage]) -> "CostSummary":
        summary = cls()
        for usage in usage_list:
            summary.total_cost_usd += usage.cost_usd
            # ... aggregate more fields
        return summary
```

**Benefits**:
- Encapsulates complex construction logic
- Easy to test
- Single place to maintain aggregation logic

**Lesson**: Use classmethod builders for complex object construction from raw data.

### 3. Default Parameters for Flexible Filtering

**Pattern**:
```python
def get_summary(
    self,
    provider: str | None = None,  # Optional filter
    operation: str | None = None,  # Optional filter
    since: datetime | None = None,  # Optional filter
) -> CostSummary:
    # Apply filters only if provided
```

**Benefits**:
- Single method handles all use cases
- Backwards compatible (adding new filter doesn't break existing code)
- Self-documenting

**Lesson**: Use optional parameters with None defaults for flexible filtering. More maintainable than multiple specialized methods.

## Common Pitfalls

### 1. ❌ Forgetting to Persist After Mutations

**Mistake**:
```python
def track(self, usage: APIUsage):
    self.usage_history.append(usage)
    # Forgot to call self._save()!
```

**Impact**: Data lost on program exit

**Fix**: Always save after mutation
```python
def track(self, usage: APIUsage):
    self.usage_history.append(usage)
    self._save()  # ✅ Persist immediately
```

**Lesson**: In persistence layers, always save after state changes. Don't rely on explicit save() calls from users.

### 2. ❌ Hardcoding Pricing

**Mistake**:
```python
# Hardcoded pricing in calculation
def calculate_cost(tokens):
    return tokens / 1_000_000 * 0.075  # What provider? What if price changes?
```

**Fix**: Use pricing constants
```python
PROVIDER_PRICING = {
    "gemini-flash": ProviderPricing(input_price_per_m=0.075, ...),
}

def calculate_cost(provider, tokens):
    pricing = PROVIDER_PRICING[provider]
    return pricing.calculate_cost(tokens)
```

**Lesson**: Externalize pricing configuration. Makes updates easier when providers change prices.

### 3. ❌ Mixing Calculation and Formatting

**Mistake**:
```python
def get_total_cost(self) -> str:
    total = sum(u.cost_usd for u in self.usage_history)
    return f"${total:.4f}"  # ❌ Returns formatted string
```

**Problem**: Can't use result in calculations, only for display

**Fix**: Return number, format in UI layer
```python
def get_total_cost(self) -> float:
    return sum(u.cost_usd for u in self.usage_history)  # ✅ Returns number

# In UI layer:
total = tracker.get_total_cost()
console.print(f"${total:.4f}")  # Format here
```

**Lesson**: Business logic should return data types (numbers, objects), not formatted strings. Keep formatting in the UI layer.

### 4. ❌ No Validation on User Input

**Mistake**:
```python
APIUsage(
    provider="openai",  # ❌ Invalid provider, should fail
    input_tokens=-100,  # ❌ Negative tokens, should fail
)
```

**Fix**: Use Pydantic with Literal types and Field constraints
```python
class APIUsage(BaseModel):
    provider: Literal["gemini", "claude", "youtube"]  # ✅ Type-safe
    input_tokens: int = Field(ge=0)  # ✅ Must be non-negative
```

**Lesson**: Use Pydantic Literal types and Field constraints to validate input at creation time.

### 5. ❌ Not Testing Edge Cases

**Common Edge Cases**:
- Empty data (no usage history)
- Corrupt files
- Invalid filters (non-existent provider)
- Zero tokens/cost
- Extremely large numbers

**Lesson**: Always test edge cases. They're where bugs hide.

## Key Takeaways

1. **JSON is often sufficient** - Don't prematurely optimize to databases
2. **Pydantic provides free validation** - Use it for all data models
3. **Auto-calculate derived fields** - Reduces boilerplate and bugs
4. **Single flexible method > many specialized methods** - Use optional parameters for filtering
5. **Handle tiered pricing explicitly** - Don't assume flat rates
6. **Always include timestamps** - Enables powerful time-based analysis
7. **Rich terminal UI is worth it** - Minimal effort, big UX improvement
8. **Separate business logic from display** - Makes code reusable and testable
9. **Add confirmation for destructive ops** - Prevents accidental data loss
10. **Handle corrupt files gracefully** - Don't crash on bad data

## Impact

**User Experience**:
- Clear visibility into API costs
- Filter and analyze usage patterns
- Make informed decisions about provider choice

**Developer Experience**:
- Reusable cost tracking infrastructure
- Easy to extend (new providers, operations)
- Well-tested and reliable

**Business Value**:
- Cost transparency
- Budget tracking capability
- Foundation for cost optimization

## Future Improvements

1. **Export to CSV**: For spreadsheet analysis
2. **Cost Alerts**: Notify when costs exceed threshold
3. **Budget Tracking**: Set monthly budgets
4. **Cost Forecasting**: Predict costs based on usage trends
5. **Provider Comparison**: "How much would this cost with Claude?"

## References

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Rich Terminal UI](https://rich.readthedocs.io/)
- [Typer CLI Framework](https://typer.tiangolo.com/)
- [Gemini Pricing](https://ai.google.dev/pricing)
- [Claude Pricing](https://www.anthropic.com/pricing)
- [Devlog](../devlog/2025-11-13-phase-5-unit-7-cost-tracking.md)
