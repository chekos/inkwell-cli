# ADR-019: Output Directory Structure

**Date**: 2025-11-07
**Status**: Accepted
**Context**: Phase 3 Unit 7 - File Output Manager

---

## Context

Extracted content needs to be organized on disk in a way that is:
- Easy to navigate
- Compatible with note-taking apps (Obsidian, Notion)
- Supports multiple episodes and podcasts
- Allows for metadata and searchability
- Prevents naming conflicts

We need to decide:
1. Directory structure (flat vs hierarchical)
2. File naming conventions
3. Metadata storage format
4. Conflict resolution strategy

## Decision

**We will use episode-based directories with a standardized naming pattern.**

Structure:
```
output/
├── podcast-name-2025-11-07-episode-title/
│   ├── .metadata.yaml
│   ├── summary.md
│   ├── quotes.md
│   ├── key-concepts.md
│   └── tools-mentioned.md
├── another-podcast-2025-11-08-another-episode/
│   ├── .metadata.yaml
│   └── ...
```

**Directory naming pattern:**
```
{podcast-name}-{YYYY-MM-DD}-{episode-title}/
```

- All lowercase
- Spaces → hyphens
- Special characters removed
- Truncated to ~200 characters

## Rationale

### Why Episode-Based Directories?

**Alternatives considered:**
1. Flat structure (all files in one directory)
2. Podcast-based hierarchy (podcast/episode/)
3. Date-based hierarchy (YYYY/MM/DD/episode/)
4. Episode-based directories (chosen)

**Decision: Episode-based directories**

**Pros:**
- ✅ Each episode is self-contained unit
- ✅ Easy to move/share individual episodes
- ✅ Works well with Obsidian (one folder per note collection)
- ✅ No deep nesting
- ✅ Sortable by name (includes date)

**Cons:**
- ❌ All episodes in one directory (can get crowded)
- ❌ Podcast name repeated in each directory

**Verdict:** Best balance of organization and simplicity.

### Why Date in Directory Name?

**Rationale:**
- Episodes from same podcast need unique names
- Date provides natural ordering
- Helps identify when episode was published
- YYYY-MM-DD format sorts correctly

**Alternative:** Use episode number
- Problem: Not all podcasts have episode numbers
- Problem: Numbers aren't unique across podcasts

### Why Lowercase with Hyphens?

**Rationale:**
- Cross-platform compatibility (case-insensitive filesystems)
- URL-friendly (can serve as web slugs)
- No whitespace issues
- Easy to type

**Example transformations:**
```
"The Tim Ferriss Show" → "the-tim-ferriss-show"
"Episode #42: Testing & More!" → "episode-42-testing-more"
```

### Why `.metadata.yaml` File?

**Alternatives:**
1. No metadata file (metadata in frontmatter only)
2. JSON metadata
3. YAML metadata (chosen)
4. SQLite database

**Decision: Hidden YAML file**

**Pros:**
- ✅ Self-contained (metadata travels with episode)
- ✅ Human-readable
- ✅ Hidden (doesn't clutter file listings)
- ✅ Easy to parse
- ✅ Can reconstruct index from filesystem

**Cons:**
- ❌ Duplication (metadata also in frontmatter)
- ❌ Extra file per episode

**Verdict:** Benefits outweigh drawbacks.

**Metadata contents:**
```yaml
podcast_name: The Test Podcast
episode_title: Episode 42
episode_url: https://example.com/ep42
transcription_source: youtube
templates_applied:
  - summary
  - quotes
  - key-concepts
total_cost_usd: 0.015
```

### Why One File Per Template?

**Alternatives:**
1. Single markdown file with all content
2. One file per template (chosen)

**Decision: Separate files**

**Rationale:**
- ✅ Obsidian works better with atomic notes
- ✅ Can link to specific extraction types
- ✅ Easier to update individual templates
- ✅ Smaller, focused files

**Trade-off:** More files, but better UX.

## Implementation

### OutputManager Class

```python
class OutputManager:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def write_episode(
        self,
        episode_metadata: EpisodeMetadata,
        extraction_results: list[ExtractionResult],
        overwrite: bool = False
    ) -> EpisodeOutput:
        # 1. Create episode directory
        episode_dir = self._create_episode_directory(episode_metadata, overwrite)

        # 2. Write markdown files (one per template)
        for result in extraction_results:
            markdown = self.markdown_generator.generate(result, metadata)
            filename = f"{result.template_name}.md"
            self._write_file_atomic(episode_dir / filename, markdown)

        # 3. Write metadata file
        self._write_metadata(episode_dir / ".metadata.yaml", episode_metadata)

        return EpisodeOutput(directory=episode_dir, ...)
```

### Atomic File Writes

**Why atomic writes?**
- Prevent partial/corrupted files
- Safe for concurrent access
- Crash-safe

**Implementation:**
```python
def _write_file_atomic(self, file_path: Path, content: str):
    # Write to temp file
    temp_path = file_path.parent / f".tmp_{file_path.name}"
    temp_path.write_text(content)

    # Atomic move (same filesystem)
    temp_path.replace(file_path)
```

### Conflict Resolution

**Strategy: Fail by default, allow overwrite**

```python
if episode_dir.exists() and not overwrite:
    raise FileExistsError("Episode directory already exists")

if overwrite:
    shutil.rmtree(episode_dir)
    episode_dir.mkdir()
```

**Rationale:**
- Safe default (don't accidentally overwrite)
- Explicit opt-in for overwrites
- Clear error message

## Usage

### Writing Episode

```python
manager = OutputManager(output_dir=Path("./output"))

output = manager.write_episode(
    episode_metadata=metadata,
    extraction_results=results,
    overwrite=False
)

print(f"Wrote to: {output.directory}")
# Output: ./output/test-podcast-2025-11-07-episode-42/
```

### Listing Episodes

```python
episodes = manager.list_episodes()

for episode_dir in episodes:
    metadata = manager.load_episode_metadata(episode_dir)
    print(f"{metadata.podcast_name}: {metadata.episode_title}")
```

### Statistics

```python
stats = manager.get_statistics()

print(f"Episodes: {stats['total_episodes']}")
print(f"Files: {stats['total_files']}")
print(f"Size: {stats['total_size_mb']} MB")
```

## Examples

### Example 1: Single Episode

```
output/
└── deep-questions-2025-11-07-on-focus/
    ├── .metadata.yaml
    ├── summary.md
    ├── quotes.md
    └── key-concepts.md
```

### Example 2: Multiple Episodes

```
output/
├── lex-fridman-2025-11-01-sam-altman-interview/
│   ├── .metadata.yaml
│   ├── summary.md
│   ├── quotes.md
│   └── tools-mentioned.md
├── lex-fridman-2025-11-05-john-carmack-interview/
│   ├── .metadata.yaml
│   ├── summary.md
│   └── quotes.md
└── the-changelog-2025-11-07-python-in-2024/
    ├── .metadata.yaml
    ├── summary.md
    └── tools-mentioned.md
```

### Example 3: Directory Name Transformation

```
Input:
  Podcast: "The Tim Ferriss Show"
  Date: 2025-11-07
  Episode: "Episode #42: Testing & More!"

Output:
  the-tim-ferriss-show-2025-11-07-episode-42-testing-more/
```

## Design Decisions

### Decision 1: Episode Directory vs Single File

**Decision:** Separate directory per episode

**Rationale:**
- Self-contained unit
- Easy to move/backup
- Multiple files per episode

### Decision 2: Date Format in Directory

**Decision:** YYYY-MM-DD format

**Rationale:**
- Sorts correctly
- ISO 8601 standard
- Unambiguous

### Decision 3: Hidden Metadata File

**Decision:** Use `.metadata.yaml` (hidden)

**Rationale:**
- Doesn't clutter file listings
- Unix convention (dotfiles are hidden)
- Clear purpose

### Decision 4: Overwrite Strategy

**Decision:** Fail by default, require explicit --overwrite

**Rationale:**
- Safe default
- Prevents accidents
- User aware of data loss

### Decision 5: No Index File

**Decision:** No central index.json

**Rationale:**
- Can reconstruct from filesystem
- No single point of failure
- Simpler implementation

**Future:** Could add index for performance.

## Consequences

### Positive

✅ Self-contained episodes (easy to move/backup)
✅ Sortable by date
✅ Cross-platform compatible
✅ Obsidian-friendly
✅ No database required
✅ Easy to understand

### Negative

❌ All episodes in one directory (can get crowded)
❌ Long directory names
❌ Metadata duplication (directory + .metadata.yaml + frontmatter)

### Neutral

- One file per template (design choice)
- Hidden metadata file (convention)

## Future Enhancements

### 1. Podcast Subdirectories

For users with many podcasts:

```
output/
├── the-tim-ferriss-show/
│   ├── 2025-11-01-episode-1/
│   └── 2025-11-05-episode-2/
└── lex-fridman-podcast/
    └── 2025-11-03-sam-altman/
```

**Trade-off:** More complex structure.

### 2. Search Index

Build search index for fast queries:

```python
manager.build_index()  # Create index.json

results = manager.search("productivity")
```

### 3. Archive Old Episodes

Move old episodes to archive:

```python
manager.archive_episodes(older_than_days=365)
```

### 4. Export Formats

Export episode in other formats:

```python
manager.export_html(episode_dir)
manager.export_pdf(episode_dir)
```

### 5. Sync Support

Detect changes for syncing:

```python
changed_episodes = manager.get_changed_since(last_sync_time)
```

## Testing Strategy

**Unit tests:**
- Directory creation
- File writing (atomic)
- Metadata generation
- Conflict handling
- Statistics
- Edge cases (unicode, long names)

**Integration tests:**
- Write multiple episodes
- Load and verify
- Overwrite scenarios

## Related

- [ADR-018: Markdown Output Format](./018-markdown-output-format.md) - Markdown structure
- [Unit 7 Devlog](../devlog/2025-11-07-phase-3-unit-7-file-output.md) - Implementation details
- [Unit 2: Output Models](../devlog/2025-11-07-phase-3-unit-2-data-models.md) - EpisodeMetadata, OutputFile

---

## Revision History

- 2025-11-07: Initial ADR (Phase 3 Unit 7)
