# Phase 1 Implementation Plan - Inkwell CLI

**Date**: 2025-11-06
**Status**: Planning
**Related**: [PRD_v0.md](../PRD_v0.md), [ADR-001](../adr/001-developer-knowledge-system.md)

## Overview

Phase 1 establishes the foundation for Inkwell as a professional-grade CLI tool. This plan goes beyond the basic checklist in the PRD to ensure we build production-ready infrastructure from day one.

## Phase 1 Scope (from PRD)

**Core Requirements:**
- Project setup (pyproject.toml, structure)
- Config system (YAML read/write, encryption for auth)
- Feed management commands (add, list, remove)
- RSS parsing with feedparser

**Professional Grade Additions:**
- Comprehensive testing framework
- Robust error handling and logging
- Security-first credential management
- Developer tooling (linting, formatting, pre-commit hooks)
- User experience polish (progress indicators, helpful errors)
- Proper packaging and installation

---

## Detailed Implementation Plan

### 1. Project Structure & Scaffolding

#### 1.1 Directory Layout
```
inkwell-cli/
├── src/
│   └── inkwell/
│       ├── __init__.py
│       ├── __version__.py
│       ├── cli.py              # Main CLI entry point (typer)
│       ├── config/
│       │   ├── __init__.py
│       │   ├── manager.py      # Config CRUD operations
│       │   ├── schema.py       # Pydantic models for validation
│       │   ├── crypto.py       # Credential encryption/decryption
│       │   └── defaults.py     # Default config templates
│       ├── feeds/
│       │   ├── __init__.py
│       │   ├── manager.py      # Feed CRUD operations
│       │   ├── parser.py       # RSS parsing with feedparser
│       │   ├── validator.py    # Feed URL/auth validation
│       │   └── models.py       # Feed data models
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── logging.py      # Logging setup
│       │   ├── errors.py       # Custom exceptions
│       │   └── paths.py        # XDG-compliant path handling
│       └── constants.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Pytest fixtures
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_feeds.py
│   │   └── test_crypto.py
│   ├── integration/
│   │   └── test_cli.py
│   └── fixtures/
│       ├── sample_feeds.xml
│       └── sample_config.yaml
├── docs/                       # Existing DKS
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── LICENSE
├── .gitignore
├── .pre-commit-config.yaml
└── Makefile                   # Development shortcuts
```

**Rationale:**
- `src/` layout for proper package isolation
- Modular structure with clear separation of concerns
- Test directory mirrors source structure
- Fixtures separate from test code

#### 1.2 pyproject.toml Setup

**Core Dependencies:**
```toml
[project]
name = "inkwell-cli"
version = "0.1.0"
description = "Transform podcast episodes into structured markdown notes"
requires-python = ">=3.10"
dependencies = [
    "typer[all]>=0.12.0",      # CLI framework with rich support
    "pyyaml>=6.0",              # Config management
    "feedparser>=6.0.0",        # RSS parsing
    "pydantic>=2.0.0",          # Data validation
    "pydantic-settings>=2.0.0", # Settings management
    "cryptography>=42.0.0",     # Credential encryption
    "httpx>=0.27.0",            # HTTP client for RSS fetching
    "platformdirs>=4.0.0",      # XDG-compliant paths
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "ruff>=0.3.0",
    "mypy>=1.8.0",
    "pre-commit>=3.6.0",
    "types-pyyaml",
    "respx>=0.20.0",           # httpx mocking
]

[project.scripts]
inkwell = "inkwell.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "A", "C4", "PT"]
ignore = []

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "--cov=inkwell --cov-report=term-missing --cov-report=html"
```

**Key Decisions:**
- **Hatchling** for build backend (modern, PEP 621 compliant)
- **Ruff** for linting/formatting (fast, replaces black+flake8+isort)
- **Mypy** for type checking (catch errors early)
- **Cryptography** library for credential encryption (industry standard)
- **Platformdirs** for XDG Base Directory compliance (proper Linux/macOS paths)

#### 1.3 Development Tooling

**Pre-commit hooks** (.pre-commit-config.yaml):
- Ruff linting and formatting
- Mypy type checking
- YAML validation
- Trailing whitespace removal
- End-of-file fixer

**Makefile shortcuts**:
```makefile
install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .
	mypy src/

format:
	ruff format .

clean:
	rm -rf build/ dist/ *.egg-info .coverage htmlcov/ .pytest_cache/
```

---

### 2. Configuration System

#### 2.1 Config Schema (Pydantic)

**Goals:**
- Type-safe configuration
- Automatic validation
- Clear error messages on invalid config
- Support for environment variables

**Models** (config/schema.py):
```python
from pydantic import BaseModel, Field, HttpUrl, DirectoryPath
from typing import Literal, Optional

class AuthConfig(BaseModel):
    type: Literal["none", "basic", "bearer"] = "none"
    username: Optional[str] = None  # Encrypted when stored
    password: Optional[str] = None  # Encrypted when stored
    token: Optional[str] = None     # Encrypted when stored

class FeedConfig(BaseModel):
    url: HttpUrl
    auth: AuthConfig = Field(default_factory=AuthConfig)
    category: Optional[str] = None
    custom_templates: list[str] = Field(default_factory=list)

class GlobalConfig(BaseModel):
    version: str = "1"
    default_output_dir: DirectoryPath = Field(
        default="~/podcasts",
        description="Where to save processed episodes"
    )
    transcription_model: str = "gemini-2.0-flash-exp"
    interview_model: str = "claude-sonnet-4-5"
    youtube_check: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    default_templates: list[str] = Field(
        default_factory=lambda: ["summary", "quotes", "key-concepts"]
    )

    template_categories: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "tech": ["tools-mentioned", "frameworks-mentioned"],
            "interview": ["books-mentioned", "people-mentioned"],
        }
    )

class Feeds(BaseModel):
    feeds: dict[str, FeedConfig] = Field(default_factory=dict)
```

#### 2.2 Config Storage

**XDG Base Directory Compliance:**
- Config: `~/.config/inkwell/` (`$XDG_CONFIG_HOME/inkwell/`)
- Data: `~/.local/share/inkwell/` (`$XDG_DATA_HOME/inkwell/`)
- Cache: `~/.cache/inkwell/` (`$XDG_CACHE_HOME/inkwell/`)

**Files:**
```
~/.config/inkwell/
├── config.yaml          # Global settings
├── feeds.yaml           # Feed configurations
└── .keyfile             # Encryption key (600 permissions)
```

#### 2.3 Credential Encryption

**Strategy:**
- Use **Fernet** (symmetric encryption from `cryptography` library)
- Generate encryption key on first run, store in `~/.config/inkwell/.keyfile`
- Encrypt all sensitive fields (passwords, tokens, usernames)
- Never log or display decrypted credentials

**Implementation** (config/crypto.py):
```python
from cryptography.fernet import Fernet
import os

class CredentialEncryptor:
    def __init__(self, key_path: Path):
        self.key_path = key_path
        self._cipher = None

    def _ensure_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes()

        # Generate new key
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        self.key_path.chmod(0o600)  # Owner read/write only
        return key

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        cipher = Fernet(self._ensure_key())
        return cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        cipher = Fernet(self._ensure_key())
        return cipher.decrypt(ciphertext.encode()).decode()
```

**Security Considerations:**
- Key file has 600 permissions (owner only)
- Warn user if key file permissions are too open
- Support key rotation in future versions
- Consider system keyring integration (v0.2+)

#### 2.4 Config Manager

**Responsibilities:**
- Load/save YAML files
- Merge defaults with user config
- Validate configuration
- Encrypt/decrypt credentials transparently
- Handle migrations between config versions

**Key Methods** (config/manager.py):
```python
class ConfigManager:
    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or get_config_dir()
        self.encryptor = CredentialEncryptor(self.config_dir / ".keyfile")

    def load_config(self) -> GlobalConfig:
        """Load and validate global config"""

    def save_config(self, config: GlobalConfig) -> None:
        """Save global config with validation"""

    def load_feeds(self) -> Feeds:
        """Load feeds with decrypted credentials"""

    def save_feeds(self, feeds: Feeds) -> None:
        """Save feeds with encrypted credentials"""

    def add_feed(self, name: str, feed_config: FeedConfig) -> None:
        """Add or update a feed"""

    def remove_feed(self, name: str) -> None:
        """Remove a feed"""

    def get_feed(self, name: str) -> FeedConfig:
        """Get single feed config"""

    def list_feeds(self) -> dict[str, FeedConfig]:
        """List all feeds"""
```

---

### 3. Feed Management

#### 3.1 RSS Parser

**Responsibilities:**
- Fetch RSS feed with authentication
- Parse with feedparser
- Extract episode metadata
- Handle malformed feeds gracefully
- Support redirects
- Cache feed data (optional)

**Implementation** (feeds/parser.py):
```python
import feedparser
import httpx
from typing import Optional

class RSSParser:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def fetch_feed(
        self,
        url: str,
        auth: Optional[AuthConfig] = None
    ) -> feedparser.FeedParserDict:
        """Fetch and parse RSS feed with auth support"""

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = self._build_auth_headers(auth)
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()

            feed = feedparser.parse(response.content)

            if feed.bozo:  # Feedparser error flag
                # Log warning but continue if we got entries
                if not feed.entries:
                    raise FeedParseError(f"Failed to parse feed: {feed.bozo_exception}")

            return feed

    def get_latest_episode(self, feed: feedparser.FeedParserDict) -> Episode:
        """Extract latest episode from feed"""

    def get_episode_by_title(
        self,
        feed: feedparser.FeedParserDict,
        title_keyword: str
    ) -> Episode:
        """Find episode by title keyword (fuzzy match)"""

    def extract_episode_metadata(self, entry: dict) -> Episode:
        """Extract Episode model from feedparser entry"""
```

#### 3.2 Feed Models

**Data Models** (feeds/models.py):
```python
from pydantic import BaseModel, HttpUrl
from datetime import datetime

class Episode(BaseModel):
    title: str
    url: HttpUrl  # Direct audio/video URL
    published: datetime
    description: str
    duration_seconds: Optional[int] = None
    podcast_name: str
    episode_number: Optional[int] = None
    season_number: Optional[int] = None

    @property
    def slug(self) -> str:
        """Generate filesystem-safe episode identifier"""
        date_str = self.published.strftime("%Y-%m-%d")
        title_slug = slugify(self.title)
        return f"{self.podcast_name}-{date_str}-{title_slug}"
```

#### 3.3 Feed Validator

**Validation** (feeds/validator.py):
```python
class FeedValidator:
    async def validate_feed_url(self, url: str, auth: Optional[AuthConfig] = None) -> bool:
        """Check if URL is valid and accessible"""

    async def validate_auth(self, url: str, auth: AuthConfig) -> bool:
        """Verify authentication works"""

    def validate_feed_has_episodes(self, feed: feedparser.FeedParserDict) -> bool:
        """Ensure feed has at least one episode"""
```

---

### 4. CLI Commands (Typer)

#### 4.1 Command Structure

**Main CLI** (cli.py):
```python
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="inkwell",
    help="Transform podcast episodes into structured markdown notes",
    no_args_is_help=True,
)
console = Console()

# Subcommands
@app.command()
def add(
    url: str = typer.Argument(..., help="RSS feed URL"),
    name: str = typer.Option(..., "--name", "-n", help="Feed identifier"),
    auth: bool = typer.Option(False, "--auth", help="Prompt for authentication"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Feed category"),
) -> None:
    """Add a new podcast feed"""

@app.command()
def list() -> None:
    """List all configured feeds"""

@app.command()
def remove(
    name: str = typer.Argument(..., help="Feed name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove a podcast feed"""

@app.command()
def config_show() -> None:
    """Display current configuration"""

@app.command()
def config_edit() -> None:
    """Open config file in $EDITOR"""

@app.command()
def config_set(
    key: str = typer.Argument(..., help="Config key (dot notation)"),
    value: str = typer.Argument(..., help="New value"),
) -> None:
    """Set a configuration value"""
```

#### 4.2 Rich Output

**Tables for `list` command:**
```python
def list_feeds(feeds: dict[str, FeedConfig]) -> None:
    table = Table(title="Configured Podcast Feeds")
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="blue")
    table.add_column("Auth", style="yellow")
    table.add_column("Category", style="green")

    for name, feed in feeds.items():
        auth_status = "✓" if feed.auth.type != "none" else "—"
        table.add_row(name, str(feed.url), auth_status, feed.category or "—")

    console.print(table)
```

**Progress indicators:**
- Use `rich.progress` for long operations
- Spinners for network requests
- Progress bars for downloads (Phase 2)

#### 4.3 Error Handling

**Custom Exceptions** (utils/errors.py):
```python
class InkwellError(Exception):
    """Base exception for all Inkwell errors"""

class ConfigError(InkwellError):
    """Configuration-related errors"""

class FeedError(InkwellError):
    """Feed management errors"""

class AuthenticationError(FeedError):
    """Authentication failures"""

class FeedParseError(FeedError):
    """RSS parsing failures"""
```

**Error Display:**
- Use `rich.console.print` with `[red]` for errors
- Show helpful suggestions (e.g., "Run `inkwell config show` to verify settings")
- Include debug info when `--verbose` flag is set

---

### 5. Logging

#### 5.1 Logging Setup (utils/logging.py)

**Strategy:**
- Console logging via rich (user-facing)
- File logging for debugging (~/.cache/inkwell/inkwell.log)
- Structured logging with context
- Respect `log_level` from config

```python
import logging
from rich.logging import RichHandler

def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> None:
    # Rich handler for console
    console_handler = RichHandler(
        show_time=False,
        show_path=False,
        markup=True,
    )

    # File handler for debugging
    file_handler = logging.FileHandler(log_file or get_log_path())
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )

    logging.basicConfig(
        level=getattr(logging, level),
        handlers=[console_handler, file_handler],
    )
```

---

### 6. Testing Strategy

#### 6.1 Test Coverage Targets

- **Unit Tests**: 90%+ coverage
- **Integration Tests**: All CLI commands
- **Fixtures**: Realistic sample data

#### 6.2 Key Test Areas

**Config Tests** (tests/unit/test_config.py):
- YAML serialization/deserialization
- Pydantic validation
- Default value handling
- Config merging
- Path resolution

**Crypto Tests** (tests/unit/test_crypto.py):
- Encryption/decryption round-trip
- Key generation and storage
- Permission checking
- Empty/null handling

**Feed Tests** (tests/unit/test_feeds.py):
- RSS parsing (with fixtures)
- Episode metadata extraction
- URL validation
- Auth header construction

**CLI Tests** (tests/integration/test_cli.py):
- All command invocations
- Error handling
- Output formatting
- Config file creation

#### 6.3 Fixtures

**Sample RSS Feed** (tests/fixtures/sample_feed.xml):
- Valid RSS 2.0 feed
- Multiple episodes
- Various metadata scenarios

**Sample Config** (tests/fixtures/sample_config.yaml):
- Pre-configured feeds
- Custom settings

#### 6.4 Mocking Strategy

- Use `pytest-mock` for function mocking
- Use `respx` for httpx request mocking
- Mock filesystem operations for path tests
- Never hit real APIs in tests

---

### 7. Implementation Order

#### Week 1: Day-by-Day Breakdown

**Day 1: Project Setup**
- [ ] Create directory structure
- [ ] Setup pyproject.toml with all dependencies
- [ ] Configure ruff, mypy, pytest
- [ ] Setup pre-commit hooks
- [ ] Create Makefile
- [ ] Verify installation works (`pip install -e ".[dev]"`)

**Day 2: Config System - Part 1**
- [ ] Implement Pydantic schemas (schema.py)
- [ ] Implement path utilities (utils/paths.py)
- [ ] Write unit tests for schemas
- [ ] Create default config templates

**Day 3: Config System - Part 2**
- [ ] Implement credential encryption (config/crypto.py)
- [ ] Write crypto tests
- [ ] Implement ConfigManager (config/manager.py)
- [ ] Write ConfigManager tests

**Day 4: Feed Management - Backend**
- [ ] Implement RSS parser (feeds/parser.py)
- [ ] Implement feed models (feeds/models.py)
- [ ] Implement feed validator (feeds/validator.py)
- [ ] Write feed tests with fixtures
- [x] ~~Implement FeedManager~~ (Not needed - ConfigManager handles feed operations)

**Day 5: CLI Commands**
- [ ] Implement main CLI entry point (cli.py)
- [ ] Implement `add` command
- [ ] Implement `list` command
- [ ] Implement `remove` command
- [ ] Implement `config` commands
- [ ] Write CLI integration tests

**Day 6: Polish & Error Handling**
- [ ] Add comprehensive error messages
- [ ] Add logging throughout
- [ ] Add rich output formatting
- [ ] Add command-line help text
- [ ] Test error scenarios

**Day 7: Documentation & Testing**
- [ ] Write README with installation and usage
- [ ] Add docstrings to all public functions
- [ ] Ensure 90%+ test coverage
- [ ] Create example config files
- [ ] Manual end-to-end testing
- [ ] Create ADR for significant decisions made

---

## Quality Gates

### Before Considering Phase 1 Complete:

**Functionality:**
- [ ] Can add feeds with all auth types (none, basic, bearer)
- [ ] Can list feeds with rich table output
- [ ] Can remove feeds with confirmation
- [ ] Can modify config via CLI
- [ ] Config stored in XDG-compliant paths
- [ ] Credentials properly encrypted

**Code Quality:**
- [ ] All tests passing
- [ ] 90%+ test coverage
- [ ] No mypy errors
- [ ] No ruff warnings
- [ ] Pre-commit hooks passing

**User Experience:**
- [ ] Clear, helpful error messages
- [ ] Rich terminal output (colors, tables)
- [ ] `--help` text is comprehensive
- [ ] Works on Linux and macOS
- [ ] Installation via pip works

**Documentation:**
- [ ] README has installation instructions
- [ ] README has usage examples
- [ ] All public APIs have docstrings
- [ ] DKS updated (devlogs, ADRs created)

---

## Key Decisions & ADRs to Create

**ADR-002: Config Management Strategy**
- Decision: XDG Base Directory + YAML + Pydantic
- Alternatives considered: TOML, JSON, INI
- Rationale: YAML human-friendly, Pydantic validation, XDG compliance

**ADR-003: Credential Encryption Approach**
- Decision: Fernet symmetric encryption
- Alternatives: System keyring, plaintext (rejected)
- Rationale: Balance security and simplicity, no external deps

**ADR-004: CLI Framework Selection**
- Decision: Typer (already in PRD)
- Rationale: Modern, type-safe, rich integration

---

## Open Questions for User

1. **Package Distribution**: Should we publish to PyPI immediately or wait until v0.1 is complete?

2. **System Keyring**: Should we support OS keyrings (macOS Keychain, Secret Service API) in Phase 1 or defer to Phase 2?

3. **Config Migration**: How should we handle config version upgrades in the future?

4. **Error Reporting**: Should we add telemetry/crash reporting (opt-in) or keep it fully offline?

5. **Testing on Windows**: PRD doesn't mention Windows - should we support it?

---

## Success Criteria

Phase 1 is complete when:
1. A user can install inkwell via pip
2. A user can add/list/remove feeds including private feeds
3. All credentials are encrypted at rest
4. Configuration is validated and provides clear errors
5. Code is tested, typed, and linted
6. Documentation allows a new user to get started in <5 minutes

---

## Next Steps

After Phase 1:
- **Phase 2**: Transcription (YouTube API + Gemini fallback)
- **Phase 3**: LLM extraction pipeline
- **Phase 4**: Interview mode
- **Phase 5**: Obsidian integration

---

## Notes

- This plan is intentionally detailed to avoid ambiguity during implementation
- Each module is designed to be independently testable
- Security is prioritized (encrypted credentials, proper permissions)
- User experience is prioritized (rich output, helpful errors)
- Code quality is enforced via tooling (ruff, mypy, pre-commit)
- Following DKS: This devlog will be updated as implementation progresses
