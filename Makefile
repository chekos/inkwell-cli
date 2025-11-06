.PHONY: install test lint format clean check

install:
	pip install -e ".[dev]"

test:
	python3 -m pytest

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/

check: format lint test

clean:
	rm -rf build/ dist/ *.egg-info .coverage htmlcov/ .pytest_cache/ .ruff_cache/ .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

pre-commit-install:
	pre-commit install

pre-commit-run:
	pre-commit run --all-files
