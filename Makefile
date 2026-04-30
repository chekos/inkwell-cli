.PHONY: install test lint format clean check

install:
	uv sync --dev

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run mypy src/

format:
	uv run ruff format .

docs:
	uv run mkdocs build --strict

coverage:
	uv run pytest --cov=src/inkwell --cov-report=term-missing --cov-report=html --cov-fail-under=75

check: format lint test docs

clean:
	rm -rf build/ dist/ *.egg-info .coverage htmlcov/ .pytest_cache/ .ruff_cache/ .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

pre-commit-install:
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push

pre-commit-run:
	uv run pre-commit run --all-files
