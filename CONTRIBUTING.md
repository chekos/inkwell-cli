# Contributing to Inkwell

Thank you for your interest in contributing! This document covers how to get started.

---

## Before You Start

- Check [existing issues](https://github.com/chekos/inkwell-cli/issues) before opening a new one.
- For significant changes, open an issue first to discuss the approach.
- Small fixes (typos, docs, trivial bugs) can go straight to a PR.

---

## Development Setup

```bash
# Clone the repo
git clone https://github.com/chekos/inkwell-cli.git
cd inkwell-cli

# Install dependencies (requires uv)
uv sync --dev

# Install git hooks (required — prevents CI failures)
uvx pre-commit install
uvx pre-commit install --hook-type pre-push
```

Run tests:

```bash
uv run pytest
```

Run linter and formatter:

```bash
uv run ruff check .
uv run ruff format .
```

---

## Making Changes

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Write your code.** Follow the existing style; the pre-commit hooks enforce formatting and linting automatically.

3. **Add tests** for any new behaviour. Bug fixes should include a regression test where practical.

4. **Run the test suite** before pushing:
   ```bash
   uv run pytest
   ```

5. **Open a pull request** against `main`. Fill in the PR template — what changed, why, and how to verify it.

---

## What We're Looking For

- Bug fixes with a clear description of the problem and fix
- Documentation improvements
- New extraction templates (see `src/inkwell/extraction/templates/`)
- Performance improvements with benchmarks
- Test coverage improvements

Features that add new external dependencies or change the CLI interface need extra discussion upfront.

---

## Code Style

- Python 3.10+, formatted with `ruff format`
- Linted with `ruff check`
- Type annotations on public functions
- No comments explaining *what* the code does — only *why* when it's non-obvious

---

## Reporting Issues

Use [GitHub Issues](https://github.com/chekos/inkwell-cli/issues). Include:

- Inkwell version (`inkwell --version`)
- Python version (`python --version`)
- OS and version
- Full command you ran
- Full error output

---

## Questions

Open a [GitHub Discussion](https://github.com/chekos/inkwell-cli/discussions) for questions that aren't bugs or feature requests.

---

## License

By contributing you agree your code will be released under the [BSD 3-Clause License](LICENSE).
