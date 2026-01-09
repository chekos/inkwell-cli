#!/bin/bash
# Claude Code PostToolUse Hook for Write/Edit operations
# Runs fast linting checks after Python file modifications

set -e

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$PROJECT_DIR"

# Only run checks if Python files were modified
# The hook runs after any Write/Edit, but we focus on .py files

echo "Running linting checks..."

# Run ruff linting (fast)
if ! uv run ruff check . --quiet; then
    echo "LINT ERROR: Ruff found issues. Fix them before continuing."
    exit 2  # Exit code 2 = blocking error
fi

# Check formatting
if ! uv run ruff format --check . --quiet 2>/dev/null; then
    echo "FORMAT ERROR: Code formatting issues found."
    echo "Run: uv run ruff format ."
    exit 2
fi

# Run type checking (moderately fast)
if ! uv run mypy src/ --no-error-summary 2>/dev/null; then
    echo "TYPE ERROR: mypy found type issues in src/"
    exit 2
fi

echo "All quick checks passed."
exit 0
