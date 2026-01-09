#!/bin/bash
# Git Pre-Push Hook
# Runs full CI checks locally before allowing push

set -e

PROJECT_DIR="$(git rev-parse --show-toplevel)"
cd "$PROJECT_DIR"

echo "========================================"
echo "Running pre-push checks (mirrors CI)"
echo "========================================"

echo ""
echo "[1/4] Linting with ruff..."
if ! uv run ruff check .; then
    echo ""
    echo "PUSH BLOCKED: Linting errors found."
    echo "Fix the errors above and try again."
    exit 1
fi

echo ""
echo "[2/4] Checking code formatting..."
if ! uv run ruff format --check .; then
    echo ""
    echo "PUSH BLOCKED: Code formatting issues."
    echo "Run: uv run ruff format ."
    exit 1
fi

echo ""
echo "[3/4] Type checking with mypy..."
if ! uv run mypy src/; then
    echo ""
    echo "PUSH BLOCKED: Type errors found."
    exit 1
fi

echo ""
echo "[4/4] Running test suite..."
if ! uv run pytest; then
    echo ""
    echo "PUSH BLOCKED: Tests failed."
    exit 1
fi

echo ""
echo "========================================"
echo "All checks passed! Pushing..."
echo "========================================"
exit 0
