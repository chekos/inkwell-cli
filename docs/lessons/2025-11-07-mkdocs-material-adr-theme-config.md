# mkdocs-material-adr Theme Configuration Discrepancy

**Date:** 2025-11-07
**Author:** Claude
**Context:** MkDocs Material implementation

## What Happened

While implementing MkDocs Material with the ADR plugin, we initially configured the theme name as `mkdocs-material-adr` based on the project's README documentation. However, Copilot flagged this during PR review, recommending we use `material` as the theme name instead.

## The Problem

There is a **discrepancy between the README documentation and the actual implementation** in the mkdocs-material-adr project:

- **README states**: `theme: name: mkdocs-material-adr`
- **Actual project mkdocs.yml**: `theme: name: material` with `custom_dir: mkdocs_material_adr`

## Investigation

Research into the actual [mkdocs-material-adr repository](https://github.com/Kl0ven/mkdocs-material-adr/blob/main/mkdocs.yml) revealed:

1. The project's own documentation site uses `name: material`
2. The `custom_dir` approach is only used internally by the project itself
3. End users should use `material` as the theme and configure the plugin separately

## The Correct Configuration

```yaml
theme:
  name: material  # Use base Material theme, NOT mkdocs-material-adr
  # ... theme features, palette, etc.

plugins:
  - search
  - mkdocs-material-adr/adr:
      graph_file: adr/README.md
```

The ADR functionality comes entirely from the **plugin** (`mkdocs-material-adr/adr`), not from a custom theme.

## Lesson Learned

**Always verify documentation against actual implementation**, especially for third-party tools. When documentation conflicts with a project's own usage:

1. Check the project's actual mkdocs.yml or configuration files
2. Look for issues/discussions that might clarify the correct approach
3. Test both approaches if possible
4. Trust the implementation over the README when they conflict

**Trust but verify** - even well-maintained projects can have outdated README instructions.

## Impact

Minimal - both configurations appear to work, but using `material` as the theme is:
- More aligned with how Material for MkDocs is intended to be used
- Consistent with the project's own implementation
- Clearer about the separation between theme (Material) and plugin (ADR)

## References

- [mkdocs-material-adr README](https://github.com/Kl0ven/mkdocs-material-adr)
- [mkdocs-material-adr actual mkdocs.yml](https://github.com/Kl0ven/mkdocs-material-adr/blob/main/mkdocs.yml)
- Research: [docs/research/mkdocs-material-setup.md](../research/mkdocs-material-setup.md)
