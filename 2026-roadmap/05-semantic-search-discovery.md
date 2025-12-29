# Semantic Search & Discovery

**Category:** New Feature | Performance
**Quarter:** Q3
**T-shirt Size:** L

## Why This Matters

After processing dozens or hundreds of episodes, finding specific content becomes challenging. Keyword search fails when you remember the concept but not the exact words used. "That episode where they talked about building habits" returns nothing if no episode uses that phrase. You know Naval said something profound about reading, but which episode?

Semantic search enables discovery by meaning, not keywords. Ask "how to build better habits" and find the episode discussing "atomic behaviors," "tiny improvements," or "system design for personal growth." This transforms your processed content from a static archive into an intelligent, queryable knowledge base.

Combined with the Knowledge Graph (#04), semantic search creates a powerful discovery layer that surfaces connections you didn't know existed and finds content you didn't know you had.

## Current State

**Existing search capabilities:**
- None built-in—Inkwell produces files for external search
- Obsidian provides basic search through files
- Dataview queries enable structured filtering

**What's missing:**
- No semantic/vector search across transcripts
- No similarity-based episode recommendations
- No concept-level search (finding "productivity" when searching "getting things done")
- No cross-episode theme detection
- No "find similar to this episode" feature

**Related files:**
- Output markdown files contain full text
- Frontmatter has structured metadata
- No search index or embedding store

## Proposed Future State

A semantic search engine that:

1. **Indexes all content:**
   - Embeddings for full transcripts, summaries, and key concepts
   - Chunk-level indexing for precise retrieval
   - Incremental updates as new content is processed

2. **Enables natural language queries:**
   - `inkwell search "discussions about morning routines"`
   - `inkwell search "advice for startup founders" --limit 5`
   - `inkwell search "similar to episode X"`

3. **Powers discovery features:**
   - "You might also like" recommendations
   - Theme clustering across episodes
   - Gap analysis ("topics you haven't explored")

4. **Provides search UI:**
   - Terminal-based results with snippets
   - Interactive selection to open/view
   - Web dashboard integration (#06)

## Key Deliverables

- [ ] Design embedding schema (transcript chunks, summaries, entities)
- [ ] Implement local vector store using SQLite + sqlite-vec
- [ ] Create embedding generation pipeline (Gemini or local models)
- [ ] Build `inkwell search` command with natural language interface
- [ ] Implement chunk-level retrieval with context expansion
- [ ] Add similarity search ("find episodes like this one")
- [ ] Create theme clustering analysis
- [ ] Implement search result ranking and snippet generation
- [ ] Add incremental index updates in processing pipeline
- [ ] Create search index migration for existing processed content
- [ ] Integrate with Knowledge Graph (#04) for entity-aware search
- [ ] Add search result export (JSON, markdown)

## Prerequisites

- **Initiative #04 (Knowledge Graph Engine):** Shares entity store, enables entity-aware search
- **Initiative #01 (CI/CD Pipeline Excellence):** Testing for search accuracy

## Risks & Open Questions

- **Risk:** Embedding generation adds cost to processing. Mitigation: Use efficient local models (all-MiniLM-L6-v2), batch processing.
- **Risk:** Vector search may return irrelevant results. Mitigation: Hybrid search (semantic + keyword), result filtering.
- **Risk:** Index size could grow large. Mitigation: Compression, pruning old/less-accessed content.
- **Question:** Should embeddings be generated locally or via API?
- **Question:** How to handle multi-lingual content in embeddings?
- **Question:** Should search extend to external knowledge (web) or stay internal?

## Notes

**Technology options:**
- **sqlite-vec:** Local vector extension for SQLite, zero dependencies
- **ChromaDB:** More features but heavier dependency
- **Embedding models:** Gemini embeddings, or local sentence-transformers

**Search interface:**
```bash
# Natural language search
inkwell search "how to negotiate salary"

# Scoped search
inkwell search "machine learning" --podcast "Lex Fridman"

# Similarity search
inkwell search --similar-to "podcast/ep-123/summary.md"

# Advanced filters
inkwell search "productivity" --after 2024-01-01 --has-interview
```

**Embedding strategy:**
```yaml
embeddings:
  - transcript_chunks: 512 tokens, 50% overlap
  - summary: full document
  - key_concepts: individual concepts
  - quotes: individual quotes
```

**Files to create:**
- `src/inkwell/search/` - New module
- `src/inkwell/search/embeddings.py` - Embedding generation
- `src/inkwell/search/index.py` - Vector store management
- `src/inkwell/search/query.py` - Search query processing
- `src/inkwell/search/ranking.py` - Result ranking and snippets
