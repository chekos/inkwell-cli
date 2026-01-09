# Multi-Export System

**Category:** New Feature | Integration
**Quarter:** Q4
**T-shirt Size:** M

## Why This Matters

Inkwell currently outputs Obsidian-optimized markdown, which works perfectly for Obsidian users but excludes everyone else. Users of Notion, Roam Research, Logseq, Craft, Bear, Mem, or even plain markdown miss out on Inkwell's value proposition. Some users want PDF reports for sharing, HTML for web publishing, or structured JSON for programmatic processing.

A multi-export system makes Inkwell platform-agnostic. Process your podcasts once, export everywhere. This dramatically expands the addressable market and removes a significant adoption barrier. The underlying extraction is the valuable work; the output format should be a simple configuration choice.

This also enables new workflows: generate a PDF summary to share with colleagues, export to Notion for team knowledge bases, or create HTML pages for a personal learning blog.

## Current State

**Current output:**
- Markdown files optimized for Obsidian
- Wikilinks: `[[Entity Name]]`
- Obsidian-style tags: `#topic/subtopic`
- Dataview-compatible frontmatter
- Directory structure per episode

**What's missing:**
- No PDF export
- No HTML export
- No Notion export
- No Roam/Logseq format
- No JSON/structured data export
- No format conversion for existing content
- No customizable templates per format

**Related ADR:**
- `docs/building-in-public/adr/026-obsidian-integration-architecture.md`

**PRD mentions:**
> "Export to other formats (Notion, Roam)" listed as future consideration

## Proposed Future State

A flexible export system that:

1. **Supports major platforms:**
   - **Obsidian:** Current format (default)
   - **Notion:** Markdown with Notion-compatible blocks
   - **Roam/Logseq:** Block-reference format
   - **Plain Markdown:** Universal compatibility
   - **HTML:** Styled web pages
   - **PDF:** Print-ready documents
   - **JSON:** Structured data for programmatic use
   - **Anki:** Flashcard decks (integration with #07)

2. **Enables format customization:**
   - Per-format templates
   - Custom styling (CSS for HTML/PDF)
   - Metadata mapping rules
   - Link format configuration

3. **Supports batch conversion:**
   - Convert existing processed content
   - Bulk export entire library
   - Scheduled exports

4. **Integrates with platform APIs:**
   - Direct Notion API push
   - Roam JSON import format
   - Logseq EDN format

## Key Deliverables

- [ ] Design output format abstraction replacing Markdown-only output
- [ ] Create format plugin specification (part of #02)
- [ ] Implement Notion export with block formatting
- [ ] Implement Roam/Logseq block-reference format
- [ ] Implement HTML export with customizable styling
- [ ] Implement PDF export using WeasyPrint or similar
- [ ] Implement plain Markdown (stripped wikilinks)
- [ ] Implement JSON structured export
- [ ] Create format conversion command (`inkwell convert`)
- [ ] Add `--format` flag to fetch command
- [ ] Create per-format template customization
- [ ] Implement Notion API direct push
- [ ] Add batch conversion for existing content
- [ ] Create export presets (e.g., "notion-team", "blog-post")

## Prerequisites

- **Initiative #02 (Plugin Architecture):** Exporters as plugins
- **Initiative #01 (CI/CD Pipeline Excellence):** Testing for format accuracy

## Risks & Open Questions

- **Risk:** Platform format changes could break exports. Mitigation: Version-specific format handlers, automated testing.
- **Risk:** PDF/HTML styling is complex. Mitigation: Default themes, CSS customization.
- **Risk:** Direct API integrations require auth management. Mitigation: OAuth flows, credential storage.
- **Question:** Should Notion push be real-time or batch?
- **Question:** How to handle format-specific features (e.g., Obsidian plugins)?
- **Question:** Should we maintain format parity or allow format-specific enhancements?

## Notes

**Format specifications:**

```yaml
# Obsidian (current default)
links: "[[Entity]]"
tags: "#topic/subtopic"
frontmatter: yaml
file_extension: .md

# Notion
links: "[Entity](notion://...)"  # Or plain text
callouts: "> [!info] Note text"
frontmatter: database properties
file_extension: .md

# Roam
links: "[[Entity]]"
blocks: "- Block content"
  - "- Nested block"
tags: "#[[topic]]"

# HTML
links: "<a href='#entity'>Entity</a>"
styling: custom CSS
output: single page or multi-page

# PDF
styling: custom CSS/WeasyPrint
output: single document
metadata: document properties
```

**CLI interface:**
```bash
# Export during fetch
inkwell fetch podcast --latest --format notion

# Convert existing content
inkwell convert episode-dir/ --to notion --output notion-export/

# Batch convert
inkwell convert --all --to html --output html-archive/

# Direct platform push
inkwell push episode-dir/ --to notion --database "Podcast Notes"
```

**Files to create:**
- `src/inkwell/export/` - Export module
- `src/inkwell/export/base.py` - Base exporter class
- `src/inkwell/export/notion.py` - Notion format
- `src/inkwell/export/roam.py` - Roam format
- `src/inkwell/export/html.py` - HTML format
- `src/inkwell/export/pdf.py` - PDF format
- `src/inkwell/export/json.py` - JSON format
