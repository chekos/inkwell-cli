# Lessons Learned: Phase 2 Unit 5 - Gemini Transcription

**Date:** 2025-11-07
**Unit:** Phase 2, Unit 5
**Component:** Gemini API integration for audio transcription
**Duration:** ~2 hours
**Lines of Code:** ~376 implementation, ~475 tests (1.3:1 ratio)

---

## Summary

Implemented Gemini-based audio transcription with cost estimation, confirmation workflows, and optional timestamp parsing. This unit completes Tier 2 of the multi-tier transcription strategy (YouTube → Gemini fallback) established in Unit 1.

---

## Key Lessons Learned

### 1. Timestamp Parsing Requires Careful Pattern Analysis

**What Happened:**
Initial timestamp parsing logic had a bug: checking `if secs > 0` to determine format type.

**The Bug:**
```python
secs = int(match.group(3)) if match.group(3) else 0

# BUG: [00:01:00] has secs=0, so this check fails
if secs > 0:  # HH:MM:SS format
    current_time = hours_or_mins * 3600 + mins_or_secs * 60 + secs
else:  # MM:SS format
    current_time = hours_or_mins * 60 + mins_or_secs
```

**The Fix:**
```python
secs = int(match.group(3)) if match.group(3) is not None else None

# CORRECT: Check if group exists, not if value > 0
if secs is not None:  # HH:MM:SS format
    current_time = hours_or_mins * 3600 + mins_or_secs * 60 + secs
else:  # MM:SS format
    current_time = hours_or_mins * 60 + mins_or_secs
```

**Impact:**
This distinction (existence vs. value) is critical for parsing. Always check `is not None` when testing for presence of optional regex groups.

---

### 2. Cost Confirmation Needs User-Friendly Formatting

**What Happened:**
Cost estimates need to be displayed to users in a clear, readable format.

**The Pattern:**
```python
class CostEstimate(BaseModel):
    file_size_mb: float
    estimated_cost_usd: float

    @property
    def formatted_cost(self) -> str:
        """Format cost for display."""
        if self.estimated_cost_usd < 0.01:
            return f"${self.estimated_cost_usd:.4f}"  # $0.0001
        return f"${self.estimated_cost_usd:.2f}"      # $0.12
```

**Why This Matters:**
- Small costs (<$0.01) need 4 decimal places to be meaningful
- Larger costs use standard 2 decimal places
- Consistent formatting improves UX

**Lesson:**
When displaying costs, consider the magnitude. Sub-cent costs need more precision than dollar amounts.

---

### 3. Fallback Logic Should Be Graceful

**What Happened:**
Gemini's response format is unpredictable - sometimes it includes timestamps, sometimes it doesn't.

**The Solution:**
```python
def _parse_response(self, response, audio_path, episode_url):
    # Try to parse timestamps
    segments = self._parse_timestamps(response.text)

    # Fall back to single segment if parsing fails
    if not segments:
        segments = [
            TranscriptSegment(
                text=response.text.strip(),
                start=0.0,
                duration=0.0,
            )
        ]

    return Transcript(segments=segments, ...)
```

**Benefits:**
- Never fails due to format changes
- Always provides valid Transcript
- Users get best available data
- System degrades gracefully

**Pattern:**
Try enhanced parsing → fall back to basic parsing → always return valid data

---

### 4. Cost Thresholds Need Flexible Confirmation

**What Happened:**
Different users have different cost tolerance. Some want to approve every transcription, others only care about expensive ones.

**The Solution:**
```python
async def _confirm_cost(self, estimate: CostEstimate) -> bool:
    # Auto-approve if below threshold
    if estimate.estimated_cost_usd < self.cost_threshold_usd:
        return True

    # If callback provided, use it
    if self.cost_confirmation_callback:
        return await self.cost_confirmation_callback(estimate)

    # Default: auto-approve
    return True
```

**Configuration Options:**
```python
# Auto-approve everything under $1.00 (default)
transcriber = GeminiTranscriber(cost_threshold_usd=1.0)

# Confirm every transcription
transcriber = GeminiTranscriber(
    cost_threshold_usd=0.0,  # Force callback for any cost
    cost_confirmation_callback=lambda est: confirm_with_user(est)
)

# Auto-approve everything (no confirmation)
transcriber = GeminiTranscriber(cost_threshold_usd=float('inf'))
```

**Lesson:**
Provide sensible defaults with flexibility for power users.

---

### 5. Regex Patterns Need Comprehensive Testing

**What Happened:**
Timestamp patterns can appear in many formats: `[00:00:00]`, `[0:00]`, `[1:30]`, etc.

**The Pattern:**
```python
# Pattern: [HH:MM:SS] or [H:MM:SS] or [MM:SS] or [M:SS]
timestamp_pattern = r"\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]"
```

**Test Coverage:**
```python
# Test HH:MM:SS format
"[00:00:00] Text"  → start=0.0
"[00:01:30] Text"  → start=90.0
"[00:03:00] Text"  → start=180.0

# Test MM:SS format
"[0:00] Text"      → start=0.0
"[1:30] Text"      → start=90.0
"[3:15] Text"      → start=195.0

# Test fallback
"No timestamps"    → Single segment
```

**Lesson:**
When working with regex, test ALL expected formats plus edge cases (no matches, partial matches, etc.).

---

### 6. API Keys Need Flexible Configuration

**What Happened:**
Different deployment environments need different ways to provide credentials.

**The Pattern:**
```python
def __init__(self, api_key: str | None = None, ...):
    # Try parameter first, then environment variable
    self.api_key = api_key or os.getenv("GOOGLE_AI_API_KEY")

    if not self.api_key:
        raise ValueError(
            "Google AI API key required. "
            "Provide via api_key parameter or GOOGLE_AI_API_KEY environment variable."
        )
```

**Benefits:**
- Development: Pass key directly in code/tests
- Production: Use environment variables (12-factor app)
- Clear error message guides users

**Lesson:**
Support both explicit parameters and environment variables for credentials.

---

## Patterns to Repeat

### 1. Cost Estimation Before API Calls
```python
# Estimate before calling API
estimate = self._estimate_cost(audio_path)

# Confirm with user if needed
if not await self._confirm_cost(estimate):
    raise Error("Cancelled by user")

# Proceed with API call
result = await self._call_api(...)

# Attach actual cost to result
result.cost_usd = estimate.estimated_cost_usd
```

### 2. Graceful Fallback Parsing
```python
# Try enhanced parsing
result = self._parse_advanced(data)

# Fall back to basic parsing
if not result:
    result = self._parse_basic(data)

# Always return valid data
return result
```

### 3. Optional Regex Groups
```python
match = re.match(r"(\d+)(?::(\d+))?", text)
if match:
    required = int(match.group(1))
    optional = int(match.group(2)) if match.group(2) is not None else None

    # Check existence, not value
    if optional is not None:
        # Process with optional field
    else:
        # Process without optional field
```

---

## Anti-Patterns to Avoid

### 1. **Don't Check Numeric Values When You Mean to Check Existence**

❌ Wrong:
```python
secs = int(match.group(3)) if match.group(3) else 0
if secs > 0:  # BUG: 0 is a valid value!
    ...
```

✅ Right:
```python
secs = int(match.group(3)) if match.group(3) is not None else None
if secs is not None:  # Check presence
    ...
```

---

### 2. **Don't Hardcode Cost Formatting**

❌ Wrong:
```python
print(f"Cost: ${cost:.2f}")  # $0.00 for sub-cent costs
```

✅ Right:
```python
@property
def formatted_cost(self) -> str:
    if self.estimated_cost_usd < 0.01:
        return f"${self.estimated_cost_usd:.4f}"
    return f"${self.estimated_cost_usd:.2f}"
```

---

### 3. **Don't Require API Keys in Code**

❌ Wrong:
```python
def __init__(self, api_key: str):  # Forces key in code
    self.api_key = api_key
```

✅ Right:
```python
def __init__(self, api_key: str | None = None):
    self.api_key = api_key or os.getenv("GOOGLE_AI_API_KEY")
    if not self.api_key:
        raise ValueError("API key required...")
```

---

## Technical Insights

### Google Generative AI SDK Architecture

**Discovered:**
- SDK uses synchronous calls (no native async support)
- `genai.upload_file()` handles large files automatically
- `GenerateContentResponse.text` contains transcript
- No built-in timestamp extraction

**File Upload Behavior:**
```python
# Small files (<10MB): Direct upload
audio_file = genai.upload_file(path="audio.m4a")

# Large files (>10MB): Resumable upload (automatic)
# SDK handles this transparently
```

**Cost Structure (Approximate):**
- Audio transcription: ~$0.000125 per MB
- 10MB file ≈ $0.00125
- 1GB file ≈ $0.125
- Costs may vary - always check latest pricing

---

### Timestamp Parsing Edge Cases

**Formats Supported:**
- `[00:00:00]` - HH:MM:SS with leading zeros
- `[0:00:00]` - H:MM:SS single digit hour
- `[00:00]` - MM:SS with leading zeros
- `[0:00]` - M:SS single digit minute

**Speaker Prefix Removal:**
```python
text_after_timestamp = re.sub(
    r"^[Ss]peaker\s*\d*\s*:?\s*",  # Matches "Speaker:", "speaker 1:", etc.
    "",
    text_after_timestamp
)
```

**Duration Calculation:**
```python
# Calculate from consecutive timestamps
for i in range(len(segments) - 1):
    segments[i].duration = segments[i + 1].start - segments[i].start

# Last segment has duration=0.0 (unknown end time)
```

---

### Testing Philosophy Reinforced

**Test-to-Code Ratio:** 1.3:1 (475 test lines / 376 implementation lines)

**Coverage:**
- 26 tests across 3 test classes
- CostEstimate: 4 tests (validation, formatting)
- GeminiTranscriber: 18 tests (initialization, transcription, errors)
- GeminiTranscriberWithSegments: 4 tests (timestamp parsing)

**Mocking Strategy:**
All Google AI SDK calls mocked:
```python
@pytest.fixture
def mock_genai():
    with patch("inkwell.transcription.gemini.genai") as mock:
        mock.configure = MagicMock()
        mock_model = MagicMock()
        mock.GenerativeModel.return_value = mock_model

        mock_file = MagicMock()
        mock.upload_file.return_value = mock_file

        mock_response = MagicMock()
        mock_response.text = "Test transcript"
        mock_model.generate_content.return_value = mock_response

        yield mock
```

---

## Impact on Future Units

### Unit 6: Transcript Caching
- Cache keys should include source ("gemini" vs "youtube")
- Cost data should be preserved in cache
- Timestamp-parsed transcripts are more valuable to cache

### Unit 7: Transcription Orchestrator
- Cost estimation can guide tier selection
- Fallback from YouTube → Gemini based on cost threshold
- Progress tracking can aggregate cost estimates

### Unit 8: CLI Integration
- Cost confirmation callback will prompt user in CLI
- Progress display can show cost accumulation
- Error messages ready for terminal display

---

## Statistics

- **Implementation:** 376 lines of code
- **Tests:** 475 lines of code
- **Test-to-code ratio:** 1.3:1
- **Tests:** 26 total (4 CostEstimate, 18 GeminiTranscriber, 4 WithSegments)
- **Test execution time:** ~3 seconds
- **Pass rate:** 100%
- **Linter:** All checks passed
- **Dependencies added:** google-generativeai>=0.8.5 (+19 transitive)

---

## References

- [ADR-009: Transcription Strategy](/docs/adr/009-transcription-strategy.md) - Multi-tier approach
- [ADR-012: Gemini Cost Management](/docs/adr/012-gemini-cost-management.md) - Cost threshold decision
- [Research: Transcription APIs Comparison](/docs/research/transcription-apis-comparison.md) - Gemini selection rationale
- [Unit 1: Research & Architecture](/docs/devlog/2025-11-07-phase-2-unit-1-research.md) - Foundation
- [Unit 4: Audio Downloader](/docs/devlog/2025-11-07-phase-2-unit-4-audio-downloader.md) - Integration point
