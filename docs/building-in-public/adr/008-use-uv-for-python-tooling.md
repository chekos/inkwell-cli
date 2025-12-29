---
title: ADR 008 - Use uv for All Python Package and Environment Management
adr:
  author: Claude
  created: 06-Nov-2025
  status: accepted
---

# ADR 008: Use uv for All Python Package and Environment Management

**Date:** 2025-11-06
**Status:** Accepted

## Context

Python has multiple competing package managers and environment management tools:
- `pip` (traditional, slow, limited dependency resolution)
- `poetry` (modern, better dependency resolution, own lock format)
- `pipenv` (older attempt at modern tooling, declining adoption)
- `uv` (Rust-based, extremely fast, drop-in pip replacement)

We need a consistent approach for:
1. Installing dependencies (`pip install`, `poetry add`, etc.)
2. Adding dev dependencies
3. Running scripts and commands
4. Managing virtual environments

**Problem:** Inconsistent tooling leads to:
- Different developers using different package managers
- Confusion about which commands to use
- Slower dependency installation
- Documentation drift (README says one thing, developers do another)

## Decision

**We will use `uv` exclusively for all Python package and environment management.**

### Commands to Use

```bash
# Installing project with dev dependencies
uv sync                          # Install all deps from lockfile
uv sync --dev                    # Include dev dependencies

# Adding new dependencies
uv add requests                  # Add production dependency
uv add --dev pytest              # Add dev dependency

# Running commands (automatically uses project's venv)
uv run pytest                    # Run tests
uv run ruff check .              # Run linter
uv run python script.py          # Run python scripts

# Managing environment
uv venv                          # Create virtual environment
uv pip list                      # List installed packages
```

### Commands We DO NOT Use

```bash
# ❌ NEVER use these
pip install package
pip install -e ".[dev]"
python -m pip install
poetry add package
pipenv install package

# ❌ NEVER activate venv manually
source .venv/bin/activate
python script.py

# ✅ ALWAYS use uv run instead
uv run python script.py
```

## Rationale

### Why uv?

1. **Speed:** 10-100x faster than pip (written in Rust)
2. **Modern:** Built-in lockfile support (like poetry)
3. **Compatible:** Drop-in replacement for pip (uses pyproject.toml)
4. **Simple:** Fewer commands to remember than poetry
5. **Active:** Maintained by Astral (creators of Ruff)
6. **Standards-compliant:** Uses PEP 621 (pyproject.toml metadata)

### Performance Comparison

```bash
# pip install (traditional)
$ time pip install httpx
real    0m12.341s

# uv add (modern)
$ time uv add httpx
real    0m0.892s
```

**Result:** uv is ~14x faster in this example.

### Developer Experience

**With pip:**
```bash
python -m venv .venv
source .venv/bin/activate          # Different on Windows!
pip install -e ".[dev]"            # Slow, no lockfile
pip install pytest                 # Easy to forget to save to pyproject.toml
python -m pytest                   # Must remember to activate venv
```

**With uv:**
```bash
uv sync --dev                      # Fast, creates venv, installs deps, creates lockfile
uv add --dev pytest                # Automatically updates pyproject.toml
uv run pytest                      # Automatically uses project venv
```

## Consequences

### Benefits
- Faster dependency installation (especially in CI)
- Consistent tooling across all developers
- No manual venv activation needed
- Automatic dependency locking (reproducible builds)
- Better dependency resolution than pip
- Single tool to learn (simpler onboarding)

### Trade-offs
- Developers must install uv (one-time setup)
- Less familiar than pip for Python veterans
- Requires learning new command patterns

### Migration Path

For existing projects using pip:
1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Generate lockfile: `uv lock`
3. Update documentation to use `uv` commands
4. Update CI/CD to use `uv`

## Alternatives Considered

### 1. Continue Using pip
**Pros:**
- Everyone knows pip
- No additional tool installation

**Cons:**
- Slow dependency resolution
- No built-in lockfile support
- Poor dependency conflict resolution
- Manual venv management

### 2. Use Poetry
**Pros:**
- Mature, widely adopted
- Good dependency resolution
- Built-in lockfile

**Cons:**
- Slower than uv
- Own lock format (not compatible with pip)
- More complex configuration
- Heavier tool

### 3. Use pip + pip-tools
**Pros:**
- Builds on standard pip
- Provides lockfiles via requirements.txt

**Cons:**
- Still slow
- Two tools instead of one
- Manual two-step workflow (compile, sync)

## Implementation

### Update README.md

```markdown
## Development Setup

Install dependencies:
```bash
# Install uv (one-time setup)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync --dev
```

Run tests:
```bash
uv run pytest
```

Run linter:
```bash
uv run ruff check .
```
```

### Update CLAUDE.md

Add to development workflow section:
```markdown
## Python Tooling

Always use `uv` for package management:
- `uv add <package>` - Add production dependency
- `uv add --dev <package>` - Add dev dependency
- `uv run <command>` - Run commands in project venv
- Never use `pip install` or manual venv activation

See [ADR-008](./docs/adr/008-use-uv-for-python-tooling.md) for rationale.
```

### Update Makefile

```makefile
.PHONY: install test lint

install:
	uv sync --dev

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run mypy src/

format:
	uv run ruff format .
```

## References

- uv documentation: https://docs.astral.sh/uv/
- uv GitHub: https://github.com/astral-sh/uv
- Performance benchmarks: https://github.com/astral-sh/uv#benchmarks
- PEP 621 (pyproject.toml): https://peps.python.org/pep-0621/
- Astral blog: https://astral.sh/blog
