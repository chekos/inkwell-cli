---
title: ADR 003 - Build System Selection (Setuptools vs Hatchling)
adr:
  author: Claude
  created: 06-Nov-2025
  status: accepted
---

# ADR-003: Build System Selection (Setuptools vs Hatchling)

**Status**: Accepted
**Date**: 2025-11-06
**Deciders**: Claude (implementation), User (approval)
**Related**: [Devlog Days 1-3](../devlog/2025-11-06-days-1-3-implementation.md)

## Context

During Day 1 implementation, we needed to choose a PEP 517 build backend for the project. The initial plan specified Hatchling as the build backend due to its modern design and PEP 621 compliance. However, we encountered package discovery issues during installation.

### The Problem

When using Hatchling with our `src/` layout:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatchling.build.targets.wheel]
packages = ["src/inkwell"]
```

Installation failed with:
```
ValueError: Unable to determine which files to ship inside the wheel using the following heuristics
The most likely cause of this is that there is no directory that matches the name of your project (inkwell_cli).
```

Multiple configuration attempts failed:
- `[tool.hatchling.build]` → Same error
- `[tool.hatchling.build.targets.wheel]` → Same error
- Package name variations → Same error

## Decision

**We switched to setuptools** as the build backend.

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

## Rationale

### Why Setuptools Won

1. **Mature `src/` Layout Support**
   - Setuptools has supported `src/` layouts for years
   - `packages.find` configuration is well-documented
   - Extensive community knowledge base

2. **Immediate Success**
   - Installation worked on first try after switch
   - No additional configuration needed
   - Package discovery "just worked"

3. **PEP 621 Compliance**
   - Setuptools 61.0+ fully supports `[project]` tables
   - Modern pyproject.toml-only configuration
   - No setup.py or setup.cfg needed

4. **Ecosystem Compatibility**
   - Most widely used Python build backend
   - Better compatibility with various environments
   - Fewer edge cases and surprises

### Why Not Hatchling

Despite Hatchling's advantages (faster, newer, cleaner):

1. **Package Discovery Issues**
   - Couldn't reliably find packages in our `src/` layout
   - Documentation unclear on src/ layout specifics
   - Time spent debugging outweighed benefits

2. **Less Mature**
   - Newer tool = less battle-tested
   - Fewer Stack Overflow answers
   - More configuration trial-and-error

3. **Not Worth the Risk**
   - Build system is infrastructure, not feature
   - Need reliability over cutting-edge
   - Can reconsider in future versions

## Consequences

### Positive
- ✅ Installation works reliably
- ✅ Standard, well-understood configuration
- ✅ Easy for contributors to understand
- ✅ Extensive documentation and examples
- ✅ Still fully PEP 621 compliant

### Negative
- ❌ Slightly slower builds (negligible for our project size)
- ❌ Not using "newest and shiniest" tool
- ❌ Setuptools is verbose compared to Hatchling

### Neutral
- Both are PEP 517/621 compliant
- Both support editable installs (`pip install -e .`)
- Both work with modern Python packaging tools

## Alternatives Considered

### 1. Hatchling with Flat Layout
**Rejected**: Would require restructuring entire project, moving away from best-practice `src/` layout

### 2. Poetry
**Rejected**: Poetry is more than a build backend (includes dependency management). We want to keep packaging simple and use pip.

### 3. Flit
**Rejected**: Flit is designed for simple, pure-Python packages. We may have future requirements (C extensions for performance) that Flit doesn't support well.

### 4. Keep Debugging Hatchling
**Rejected**: Time investment not justified. Setuptools works, and we have a project to build.

## Implementation Notes

The change required modifying only `pyproject.toml`:

```diff
[build-system]
-requires = ["hatchling"]
-build-backend = "hatchling.build"
+requires = ["setuptools>=61.0", "wheel"]
+build-backend = "setuptools.build_meta"

-[tool.hatchling.build.targets.wheel]
-packages = ["src/inkwell"]
+[tool.setuptools.packages.find]
+where = ["src"]
```

After this change:
```bash
$ pip install -e .
# Successfully installed inkwell-cli-0.1.0

$ inkwell --help
# Works perfectly
```

## Future Considerations

- If Hatchling's `src/` layout support improves, we could reconsider
- For now, setuptools is the pragmatic choice
- This decision can be revisited in v0.2+ without breaking changes

## Lessons Learned

1. **Test Installation Early**: Caught this on Day 1, not Day 7
2. **Pragmatism Over Perfection**: Setuptools isn't exciting, but it works
3. **Build System is Infrastructure**: Boring and reliable beats new and shiny
4. **Document the Why**: This ADR explains decision for future contributors

## References

- [PEP 517 - Build Backend Interface](https://peps.python.org/pep-0517/)
- [PEP 621 - Project Metadata](https://peps.python.org/pep-0621/)
- [Setuptools src/ Layout Documentation](https://setuptools.pypa.io/en/latest/userguide/package_discovery.html#src-layout)
- [Hatchling Documentation](https://hatch.pypa.io/latest/)
