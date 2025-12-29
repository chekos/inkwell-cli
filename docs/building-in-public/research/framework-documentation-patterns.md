# Framework Documentation Patterns Research

**Date**: 2025-11-14
**Author**: Claude Code (Framework Documentation Researcher)
**Status**: Complete
**Related ADRs**: None yet
**Context**: Research documentation best practices for the specific frameworks/libraries used in inkwell-cli

## Executive Summary

This research document consolidates documentation patterns and best practices for the core frameworks and libraries used in inkwell-cli: Typer (CLI), Rich (Terminal UI), Pydantic V2 (Data Models), Anthropic SDK (LLM), Google Generative AI (LLM), and Python packaging standards. These patterns should guide all documentation efforts across the project.

**Key Finding**: Modern Python documentation emphasizes three layers:
1. **Code-level documentation** (docstrings, type hints, field descriptions)
2. **User-facing documentation** (READMEs, tutorials, guides)
3. **API documentation** (auto-generated from docstrings)

## 1. Typer CLI Documentation Patterns

### 1.1 Official Documentation

**Primary Resource**: https://typer.tiangolo.com/
**GitHub**: https://github.com/fastapi/typer
**Version Used**: typer[all]>=0.12.0

### 1.2 Key Patterns

#### 1.2.1 Command Help with Docstrings

Typer automatically uses function docstrings for command help text:

```python
@app.command("add")
def add_feed(
    url: str = typer.Argument(..., help="RSS feed URL"),
    name: str = typer.Option(..., "--name", "-n", help="Feed identifier name"),
) -> None:
    """Add a new podcast feed.

    This command registers a new podcast RSS feed for processing.
    You can optionally provide authentication credentials for private feeds.

    Examples:
        inkwell add https://example.com/feed.rss --name my-podcast

        inkwell add https://private.com/feed.rss --name private --auth
    """
    pass
```

**Best Practices**:
- Use function docstring for command-level description
- Use `help` parameter for argument/option descriptions
- Include practical examples in docstring
- Keep argument help text concise (1 line)
- Use longer descriptions in docstring

#### 1.2.2 Application-Level Help

```python
app = typer.Typer(
    name="inkwell",
    help="Transform podcast episodes into structured markdown notes",
    no_args_is_help=True,
)
```

**Best Practices**:
- Provide clear, concise app-level help
- Set `no_args_is_help=True` for better UX
- Use `add_typer()` to organize commands into groups

#### 1.2.3 Rich Markup in Help Text (Typer 0.12+)

```python
app = typer.Typer(
    name="inkwell",
    rich_markup_mode="rich",  # Enable Rich formatting
)

@app.command()
def process() -> None:
    """Process episodes with [bold cyan]LLM extraction[/bold cyan].

    This command supports:
    - [green]YouTube transcription[/green] (free)
    - [yellow]Gemini transcription[/yellow] (paid)
    - [blue]Claude extraction[/blue] (premium)
    """
    pass
```

**Best Practices**:
- Use Rich markup for emphasis and color
- Use console markup syntax: `[bold red]text[/bold red]`
- Keep formatting subtle and purposeful
- Test help output with `--help`

#### 1.2.4 Modern Annotated Syntax

```python
from typing import Annotated

@app.command()
def fetch(
    feed_name: Annotated[str, typer.Argument(help="Feed identifier")],
    latest: Annotated[bool, typer.Option("--latest", help="Process latest episode")] = False,
    count: Annotated[int, typer.Option("--count", "-c", help="Number of episodes")] = 1,
) -> None:
    """Fetch and process episodes."""
    pass
```

**Best Practices**:
- Prefer `Annotated` syntax for cleaner code
- Combine with type hints for better IDE support
- Use descriptive variable names
- Keep default values explicit

### 1.3 Auto-Documentation

Typer provides `typer utils docs` command to generate markdown documentation:

```bash
typer src/inkwell/cli.py utils docs --name inkwell --output docs/cli-reference.md
```

**Best Practices**:
- Generate CLI reference documentation automatically
- Keep generated docs in sync with code
- Supplement with hand-written guides
- Include in documentation build process

### 1.4 References

- **Tutorial - Command Help**: https://typer.tiangolo.com/tutorial/commands/help/
- **Tutorial - Argument Help**: https://typer.tiangolo.com/tutorial/arguments/help/
- **Rich Markup**: https://typer.tiangolo.com/tutorial/commands/help/#rich-markup
- **GitHub Examples**: https://github.com/fastapi/typer/blob/master/README.md

---

## 2. Rich Terminal UI Documentation

### 2.1 Official Documentation

**Primary Resource**: https://rich.readthedocs.io/
**GitHub**: https://github.com/Textualize/rich
**Version Used**: rich>=14.2.0

### 2.2 Key Patterns

#### 2.2.1 Console Documentation

```python
from rich.console import Console

console = Console()

def display_results(episodes: list[Episode]) -> None:
    """Display processing results in a formatted table.

    Uses Rich Console to render a table with episode information,
    including status indicators and cost summaries.

    Args:
        episodes: List of processed episodes

    Note:
        This function uses Rich markup for colored output:
        - [green] for success
        - [yellow] for warnings
        - [red] for errors
    """
    table = Table(title="Processing Results")
    table.add_column("Episode", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Cost", justify="right", style="yellow")

    for ep in episodes:
        table.add_row(ep.title, "[green]✓[/green]", f"${ep.cost:.4f}")

    console.print(table)
```

**Best Practices**:
- Document Rich markup usage in docstrings
- Note color schemes and their meanings
- Explain table structure and columns
- Document any custom styling

#### 2.2.2 Progress Indicators

```python
from rich.progress import Progress, SpinnerColumn, TextColumn

def process_with_progress(items: list[str]) -> None:
    """Process items with progress indication.

    Displays a spinner and status text while processing each item.
    Uses Rich Progress for better UX during long-running operations.

    Args:
        items: List of items to process

    Example:
        >>> process_with_progress(["item1", "item2"])
        ⠸ Processing item1...
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        task = progress.add_task("Processing...", total=len(items))
        for item in items:
            # Process item
            progress.update(task, advance=1, description=f"Processing {item}...")
```

**Best Practices**:
- Document progress indicator behavior
- Show example output in docstrings
- Explain spinner vs. progress bar usage
- Document task description format

#### 2.2.3 Console Markup

```python
def show_error(message: str) -> None:
    """Display error message with Rich formatting.

    Renders error messages with red background and bold text
    for high visibility in terminal output.

    Args:
        message: Error message to display

    Example:
        >>> show_error("Invalid API key")
        [bold red on white] ERROR [/] Invalid API key
    """
    console.print(f"[bold red on white] ERROR [/] {message}")
```

**Best Practices**:
- Document markup syntax used
- Show example output
- Explain color choices
- Note accessibility considerations

### 2.3 References

- **Introduction**: https://rich.readthedocs.io/en/stable/introduction.html
- **Console API**: https://rich.readthedocs.io/en/stable/console.html
- **Console Markup**: https://rich.readthedocs.io/en/stable/markup.html
- **Progress**: https://rich.readthedocs.io/en/stable/progress.html
- **Tables**: https://rich.readthedocs.io/en/stable/tables.html
- **Real Python Tutorial**: https://realpython.com/python-rich-package/

---

## 3. Pydantic V2 Model Documentation

### 3.1 Official Documentation

**Primary Resource**: https://docs.pydantic.dev/latest/
**Version Used**: pydantic>=2.0.0, pydantic-settings>=2.0.0

### 3.2 Key Patterns

#### 3.2.1 Model-Level Documentation

```python
from pydantic import BaseModel, Field

class FeedConfig(BaseModel):
    """Configuration for a single podcast feed.

    This model stores all metadata and settings for a podcast RSS feed,
    including authentication credentials (encrypted at rest) and custom
    processing preferences.

    Attributes:
        url: RSS feed URL (validated as HttpUrl)
        auth: Authentication configuration (defaults to no auth)
        category: Optional category for organization (e.g., "tech", "interview")
        custom_templates: List of custom template names to use

    Example:
        >>> config = FeedConfig(
        ...     url="https://example.com/feed.rss",
        ...     category="tech"
        ... )
        >>> config.url
        HttpUrl('https://example.com/feed.rss')
    """

    url: HttpUrl
    auth: AuthConfig = Field(default_factory=AuthConfig)
    category: str | None = None
    custom_templates: list[str] = Field(default_factory=list)
```

**Best Practices**:
- Use class docstring for model overview
- List all attributes with descriptions
- Include usage examples
- Note validation behavior
- Explain field defaults

#### 3.2.2 Field-Level Documentation

```python
class ObsidianConfig(BaseModel):
    """Obsidian integration configuration.

    Controls all Obsidian-specific features including wikilinks,
    tags, and Dataview frontmatter generation.
    """

    wikilinks_enabled: bool = Field(
        default=True,
        description="Enable automatic wikilink generation for entities (books, people, concepts)"
    )

    wikilink_style: Literal["simple", "prefixed"] = Field(
        default="simple",
        description="Wikilink format: [[Name]] (simple) or [[Type - Name]] (prefixed)"
    )

    min_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold (0.0-1.0) for entity extraction",
    )

    max_entities_per_type: int = Field(
        default=10,
        gt=0,
        description="Maximum number of entities to extract per type to avoid clutter",
    )
```

**Best Practices**:
- Use `Field(description=...)` for all fields
- Include value ranges and constraints
- Explain the purpose and impact of each field
- Use `ge`, `le`, `gt`, `lt` for numeric constraints
- Document default values and their rationale

#### 3.2.3 Field Examples

```python
class ExtractionTemplate(BaseModel):
    """Template for LLM-based content extraction.

    Defines the structure, prompt, and validation rules for extracting
    specific types of content from podcast transcripts.
    """

    name: str = Field(
        description="Unique template identifier (e.g., 'summary', 'quotes')",
        examples=["summary", "quotes", "key-concepts"],
    )

    prompt: str = Field(
        description="LLM prompt template with {transcript} placeholder",
        examples=[
            "Summarize this podcast transcript: {transcript}",
            "Extract key quotes from: {transcript}",
        ],
    )

    max_tokens: int = Field(
        default=2000,
        ge=100,
        le=100000,
        description="Maximum tokens for LLM response (100-100000)",
        examples=[1000, 2000, 4000],
    )
```

**Best Practices**:
- Use `examples` parameter for field values
- Provide multiple example variations
- Show realistic, practical examples
- Examples appear in JSON schema

#### 3.2.4 Settings Models (pydantic-settings)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class GlobalConfig(BaseSettings):
    """Global Inkwell configuration.

    Loads configuration from multiple sources in priority order:
    1. Environment variables (INKWELL_*)
    2. .env file
    3. Config file (~/.config/inkwell/config.yaml)
    4. Default values

    Environment variables are case-insensitive and prefixed with INKWELL_.

    Example:
        # Set via environment
        export INKWELL_LOG_LEVEL=DEBUG
        export INKWELL_DEFAULT_PROVIDER=claude

        # Or in .env file
        INKWELL_LOG_LEVEL=DEBUG
        INKWELL_DEFAULT_PROVIDER=claude

        # Or in config.yaml
        log_level: DEBUG
        default_provider: claude
    """

    model_config = SettingsConfigDict(
        env_prefix="INKWELL_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: LogLevel = Field(
        default="INFO",
        description="Logging verbosity: DEBUG, INFO, WARNING, ERROR",
    )

    default_provider: Literal["gemini", "claude"] = Field(
        default="gemini",
        description="Default LLM provider for extraction",
    )

    gemini_api_key: str | None = Field(
        default=None,
        description="Google Gemini API key (can also use GOOGLE_API_KEY env var)",
        alias="GOOGLE_API_KEY",  # Allow both naming conventions
    )
```

**Best Practices**:
- Document settings loading priority
- Explain environment variable naming
- Show examples for all config methods
- Use `alias` for alternative env var names
- Document `model_config` settings
- Note case sensitivity behavior

#### 3.2.5 Validation Error Documentation

```python
from pydantic import field_validator, ValidationError

class FeedConfig(BaseModel):
    """Configuration for a single podcast feed."""

    url: HttpUrl
    category: str | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        """Validate category is lowercase and alphanumeric.

        Categories are used for organization and filtering, so we enforce
        a consistent format to avoid issues with file paths and queries.

        Args:
            v: Category value to validate

        Returns:
            Validated (lowercase) category or None

        Raises:
            ValueError: If category contains invalid characters

        Example:
            >>> FeedConfig(url="https://example.com", category="Tech")
            FeedConfig(url='https://example.com', category='tech')

            >>> FeedConfig(url="https://example.com", category="Tech & AI")
            ValidationError: Category must be alphanumeric...
        """
        if v is None:
            return v

        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Category must be alphanumeric (letters, numbers, hyphens, underscores)"
            )

        return v.lower()
```

**Best Practices**:
- Document validators with docstrings
- Explain validation rules and rationale
- Show valid and invalid examples
- Document all raised exceptions
- Include example error messages

### 3.3 JSON Schema Generation

Pydantic V2 automatically generates JSON schemas from models:

```python
# Generate schema
schema = FeedConfig.model_json_schema()

# Schema includes:
# - Field descriptions
# - Field examples
# - Validation constraints (min/max, regex, etc.)
# - Required vs optional fields
# - Default values
```

**Documentation Strategy**:
- Field descriptions become schema descriptions
- Examples appear in schema examples
- Constraints are automatically documented
- Use for API documentation generation

### 3.4 References

- **Models**: https://docs.pydantic.dev/latest/concepts/models/
- **Fields**: https://docs.pydantic.dev/latest/concepts/fields/
- **Settings Management**: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **JSON Schema**: https://docs.pydantic.dev/latest/concepts/json_schema/
- **Validation**: https://docs.pydantic.dev/latest/concepts/validators/

---

## 4. LLM Integration Documentation

### 4.1 Anthropic SDK (Claude)

**Primary Resource**: https://docs.anthropic.com/
**GitHub**: https://github.com/anthropics/anthropic-sdk-python
**Version Used**: anthropic>=0.72.0

#### 4.1.1 API Client Documentation

```python
from anthropic import Anthropic, APIError

class ClaudeExtractor:
    """LLM content extractor using Anthropic Claude.

    This extractor uses Claude Sonnet 4.5 for content extraction from
    podcast transcripts. It supports streaming responses and automatic
    retry logic for transient failures.

    API Costs (as of 2025-11):
        - Claude Sonnet 4.5:
            - Input: $3.00 per 1M tokens
            - Output: $15.00 per 1M tokens
        - Claude Haiku 4:
            - Input: $0.80 per 1M tokens
            - Output: $4.00 per 1M tokens

    Rate Limits:
        - Free tier: 50 requests/day
        - Tier 1: 50 requests/minute, 40,000 tokens/minute
        - Tier 2: 1,000 requests/minute, 80,000 tokens/minute

    Retry Logic:
        - Automatic retry for: 408, 409, 429, >=500 errors
        - Default: 2 retries with exponential backoff
        - Custom retry via httpx client configuration

    Environment Variables:
        - ANTHROPIC_API_KEY: Required API key
        - ANTHROPIC_LOG: Set to 'debug' for detailed logging

    Example:
        >>> extractor = ClaudeExtractor(api_key="sk-...")
        >>> result = extractor.extract(
        ...     template=template,
        ...     transcript=transcript
        ... )
        >>> print(f"Cost: ${result.cost:.4f}")
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        """Initialize Claude extractor.

        Args:
            api_key: Anthropic API key
            model: Model identifier (default: claude-sonnet-4-5)

        Raises:
            APIKeyError: If API key is invalid or missing
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model
```

**Best Practices**:
- Document API costs prominently
- Include rate limits and tiers
- Document retry behavior
- List required environment variables
- Show cost estimation examples
- Document error types and handling

#### 4.1.2 Prompt Template Documentation

```python
class PromptTemplate(BaseModel):
    """LLM prompt template for content extraction.

    Templates use {transcript} placeholder for the podcast transcript
    and support optional {context} for additional information.

    Prompt Engineering Guidelines:
        - Be specific about desired output format
        - Include examples when possible
        - Use clear, concise instructions
        - Specify constraints (length, style, etc.)
        - Request structured output (JSON, markdown, etc.)

    Cost Optimization:
        - Keep prompts concise (fewer input tokens)
        - Use efficient output formats (JSON vs prose)
        - Request specific information (avoid "tell me everything")
        - Use caching for repeated prompts (Claude only)

    Example:
        >>> template = PromptTemplate(
        ...     name="summary",
        ...     prompt='''
        ...     Summarize this podcast transcript in 3-5 sentences.
        ...     Focus on the main topics and key takeaways.
        ...
        ...     Transcript:
        ...     {transcript}
        ...
        ...     Format your response as markdown.
        ...     '''
        ... )
    """

    name: str = Field(description="Template identifier")
    prompt: str = Field(description="Prompt with {transcript} placeholder")
    max_tokens: int = Field(
        default=2000,
        description="Maximum output tokens (affects cost)"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Sampling temperature (0.0=deterministic, 1.0=creative)"
    )
```

**Best Practices**:
- Document prompt placeholders
- Include prompt engineering guidelines
- Document cost optimization strategies
- Show example prompts
- Explain temperature and sampling parameters

### 4.2 Google Generative AI (Gemini)

**Primary Resource**: https://ai.google.dev/docs
**Version Used**: google-generativeai>=0.8.5

#### 4.2.1 API Documentation

```python
import google.generativeai as genai

class GeminiExtractor:
    """LLM content extractor using Google Gemini.

    This extractor uses Gemini 2.0 Flash for content extraction.
    Gemini is the default provider due to lower costs and higher rate limits.

    API Costs (as of 2025-11):
        - Gemini 2.0 Flash:
            - Input: $0.075 per 1M tokens (≤128K context)
            - Input: $0.15 per 1M tokens (>128K context)
            - Output: $0.30 per 1M tokens
        - Gemini 1.5 Pro:
            - Input: $1.25 per 1M tokens
            - Output: $5.00 per 1M tokens

    Rate Limits:
        - Free tier: 15 requests/minute, 1M tokens/minute
        - Paid tier: 1,000 requests/minute, 4M tokens/minute

    Context Windows:
        - Flash: 1M tokens
        - Pro: 2M tokens

    Safety Settings:
        - Default: BLOCK_MEDIUM_AND_ABOVE for all categories
        - Configurable per request
        - Categories: HARM_CATEGORY_HARASSMENT, HATE_SPEECH,
                     SEXUALLY_EXPLICIT, DANGEROUS_CONTENT

    Example:
        >>> extractor = GeminiExtractor(api_key="...")
        >>> result = extractor.extract(template, transcript)
        >>> print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
        >>> print(f"Cost: ${result.cost:.4f}")
    """

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        """Initialize Gemini extractor.

        Args:
            api_key: Google AI API key
            model: Model identifier (default: gemini-2.0-flash-exp)

        Raises:
            APIKeyError: If API key is invalid
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
```

**Best Practices**:
- Document pricing tiers clearly
- Note context window sizes
- Document safety settings
- Show token usage tracking
- Compare with alternative models

### 4.3 Cost Estimation Documentation

```python
def estimate_cost(
    input_text: str,
    template: ExtractionTemplate,
    provider: Literal["gemini", "claude"] = "gemini"
) -> CostEstimate:
    """Estimate LLM API cost before making request.

    Calculates estimated cost based on input tokens (text + prompt)
    and expected output tokens (from template.max_tokens).

    Token Estimation:
        - Uses tiktoken for accurate token counting
        - Accounts for prompt template overhead
        - Adds safety margin (10%) for variability

    Cost Calculation:
        - Input cost = input_tokens * input_price_per_token
        - Output cost = output_tokens * output_price_per_token
        - Total = input_cost + output_cost

    Pricing Data:
        - Updated monthly from provider websites
        - Stored in src/inkwell/utils/costs.py
        - Version-controlled for audit trail

    Args:
        input_text: Text to process (e.g., podcast transcript)
        template: Extraction template with prompt and max_tokens
        provider: LLM provider ('gemini' or 'claude')

    Returns:
        CostEstimate with min/max/expected cost range

    Example:
        >>> estimate = estimate_cost(transcript, summary_template, "gemini")
        >>> print(f"Estimated cost: ${estimate.expected:.4f}")
        >>> print(f"Range: ${estimate.min:.4f} - ${estimate.max:.4f}")
        >>>
        >>> # Check before proceeding
        >>> if estimate.expected > 0.10:
        ...     if not confirm(f"This will cost ~${estimate.expected:.4f}. Continue?"):
        ...         return
    """
    pass
```

**Best Practices**:
- Document estimation methodology
- Show estimation accuracy notes
- Include pricing data source
- Provide cost ranges (min/max/expected)
- Show example cost checks
- Document pricing update process

### 4.4 References

- **Anthropic Docs**: https://docs.anthropic.com/
- **Anthropic Python SDK**: https://github.com/anthropics/anthropic-sdk-python
- **Google AI Docs**: https://ai.google.dev/docs
- **Gemini API Python**: https://ai.google.dev/tutorials/python_quickstart
- **LLM Pricing Comparison**: https://research.aimultiple.com/llm-pricing/
- **Cost Tracking Best Practices**: https://www.finops.org/wg/cost-estimation-of-ai-workloads/

---

## 5. Python Package Documentation

### 5.1 pyproject.toml Documentation

**Primary Resource**: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
**PEP 621**: https://peps.python.org/pep-0621/

#### 5.1.1 Project Metadata

```toml
[project]
name = "inkwell-cli"
version = "1.0.0"
description = "Transform podcast episodes into structured markdown notes"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Inkwell Contributors"}
]

# PyPI classifiers for discoverability
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Multimedia :: Sound/Audio",
    "Topic :: Text Processing :: Markup :: Markdown",
    "Environment :: Console",
    "Operating System :: OS Independent",
]

# Project URLs for PyPI
[project.urls]
Homepage = "https://github.com/your-username/inkwell-cli"
Documentation = "https://inkwell-cli.readthedocs.io"
Repository = "https://github.com/your-username/inkwell-cli"
Issues = "https://github.com/your-username/inkwell-cli/issues"
Changelog = "https://github.com/your-username/inkwell-cli/blob/main/CHANGELOG.md"
```

**Best Practices**:
- Use semantic versioning (MAJOR.MINOR.PATCH)
- Include all supported Python versions in classifiers
- Add relevant topic classifiers for PyPI search
- Provide comprehensive project URLs
- Keep README.md as the readme source
- Use SPDX license identifiers (PEP 639)

#### 5.1.2 Dependencies Documentation

```toml
[project]
dependencies = [
    # Core framework
    "typer[all]>=0.12.0",      # CLI framework with Rich support
    "pyyaml>=6.0",             # Config file parsing

    # Data validation
    "pydantic>=2.0.0",         # Data models and validation
    "pydantic-settings>=2.0.0", # Settings from env/files

    # HTTP and security
    "httpx>=0.27.0",           # Modern HTTP client
    "cryptography>=42.0.0",    # Credential encryption

    # Podcast processing
    "feedparser>=6.0.0",       # RSS/Atom feed parsing
    "yt-dlp>=2025.10.22",      # Audio download
    "youtube-transcript-api>=1.2.3", # YouTube transcript extraction

    # LLM APIs
    "google-generativeai>=0.8.5", # Gemini API
    "anthropic>=0.72.0",       # Claude API

    # Utilities
    "tenacity>=9.1.2",         # Retry logic with backoff
    "platformdirs>=4.0.0",     # XDG base directories
    "aiofiles>=23.2.0",        # Async file operations
    "regex>=2023.12.25",       # Advanced regex support
]

[project.optional-dependencies]
dev = [
    # Testing
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "pytest-asyncio>=0.23.0",
    "respx>=0.20.0",           # HTTPX mocking

    # Code quality
    "ruff>=0.3.0",             # Linting and formatting
    "mypy>=1.8.0",             # Type checking
    "pre-commit>=3.6.0",       # Git hooks

    # Type stubs
    "types-pyyaml",
]

# Alternative: uv dependency groups
[dependency-groups]
dev = [
    "pytest>=8.4.2",
    "pytest-asyncio>=1.2.0",
    "respx>=0.22.0",
    "ruff>=0.14.4",
    "mkdocs>=1.6.1",           # Documentation
    "mkdocs-material>=9.6.23", # Material theme
]
```

**Best Practices**:
- Add inline comments explaining each dependency's purpose
- Group dependencies logically (framework, data, HTTP, etc.)
- Use version constraints appropriately:
  - `>=` for minimum version requirements
  - `~=` for compatible releases (e.g., `~=1.2.0` = `>=1.2.0, <1.3.0`)
  - `==` only for exact pinning (rare)
- Separate development dependencies
- Document why specific versions are required
- Keep dependencies minimal (avoid bloat)

#### 5.1.3 Entry Points

```toml
[project.scripts]
# Creates `inkwell` command that runs src/inkwell/cli.py:app
inkwell = "inkwell.cli:app"

[project.entry-points."mkdocs.plugins"]
# Example: Register MkDocs plugins (if creating one)
# inkwell-docs = "inkwell.docs.plugin:InkwellPlugin"
```

**Best Practices**:
- Use clear, memorable command names
- Document the module and function/object being called
- Consider namespace conflicts (check PyPI)
- Include in usage documentation

### 5.2 README Documentation

**Best Practices** (from inkwell-cli README.md):

1. **Clear Value Proposition**
   - One-line description
   - Vision statement
   - Key benefits upfront

2. **Quick Start Section**
   - Installation (copy-paste ready)
   - API key setup
   - First working example
   - Expected output

3. **Feature Showcase**
   - Visual hierarchy (headers, bullets)
   - Code examples for each feature
   - Screenshots or example output
   - Cost information (for LLM tools)

4. **Documentation Links**
   - Separate user vs developer docs
   - Tutorial for beginners
   - Reference for advanced users
   - Examples and workflows

5. **Technical Details**
   - Requirements (Python version, system deps)
   - Configuration options
   - Architecture overview
   - Project structure

6. **Development Section**
   - Setup instructions
   - Running tests
   - Code quality tools
   - Contributing guidelines

7. **Maintenance Info**
   - License
   - Acknowledgments
   - Support channels
   - Roadmap

**Structure Template**:

```markdown
# Project Name

One-line description

> Vision: Longer vision statement

## Status

Current version and stability

## Quick Start

### Installation
[3-5 lines max]

### First Example
[Working example with output]

## Features

### Feature 1
[Description + code example]

### Feature 2
[Description + code example]

## Documentation

- [Tutorial](link)
- [User Guide](link)
- [API Reference](link)

## Requirements

- Python version
- System dependencies
- API keys

## Configuration

[Config options and locations]

## Development

[Setup and testing]

## License

[License name and link]
```

### 5.3 MkDocs Documentation Structure

**Primary Resource**: https://www.mkdocs.org/
**Material Theme**: https://squidfunk.github.io/mkdocs-material/

#### 5.3.1 Project Structure

```
docs/
├── index.md              # Homepage (generated from README)
├── tutorial.md           # Getting started guide
├── user-guide.md         # Complete reference
├── examples.md           # Use cases and workflows
├── api/                  # API reference (auto-generated)
│   ├── cli.md
│   ├── config.md
│   └── ...
├── adr/                  # Architecture decisions
│   └── *.md
├── lessons/              # Lessons learned
│   └── *.md
└── assets/               # Images, CSS, etc.
    └── images/
```

#### 5.3.2 mkdocs.yml Configuration

```yaml
site_name: Inkwell CLI
site_description: Transform podcast episodes into structured markdown notes
site_url: https://inkwell-cli.readthedocs.io
repo_url: https://github.com/your-username/inkwell-cli
repo_name: inkwell-cli

theme:
  name: material
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy

plugins:
  - search
  - mkdocstrings:  # Auto-generate API docs from docstrings
      handlers:
        python:
          paths: [src]
          options:
            docstring_style: google
            show_source: true
  - mkdocs-material-adr:  # ADR support
      adr_folder: docs/adr

nav:
  - Home: index.md
  - Getting Started:
    - Tutorial: tutorial.md
    - Installation: installation.md
  - User Guide:
    - Overview: user-guide.md
    - CLI Reference: cli-reference.md
    - Configuration: configuration.md
    - Examples: examples.md
  - API Reference:
    - CLI: api/cli.md
    - Config: api/config.md
    - Extraction: api/extraction.md
  - Developer Guide:
    - Architecture: architecture.md
    - ADRs: adr/
    - Lessons Learned: lessons/

markdown_extensions:
  - admonition
  - codehilite
  - pymdownx.highlight
  - pymdownx.superfences
  - pymdownx.tabbed
  - toc:
      permalink: true
```

**Best Practices**:
- Use Material theme for modern UI
- Enable code copy buttons
- Use mkdocstrings for API docs
- Organize navigation logically
- Include search functionality
- Link to GitHub repository

#### 5.3.3 API Documentation with mkdocstrings

```markdown
<!-- docs/api/cli.md -->

# CLI Reference

::: inkwell.cli
    options:
      show_source: true
      heading_level: 2

## Commands

### add

::: inkwell.cli.add_feed
    options:
      show_source: false
      heading_level: 3

### fetch

::: inkwell.cli.fetch_episodes
    options:
      show_source: false
      heading_level: 3
```

This auto-generates documentation from docstrings in the code.

**Best Practices**:
- Use Google or NumPy docstring style
- Set `show_source: true` for reference
- Organize by module and function
- Include examples in docstrings
- Cross-reference between pages

### 5.4 References

- **Python Packaging Guide**: https://packaging.python.org/
- **pyproject.toml Spec**: https://packaging.python.org/en/latest/specifications/pyproject-toml/
- **PEP 621** (Project Metadata): https://peps.python.org/pep-0621/
- **PEP 639** (License Field): https://peps.python.org/pep-0639/
- **MkDocs**: https://www.mkdocs.org/
- **MkDocs Material**: https://squidfunk.github.io/mkdocs-material/
- **mkdocstrings**: https://mkdocstrings.github.io/
- **Python Package Guide (pyOpenSci)**: https://www.pyopensci.org/python-package-guide/

---

## 6. Cross-Cutting Documentation Patterns

### 6.1 Code-Level Documentation Standards

#### 6.1.1 Module Docstrings

```python
"""Module name and purpose.

Longer description of what this module does, what problems it solves,
and how it fits into the larger system architecture.

Key Components:
    - ClassName1: Brief description
    - ClassName2: Brief description
    - function_name: Brief description

Example:
    Basic usage example showing the most common use case::

        from module import ClassName
        obj = ClassName()
        result = obj.method()

See Also:
    - Related module 1
    - Related module 2

Note:
    Any important notes about the module, such as:
    - Thread safety
    - Performance considerations
    - Known limitations
"""
```

#### 6.1.2 Function/Method Docstrings (Google Style)

```python
def extract_content(
    transcript: str,
    template: ExtractionTemplate,
    provider: Literal["gemini", "claude"] = "gemini",
) -> ExtractionResult:
    """Extract structured content from podcast transcript using LLM.

    Uses template-based prompts to extract specific information (quotes,
    concepts, etc.) from transcripts. Supports multiple LLM providers with
    automatic retry and cost tracking.

    Args:
        transcript: Full podcast transcript text
        template: Extraction template with prompt and settings
        provider: LLM provider to use ('gemini' or 'claude')

    Returns:
        ExtractionResult containing:
            - content: Extracted text in markdown format
            - input_tokens: Number of input tokens used
            - output_tokens: Number of output tokens generated
            - cost: Total API cost in USD
            - provider: Provider used for extraction
            - model: Specific model used

    Raises:
        APIKeyError: If API key is missing or invalid
        RateLimitError: If rate limit is exceeded (automatic retry)
        ExtractionError: If extraction fails after retries

    Example:
        >>> template = TemplateLoader().load_template("summary")
        >>> result = extract_content(transcript, template, "gemini")
        >>> print(f"Cost: ${result.cost:.4f}")
        Cost: $0.0042
        >>> print(result.content)
        # Episode Summary
        This episode discusses...

    Note:
        - Uses exponential backoff for retries (3 attempts)
        - Costs vary by provider and model (see cost tracking docs)
        - Results are not cached (use TranscriptionManager for caching)

    See Also:
        - :func:`estimate_cost`: Estimate cost before extraction
        - :class:`ExtractionTemplate`: Template structure
        - :class:`ExtractionResult`: Result structure
    """
    pass
```

**Best Practices**:
- Use Google style (Args/Returns/Raises)
- Include practical examples
- Document return value structure
- List all exceptions
- Add "See Also" for related functions
- Include notes for important caveats

#### 6.1.3 Class Docstrings

```python
class TranscriptionManager:
    """Manage podcast transcription with multi-tier fallback strategy.

    Orchestrates transcription using a cost-optimized approach:
    1. Check local cache (free)
    2. Try YouTube transcript API (free)
    3. Fall back to Gemini transcription (paid)

    All transcripts are cached locally with 30-day TTL to minimize costs.

    Attributes:
        cache_dir: Path to transcript cache directory
        cache_ttl_days: Cache time-to-live in days (default: 30)
        youtube_client: YouTube transcript API client
        gemini_client: Gemini API client for audio transcription

    Example:
        >>> manager = TranscriptionManager()
        >>> result = await manager.get_transcript(episode)
        >>> print(f"Source: {result.source}")
        Source: youtube
        >>> print(f"Cost: ${result.cost:.4f}")
        Cost: $0.0000

    Thread Safety:
        This class is not thread-safe. Use separate instances per thread
        or implement external locking for concurrent access.

    Performance:
        - Cache hits: <10ms
        - YouTube API: 1-3 seconds
        - Gemini transcription: 30-60 seconds (depends on audio length)

    See Also:
        - :class:`YouTubeTranscriber`: YouTube transcript extraction
        - :class:`GeminiTranscriber`: Gemini audio transcription
        - :class:`TranscriptionCache`: Cache implementation
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl_days: int = 30,
    ):
        """Initialize transcription manager.

        Args:
            cache_dir: Custom cache directory (default: XDG cache)
            cache_ttl_days: Cache TTL in days (default: 30)
        """
        pass
```

**Best Practices**:
- Describe class purpose and responsibilities
- Explain key algorithms or strategies
- List important attributes
- Include usage examples
- Document thread safety
- Note performance characteristics

### 6.2 Documentation Maintenance

#### 6.2.1 Keeping Docs in Sync

1. **Use docstrings as source of truth**
   - Auto-generate API docs from docstrings (mkdocstrings)
   - Write comprehensive docstrings
   - Keep hand-written docs minimal

2. **Version documentation**
   - Tag docs with version numbers
   - Maintain changelog
   - Archive old versions

3. **Test examples in docs**
   - Use doctest for testable examples
   - Run examples in CI/CD
   - Keep examples simple and working

4. **Review docs in PRs**
   - Require doc updates for new features
   - Review docstring changes
   - Check for broken links

#### 6.2.2 Documentation Checklist

For new features:

- [ ] Module docstring updated
- [ ] Class/function docstrings added
- [ ] Type hints complete
- [ ] Examples included
- [ ] README.md updated (if user-facing)
- [ ] User guide updated
- [ ] API reference generated
- [ ] Changelog entry added
- [ ] ADR created (if architectural)

### 6.3 Common Pitfalls to Avoid

1. **Don't duplicate information**
   - Keep docstrings as source of truth
   - Reference docstrings from guides
   - Use "See Also" for cross-references

2. **Don't let docs get stale**
   - Update docs when code changes
   - Use automated checks
   - Review regularly

3. **Don't over-document**
   - Self-documenting code > comments
   - Focus on "why" not "what"
   - Remove outdated comments

4. **Don't ignore the user perspective**
   - Write for users, not yourself
   - Include practical examples
   - Test docs with new users

5. **Don't forget cost documentation (for LLM projects)**
   - Always document API costs
   - Show cost estimation examples
   - Include rate limits
   - Update pricing regularly

---

## 7. Recommendations for Inkwell-CLI

Based on this research, here are specific recommendations for improving inkwell-cli documentation:

### 7.1 Immediate Actions

1. **Enhance CLI help text**
   - Add Rich markup to key commands
   - Include more examples in docstrings
   - Use `Annotated` syntax throughout

2. **Document LLM costs prominently**
   - Add cost tables to README
   - Include pricing in API docstrings
   - Create cost optimization guide

3. **Improve Pydantic model docs**
   - Add `description` to all Fields
   - Include `examples` for complex fields
   - Document validation rules clearly

4. **Generate API documentation**
   - Set up MkDocs with Material theme
   - Configure mkdocstrings for API docs
   - Auto-generate from docstrings

### 7.2 Long-Term Improvements

1. **Create comprehensive user guide**
   - Tutorial (10 minutes, already done ✓)
   - User guide (reference, already done ✓)
   - Examples and workflows (already done ✓)
   - Troubleshooting guide (needed)
   - Cost optimization guide (needed)

2. **Build API reference**
   - Auto-generated from docstrings
   - Organized by module
   - Include examples
   - Cross-referenced

3. **Maintain documentation site**
   - Host on Read the Docs
   - Version documentation
   - Include search
   - Mobile-friendly

4. **Document LLM integration patterns**
   - Prompt engineering guide
   - Template creation guide
   - Cost optimization strategies
   - Error handling patterns

### 7.3 Documentation Priorities

**High Priority** (User-facing):
1. CLI help text and examples
2. README.md improvements
3. Cost documentation
4. Configuration guide
5. Troubleshooting guide

**Medium Priority** (Developer-facing):
1. API reference (auto-generated)
2. Architecture documentation
3. Contributing guide
4. Testing guide

**Low Priority** (Nice-to-have):
1. Video tutorials
2. Blog posts
3. Community templates
4. Case studies

---

## 8. Conclusion

Modern Python documentation requires a multi-layered approach:

1. **Code-level**: Comprehensive docstrings with type hints
2. **User-facing**: Clear guides, tutorials, and examples
3. **API reference**: Auto-generated from docstrings
4. **Maintenance**: Automated checks, versioning, regular updates

For LLM-powered tools like inkwell-cli, cost documentation is critical. Users need to understand:
- Pricing models and tiers
- Cost estimation before operations
- Optimization strategies
- Rate limits and quotas

The frameworks we use (Typer, Rich, Pydantic) all support modern documentation patterns:
- Typer: Automatic help from docstrings + Rich markup
- Rich: Self-documenting terminal UI
- Pydantic: Auto-generated JSON schemas from Field descriptions
- MkDocs: Auto-generated API docs from docstrings

**Next Steps**:
1. Review and enhance all module/class/function docstrings
2. Add Field descriptions to all Pydantic models
3. Set up MkDocs with Material theme
4. Create cost optimization guide
5. Generate and publish API reference

---

## References

### Official Documentation
- **Typer**: https://typer.tiangolo.com/
- **Rich**: https://rich.readthedocs.io/
- **Pydantic**: https://docs.pydantic.dev/
- **Anthropic**: https://docs.anthropic.com/
- **Google AI**: https://ai.google.dev/docs
- **Python Packaging**: https://packaging.python.org/

### Best Practices
- **Google Python Style Guide**: https://google.github.io/styleguide/pyguide.html
- **NumPy Docstring Guide**: https://numpydoc.readthedocs.io/
- **Real Python - Documenting Python Code**: https://realpython.com/documenting-python-code/
- **Write the Docs**: https://www.writethedocs.org/

### Tools
- **MkDocs**: https://www.mkdocs.org/
- **MkDocs Material**: https://squidfunk.github.io/mkdocs-material/
- **mkdocstrings**: https://mkdocstrings.github.io/
- **Sphinx**: https://www.sphinx-doc.org/ (alternative)
- **Read the Docs**: https://readthedocs.org/ (hosting)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Next Review**: 2025-12-14 (or when major framework updates occur)
