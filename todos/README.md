# Inkwell CLI - Code Review Todos

**Review Date**: 2025-11-13
**PR**: #9 (Phase 5 - Obsidian Integration & v1.0.0 Release)
**Reviewer**: Claude Code Review System

---

## 📊 Summary

This directory contains actionable todo files for issues discovered during comprehensive code review of PR #9.

**Total Issues**: 20+
**Created Todos**: 15 (7 P1 + 4 P2 + 4 P3)
**Total Estimated Effort**: ~20-28 hours

---

## 🔴 Critical Priority (P1) - Must Fix Before Merge

| # | Issue | Severity | Effort | File |
|---|-------|----------|--------|------|
| 001 | Command Injection via EDITOR | CRITICAL (CVSS 9.1) | 1 hour | [View](001-pending-p1-command-injection-editor-variable.md) |
| 002 | Path Traversal in Output Dir | CRITICAL (CVSS 7.5) | 1-2 hours | [View](002-pending-p1-path-traversal-output-directory.md) |
| 003 | Print Statements (12×) | CRITICAL (Ops) | 1-2 hours | [View](003-pending-p1-replace-print-with-logging.md) |
| 004 | Retry Timing Issues | CRITICAL (UX) | 30 min | [View](004-pending-p1-fix-retry-timing-issues.md) |
| 005 | Cost Tracking Race Conditions | CRITICAL (Data Loss) | 2 hours | [View](005-pending-p1-add-file-locking-cost-tracking.md) |
| 006 | Datetime Timezone Mixing | CRITICAL (Data) | 1 hour | [View](006-pending-p1-fix-datetime-timezone-mixing.md) |
| 007 | Missing fsync in Atomic Writes | CRITICAL (Data Loss) | 30 min | [View](007-pending-p1-add-fsync-atomic-writes.md) |

**Total P1 Effort**: ~7.5 hours

---

## 🟡 High Priority (P2) - Fix Soon

| # | Issue | Severity | Effort | File |
|---|-------|----------|--------|------|
| 008 | API Key Validation | HIGH (CVSS 6.5) | 1-2 hours | [View](008-pending-p2-insufficient-api-key-validation.md) |
| 009 | Unsafe JSON from LLM | HIGH (CVSS 6.0) | 1-2 hours | [View](009-pending-p2-unsafe-json-deserialization-llm.md) |
| 010 | ReDoS in Regex Patterns | MEDIUM-HIGH (CVSS 5.5) | 1-2 hours | [View](010-pending-p2-redos-regex-patterns.md) |
| 011 | Missing Rate Limiting | MEDIUM (CVSS 5.0) | 2-3 hours | [View](011-pending-p2-missing-rate-limiting.md) |

**Total P2 Effort**: ~5-9 hours

---

## 🟢 Performance & Code Quality (P3) - Nice to Have

| # | Issue | Category | Effort | File |
|---|-------|----------|--------|------|
| 012 | Remove Dead Code (262 lines) | Code Quality | 30 min | [View](012-pending-p3-remove-dead-code.md) |
| 013 | Consolidate Duplicate Code (182 lines) | Code Quality | 2 hours | [View](013-pending-p3-consolidate-duplicate-code.md) |
| 014 | Batch API Requests | Performance | 3-4 hours | [View](014-pending-p3-batch-api-requests.md) |
| 015 | Async File I/O | Performance | 1-2 hours | [View](015-pending-p3-async-file-io.md) |

**Total P3 Effort**: ~7-9 hours

### Additional Issues (Not Yet Documented)

**Performance Optimizations**:
- Transcription tier racing (30-50% faster transcription)
- Multi-level caching (10-50x for hot data)

**Other Security Issues**:
- Insecure temp file creation
- Error messages leaking info
- No input size limits
- HTTP URLs accepted without warning
- No YAML bomb protection

---

## 🚀 Quick Start Guide

### 1. Review Priority Order

**Immediate (Block Merge)**:
1. Security vulnerabilities: 001, 002
2. Quick wins: 004, 007 (1 hour total, big impact)
3. Data integrity: 003, 005, 006 (4-5 hours)

**Post-Merge (v1.0.1)**:
4. High-priority security: 008-011 (5-9 hours)

### 2. Working with Todos

Each todo file contains:
- ✅ Detailed problem description with code examples
- ✅ Multiple solution options with pros/cons
- ✅ Complete implementation code ready to use
- ✅ Testing requirements
- ✅ Acceptance criteria
- ✅ Work log and learning notes

### 3. Todo File Format

```markdown
---
status: pending | in_progress | completed
priority: p1 | p2 | p3
issue_id: "NNN"
tags: [...]
dependencies: []
---

# Issue Title

## Problem Statement
[Detailed description]

## Findings
[What was discovered]

## Proposed Solutions
[Multiple options with trade-offs]

## Recommended Action
[What to do]

## Acceptance Criteria
- [ ] Checkboxes for requirements
```

### 4. Updating Todo Status

When working on a todo, update the front matter:
```yaml
---
status: in_progress  # Changed from pending
priority: p1
issue_id: "001"
---
```

When completed:
```yaml
---
status: completed  # Changed from in_progress
priority: p1
issue_id: "001"
---
```

---

## 📈 Progress Tracking

### By Status
```bash
# Count pending todos
grep -l "status: pending" todos/*.md | wc -l

# Count in-progress todos
grep -l "status: in_progress" todos/*.md | wc -l

# Count completed todos
grep -l "status: completed" todos/*.md | wc -l
```

### By Priority
```bash
# Critical (P1) todos
ls todos/*-p1-*.md | wc -l

# High priority (P2) todos
ls todos/*-p2-*.md | wc -l
```

---

## 🎯 Estimated Timeline

### Sprint 1 (Week 1) - Critical Fixes
**Goal**: Make PR merge-ready

- Day 1-2: Security fixes (001, 002) - 2-3 hours
- Day 3: Quick wins (004, 007) - 1 hour
- Day 4-5: Data integrity (003, 005, 006) - 5 hours

**Total**: ~8 hours, PR ready to merge

### Sprint 2 (Week 2) - High Priority
**Goal**: v1.0.1 release

- Day 1: API key validation (008) - 2 hours
- Day 2: JSON safety (009) - 2 hours
- Day 3: ReDoS protection (010) - 2 hours
- Day 4: Rate limiting (011) - 3 hours

**Total**: ~9 hours, v1.0.1 ready

### Sprint 3+ (Future) - Enhancements
**Goal**: Code quality and performance

- Day 1: Remove dead code (012) - 30 min
- Day 2: Consolidate duplicates (013) - 2 hours
- Day 3: Batch API requests (014) - 4 hours
- Day 4: Async file I/O (015) - 2 hours

**Total**: ~8.5 hours, v1.2 ready with optimizations

---

## 📚 Resources

### Documentation
- [PRD v0](../docs/PRD_v0.md) - Product requirements
- [Architecture Decision Records](../docs/adr/) - Design decisions
- [Developer Knowledge System](../docs/README.md) - Complete documentation

### Review Reports
All findings are based on analysis from these specialized agents:
- **kieran-python-reviewer** - Python code quality
- **git-history-analyzer** - Development patterns
- **pattern-recognition-specialist** - Design patterns
- **architecture-strategist** - System architecture
- **security-sentinel** - Security vulnerabilities
- **performance-oracle** - Performance issues
- **data-integrity-guardian** - Data integrity
- **code-simplicity-reviewer** - Code complexity

### External Resources
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- Python Security: https://python.readthedocs.io/en/stable/library/security_warnings.html
- Rate Limiting: https://cloud.google.com/architecture/rate-limiting-strategies-techniques

---

## 🤝 Contributing

When you complete a todo:
1. Update the status in the front matter
2. Add completion notes to the Work Log section
3. Document any deviations from the proposed solution
4. Update this README if needed

When you discover new issues:
1. Create a new todo file following the template
2. Use next sequential issue_id
3. Add entry to this README
4. Link to related todos in dependencies field

---

## 📞 Questions?

If you need clarification on any todo:
1. Check the complete implementation code in the todo file
2. Review the "Technical Details" section
3. Check related ADRs in `docs/adr/`
4. Review the original code review reports

---

## ✅ Next Steps

1. **Review this README** to understand priorities
2. **Read todo 001** (command injection) - highest risk
3. **Start with security fixes** (001, 002) - block merge
4. **Track your progress** - update todo status as you work
5. **Test thoroughly** - each todo has acceptance criteria

**Remember**: All P1 issues must be fixed before merge! 🚫

---

**Last Updated**: 2025-11-13
**Review Command**: `/review #9`
**Total Todos**: 15 (7 P1 + 4 P2 + 4 P3)
