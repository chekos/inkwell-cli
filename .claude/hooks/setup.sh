#!/bin/bash
# Claude Code Session Start Hook
# Ensures development environment is properly configured

set -e

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$PROJECT_DIR"

# Check if pre-commit hooks are installed
if [ ! -f ".git/hooks/pre-commit" ] || [ -f ".git/hooks/pre-commit.sample" ] && [ ! -x ".git/hooks/pre-commit" ]; then
    echo "Installing pre-commit hooks..."
    uv run pre-commit install
    echo "Pre-commit hooks installed successfully."
fi

# Sync dependencies to ensure everything is up to date
echo "Syncing dependencies..."
uv sync --dev --quiet

echo "Development environment ready."
exit 0
