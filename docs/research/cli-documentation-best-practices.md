# Research: Production-Grade CLI Tool Documentation Best Practices

**Date:** 2025-11-14
**Status:** Complete
**Context:** Research to inform GitHub issue for inkwell-cli documentation improvements

## Executive Summary

This research synthesizes best practices from authoritative sources including clig.dev (CLI Guidelines), well-documented projects (GitHub CLI, uv, Typer), Python packaging guides (pyOpenSci), and industry standards. The findings cover five key areas: CLI-specific documentation, Python project standards, developer experience, user experience, and modern tooling recommendations.

---

## 1. CLI Tool Documentation Best Practices

### 1.1 Core Philosophy (Source: clig.dev)

**Human-First Design:**
- Modern CLIs should prioritize user experience over legacy UNIX constraints
- "If a command is going to be used primarily by humans, it should be designed for humans first"
- Balance machine composability with human readability

**The Basics (Non-Negotiable):**
- Use argument parsing libraries (never roll your own)
- Return zero exit codes for success, non-zero for failure
- Send primary output to `stdout`, messaging to `stderr`
- Handle interrupts (Ctrl-C) gracefully
- Display help via `-h` or `--help` flags

### 1.2 Help & Discovery

**Essential Help Requirements:**
- Show concise help when commands run without required arguments
- Include usage examples, common flags, and instructions to access full documentation
- Structure help with clear headings (USAGE, OPTIONS, EXAMPLES, COMMANDS)
- "The CLI help screen is essentially your getting started documentation for the command line"

**Multi-Layered Documentation:**
1. Built-in help text (`--help`)
2. Terminal-based documentation accessible through the tool
3. Web-based docs (searchable, linkable, accessible)
4. Man pages (for discoverability on Unix systems)

**Discovery Patterns:**
- Make functionality learnable through examples and helpful suggestions
- Suggest command corrections for invalid input
- Guide users through multi-step workflows
- Provide "See what to do next" suggestions in output

### 1.3 Examples from Well-Documented CLIs

**GitHub CLI (gh):**
- Main documentation at cli.github.com with manual and quickstart
- Command structure: `gh <command> <subcommand> [flags]`
- Organized command groups (Core Commands, Extension Commands)
- Platform-specific installation guides (macOS, Linux, Windows, from source)
- Comparison with predecessor tools (gh-vs-hub.md)

**uv (Astral):**
Documentation structure follows progressive disclosure:
1. **Introduction** - Overview, key features, speed benchmarks
2. **Getting Started** - Installation, first steps, help resources
3. **Guides** - Practical tutorials (Installing Python, running scripts, Docker integration, etc.)
4. **Concepts** - Deep technical understanding (projects, resolution, caching)
5. **Reference** - CLI commands, settings, environment variables, troubleshooting

### 1.4 Output & Error Handling

**Output Best Practices:**
- Display status updates for state-changing operations
- Use human-readable formatting as default
- Offer `--json` and `--plain` flags for machine integration
- Include brief, meaningful output on success
- Reserve verbose output for explicit requests (`--verbose` or `-v`)

**Error Handling:**
- Rewrite technical errors into actionable guidance
- Minimize noise; group similar errors under explanatory headers
- Place critical information where users will notice it
- Provide debug information only when explicitly requested

---

## 2. Python Project Documentation Standards

### 2.1 README.md Structure (Source: pyOpenSci)

**Essential Sections (In Order):**
1. **Package Name** - Ideally matching repository name
2. **Badges** - Version, CI/CD status, docs build, coverage
3. **Description** - 1-3 sentences, accessible to "high school level" audience
4. **Key Features** - Bullet list of main capabilities
5. **Installation** - Multiple package managers if applicable
6. **Quick Start** - Brief, functional code example
7. **Documentation Links** - Descriptive links to full docs
8. **Usage Examples** - Common workflows
9. **Contributing** - Link to CONTRIBUTING.md
10. **License** - License type and link
11. **Citation** - DOI and preferred format (if academic)

**Badge Recommendations:**
- PyPI version
- CI/CD test status (GitHub Actions, etc.)
- Documentation build status
- Code coverage percentage
- License type
- Python version compatibility

**Writing Guidelines:**
- Target accessible language for varied backgrounds
- Keep descriptions concise
- Link to detailed docs rather than embedding lengthy content
- Limit badges to avoid visual clutter (5-7 maximum)

### 2.2 Docstring Standards (PEP 257 + Extensions)

**PEP 257 Basics:**
- Always use `"""triple double quotes"""`
- Two forms: one-liners and multi-line docstrings
- Multi-line: summary line + blank line + detailed description

**Popular Format Styles:**

**Google Style** (Recommended for readability):
```python
def function(arg1: str, arg2: int) -> bool:
    """Summary line describing the function.

    Longer description providing more context about what
    this function does and when to use it.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When invalid input is provided

    Example:
        >>> function("test", 42)
        True
    """
```

**NumPy Style** (For scientific/data libraries):
- Extension of Google style with more detailed sections
- Well-suited for scientific computing libraries
- Includes Parameters, Returns, Raises, See Also, Notes, Examples sections

**Tool Support:**
- Sphinx napoleon extension parses Google/NumPy styles
- Pydocstyle supports: pep257 (default), numpy, google conventions
- Ruff includes docstring checks (pydocstyle reimplemented in Rust)

### 2.3 Documentation Tools & Generation

**Sphinx (Industry Standard):**
- Automatic API documentation from docstrings
- Extensions: autodoc, napoleon, autosummary
- Themes: Read the Docs, PyData, Furo, Book
- Configuration: `docs/conf.py`

**Sphinx autodoc Best Practices:**
- Add `autodoc` to enabled extensions in conf.py
- Use `:members:` to show all documented class members
- Set `autodoc_member_order = "bysource"` for source ordering
- Mock dependencies with `autodoc_mock_imports`

**Sphinx AutoAPI (Alternative):**
- Generates docs without importing code (safer for complex dependencies)
- Automatic discovery of all modules
- No manual authoring of API directives
- Better for projects with complex import requirements

**sphinx-apidoc Tool:**
- Generates reStructuredText source files from code
- Automates creation of API reference structure
- Command: `sphinx-apidoc -o docs/source mypackage/`

### 2.4 Project Structure (Source: Hitchhiker's Guide to Python)

**Standard Python Project Layout:**
```
project-name/
├── .github/
│   ├── CONTRIBUTING.md
│   ├── CODE_OF_CONDUCT.md
│   └── SECURITY.md
├── docs/
│   ├── conf.py
│   ├── index.rst
│   ├── installation.rst
│   ├── usage.rst
│   ├── api.rst
│   └── contributing.rst
├── src/
│   └── package_name/
│       ├── __init__.py
│       ├── __main__.py
│       └── ...
├── tests/
│   └── ...
├── .gitignore
├── CHANGELOG.md
├── LICENSE
├── README.md
├── pyproject.toml
└── setup.py (if needed)
```

**Key File Purposes:**
- `README.md` - Project overview and quick start
- `CHANGELOG.md` - Version history (Keep a Changelog format)
- `CONTRIBUTING.md` - Contribution guidelines
- `CODE_OF_CONDUCT.md` - Community standards
- `LICENSE` - Software license
- `SECURITY.md` - Security policy and vulnerability reporting

---

## 3. Developer Experience (DX) Best Practices

### 3.1 CONTRIBUTING.md Structure (Source: contributing.md, GitHub)

**Essential Contents:**
1. **Welcome Message** - Encouraging note about contributions
2. **Table of Contents** - If file is lengthy
3. **Code of Conduct** - Link to CODE_OF_CONDUCT.md
4. **Ways to Contribute** - Code, docs, bug reports, feature requests
5. **Development Setup**
   - Prerequisites (Python version, system dependencies)
   - Installation steps using project's package manager
   - Running tests
   - Running linters
6. **Project Structure** - Brief overview of directory layout
7. **Coding Standards**
   - Style guide (PEP 8, project-specific deviations)
   - Docstring requirements
   - Type hint expectations
8. **Testing Guidelines**
   - Where tests are located
   - How to run tests
   - Coverage expectations
   - Writing new tests
9. **Pull Request Process**
   - Branch naming conventions
   - Commit message format
   - PR title/description requirements
   - Review process and timelines
10. **Documentation Requirements**
    - When to update docs
    - How to build docs locally
11. **Getting Help** - Communication channels (Discord, Slack, GitHub Discussions)

**Python-Specific Recommendations:**
- Reference PEP 8 with any project-specific deviations
- Specify docstring format (Google, NumPy, reStructuredText)
- Document required Python version and dependency management tool
- Include changelog entry requirements for all PRs
- Credit contributors in changelog entries

**Pull Request Guidelines:**
- Always make a new branch for work
- Don't submit unrelated changes in same PR
- Include tests for behavior changes
- For significant changes, open an issue first for discussion
- Focused PRs get merged faster

### 3.2 Development Setup Documentation

**Prerequisites Section:**
- Operating system requirements
- Python version (use `python --version` format)
- System dependencies (ffmpeg, build tools, etc.)
- API keys or credentials needed

**Installation Instructions:**
```markdown
## Development Setup

### Prerequisites
- Python 3.10 or higher
- ffmpeg (for audio processing)
- API keys: Anthropic Claude, Google Gemini

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/user/project.git
   cd project
   ```

2. Install dependencies:
   ```bash
   uv sync --dev
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. Verify installation:
   ```bash
   uv run project --version
   ```
```

### 3.3 Testing Documentation

**What to Include:**
- Testing framework used (pytest, unittest)
- How to run full test suite
- How to run specific tests
- Coverage reporting
- Test file organization
- Writing new tests guidelines

**Example:**
```markdown
## Testing

This project uses pytest for testing.

### Running Tests
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_transcription.py

# Run with coverage report
uv run pytest --cov=inkwell --cov-report=html
```

### Test Organization
- `tests/unit/` - Unit tests for individual functions
- `tests/integration/` - Integration tests
- `tests/fixtures/` - Test data and fixtures
```

### 3.4 Architecture Documentation

**Architecture Decision Records (ADRs):**
- Small text files in Markdown format
- Capture context, decision, and consequences
- Location: `docs/adr/` or `docs/architecture/`
- Use sequential numbering: `001-decision-name.md`
- Template: MADR (Markdown Any Decision Records)

**ADR Structure:**
```markdown
# ADR-NNN: [Decision Title]

**Status:** [Proposed | Accepted | Rejected | Superseded by ADR-XXX]
**Date:** YYYY-MM-DD
**Deciders:** [List of people involved]

## Context
What is the issue we're facing?

## Decision
What did we decide to do?

## Consequences
What are the positive and negative outcomes?

## Alternatives Considered
What other options did we evaluate?
```

**Benefits:**
- Prevents "decision amnesia"
- Provides context for future developers
- Helps AI assistants make better suggestions
- Documents the "why" behind choices

**Tools:**
- `adr-tools` - CLI for managing ADRs
- `pyadr` - Python-specific ADR management
- `adr-viewer` - Python-based viewer for ADRs

---

## 4. User Experience (UX) Best Practices

### 4.1 Quick Start Guide Structure

**Progressive Difficulty:**
1. **Installation** - Single command if possible
2. **First Command** - Simplest possible use case
3. **Common Workflow** - Most typical usage pattern
4. **Next Steps** - Links to tutorials and advanced features

**Example Structure:**
```markdown
## Quick Start

### 1. Install
```bash
pip install inkwell-cli
```

### 2. Configure
```bash
inkwell config --api-key YOUR_KEY
```

### 3. Process Your First Podcast
```bash
inkwell process https://example.com/feed.rss --latest
```

### Next Steps
- [Tutorial: Complete Workflow](docs/tutorial.md)
- [Configuration Guide](docs/configuration.md)
- [Command Reference](docs/reference.md)
```

### 4.2 Tutorial Progression

**Typer Documentation Model:**
- Start simple, grow complex
- "The simplest example adds only 2 lines of code"
- Scaffold from basic scripts to sophisticated applications

**Recommended Tutorial Structure:**
1. **Fundamentals** - Installation, first steps, basic usage
2. **Core Features** - Main workflows, common patterns
3. **Configuration** - Customization options
4. **Advanced Features** - Complex scenarios, integrations
5. **Best Practices** - Tips, common pitfalls, optimization

**Tutorial Best Practices:**
- Each tutorial should be completable in 5-15 minutes
- Include copy-pasteable code examples
- Show expected output for each command
- Link to reference docs for deep dives
- Provide downloadable example files/repos

### 4.3 Troubleshooting & FAQ

**Troubleshooting Structure:**
```markdown
## Troubleshooting

### Common Issues

#### Issue: Command Not Found
**Symptoms:** `bash: inkwell: command not found`

**Cause:** Package not in PATH or not installed globally

**Solution:**
```bash
# Option 1: Use uv run
uv run inkwell --version

# Option 2: Install globally
pipx install inkwell-cli
```

#### Issue: API Rate Limiting
**Symptoms:** `Error: Rate limit exceeded`

**Cause:** Too many requests to API

**Solution:** Add delays between requests or use batch mode
```

**FAQ Organization:**
- Group by topic (Installation, Configuration, Usage, Errors)
- Use clear question format for headers
- Provide concise, actionable answers
- Link to relevant documentation sections
- Include search-friendly keywords

**Recommended Sections:**
- Installation & Setup
- Configuration & API Keys
- Common Errors & Solutions
- Performance & Optimization
- Integration & Compatibility

### 4.4 Example Repositories & Templates

**Provide:**
- Starter templates in separate repository
- Example configurations for common use cases
- Sample output to show expected results
- Integration examples (CI/CD, Docker, etc.)

**Example:**
```markdown
## Examples

### Basic Usage
See [examples/basic/](examples/basic/) for simple podcast processing

### Advanced Workflows
- [CI/CD Integration](examples/github-actions/)
- [Docker Deployment](examples/docker/)
- [Batch Processing](examples/batch/)

### Configuration Templates
- [Minimal Config](examples/configs/minimal.yaml)
- [Production Config](examples/configs/production.yaml)
```

---

## 5. Documentation Tooling & Frameworks

### 5.1 Modern Documentation Frameworks

**MkDocs Material** (Recommended for Python projects)

**Pros:**
- Simple configuration (YAML-based)
- Beautiful Material Design theme
- Markdown-centric (no complex markup)
- Fast setup (Python + pip)
- Excellent search functionality
- Code syntax highlighting built-in
- Ideal for API and software architecture docs

**Cons:**
- Less suitable for single-page applications
- Fewer interactive features than React-based alternatives

**Setup:**
```bash
pip install mkdocs-material
mkdocs new .
mkdocs serve  # Local preview
mkdocs build  # Generate static site
```

**Configuration (mkdocs.yml):**
```yaml
site_name: Inkwell CLI
site_url: https://inkwell.example.com
theme:
  name: material
  features:
    - navigation.tabs
    - navigation.sections
    - toc.integrate
    - search.suggest
    - search.highlight
    - content.code.copy
nav:
  - Home: index.md
  - Getting Started:
    - Installation: getting-started/installation.md
    - Quick Start: getting-started/quickstart.md
  - User Guide:
    - Configuration: guide/configuration.md
    - Processing Podcasts: guide/processing.md
  - Reference:
    - CLI Commands: reference/commands.md
    - API: reference/api.md
  - Contributing: contributing.md
```

**Docusaurus** (Alternative for React-heavy projects)

**Pros:**
- React-based single-page application
- Highly interactive
- Versioned documentation support
- MDX support (Markdown + JSX)
- Large ecosystem of plugins

**Cons:**
- More complex setup (Node.js required)
- Higher resource usage for generation/display
- Overkill for straightforward documentation

**When to Choose:**
- MkDocs: Backend tools, API docs, straightforward documentation, faster setup
- Docusaurus: Need SPA, interactive features, React integration, versioning

### 5.2 API Documentation Generators

**Sphinx with Napoleon** (Traditional approach):
```python
# conf.py
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
]

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
autodoc_member_order = 'bysource'
```

**Sphinx AutoAPI** (Modern alternative):
```python
# conf.py
extensions = ['autoapi.extension']
autoapi_type = 'python'
autoapi_dirs = ['../src/inkwell']
autoapi_options = [
    'members',
    'undoc-members',
    'show-inheritance',
    'show-module-summary',
    'imported-members',
]
```

**pdoc** (Lightweight alternative):
- Simpler than Sphinx
- Automatic generation from docstrings
- No configuration needed
- Command: `pdoc --html --output-dir docs mypackage`

### 5.3 Documentation Testing & Validation

**Doctest:**
- Test code examples in docstrings
- Ensures examples stay up-to-date
```python
def add(a: int, b: int) -> int:
    """Add two numbers.

    Example:
        >>> add(2, 3)
        5
    """
    return a + b
```

**Markdown Link Checking:**
- Tool: `markdown-link-check`
- CI integration to catch broken links
```bash
npm install -g markdown-link-check
markdown-link-check README.md
```

**Spell Checking:**
- Tool: `codespell` (Python)
- Catches typos in documentation
```bash
pip install codespell
codespell docs/
```

### 5.4 Documentation Hosting

**Read the Docs:**
- Free for open source
- Automatic builds from GitHub
- Versioned documentation
- Search functionality
- Sphinx and MkDocs support

**GitHub Pages:**
- Free for public repositories
- Custom domains supported
- GitHub Actions integration
- Good for MkDocs Material

**Setup Example (GitHub Actions + MkDocs):**
```yaml
# .github/workflows/docs.yml
name: Deploy Docs
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install mkdocs-material
      - run: mkdocs gh-deploy --force
```

---

## 6. CHANGELOG Best Practices

### 6.1 Keep a Changelog Format

**Standard Structure:**
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- New feature X for improved Y

### Changed
- Updated dependency Z to version 2.0

### Fixed
- Bug where A caused B

## [1.0.0] - 2025-11-14
### Added
- Initial release
- Feature A
- Feature B

[Unreleased]: https://github.com/user/repo/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/user/repo/releases/tag/v1.0.0
```

**Change Categories:**
- **Added** - New features
- **Changed** - Changes in existing functionality
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Security vulnerability fixes

**Best Practices:**
- Keep "Unreleased" section at top for upcoming changes
- Use semantic versioning (MAJOR.MINOR.PATCH)
- Focus on user-facing changes, not internal refactoring
- Credit contributors in entries
- Link to GitHub releases/tags

### 6.2 Automation Tools

**commitizen:**
- Enforces conventional commit format
- Automatically bumps version
- Generates changelog from commits
```bash
pip install commitizen
cz init
cz commit  # Interactive commit message builder
cz bump  # Bump version and update changelog
```

**keepachangelog (Python package):**
- Parse and manipulate Keep a Changelog formatted files
```python
from keepachangelog import to_dict
changes = to_dict("CHANGELOG.md")
```

---

## 7. Code of Conduct

### 7.1 Standard Templates

**Contributor Covenant** (Most Popular):
- Used by 40,000+ projects (Kubernetes, Rails, Swift)
- Available at contributor-covenant.org
- Current version: 2.1
- Drop-in template, just add contact info

**Python Community Code of Conduct:**
- Python.org/psf/conduct/
- Specifically tailored to Python projects
- Emphasizes being open, considerate, and respectful

**Key Elements:**
1. **Our Pledge** - Commitment to inclusive environment
2. **Our Standards** - Examples of positive/negative behavior
3. **Enforcement Responsibilities** - Who enforces and how
4. **Scope** - Where code applies
5. **Enforcement** - Reporting process and consequences
6. **Attribution** - Credit to template source

### 7.2 File Location

GitHub recognizes CODE_OF_CONDUCT.md in:
- Repository root: `/CODE_OF_CONDUCT.md`
- Docs directory: `/docs/CODE_OF_CONDUCT.md`
- .github directory: `/.github/CODE_OF_CONDUCT.md`

When present, GitHub automatically links to it when contributors create issues or PRs.

---

## 8. Recommended Documentation Structure for Inkwell CLI

Based on all research, here's the recommended structure:

```
inkwell-cli/
├── .github/
│   ├── CONTRIBUTING.md
│   ├── CODE_OF_CONDUCT.md
│   └── SECURITY.md
├── docs/
│   ├── index.md (landing page)
│   ├── getting-started/
│   │   ├── installation.md
│   │   ├── configuration.md
│   │   └── quick-start.md
│   ├── user-guide/
│   │   ├── adding-feeds.md
│   │   ├── processing-episodes.md
│   │   ├── interview-mode.md
│   │   ├── output-structure.md
│   │   └── obsidian-integration.md
│   ├── tutorials/
│   │   ├── first-podcast.md
│   │   ├── private-feeds.md
│   │   └── batch-processing.md
│   ├── reference/
│   │   ├── cli-commands.md
│   │   ├── configuration-options.md
│   │   ├── environment-variables.md
│   │   └── api/  (Sphinx-generated)
│   ├── troubleshooting/
│   │   ├── common-issues.md
│   │   ├── faq.md
│   │   └── error-codes.md
│   ├── development/
│   │   ├── setup.md
│   │   ├── testing.md
│   │   ├── architecture.md
│   │   └── contributing.md
│   ├── adr/  (existing)
│   ├── devlog/  (existing)
│   ├── lessons/  (existing)
│   └── research/  (existing)
├── examples/
│   ├── basic-usage/
│   ├── advanced-workflows/
│   └── configs/
├── CHANGELOG.md
├── README.md
└── mkdocs.yml
```

---

## 9. Priority Recommendations for Inkwell CLI

### 9.1 Must Have (Priority 1)

1. **Enhanced README.md**
   - Add badges (version, tests, coverage, license)
   - Improve description with use case examples
   - Add quick start section with copy-paste commands
   - Include screenshots/GIFs of CLI output
   - Link to comprehensive documentation

2. **Getting Started Guide**
   - Installation (pip, pipx, uv)
   - Configuration (API keys setup)
   - First command walkthrough
   - Expected output examples

3. **CLI Help Text**
   - Ensure all commands have `--help`
   - Include usage examples in help
   - Suggest next steps in output
   - Provide web docs links

4. **CONTRIBUTING.md**
   - Development setup with uv
   - Running tests
   - Code style (Ruff configuration)
   - PR process

5. **CHANGELOG.md**
   - Adopt Keep a Changelog format
   - Document all releases
   - Keep Unreleased section current

### 9.2 Should Have (Priority 2)

6. **MkDocs Documentation Site**
   - Set up MkDocs Material
   - Deploy to GitHub Pages or Read the Docs
   - Organize with progressive disclosure pattern

7. **User Guide**
   - Feed management
   - Processing episodes
   - Interview mode usage
   - Output structure explanation
   - Obsidian integration

8. **Reference Documentation**
   - All CLI commands with examples
   - Configuration file format
   - Environment variables
   - Exit codes

9. **Troubleshooting Guide**
   - Common issues (API keys, ffmpeg, rate limits)
   - Error message explanations
   - FAQ section

10. **API Documentation**
    - Set up Sphinx with autodoc
    - Document public APIs
    - Use Google-style docstrings consistently

### 9.3 Nice to Have (Priority 3)

11. **Tutorial Series**
    - Processing first podcast
    - Working with private feeds
    - Batch processing workflows
    - Custom LLM templates

12. **Example Repository**
    - Sample configurations
    - Common workflow scripts
    - Integration examples

13. **Architecture Documentation**
    - Update existing ADRs
    - Add architecture diagrams
    - Document pipeline flow

14. **CODE_OF_CONDUCT.md**
    - Adopt Contributor Covenant
    - Define community standards

15. **SECURITY.md**
    - Vulnerability reporting process
    - Security best practices

---

## 10. Implementation Recommendations

### 10.1 Tooling Choices

**Documentation Framework:** MkDocs Material
- Rationale: Simpler than Docusaurus, Python-native, excellent for CLI docs
- Command: `uv add --dev mkdocs-material`

**API Documentation:** Sphinx with Napoleon
- Rationale: Industry standard, good Python integration
- Command: `uv add --dev sphinx sphinx-rtd-theme`

**Docstring Style:** Google Style
- Rationale: More readable than NumPy, widely adopted
- Configure in pyproject.toml for Ruff

**Changelog Management:** Keep a Changelog format
- Optional: Add commitizen for automation
- Manual updates acceptable for small team

### 10.2 Phased Rollout

**Phase 1: Core Documentation (Week 1)**
- Update README.md with badges and quick start
- Create CONTRIBUTING.md
- Standardize CHANGELOG.md format
- Improve CLI help text

**Phase 2: User Documentation (Week 2-3)**
- Set up MkDocs with Material theme
- Write Getting Started guide
- Create User Guide sections
- Add Troubleshooting/FAQ

**Phase 3: Developer Documentation (Week 4)**
- Set up Sphinx for API docs
- Add docstrings to all public APIs
- Document architecture
- Create example repository

**Phase 4: Polish (Ongoing)**
- Add tutorials
- Create video walkthroughs
- Gather user feedback
- Iterate on clarity

### 10.3 Maintenance Strategy

**Continuous:**
- Update CHANGELOG with every PR
- Keep examples working with tests
- Review documentation in PR process

**Quarterly:**
- Review all documentation for accuracy
- Update screenshots/examples
- Check for broken links
- Gather user feedback

**Major Releases:**
- Update Getting Started for breaking changes
- Add migration guides if needed
- Update all version references

---

## 11. Key Sources & References

### 11.1 Primary Sources

- **clig.dev** - Command Line Interface Guidelines (authoritative)
- **pyOpenSci Python Packaging Guide** - README and documentation standards
- **Keep a Changelog** - keepachangelog.com
- **Contributor Covenant** - contributor-covenant.org
- **PEP 257** - Docstring Conventions
- **The Hitchhiker's Guide to Python** - Project structure

### 11.2 Example Projects Studied

- **GitHub CLI (gh)** - cli.github.com
- **uv (Astral)** - docs.astral.sh/uv
- **Typer** - typer.tiangolo.com
- **Click** - click.palletsprojects.com

### 11.3 Tool Documentation

- **MkDocs Material** - squidfunk.github.io/mkdocs-material
- **Sphinx** - sphinx-doc.org
- **Read the Docs** - docs.readthedocs.io

### 11.4 Python Standards

- **PEP 8** - Style Guide for Python Code
- **PEP 257** - Docstring Conventions
- **Google Python Style Guide** - google.github.io/styleguide/pyguide.html

---

## 12. Conclusion

Production-grade CLI tool documentation requires:

1. **Human-first design** - Prioritize user experience in help text, errors, and guides
2. **Progressive disclosure** - Introduction → Guides → Concepts → Reference
3. **Multiple formats** - Built-in help, web docs, man pages
4. **Clear contribution path** - CONTRIBUTING.md, development setup, testing
5. **Modern tooling** - MkDocs/Sphinx, automated testing, CI/CD integration
6. **Community standards** - Code of Conduct, Security policy
7. **Comprehensive coverage** - User docs, API docs, architecture, troubleshooting
8. **Maintenance strategy** - Keep docs current with code changes

For Inkwell CLI specifically:
- Start with enhanced README and CONTRIBUTING
- Set up MkDocs Material for user-facing documentation
- Use Sphinx for API documentation
- Adopt Keep a Changelog format
- Implement in phases over 4 weeks

The investment in documentation pays dividends through:
- Reduced support burden
- Faster onboarding of contributors
- Higher user satisfaction
- Better AI assistant integration (with clear context)
- Professional project perception
