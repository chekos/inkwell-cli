# Documentation Reorganization Plan

## Executive Summary

**Problem:** The `docs/` directory currently mixes user-facing documentation (for CLI users) with the Developer Knowledge System (DKS - for internal engineering). The landing page focuses on DKS rather than helping users get started with Inkwell.

**Solution:** Reorganize with user documentation as the primary focus, while keeping DKS content accessible under a "Building in Public" section.

**Guiding Principles:**
1. Users visiting the docs should immediately see what Inkwell does and how to get started
2. Installation should be 1-2-3 commands on the landing page
3. DKS content remains available (building in public) but is clearly secondary
4. Follow documentation best practices (Stripe, Vercel, etc.)

---

## Current State Analysis

### Current Landing Page (`docs/README.md`)
- **Focus:** Developer Knowledge System (DKS)
- **Problem:** A CLI user landing here sees "Five Pillars" and internal engineering processes, not product features

### Current Navigation Structure
```
Home (DKS focus)
Getting Started
  - Tutorial
  - End-to-End Testing
Product
  - Product Requirements
  - User Guide
  - Phase 1 Summary/Complete
Architecture
Architecture Decisions (ADRs)
Engineering Logs (Devlogs)
Research
Experiments
Lessons Learned
```

**Issues:**
1. DKS dominates the navigation
2. "Product" section contains PRD (internal) mixed with User Guide (external)
3. Phase summaries are internal project tracking, not user docs
4. No clear "Installation" or "Features" sections

### File Inventory
| Category | Files | In Nav | Purpose |
|----------|-------|--------|---------|
| User Documentation | ~5 | 4 | For CLI users |
| DKS (ADRs, devlogs, etc.) | ~170 | ~20 | Internal engineering |
| Project Status (phases) | ~10 | 2 | Internal tracking |
| Analysis (PR reviews) | ~17 | 0 | Code review artifacts |

---

## Proposed Directory Structure

```
docs/
├── index.md                    # NEW: User-focused landing page
├── assets/                     # NEW: Images, diagrams, logos
│   └── inkwell-list.svg        # Moved from root
│
├── getting-started/            # NEW: Quick start content
│   ├── index.md                # Overview of getting started
│   ├── installation.md         # Detailed installation guide
│   ├── quickstart.md           # 5-minute quickstart
│   └── first-episode.md        # Tutorial (renamed from tutorial.md)
│
├── user-guide/                 # NEW: Comprehensive user docs
│   ├── index.md                # User guide overview
│   ├── feeds.md                # Managing podcast feeds
│   ├── processing.md           # Processing episodes
│   ├── extraction.md           # Content extraction & templates
│   ├── interview.md            # Interview mode
│   ├── obsidian.md             # Obsidian integration
│   └── configuration.md        # Configuration reference
│
├── reference/                  # NEW: Technical reference
│   ├── index.md                # Reference overview
│   ├── cli-commands.md         # Command reference (inkwell --help)
│   ├── templates.md            # Available templates
│   ├── config-options.md       # All configuration options
│   └── troubleshooting.md      # Common issues & solutions
│
├── building-in-public/         # RENAMED: DKS content
│   ├── index.md                # What is Building in Public?
│   │
│   ├── adr/                    # Architecture Decision Records
│   │   ├── index.md            # ADR overview + graph (renamed from README.md)
│   │   ├── 000-template.md
│   │   └── 001-034-*.md        # All ADRs
│   │
│   ├── devlog/                 # Engineering Logs
│   │   ├── index.md            # Devlog overview (renamed from README.md)
│   │   └── *.md                # All devlogs
│   │
│   ├── research/               # Research Documentation
│   │   ├── index.md            # Research overview (renamed from README.md)
│   │   └── *.md                # All research docs
│   │
│   ├── experiments/            # Experiments & Benchmarks
│   │   ├── index.md            # Experiments overview (renamed from README.md)
│   │   └── *.md                # All experiments
│   │
│   ├── lessons/                # Lessons Learned
│   │   ├── index.md            # Lessons overview (renamed from README.md)
│   │   └── *.md                # All lessons
│   │
│   └── architecture/           # Architecture docs
│       └── *.md                # Phase overviews, etc.
│
├── _internal/                  # NEW: Explicitly internal (excluded from nav)
│   ├── phases/                 # Phase summaries, checklists
│   ├── analysis/               # PR reviews, audits
│   ├── templates/              # Authoring templates
│   └── prd.md                  # Product Requirements Doc
│
└── legacy/                     # Optional: Archive old/duplicate files
    ├── user-guide.md           # Duplicate of USER_GUIDE.md
    ├── examples.md             # Orphaned
    └── dataview-queries.md     # Could move to user-guide/obsidian.md
```

---

## New Navigation Structure (`mkdocs.yml`)

```yaml
nav:
  - Home: index.md

  - Getting Started:
    - Overview: getting-started/index.md
    - Installation: getting-started/installation.md
    - Quick Start: getting-started/quickstart.md
    - Your First Episode: getting-started/first-episode.md

  - User Guide:
    - Overview: user-guide/index.md
    - Managing Feeds: user-guide/feeds.md
    - Processing Episodes: user-guide/processing.md
    - Content Extraction: user-guide/extraction.md
    - Interview Mode: user-guide/interview.md
    - Obsidian Integration: user-guide/obsidian.md
    - Configuration: user-guide/configuration.md

  - Reference:
    - Overview: reference/index.md
    - CLI Commands: reference/cli-commands.md
    - Templates: reference/templates.md
    - Configuration Options: reference/config-options.md
    - Troubleshooting: reference/troubleshooting.md

  - Building in Public:
    - What's This?: building-in-public/index.md
    - Architecture Decisions:
      - Overview: building-in-public/adr/index.md
      - ADR-001 (DKS): building-in-public/adr/001-developer-knowledge-system.md
      # ... more ADRs (or auto-generated)
    - Engineering Logs:
      - Overview: building-in-public/devlog/index.md
      # ... selective entries or auto-generated
    - Research:
      - Overview: building-in-public/research/index.md
    - Experiments:
      - Overview: building-in-public/experiments/index.md
    - Lessons Learned:
      - Overview: building-in-public/lessons/index.md
```

---

## New Landing Page Design (`docs/index.md`)

```markdown
# Inkwell

**Transform podcast episodes into structured, searchable markdown notes.**

Inkwell downloads podcast audio, transcribes it, extracts key information using AI,
and generates Obsidian-compatible notes—all from the command line.

## Quick Start

# Install with pipx (recommended)
pipx install inkwell-cli

# Or with pip
pip install inkwell-cli

# Set your API key
export GOOGLE_API_KEY="your-key"

# Process your first episode
inkwell fetch https://youtube.com/watch?v=xyz

## Features

- **Automatic Transcription** - YouTube transcripts (free) or Gemini fallback
- **AI-Powered Extraction** - Quotes, summaries, key concepts, tools mentioned
- **Obsidian Integration** - Wikilinks, tags, and Dataview-compatible frontmatter
- **Interview Mode** - Capture your personal insights with guided Q&A
- **Cost Tracking** - Know exactly what you're spending

## What You Get

Each episode produces a folder with structured markdown:

output/podcast-2025-01-15-episode-title/
├── summary.md          # Episode overview
├── quotes.md           # Notable quotes
├── key-concepts.md     # Main ideas
├── tools-mentioned.md  # Software & resources
└── my-notes.md         # Your insights (if --interview)

## Next Steps

- [Installation Guide](getting-started/installation.md) - Detailed setup instructions
- [Quick Start Tutorial](getting-started/quickstart.md) - Process your first episode
- [User Guide](user-guide/index.md) - Complete feature documentation

## Building in Public

Inkwell is built in public. Browse our [engineering notes](building-in-public/index.md)
to see architecture decisions, research, experiments, and lessons learned.
```

---

## Content Migration Plan

### Phase 1: Create New Structure (No Content Changes)
1. Create new directories: `getting-started/`, `user-guide/`, `reference/`, `building-in-public/`, `_internal/`, `assets/`
2. Create placeholder `index.md` files in each directory

### Phase 2: Create New Landing Page
1. Create `docs/index.md` with user-focused content (as designed above)
2. Move current `docs/README.md` to `docs/building-in-public/index.md` (edit to explain "Building in Public")

### Phase 3: Migrate User Documentation
1. **Getting Started:**
   - Create `getting-started/index.md` (overview)
   - Create `getting-started/installation.md` (extract from USER_GUIDE.md)
   - Create `getting-started/quickstart.md` (new, 2-minute version)
   - Move `tutorial.md` → `getting-started/first-episode.md`

2. **User Guide:**
   - Split `USER_GUIDE.md` into focused pages:
     - `user-guide/feeds.md` - Managing Feeds section
     - `user-guide/processing.md` - Content Extraction basics
     - `user-guide/extraction.md` - Templates, providers, costs
     - `user-guide/interview.md` - Interview Mode section
     - `user-guide/obsidian.md` - Obsidian Integration section + dataview-queries.md content
     - `user-guide/configuration.md` - Configuration section

3. **Reference:**
   - Create `reference/cli-commands.md` (generated from `inkwell --help`)
   - Create `reference/templates.md` (template documentation)
   - Create `reference/config-options.md` (all config options with defaults)
   - Move troubleshooting sections → `reference/troubleshooting.md`

### Phase 4: Migrate DKS Content
1. Move `adr/` → `building-in-public/adr/`
2. Move `devlog/` → `building-in-public/devlog/`
3. Move `research/` → `building-in-public/research/`
4. Move `experiments/` → `building-in-public/experiments/`
5. Move `lessons/` → `building-in-public/lessons/`
6. Move `architecture/` → `building-in-public/architecture/`
7. Rename all `README.md` files to `index.md` in these directories

### Phase 5: Move Internal Content
1. Move all `PHASE_*.md` files → `_internal/phases/`
2. Move `analysis/` → `_internal/analysis/`
3. Move `templates/` → `_internal/templates/`
4. Move `PRD_v0.md` → `_internal/prd.md`
5. Move `end-to-end-testing.md` → `_internal/e2e-testing.md` (or keep in reference)

### Phase 6: Update mkdocs.yml
1. Update nav structure as shown above
2. Add `_internal/` to exclude patterns (not published)
3. Update ADR plugin path

### Phase 7: Cleanup
1. Remove duplicate files (`user-guide.md` lowercase)
2. Move truly orphaned files to `legacy/` or delete
3. Update internal links throughout docs
4. Move `inkwell-list.svg` to `assets/`

---

## File Mapping Reference

| Current Location | New Location | Action |
|-----------------|--------------|--------|
| `docs/README.md` | `docs/building-in-public/index.md` | Move + edit |
| `docs/tutorial.md` | `docs/getting-started/first-episode.md` | Move + rename |
| `docs/USER_GUIDE.md` | Split into `user-guide/*.md` | Split |
| `docs/user-guide.md` | Delete (duplicate) | Delete |
| `docs/PRD_v0.md` | `docs/_internal/prd.md` | Move |
| `docs/PHASE_*.md` | `docs/_internal/phases/` | Move all |
| `docs/adr/` | `docs/building-in-public/adr/` | Move directory |
| `docs/devlog/` | `docs/building-in-public/devlog/` | Move directory |
| `docs/research/` | `docs/building-in-public/research/` | Move directory |
| `docs/experiments/` | `docs/building-in-public/experiments/` | Move directory |
| `docs/lessons/` | `docs/building-in-public/lessons/` | Move directory |
| `docs/architecture/` | `docs/building-in-public/architecture/` | Move directory |
| `docs/analysis/` | `docs/_internal/analysis/` | Move directory |
| `docs/templates/` | `docs/_internal/templates/` | Move directory |
| `docs/end-to-end-testing.md` | `docs/reference/e2e-testing.md` or `_internal/` | Move |
| `docs/examples.md` | `docs/user-guide/examples.md` or delete | TBD |
| `docs/dataview-queries.md` | Merge into `docs/user-guide/obsidian.md` | Merge |
| `docs/inkwell-list.svg` | `docs/assets/inkwell-list.svg` | Move |

---

## Implementation Checklist

### Preparation
- [ ] Create ADR for this reorganization decision
- [ ] Backup current docs structure

### Structure Creation
- [ ] Create `docs/assets/`
- [ ] Create `docs/getting-started/`
- [ ] Create `docs/user-guide/`
- [ ] Create `docs/reference/`
- [ ] Create `docs/building-in-public/`
- [ ] Create `docs/_internal/`
- [ ] Create `docs/_internal/phases/`
- [ ] Create `docs/_internal/analysis/`
- [ ] Create `docs/_internal/templates/`

### Content Creation
- [ ] Create `docs/index.md` (new landing page)
- [ ] Create `docs/getting-started/index.md`
- [ ] Create `docs/getting-started/installation.md`
- [ ] Create `docs/getting-started/quickstart.md`
- [ ] Create `docs/user-guide/index.md`
- [ ] Create `docs/reference/index.md`
- [ ] Create `docs/building-in-public/index.md`

### Content Migration
- [ ] Move `tutorial.md` → `getting-started/first-episode.md`
- [ ] Split `USER_GUIDE.md` into user-guide sections
- [ ] Move `adr/` → `building-in-public/adr/`
- [ ] Move `devlog/` → `building-in-public/devlog/`
- [ ] Move `research/` → `building-in-public/research/`
- [ ] Move `experiments/` → `building-in-public/experiments/`
- [ ] Move `lessons/` → `building-in-public/lessons/`
- [ ] Move `architecture/` → `building-in-public/architecture/`
- [ ] Move `PHASE_*.md` → `_internal/phases/`
- [ ] Move `analysis/` → `_internal/analysis/`
- [ ] Move `templates/` → `_internal/templates/`
- [ ] Move `PRD_v0.md` → `_internal/prd.md`
- [ ] Move `inkwell-list.svg` → `assets/`

### Rename README.md to index.md
- [ ] `building-in-public/adr/README.md` → `index.md`
- [ ] `building-in-public/devlog/README.md` → `index.md`
- [ ] `building-in-public/research/README.md` → `index.md`
- [ ] `building-in-public/experiments/README.md` → `index.md`
- [ ] `building-in-public/lessons/README.md` → `index.md`

### Configuration
- [ ] Update `mkdocs.yml` nav structure
- [ ] Add exclude for `_internal/` directory
- [ ] Update ADR plugin paths

### Cleanup
- [ ] Delete `docs/user-guide.md` (duplicate)
- [ ] Merge `dataview-queries.md` into obsidian.md
- [ ] Update all internal links
- [ ] Test MkDocs build
- [ ] Remove old files

### Verification
- [ ] Run `mkdocs build` - no errors
- [ ] Run `mkdocs serve` - verify navigation
- [ ] Check all links work
- [ ] Verify ADR graph still works
- [ ] Update CLAUDE.md references to new paths

---

## Questions for Review

1. **_internal vs excluded:** Should `_internal/` files be completely excluded from MkDocs build, or just hidden from nav but still accessible via direct URL?

2. **ADR in nav:** Should all 34 ADRs be listed in the nav, or just an overview with links to browse?

3. **Devlog granularity:** Should all 51 devlog entries be in nav, or just phase summaries?

4. **end-to-end-testing.md:** Is this user-facing (keep in reference) or internal (move to _internal)?

5. **Legacy files:** Delete or archive to `legacy/` directory?

---

## Success Criteria

After reorganization:

1. **User arriving at docs sees:**
   - What Inkwell is (headline + description)
   - How to install (1-2-3 commands)
   - Key features
   - Clear path to getting started

2. **Navigation is intuitive:**
   - Getting Started → User Guide → Reference (progressive)
   - Building in Public is clearly optional/supplemental

3. **DKS is still accessible:**
   - All ADRs, devlogs, research, experiments, lessons available
   - Clear framing as "engineering transparency"

4. **MkDocs builds cleanly:**
   - No broken links
   - No orphaned pages
   - ADR graph still works
