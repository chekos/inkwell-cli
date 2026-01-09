#!/bin/bash
# Install git hooks that aren't managed by pre-commit
# Run this once after cloning the repository

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_DIR"

echo "Installing git hooks..."

# Install pre-commit hooks
uv run pre-commit install

# Install pre-push hook
cp "$PROJECT_DIR/.claude/hooks/pre-push-check.sh" "$PROJECT_DIR/.git/hooks/pre-push"
chmod +x "$PROJECT_DIR/.git/hooks/pre-push"

echo "Git hooks installed successfully!"
echo ""
echo "Installed hooks:"
echo "  - pre-commit: Runs ruff lint, format, and mypy checks"
echo "  - pre-push: Runs full CI checks (lint, format, type check, tests)"
