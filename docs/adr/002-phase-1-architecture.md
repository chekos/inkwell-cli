---
title: ADR 002 - Phase 1 Architecture & Technology Decisions
adr:
  author: Claude
  created: 06-Nov-2025
  status: proposed
---

# ADR-002: Phase 1 Architecture & Technology Decisions

**Status**: Proposed
**Date**: 2025-11-06
**Deciders**: Claude
**Related**: [PRD_v0.md](../PRD_v0.md), [Devlog: Phase 1 Plan](../devlog/2025-11-06-phase-1-implementation-plan.md)

## Context

Phase 1 establishes the foundation for Inkwell CLI. We need to make architectural decisions that will support the tool through v0.1-v0.3 while maintaining professional-grade quality standards.

## Decision

### 1. Package Structure: `src/` Layout

**Chosen**: Use `src/inkwell/` structure with hatchling build backend

**Rationale**:
- Prevents accidental imports of development code
- Clean separation between package and development files
- Modern Python packaging best practice
- PEP 621 compliant

### 2. Configuration: XDG + YAML + Pydantic

**Chosen**: XDG Base Directory specification with YAML files and Pydantic validation

**Alternatives Considered**:
- TOML: Less human-friendly for nested structures
- JSON: No comments, less forgiving syntax
- Single file: Harder to manage feeds separately

**Rationale**:
- YAML is human-editable and supports comments
- XDG compliance = proper Linux/macOS citizenship
- Pydantic provides type safety and validation
- Separate files (config.yaml, feeds.yaml) = clearer organization

**Files**:
```
~/.config/inkwell/config.yaml    # Global settings
~/.config/inkwell/feeds.yaml     # Feed configurations
~/.config/inkwell/.keyfile       # Encryption key (600 perms)
```

### 3. Credential Security: Fernet Encryption

**Chosen**: Symmetric encryption using Fernet (from `cryptography` library)

**Alternatives Considered**:
- **Plaintext**: Rejected - security risk
- **System keyring** (macOS Keychain, Secret Service): Better but adds complexity
- **Environment variables**: Not suitable for multi-feed storage

**Rationale**:
- Fernet is industry-standard symmetric encryption
- Simple implementation, no external services needed
- Better than plaintext, good enough for v0.1
- Can migrate to system keyring in v0.2+ if needed

**Trade-offs**:
- Key stored on disk (mitigated by 600 permissions)
- Not as secure as system keyring
- Acceptable for v0.1 given target audience (developers)

### 4. Dependency Management: Modern, Minimal

**Key Dependencies**:
- `typer[all]` - CLI framework (includes rich)
- `feedparser` - RSS parsing
- `pydantic` - Data validation
- `cryptography` - Credential encryption
- `httpx` - Async HTTP client
- `platformdirs` - XDG path handling

**Dev Dependencies**:
- `ruff` - Fast linting/formatting (replaces black+flake8+isort)
- `mypy` - Type checking
- `pytest` + `pytest-cov` + `pytest-mock` - Testing
- `respx` - httpx request mocking

**Rationale**:
- Minimize dependency tree
- Prefer modern, actively maintained libraries
- All async-capable for future scalability

### 5. Code Quality: Automated Enforcement

**Chosen**: Ruff + Mypy + Pre-commit hooks

**Rationale**:
- Ruff is 10-100x faster than traditional tools
- Mypy catches type errors at development time
- Pre-commit prevents bad commits
- Enforces consistency without manual review

### 6. Testing Strategy: High Coverage, Realistic Fixtures

**Targets**:
- 90%+ unit test coverage
- Integration tests for all CLI commands
- Fixtures with real-world RSS samples

**Rationale**:
- High confidence in refactoring
- Catch regressions early
- Document expected behavior through tests

### 7. Error Handling: User-Focused Messages

**Approach**:
- Custom exception hierarchy
- Rich terminal output for errors
- Helpful suggestions (e.g., "Run `inkwell config show` to verify")
- Debug logs to ~/.cache/inkwell/inkwell.log

**Rationale**:
- Users shouldn't need to read code to debug
- Professional tools have professional error messages
- Logs help with troubleshooting without cluttering terminal

### 8. Async-First Design

**Chosen**: Use `httpx` (async) and `async/await` patterns

**Rationale**:
- Future-proof for parallel episode processing
- Better UX with progress indicators during network requests
- Modern Python best practice

## Consequences

### Positive
- Professional-grade codebase from day one
- Easy to onboard contributors (clear structure, typed code)
- High confidence in changes (testing, type checking)
- Good user experience (helpful errors, rich output)

### Negative
- More upfront work than minimal implementation
- Learning curve for contributors unfamiliar with modern Python tooling
- Dependency on external libraries (though all are stable)

### Neutral
- Config encryption is "good enough" but not perfect
- Will need migration path if we switch to system keyring later

## Implementation Notes

See [Phase 1 Implementation Plan](../devlog/2025-11-06-phase-1-implementation-plan.md) for detailed day-by-day breakdown.

## Review & Approval

- [ ] User approval on architectural approach
- [ ] User decision on open questions (PyPI publishing, Windows support, etc.)
