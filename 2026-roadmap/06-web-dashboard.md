# Web Dashboard

**Category:** New Feature | DX Improvement
**Quarter:** Q3
**T-shirt Size:** XL

## Why This Matters

CLI tools have inherent limitations for knowledge management workflows. You can't easily browse your processed content, visualize relationships, or manage feeds without memorizing commands. The target audience—knowledge workers who want to transform podcast listening into active learning—often prefer visual interfaces for exploration and discovery.

A web dashboard extends Inkwell's reach beyond CLI power users to the broader knowledge management community. It provides a visual command center for managing feeds, browsing processed content, exploring the knowledge graph (#04), and conducting semantic searches (#05). This is how Inkwell becomes accessible to everyone, not just developers.

This also unlocks collaborative features in the future—shared team knowledge bases, curated collections, and social learning features.

## Current State

**CLI-only interface:**
- All operations via `inkwell` commands
- Terminal output with rich formatting
- Configuration via YAML files
- No visual browsing of processed content
- No interactive exploration

**Explicit non-goal in PRD:**
> "Web UI or GUI interface" listed as non-goal for v0.1-0.3

**Current tech stack:**
- Python 3.10+ with typer CLI
- No web framework dependencies
- No frontend infrastructure

## Proposed Future State

A beautiful, responsive web dashboard that:

1. **Provides a command center:**
   - Dashboard overview: recent activity, stats, cost tracking
   - Feed management: add/remove/configure feeds
   - Processing queue: see what's processing, history
   - Cost analytics: spending over time, per-provider breakdown

2. **Enables content browsing:**
   - Library view: all processed content, filterable
   - Episode detail: summary, quotes, key concepts, my notes
   - Visual knowledge graph explorer
   - Semantic search with result previews

3. **Supports interactive workflows:**
   - In-browser interview mode
   - Template customization UI
   - Entity curation and merging
   - Export format selection

4. **Runs locally by default:**
   - `inkwell serve` starts local web server
   - No cloud dependency required
   - Optional cloud sync in future

## Key Deliverables

- [ ] Select web framework (FastAPI + React/htmx hybrid recommended)
- [ ] Design API layer between CLI and web (see #10 REST API)
- [ ] Create core dashboard layout and navigation
- [ ] Build feed management interface
- [ ] Build content library browser with filtering
- [ ] Create episode detail view with all extracted content
- [ ] Integrate knowledge graph visualization (force-directed graph)
- [ ] Integrate semantic search with live results
- [ ] Build cost analytics dashboard
- [ ] Create interview mode web interface
- [ ] Add template editing UI
- [ ] Implement real-time processing progress
- [ ] Add responsive design for tablet/mobile viewing
- [ ] Create `inkwell serve` command

## Prerequisites

- **Initiative #04 (Knowledge Graph Engine):** Visualization requires graph data
- **Initiative #05 (Semantic Search):** Search integration requires index
- **Initiative #10 (REST API Layer):** Web dashboard consumes API

## Risks & Open Questions

- **Risk:** Web development is a different skillset than CLI/Python. Mitigation: Use Python-friendly stack (FastAPI + htmx), or partner with frontend developer.
- **Risk:** Maintaining two interfaces (CLI + web) doubles surface area. Mitigation: Share logic through API layer, CLI becomes thin wrapper.
- **Risk:** Performance expectations differ for web vs CLI. Mitigation: Progressive loading, optimistic UI updates.
- **Question:** Should we use React/Vue/Svelte or stick with Python (htmx/FastAPI templates)?
- **Question:** How to handle authentication for multi-user scenarios?
- **Question:** Should we offer a hosted cloud version or local-only?

## Notes

**Technology recommendations:**
- **Backend:** FastAPI (already Python, async, OpenAPI auto-docs)
- **Frontend options:**
  - htmx + Tailwind for Python-first team
  - React + Vite for modern SPA experience
  - Svelte for lightweight alternative
- **Graph visualization:** D3.js or vis-network

**Dashboard sections:**
```
┌────────────────────────────────────────────────┐
│ Inkwell                     [Search] [Profile] │
├────────────┬───────────────────────────────────┤
│ Dashboard  │ ┌─────────┐ ┌─────────┐          │
│ Library    │ │Recent   │ │Costs    │          │
│ Feeds      │ │Episodes │ │This Mo. │          │
│ Graph      │ └─────────┘ └─────────┘          │
│ Search     │                                   │
│ Settings   │ Processing Queue                  │
│            │ ├── Lex Fridman #500 (45%)       │
│            │ └── Tim Ferriss #700 (pending)   │
│            │                                   │
│            │ Recent Activity                   │
│            │ • Processed Naval x Joe Rogan    │
│            │ • Added new feed: Acquired       │
└────────────┴───────────────────────────────────┘
```

**Files to create:**
- `src/inkwell/web/` - Web application module
- `src/inkwell/web/app.py` - FastAPI application
- `src/inkwell/web/routers/` - API route handlers
- `src/inkwell/web/static/` - CSS, JS, images
- `src/inkwell/web/templates/` - HTML templates (if htmx)
- `web/` - Frontend application (if React/Vue)
