# Contributing to Inkwell CLI

Thank you for your interest in contributing to Inkwell! This document provides guidelines for contributing to the project.

## Quick Start

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- ffmpeg (for audio processing)
- Git

### Development Setup

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/chekos/inkwell-cli.git
   cd inkwell-cli
   ```

3. **Install dependencies**:
   ```bash
   uv sync --dev
   ```

4. **Install pre-commit hooks**:
   ```bash
   uv run pre-commit install
   ```

5. **Run tests to verify setup**:
   ```bash
   uv run pytest
   ```

## Development Workflow

### Branch Naming

Use descriptive branch names with prefixes:
- `feat/feature-name` - New features
- `fix/bug-name` - Bug fixes
- `docs/doc-name` - Documentation updates
- `refactor/refactor-name` - Code refactoring
- `test/test-name` - Test additions/updates

### Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test additions/updates
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `chore`: Build process or tooling changes

**Examples:**
```
feat(transcription): add Gemini fallback for failed YouTube transcripts

fix(costs): correct cost calculation for multi-page API responses

docs(tutorial): add troubleshooting section for ffmpeg installation
```

### Testing

**All changes must include tests.** We maintain 95%+ code coverage.

```bash
# Run all tests
uv run pytest

# Run specific test types
uv run pytest tests/unit/           # Unit tests
uv run pytest tests/integration/    # Integration tests
uv run pytest tests/e2e/            # End-to-end tests

# Run with coverage
uv run pytest --cov=inkwell --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_costs.py -v
```

### Linting and Type Checking

Pre-commit hooks will automatically run linting, but you can run manually:

```bash
# Lint code
uv run ruff check .

# Format code
uv run ruff format .

# Type checking
uv run mypy src/
```

All checks must pass before submitting a PR.

### Documentation

#### User Documentation

Update user-facing documentation when adding features:
- `docs/user-guide.md` - Complete feature reference
- `docs/tutorial.md` - For beginner-friendly features
- `docs/examples.md` - Add real-world usage examples
- `README.md` - Update if adding major features

#### Developer Knowledge System (DKS)

The project uses a structured documentation system in `docs/`. See [docs/README.md](../docs/README.md) for full details.

**When to create documentation:**

1. **ADRs (Architecture Decision Records)** - `docs/adr/NNN-decision-title.md`
   - Create when making significant architectural decisions
   - Use next sequential number
   - Follow template at `docs/adr/000-template.md`
   - Keep brief - document the decision and rationale, not implementation details

2. **Devlogs** - `docs/devlog/YYYY-MM-DD-description.md`
   - Create when starting new features
   - Document implementation decisions, surprises, and next steps
   - Link to related ADRs and issues

3. **Research Docs** - `docs/research/topic-name.md`
   - Create before making technology decisions
   - Include findings, recommendations, and references
   - Link in subsequent ADRs

4. **Lessons Learned** - `docs/lessons/YYYY-MM-DD-topic.md`
   - Add after completing significant work
   - Document what worked, what didn't, and why

**Example workflow:**
```bash
# Starting a new feature
1. Create devlog: docs/devlog/2025-11-14-add-batch-processing.md
2. Research options: docs/research/batch-processing-patterns.md
3. Make decision: docs/adr/015-use-parallel-workers.md
4. Implement feature (with tests)
5. Document learnings: docs/lessons/2025-11-15-parallel-processing.md
6. Update user guide and examples
```

## Pull Request Process

### Before Submitting

1. **Create an issue first** for discussion (unless it's a trivial fix)
2. **Fork the repository** and create your feature branch
3. **Write tests** that cover your changes
4. **Update documentation** (user guide, API docs, CHANGELOG.md)
5. **Run all quality checks**:
   ```bash
   uv run pytest
   uv run ruff check .
   uv run mypy src/
   ```
6. **Test your changes** end-to-end with real API calls (if applicable)
7. **Update CHANGELOG.md** under "Unreleased" section

### PR Checklist

Your PR should include:

- [ ] Tests added/updated (95%+ coverage maintained)
- [ ] Documentation updated (user guide, API docs, examples)
- [ ] CHANGELOG.md entry added under "Unreleased"
- [ ] ADR created (if architectural decision made)
- [ ] Devlog created (if feature implementation)
- [ ] Pre-commit hooks pass
- [ ] All tests pass locally (`uv run pytest`)
- [ ] Type checking passes (`uv run mypy src/`)
- [ ] Linting passes (`uv run ruff check .`)

### PR Description

Use the pull request template to provide:
- Clear description of what the PR does
- Type of change (bug fix, feature, breaking change, etc.)
- Testing performed
- Screenshots/terminal recordings (if UI changes)
- Related issues (use "Closes #123" to auto-close)

### Review Process

1. Maintainers will review your PR within 48 hours
2. Address any feedback or requested changes
3. Once approved, a maintainer will merge your PR
4. Your contribution will be included in the next release

## Code Style Guidelines

### Python Style

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints everywhere (enforced by mypy)
- Maximum line length: 100 characters
- Use double quotes for strings (enforced by ruff)

### Docstrings

Use Google-style docstrings:

```python
def process_episode(url: str, interview: bool = False) -> EpisodeOutput:
    """Process a podcast episode from a URL.

    Args:
        url: The episode URL (RSS feed or direct YouTube link)
        interview: Whether to conduct an interactive interview

    Returns:
        EpisodeOutput containing all generated markdown files

    Raises:
        TranscriptionError: If transcription fails
        ExtractionError: If LLM extraction fails
    """
```

### Testing Style

- One test file per module (`test_<module>.py`)
- Descriptive test names (`test_should_retry_on_rate_limit_error`)
- Use fixtures for common setup
- Mock external API calls
- Use `pytest.raises()` for exception testing

## API Keys and Secrets

**NEVER commit API keys or secrets to the repository.**

- Use environment variables for API keys
- Use `.env` files locally (never commit them)
- Add sensitive files to `.gitignore`
- Use the encrypted credential storage for user credentials

## Getting Help

- **Questions**: Open a [GitHub Discussion](https://github.com/chekos/inkwell-cli/discussions)
- **Bugs**: Create a [Bug Report](https://github.com/chekos/inkwell-cli/issues/new?template=bug_report.yml)
- **Features**: Create a [Feature Request](https://github.com/chekos/inkwell-cli/issues/new?template=feature_request.yml)
- **Documentation**: Create a [Documentation Issue](https://github.com/chekos/inkwell-cli/issues/new?template=documentation.yml)

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to [maintainer email].

## License

By contributing to Inkwell CLI, you agree that your contributions will be licensed under the BSD 3-Clause License.

## Recognition

All contributors will be recognized in:
- The project's README.md
- GitHub's contributors page
- Release notes for their contributions

Thank you for contributing to Inkwell! 🎉
