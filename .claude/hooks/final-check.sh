#!/bin/bash
# Claude Code Stop Hook
# Runs full validation before Claude finishes a task

set -e

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$PROJECT_DIR"

echo "Running final checks before completion..."

# Check for uncommitted changes first
if git diff --quiet && git diff --cached --quiet; then
    echo "No changes detected, skipping checks."
    exit 0
fi

echo "1/4 Running linting..."
if ! uv run ruff check .; then
    echo "FAILED: Linting errors found."
    exit 2
fi

echo "2/4 Checking formatting..."
if ! uv run ruff format --check .; then
    echo "FAILED: Formatting issues found. Run: uv run ruff format ."
    exit 2
fi

echo "3/4 Running type checks..."
if ! uv run mypy src/; then
    echo "FAILED: Type checking errors found."
    exit 2
fi

echo "4/4 Running tests..."
if ! uv run pytest -x --tb=short; then
    echo "FAILED: Tests failed."
    exit 2
fi

echo "All checks passed! Safe to commit and push."
exit 0
