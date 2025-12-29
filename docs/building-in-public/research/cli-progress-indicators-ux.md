# CLI Progress Indicators: UX Best Practices Research

**Date:** 2025-12-21
**Status:** Complete
**Research Question:** What are the UX best practices for CLI progress indicators during long-running operations (1-10 minutes)?

## Executive Summary

This research explores UI/UX best practices for CLI progress indicators, focusing on operations that take 1-10 minutes. Key findings:

1. **Use progress bars (determinate) for operations >10 seconds**, spinners (indeterminate) for 2-10 seconds
2. **Avoid elapsed time displays** - they psychologically increase perceived wait time
3. **Show what's happening**, not just that something is happening
4. **Multiple progress bars** (like Docker) provide better UX than single indicators
5. **Real-time updates create perception of progress** but should be meaningful (per-file, per-step)

## 1. Information to Display During Long Operations (1-10 Minutes)

### Critical Information Elements

Based on analysis of modern CLI tools and UX research, users need:

1. **Current Activity Status**
   - What the system is doing right now (downloading, transcribing, processing)
   - Use present continuous tense during action ("-ing" form)
   - Switch to past tense when complete to avoid confusion

2. **Progress Indication**
   - Percentage complete (when determinable)
   - Items processed vs. total (e.g., "3/10 files")
   - Visual progress bar for operations >10 seconds

3. **Contextual Details**
   - Which specific item is being processed (filename, episode title)
   - Layer/stage information for multi-step processes (Docker's approach)
   - Size or scope information when relevant

4. **Time Estimation** (use cautiously)
   - Estimated time remaining (countdown) preferred over elapsed time
   - Base estimates on historical data from previous runs
   - Only show when reasonably predictable

### What NOT to Display

- **Elapsed time counting up** - research shows this "psychologically is a bit of torture for the user and it accentuates the passing of each and every second"
- **Technical debug output** (unless --verbose flag)
- **Overly detailed logs** that obscure progress
- **Static messages** that don't update (appears frozen)

**Source:** [Expressing Time in UI & UX Design](https://blog.prototypr.io/expressing-time-in-ui-ux-design-5-rules-and-a-few-other-things-eda5531a41a7)

## 2. How Should Time Be Displayed?

### Research Findings on Time Display

**Countdown vs. Count-up:**
- **Countdown timers** (time remaining) are preferred - they provide "a more specific indication"
- **Elapsed time** (count-up) should be avoided except when time dependency is critical (e.g., phone calls, cooking timers)
- Studies show "people overestimate how long they wait by about 36%"

**Update Frequency:**
- **Real-time updates** (sub-second) are appropriate for:
  - Downloading with byte/speed metrics
  - Active processing with item counts
  - Multiple simultaneous operations (Docker-style)

- **Milestone updates** (per-item, per-step) are better for:
  - File processing (update per file completion)
  - Multi-stage pipelines (transcribe → extract → interview)
  - Operations where progress is discrete, not continuous

### Implementation Recommendation for Inkwell

For operations taking 1-10 minutes:
1. **Show estimated time remaining** (countdown) based on average past runs
2. **Update per logical milestone** (e.g., per file processed, per stage completed)
3. **Avoid constantly updating elapsed time** - it increases anxiety
4. **Show progress percentage** when determinable

**Sources:**
- [Expressing Time in UI & UX Design](https://blog.prototypr.io/expressing-time-in-ui-ux-design-5-rules-and-a-few-other-things-eda5531a41a7)
- [NN/G Progress Indicators Research](https://www.nngroup.com/articles/progress-indicators/)

## 3. Psychological Effects of Progress Indicators

### Core Psychological Principles

**Perception of Time:**
- **Occupied time feels shorter than unoccupied time** - any indicator is better than none
- **Uncertain waits feel longer than known, finite waits** - deterministic progress bars reduce anxiety
- **Studies show people overestimate waiting by ~36%** without feedback

**User Control and Uncertainty:**
- "Percent-done indicators give users control (they can decide whether to wait or not)"
- "This information decreases uncertainty about the length of the process and may reduce the perceived wait time"
- Lack of feedback creates uncertainty, making "users assume the worst"

**Animation Speed Perception:**
- "Users observe constant speed as slowing down"
- **Best practice:** "Start the movement slowly in the beginning and speed up over time"
- This creates perception of faster overall completion

**Cognitive Load:**
- "Overly complex stimuli may overload limited mental resources, making waits seem even longer"
- Simple, clear progress indicators work better than busy animations
- Color affects perception: "color-changing interactive animation was perceived as faster and more likeable"

### Application to CLI Tools

For long-running CLI operations:
1. **Any indicator is better than silence** - prevents perception of freeze/crash
2. **Deterministic (progress bar) > Indeterminate (spinner)** for operations >10 seconds
3. **Simple, clear updates** better than complex animations
4. **Showing what's happening** reduces anxiety and perception of slowness

**Sources:**
- [Progress Bars vs. Spinners: When to Use Which](https://uxmovement.com/navigation/progress-bars-vs-spinners-when-to-use-which/)
- [NN/G Progress Indicators](https://www.nngroup.com/articles/progress-indicators/)
- [UX Psychology: Beyond the Wait](https://uxpsychology.substack.com/p/beyond-the-wait-enhancing-user-experience)
- [Research: Enhancing UX During Waiting Time](https://www.researchgate.net/publication/254462182_Enhancing_User_eXperience_during_waiting_time_in_HCI_Contributions_of_cognitive_psychology)

## 4. How Modern CLI Tools Handle Long Operations

### Docker (Best-in-Class Example)

**Approach:** Multiple simultaneous progress bars
```
Pulling repository ubuntu
e9e06b06e14c: Pull complete
a82efea989f9: Downloading  [=======>   ] 32.4 MB/97.5 MB
2dfe6376a932: Download complete
```

**Why it works:**
- Shows exactly what's happening at granular level
- Multiple layers visible simultaneously
- Users can see if one layer is stuck
- Provides sense of continuous progress

**Source:** [UX Patterns for CLI Tools](https://lucasfcosta.com/2022/06/01/ux-patterns-cli-tools.html)

### GitHub CLI (gh)

**Approach:** Status messages with spinners for indeterminate operations
- Shows current action (e.g., "Fetching pull requests...")
- Uses verb-noun subcommand pattern (e.g., `gh pr create`)
- Provides examples for common operations

**Source:** [Command Line Interface Guidelines](https://clig.dev/)

### kubectl (Kubernetes)

**Approach:** Real-time status updates for resource operations
- Shows state changes (Creating → Running → Ready)
- Provides structured output (can be piped/grepped)
- Offers `--watch` flag for continuous monitoring

### npm/yarn

**Approach:** Package-by-package progress with counts
```
[1/4] Resolving packages...
[2/4] Fetching packages...
[3/4] Linking dependencies...
[4/4] Building fresh packages...
```

**Why it works:**
- Clear stage progression
- Fraction shows completion progress
- Each stage has meaningful name
- Users know what to expect next

### Common Patterns Across Modern CLIs

1. **Multi-stage operations show stage names explicitly**
2. **Counts use fraction format** (3/10, [2/4])
3. **Status messages use present continuous** during action
4. **Structured output** can be parsed/piped (--plain flags)
5. **Examples provided** for complex operations

**Sources:**
- [CLI UX Best Practices (Evil Martians)](https://evilmartians.com/chronicles/cli-ux-best-practices-3-patterns-for-improving-progress-displays)
- [UX Patterns for CLI Tools](https://lucasfcosta.com/2022/06/01/ux-patterns-cli-tools.html)

## 5. Progress Bars vs. Spinners: UX Differences

### When to Use Each (Evidence-Based Guidelines)

**Spinners (Indeterminate):**
- **Duration:** 2-10 seconds
- **Use when:**
  - Duration is unknown/unpredictable
  - System is initiating a task (connecting to server)
  - Searching/querying with unknown result time
- **Drawback:** "Lack of feedback creates uncertainty, which makes users assume the worst"
- **For <1 second:** Don't use anything (distracting)
- **For >10 seconds:** Switch to progress bar to avoid user anxiety

**Progress Bars (Determinate):**
- **Duration:** >10 seconds (required for long operations)
- **Use when:**
  - Process duration is predictable
  - Based on historical data or item counts
  - Users need exact progress information
- **Benefits:**
  - "Sets a clear expectation of load time"
  - "Users are more willing to tolerate a long wait time if they see a progress bar"
  - Reduces uncertainty and perceived wait time

### Advanced Pattern: Adaptive Spinners

**CLI-specific innovation:**
- Program spinner to update only on completed actions (not time-based)
- Example: Tick each time a file finishes processing
- Benefits:
  - Shows ongoing activity
  - Signals if process is stuck (no ticks = potential issue)
  - More meaningful than time-based animation

**Source:** [CLI UX Best Practices (Evil Martians)](https://evilmartians.com/chronicles/cli-ux-best-practices-3-patterns-for-improving-progress-displays)

### Alternative: Skeleton Screens

Research finding: "Skeleton screens are perceived as faster and leave users happier" compared to spinners.

**Why they work:**
- Shift attention from wait time to expected outcome
- Show users what to expect visually
- Create sense of gradual progress
- "Make people perceive your site to be faster than it actually is"

**CLI application:**
- Less common in CLI but could be adapted
- Show placeholder structure of output while loading
- Example: Show markdown template structure while processing

**Sources:**
- [Progress Bars vs. Spinners](https://uxmovement.com/navigation/progress-bars-vs-spinners-when-to-use-which/)
- [Stop Using Loading Spinners](https://uxdesign.cc/stop-using-a-loading-spinner-theres-something-better-d186194f771e)
- [Loading Spinners: Purpose and Alternatives](https://blog.logrocket.com/ux-design/loading-spinners-purpose-alternatives/)

## Recommendations for Inkwell CLI

Based on this research, here are specific recommendations for Inkwell's 1-10 minute operations:

### 1. Use Multi-Stage Progress Display (Docker Model)

For the full pipeline (download → transcribe → extract → interview):
```
[1/4] Downloading audio... ━━━━━━━━━━━━━━━━━━━━ 100% 45.2 MB
[2/4] Transcribing audio... ━━━━━━━━━━━━━━━━━━━━ 67% ~2m remaining
[3/4] Extracting content... (pending)
[4/4] Interactive interview... (pending)
```

**Rationale:**
- Shows overall pipeline progress
- Current stage has progress bar
- Pending stages visible (sets expectations)
- Estimated time remaining (countdown, not elapsed)

### 2. Per-File Progress for Batch Operations

When processing multiple episodes:
```
Processing 3 episodes from The Changelog

Episode 1/3: Building CLI Tools (Dec 2024)
  ✓ Downloaded audio (45.2 MB)
  → Transcribing... ━━━━━━━━━━━━━━━ 45% ~3m

Episode 2/3: (pending)
Episode 3/3: (pending)
```

**Rationale:**
- Fraction format (1/3) shows clear progress
- Checkmarks for completed steps
- Current operation clearly marked
- Future items visible

### 3. Time Display Strategy

**DO:**
- Show estimated time remaining (e.g., "~3m remaining")
- Base on historical averages (per previous runs)
- Update per milestone (stage completion)
- Hide if estimate is unreliable

**DON'T:**
- Show elapsed time counting up (increases anxiety)
- Update time every second (distracting)
- Show time for operations <30 seconds

### 4. Status Message Patterns

**During operation:**
```
Transcribing audio with Gemini API...
```

**After completion:**
```
✓ Transcribed audio (3,847 words)
```

**Rationale:**
- Present continuous (-ing) during action
- Past tense when complete
- Include result metadata (word count)

### 5. Fallback/Error Visibility

When falling back to alternative method:
```
✗ YouTube transcript not available
→ Using Gemini API fallback...
```

**Rationale:**
- Clear indication of fallback
- User understands why it might take longer
- Transparency builds trust

## Implementation Libraries

### Python (Inkwell's Stack)

**Recommended:** `rich.progress` (already in stack)
- Multiple simultaneous progress bars ✓
- Customizable columns (percentage, speed, time remaining) ✓
- Clean API, well-maintained ✓
- Examples: `rich.progress.Progress`, `rich.progress.track()`

**Alternatives:**
- `tqdm` - popular, simpler API
- `click.progressbar` - if using Click CLI framework
- `yaspin` - for spinners

**Source:** [14 Tips to Make Amazing CLI Applications](https://dev.to/wesen/14-great-tips-to-make-amazing-cli-applications-3gp3)

## Key Takeaways

1. **For 1-10 minute operations, always use deterministic progress bars** (not spinners)
2. **Show time remaining (countdown), not elapsed time** (avoid psychological torture)
3. **Update per meaningful milestone** (file, stage) not per second
4. **Multi-stage pipelines need multi-level progress** (Docker model)
5. **Status messages matter** - use correct tense, show what's happening
6. **Any feedback is better than silence** - prevents perception of freeze

## References

- [CLI UX Best Practices: 3 Patterns for Progress Displays (Evil Martians)](https://evilmartians.com/chronicles/cli-ux-best-practices-3-patterns-for-improving-progress-displays)
- [Progress Bar Indicator UX/UI Design (Usersnap)](https://usersnap.com/blog/progress-indicators/)
- [UX Patterns for CLI Tools (Lucas Costa)](https://lucasfcosta.com/2022/06/01/ux-patterns-cli-tools.html)
- [Progress Bars vs. Spinners (UX Movement)](https://uxmovement.com/navigation/progress-bars-vs-spinners-when-to-use-which/)
- [Progress Indicators Research (NN/G)](https://www.nngroup.com/articles/progress-indicators/)
- [Stop Using Loading Spinners (UX Collective)](https://uxdesign.cc/stop-using-a-loading-spinner-theres-something-better-d186194f771e)
- [Expressing Time in UI & UX Design (Prototypr)](https://blog.prototypr.io/expressing-time-in-ui-ux-design-5-rules-and-a-few-other-things-eda5531a41a7)
- [Enhancing UX During Waiting Time (ResearchGate)](https://www.researchgate.net/publication/254462182_Enhancing_User_eXperience_during_waiting_time_in_HCI_Contributions_of_cognitive_psychology)
- [Beyond the Wait: UX Psychology (Substack)](https://uxpsychology.substack.com/p/beyond-the-wait-enhancing-user-experience)
- [Command Line Interface Guidelines](https://clig.dev/)
- [14 Tips to Make Amazing CLI Applications (DEV)](https://dev.to/wesen/14-great-tips-to-make-amazing-cli-applications-3gp3)
