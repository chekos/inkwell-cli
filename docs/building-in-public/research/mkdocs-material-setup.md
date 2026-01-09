# Research – MkDocs Material with Existing DKS Structure

**Date:** 2025-11-06
**Author:** Claude
**Status:** Completed

## Purpose

Investigate whether MkDocs Material can be integrated with the existing Developer Knowledge System (DKS) documentation structure without requiring major reorganization of the docs/ directory.

## Scope

- Compatibility of MkDocs Material with existing subdirectory structures (adr/, devlog/, research/, lessons/, experiments/)
- Configuration requirements for MkDocs with pre-existing documentation
- Available plugins for enhancing ADR and devlog documentation
- Navigation setup for multiple documentation types

## Findings

### 1. **MkDocs Works With Existing Structures**

MkDocs and MkDocs Material are designed to work with existing documentation hierarchies:

- **`docs_dir` configuration**: Points to your documentation directory (defaults to 'docs')
- **Recursive processing**: Automatically discovers and processes all Markdown files in subdirectories
- **No restructuring needed**: Your current structure (adr/, devlog/, research/, lessons/, experiments/) is fully compatible
- **Flexible navigation**: The `nav` configuration in mkdocs.yml controls how docs appear in the site menu and doesn't need to mirror your directory structure

### 2. **ADR Plugin Available**

The `mkdocs-material-adr` plugin provides specialized support for Architecture Decision Records:

**Features:**
- Visual ADR headers with metadata (author, date, status, relationships)
- Auto-generated relationship graphs showing connections between ADRs
- Status pills with customizable colors (draft, proposed, accepted, rejected, superseded)
- Graph visualization using `[GRAPH]` placeholder in markdown

**Frontmatter format:**
```yaml
title: 0004 Title
adr:
  author: Jean-Loup Monnier
  created: 01-Aug-2023
  status: draft | proposed | rejected | accepted | superseded
  superseded_by: 0001-test
  extends: [0001-first, 0002-second]
```

**Installation:**
```bash
pip install mkdocs-material-adr
```

**Important Note on Theme Configuration:**

There is a discrepancy between the README documentation and actual implementation:
- **README says**: Use `theme: name: mkdocs-material-adr`
- **Actual implementation**: The project itself uses `theme: name: material`

**Correct approach**: Use `material` as the theme name. The ADR functionality comes from the plugin, not a custom theme.

See: [Lesson Learned - mkdocs-material-adr Theme Configuration](../lessons/2025-11-07-mkdocs-material-adr-theme-config.md)

### 3. **Configuration Requirements**

Minimal setup needed - just create `mkdocs.yml` at project root:

```yaml
site_name: Inkwell Documentation
docs_dir: docs

theme:
  name: material  # or 'mkdocs-material-adr' for ADR plugin

nav:
  - Home: README.md
  - Product: PRD_v0.md
  - User Guide: USER_GUIDE.md
  - Architecture Decisions:
    - Overview: adr/README.md
    - ADRs: adr/
  - Engineering Logs: devlog/
  - Research: research/
  - Experiments: experiments/
  - Lessons Learned: lessons/

plugins:
  - search
  - mkdocs-material-adr/adr  # if using ADR plugin

markdown_extensions:
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
```

### 4. **Navigation Flexibility**

MkDocs provides multiple navigation approaches:

- **Automatic**: If no `nav` is specified, MkDocs auto-generates navigation from directory structure (alphabetically)
- **Manual**: Explicitly define navigation structure in mkdocs.yml
- **Plugin-assisted**: Use plugins like `mkdocs-awesome-pages` for custom ordering without manual configuration
- **Multi-project**: The Material projects plugin can build nested documentation projects concurrently

## Recommendations

### Option 1: Basic MkDocs Material (Minimal Setup)

**Best for:** Quick start, no ADR enhancements needed

```bash
uv add --dev mkdocs-material
```

Create minimal `mkdocs.yml` with automatic navigation discovery.

**Pros:**
- Simplest setup
- No changes to existing files
- Works immediately

**Cons:**
- No special ADR features
- Basic navigation

### Option 2: MkDocs Material + ADR Plugin (Recommended)

**Best for:** Enhanced ADR documentation with relationship tracking

```bash
uv add --dev mkdocs-material-adr
```

Add frontmatter to existing ADR files (optional but recommended for full features).

**Pros:**
- Visual ADR headers and status
- Relationship graphs between decisions
- Professional presentation
- Minimal file changes needed

**Cons:**
- Requires adding frontmatter to ADR files for full benefits
- Slightly more complex setup

### Implementation Path

1. **Install dependencies:**
   ```bash
   uv add --dev mkdocs-material
   # or
   uv add --dev mkdocs-material-adr
   ```

2. **Create `mkdocs.yml`** at project root with navigation structure

3. **Test locally:**
   ```bash
   uv run mkdocs serve
   ```

4. **Optional: Enhance ADR files** with frontmatter for relationship tracking

5. **Deploy** (GitHub Pages, Read the Docs, Netlify, etc.)

## References

- [MkDocs Configuration Guide](https://www.mkdocs.org/user-guide/configuration/)
- [MkDocs Material Setup](https://squidfunk.github.io/mkdocs-material/setup/)
- [mkdocs-material-adr Plugin](https://github.com/Kl0ven/mkdocs-material-adr)
- [MkDocs Writing Your Docs](https://www.mkdocs.org/user-guide/writing-your-docs/)
- [Material for MkDocs Projects Plugin](https://squidfunk.github.io/mkdocs-material/plugins/projects/)
