# ADR-021: Interview State Persistence

**Status**: Accepted
**Date**: 2025-11-08
**Deciders**: Development Team
**Related**: Phase 4 Unit 1, ADR-020

## Context

Interview sessions may be interrupted (user closes terminal, network issue, system crash) or deliberately paused. Users should be able to resume interviews without losing progress. We need a persistence strategy for interview session state.

### Requirements

1. **Resume Capability** - Restore full conversation state after interruption
2. **Human Readable** - Users should be able to inspect saved sessions
3. **Version Control Friendly** - Text-based format for debugging
4. **Atomic Writes** - No corruption on crash mid-save
5. **Low Overhead** - Fast read/write operations
6. **Portable** - Works across platforms
7. **Debuggable** - Easy to inspect and validate state

### State to Persist

```python
class InterviewSession(BaseModel):
    session_id: str
    episode_url: str
    episode_title: str
    podcast_name: str

    # Timestamps
    started_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    # Configuration
    template_name: str
    max_questions: int

    # Conversation state
    exchanges: list[Exchange]  # Question + Response pairs
    current_question_number: int
    status: Literal["active", "paused", "completed", "abandoned"]

    # Context
    extracted_content_summary: dict

    # Metrics
    total_tokens_used: int
    total_cost_usd: float
```

**Size Estimate**:
- Small session (3 Q&A pairs): ~5KB
- Typical session (5 Q&A pairs): ~10KB
- Large session (10 Q&A pairs): ~20KB

## Decision

**Use JSON files for interview session persistence**, stored in the episode output directory with atomic write operations.

### Implementation

```python
from pathlib import Path
import json
import tempfile
from datetime import datetime

class SessionPersistence:
    """Manage interview session persistence"""

    def save_session(
        self,
        session: InterviewSession,
        output_dir: Path,
    ) -> Path:
        """Save session to JSON file with atomic write"""

        # Determine file path
        session_file = output_dir / ".interview_session.json"

        # Serialize session
        session_data = {
            "version": "1.0",  # Schema version
            "saved_at": datetime.utcnow().isoformat(),
            "session": session.model_dump(mode="json"),
        }

        # Atomic write pattern
        # Write to temp file, then rename (atomic on POSIX)
        with tempfile.NamedTemporaryFile(
            mode='w',
            dir=output_dir,
            delete=False,
            suffix='.tmp'
        ) as tmp:
            json.dump(session_data, tmp, indent=2)
            tmp_path = Path(tmp.name)

        # Atomic rename
        tmp_path.replace(session_file)

        return session_file

    def load_session(
        self,
        session_file: Path,
    ) -> Optional[InterviewSession]:
        """Load session from JSON file"""

        if not session_file.exists():
            return None

        try:
            data = json.loads(session_file.read_text())

            # Version check
            version = data.get("version", "1.0")
            if version != "1.0":
                logger.warning(f"Unknown session version: {version}")

            # Deserialize
            session = InterviewSession(**data["session"])
            return session

        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to load session: {e}")
            return None

    def find_resumable_sessions(
        self,
        output_dir: Path,
    ) -> list[Path]:
        """Find all resumable interview sessions"""

        sessions = []
        for episode_dir in output_dir.iterdir():
            if not episode_dir.is_dir():
                continue

            session_file = episode_dir / ".interview_session.json"
            if session_file.exists():
                # Check if still active/paused
                session = self.load_session(session_file)
                if session and session.status in ["active", "paused"]:
                    sessions.append(session_file)

        return sessions
```

**File Location**:
```
output_dir/
  └── podcast-2025-11-08-episode-title/
      ├── .interview_session.json   # ← Session state
      ├── .metadata.yaml
      ├── summary.md
      ├── quotes.md
      └── (my-notes.md when complete)
```

**Example JSON**:
```json
{
  "version": "1.0",
  "saved_at": "2025-11-08T15:30:45Z",
  "session": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "episode_url": "https://...",
    "episode_title": "The Future of AI",
    "podcast_name": "My Podcast",
    "started_at": "2025-11-08T15:00:00Z",
    "updated_at": "2025-11-08T15:30:45Z",
    "completed_at": null,
    "template_name": "reflective",
    "max_questions": 5,
    "status": "active",
    "current_question_number": 2,
    "exchanges": [
      {
        "question": {
          "id": "q1",
          "text": "What surprised you?",
          "question_number": 1,
          "depth_level": 0
        },
        "response": {
          "question_id": "q1",
          "text": "The discussion about alignment...",
          "word_count": 45,
          "responded_at": "2025-11-08T15:15:00Z"
        }
      }
    ],
    "extracted_content_summary": {...},
    "total_tokens_used": 1250,
    "total_cost_usd": 0.05
  }
}
```

## Alternatives Considered

### Alternative 1: SQLite Database

**Description**: Store all sessions in a SQLite database

**Pros**:
- Structured queries (find all sessions, filter by date, etc.)
- ACID guarantees
- Efficient for many sessions
- Can index and search

**Cons**:
- Binary format (not human-readable)
- Harder to inspect and debug
- Requires schema migrations
- File locking issues with concurrent access
- Overkill for simple key-value storage
- Less portable (binary format)

**Why Rejected**: Too complex for our needs. Interview sessions are isolated, rarely queried across episodes. JSON is simpler and meets all requirements.

### Alternative 2: Pickle (Python serialization)

**Description**: Use Python's pickle for direct object serialization

**Pros**:
- Native Python support
- Preserves object types exactly
- Fast serialization

**Cons**:
- Binary format (not human-readable)
- Security risk (code execution)
- Python-specific (not portable)
- Version brittleness
- Debugging nightmare
- Not version control friendly

**Why Rejected**: Security concerns and lack of human readability are deal-breakers. JSON is safer and more inspectable.

### Alternative 3: YAML

**Description**: Use YAML for session persistence

**Pros**:
- Human readable
- Supports comments
- Clean syntax
- Already used for config

**Cons**:
- Slower than JSON
- More complex parsing
- Type ambiguity (strings vs numbers)
- Larger file size
- Syntax edge cases

**Why Rejected**: JSON is faster, simpler, and has better Python support. YAML's advantages (comments, readability) don't matter for machine-generated session files.

### Alternative 4: In-Memory Only (No Persistence)

**Description**: Don't save sessions, require completing in one session

**Pros**:
- Simplest implementation
- No file I/O complexity
- No schema versioning

**Cons**:
- Lost work on interruption
- Can't pause and resume
- Bad user experience
- Terminal close = data loss

**Why Rejected**: Resume capability is a key requirement. Users will get interrupted, and losing interview progress is unacceptable.

### Alternative 5: Cloud Storage / Database

**Description**: Store sessions in cloud database (Supabase, Firebase, etc.)

**Pros**:
- Multi-device sync
- Automatic backups
- Query capabilities
- Collaborative features possible

**Cons**:
- Requires internet connection
- Privacy concerns (user data in cloud)
- Additional service dependency
- Authentication complexity
- Cost for hosting
- Massive scope increase

**Why Rejected**: Inkwell is designed to work offline and keep data local. Cloud storage contradicts our privacy-first approach.

## Decision Rationale

### Why JSON Files are Best

1. **Human Readable**
   - Users can inspect sessions
   - Easy debugging
   - Can manually fix corruption
   - Git-friendly for development

2. **Simple & Reliable**
   - Built-in Python json module
   - No external dependencies
   - Fast enough (< 10ms read/write)
   - Atomic writes prevent corruption

3. **Portable**
   - Works on all platforms
   - Text-based (no binary issues)
   - Can be edited by hand if needed
   - Easy to migrate or export

4. **Pydantic Integration**
   - Direct serialization with model_dump(mode="json")
   - Type validation on load
   - Schema evolution via Pydantic

5. **Isolation**
   - One file per session
   - No shared database state
   - No locking issues
   - Can delete/archive easily

6. **Debugging**
   - Can `cat` file to see state
   - Can edit in emergencies
   - Can commit to git for bug reports
   - Clear structure

### Atomic Write Pattern

**Critical**: Prevent corruption if interrupted mid-write

**Pattern**:
1. Write to temp file in same directory
2. Flush and fsync
3. Rename temp file to target (atomic operation)

**Guarantees**:
- Never partially written file
- Always valid JSON or old version
- No corruption on crash

### Schema Versioning

**Version field** enables future format changes:

```python
# Current version
{"version": "1.0", ...}

# Future version (example)
{"version": "2.0", ...}  # Maybe adds new fields

# Load with migration
def load_session(path):
    data = json.loads(path.read_text())

    if data["version"] == "1.0":
        return InterviewSession(**data["session"])
    elif data["version"] == "2.0":
        # Migrate or handle new format
        return migrate_v2_to_current(data)
```

## Consequences

### Positive

- ✅ **Simple implementation** - Standard library only
- ✅ **Human readable** - Easy inspection and debugging
- ✅ **Atomic writes** - No corruption on crash
- ✅ **Fast enough** - < 10ms for typical sessions
- ✅ **Portable** - Works everywhere
- ✅ **Git-friendly** - Can commit for testing
- ✅ **Debuggable** - Clear format
- ✅ **Isolated** - One file per session

### Negative

- ⚠️ **File system dependency** - Requires write access
  - *Mitigation*: Check permissions, fail gracefully
- ⚠️ **No queries** - Can't search across sessions
  - *Mitigation*: Scan directories if needed (rare)
- ⚠️ **Manual cleanup** - Old sessions accumulate
  - *Mitigation*: Auto-delete completed sessions or add cleanup command

### Trade-offs Accepted

- **Simplicity over Querying** - We don't need to search sessions
- **Files over Database** - Isolation and simplicity win
- **JSON over YAML** - Performance and simplicity over readability
- **Local over Cloud** - Privacy and offline-first

## Implementation Details

### Save Frequency

**Strategy**: Save after each exchange

```python
# After each question/response pair
exchange = Exchange(question=q, response=r)
session.exchanges.append(exchange)
session.updated_at = datetime.utcnow()

# Save to disk
persistence.save_session(session, output_dir)
```

**Reasoning**:
- Small files (< 20KB) = fast writes
- Guarantees at most one Q&A pair lost
- Simple logic (no batching complexity)

### Cleanup Policy

**Completed sessions**: Keep for 7 days, then delete

```python
def cleanup_old_sessions(output_dir: Path, days: int = 7):
    """Remove old completed sessions"""

    cutoff = datetime.utcnow() - timedelta(days=days)

    for session_file in find_all_sessions(output_dir):
        session = load_session(session_file)

        if session.status == "completed" and session.completed_at < cutoff:
            session_file.unlink()
```

**User override**: Config option to keep forever

```yaml
interview:
  keep_session_files: true  # Never auto-delete
```

### Resume UX

```bash
# User can resume by episode directory
$ inkwell interview resume podcast-2025-11-08-episode-title

# Or get list of resumable sessions
$ inkwell interview list-resumable

# Output:
# Resumable interviews:
# 1. My Podcast - Episode Title (2 of 5 questions, $0.05)
# 2. Other Podcast - Other Title (3 of 5 questions, $0.08)
```

## Testing Strategy

### Unit Tests

```python
def test_save_and_load_session(tmp_path):
    """Test session persistence"""

    session = InterviewSession(...)
    persistence = SessionPersistence()

    # Save
    path = persistence.save_session(session, tmp_path)
    assert path.exists()

    # Load
    loaded = persistence.load_session(path)
    assert loaded.session_id == session.session_id
    assert loaded.exchanges == session.exchanges

def test_atomic_write(tmp_path):
    """Test atomic write prevents corruption"""

    # Simulate crash mid-write
    with pytest.raises(SystemExit):
        with mock.patch('json.dump', side_effect=SystemExit):
            persistence.save_session(session, tmp_path)

    # Old file should still be valid or not exist
    session_file = tmp_path / ".interview_session.json"
    if session_file.exists():
        loaded = persistence.load_session(session_file)
        assert loaded is not None  # Can still load
```

### Integration Tests

- Test resume after interruption
- Test version migration (when needed)
- Test corrupted file handling
- Test permission errors

## Migration Path

If we ever need to change format:

1. Bump version number in new saves
2. Add migration code to load old versions
3. Gradual migration on load
4. Deprecate old versions after 6 months

```python
def migrate_v1_to_v2(old_data: dict) -> dict:
    """Migrate v1 session to v2 format"""
    new_data = old_data.copy()
    new_data["version"] = "2.0"
    # ... transform fields ...
    return new_data
```

## Monitoring & Review

### Success Criteria

- Resume works 100% of the time
- No reports of corrupted sessions
- Save/load < 10ms for typical sessions
- Users can inspect sessions if curious

### Review Trigger

Consider revisiting if:
- Users report frequent corruption
- Performance becomes issue (> 100ms save)
- Need to query across sessions becomes common
- Multi-device sync becomes requested feature

## References

- [JSON Specification](https://www.json.org/)
- [Pydantic JSON Serialization](https://docs.pydantic.dev/latest/concepts/serialization/)
- [Atomic File Writes Pattern](https://stackoverflow.com/questions/2333872/how-to-make-file-creation-an-atomic-operation)

## Related Decisions

- ADR-020: Interview Framework Selection
- ADR-022: Interview UI Framework
- ADR-023: Interview Template System

---

**Decision**: JSON file persistence with atomic writes
**Rationale**: Simple, reliable, human-readable, perfect for isolated session state
**Status**: ✅ Accepted
