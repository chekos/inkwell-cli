# Knowledge Graph Engine

**Category:** New Feature | Architecture
**Quarter:** Q2
**T-shirt Size:** XL

## Why This Matters

Inkwell currently extracts entities (people, books, tools, concepts) and creates wikilinks, but these connections are local to each episode. There's no persistent understanding of how entities relate across your entire knowledge base. When the same guest appears on three different podcasts, when an author's book is mentioned in multiple episodes, when a concept connects to another—these relationships are invisible.

A knowledge graph engine transforms isolated notes into an interconnected knowledge network. It enables queries like "What has Naval Ravikant said about reading?" across all content, shows you unexpected connections ("5 episodes mentioned stoicism and productivity"), and builds a living map of ideas that grows with every episode you process.

This is the difference between having notes and having knowledge. It's what makes Inkwell a true "second brain" rather than just a transcription tool.

## Current State

**Existing capabilities:**
- Entity extraction in LLM templates (people, books, tools, concepts)
- Wikilink generation: `[[Person Name]]`, `[[Book Title]]`
- Tag generation with hierarchical structure
- Dataview-compatible frontmatter

**What's missing:**
- No persistent entity store—extracted entities aren't tracked across episodes
- No relationship detection—connections between entities aren't captured
- No deduplication—"Naval" vs "Naval Ravikant" vs "@naval" are three entities
- No cross-episode queries—can't search for concepts across your archive
- No graph visualization—relationships aren't visible
- No entity enrichment—no metadata about extracted entities

**Related ADR:**
- `docs/building-in-public/adr/026-obsidian-integration-architecture.md`

## Proposed Future State

A rich knowledge graph that:

1. **Persistently tracks entities:**
   - Unified entity store in `~/.local/share/inkwell/graph.db` (SQLite with vector extensions)
   - Entity types: Person, Book, Tool, Concept, Topic, Company, Quote
   - Metadata enrichment (bio, links, first/last mention, mention count)

2. **Detects and stores relationships:**
   - Person → mentioned_book → Book
   - Episode → discusses → Concept
   - Person → worked_at → Company
   - Concept → related_to → Concept

3. **Resolves entity variations:**
   - "Naval" = "Naval Ravikant" = "@naval"
   - LLM-powered coreference resolution
   - User-confirmable merge suggestions

4. **Enables powerful queries:**
   - `inkwell graph search "stoicism"` → all mentions across episodes
   - `inkwell graph connections "Tim Ferriss"` → people, books, companies
   - `inkwell graph path "Naval" "Stoicism"` → how these connect

5. **Visualizes knowledge:**
   - Export to Obsidian graph view (via metadata)
   - Export to dedicated graph tools (Neo4j, Gephi)
   - Built-in visualization with `inkwell graph view`

## Key Deliverables

- [ ] Design entity schema (Person, Book, Tool, Concept, Topic, Company, Quote)
- [ ] Create SQLite graph store with FTS5 and vector extensions
- [ ] Implement entity extraction pipeline that persists to graph
- [ ] Build coreference resolution for entity deduplication
- [ ] Implement relationship detection from transcript context
- [ ] Create `inkwell graph` command group (search, connections, stats, view)
- [ ] Add graph update step to main processing pipeline
- [ ] Implement entity enrichment (fetch metadata from external sources)
- [ ] Create graph export formats (JSON-LD, RDF, Neo4j CSV)
- [ ] Build simple terminal-based graph visualization
- [ ] Add Obsidian graph view metadata enhancement
- [ ] Create graph analysis commands (clusters, central nodes, orphans)

## Prerequisites

- **Initiative #01 (CI/CD Pipeline Excellence):** Complex feature needs solid testing
- **Initiative #03 (Universal Content):** Graph should span all content types

## Risks & Open Questions

- **Risk:** Entity resolution is an unsolved AI problem—accuracy may be low. Mitigation: User confirmation for merges, confidence thresholds.
- **Risk:** Graph storage could grow large with many episodes. Mitigation: Use efficient storage, pruning strategies for low-value entities.
- **Risk:** Relationship extraction may produce noisy data. Mitigation: High-precision prompts, user curation.
- **Question:** Should the graph be local-only or support sync/backup?
- **Question:** How to handle entity disambiguation across different contexts?
- **Question:** Should we integrate with existing graph tools (Obsidian, Neo4j) or build standalone?

## Notes

**Technology considerations:**
- SQLite with `sqlite-vec` for vector similarity search
- Optional Neo4j integration for advanced graph queries
- JSON-LD for semantic web compatibility

**Entity schema example:**
```yaml
entities:
  person:
    fields: [name, aliases, bio, twitter, website, mentions_count, first_seen, last_seen]
  book:
    fields: [title, author, isbn, goodreads_url, mentions_count]
  concept:
    fields: [name, definition, related_concepts, mentions_count]
```

**Query interface:**
```bash
# Find all mentions of a person
inkwell graph search "Naval Ravikant"

# Show connections for an entity
inkwell graph connections "Atomic Habits" --depth 2

# Find path between entities
inkwell graph path "Tim Ferriss" "Stoicism"

# View graph statistics
inkwell graph stats
```

**Files to create:**
- `src/inkwell/graph/` - New module
- `src/inkwell/graph/store.py` - SQLite-based graph storage
- `src/inkwell/graph/entities.py` - Entity models
- `src/inkwell/graph/resolution.py` - Coreference resolution
- `src/inkwell/graph/visualization.py` - Terminal graph view
