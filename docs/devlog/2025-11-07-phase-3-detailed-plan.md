# Phase 3 Detailed Implementation Plan - LLM Extraction Pipeline

**Date**: 2025-11-07
**Status**: Planning
**Phase**: 3 of 5
**Related**: [PRD_v0.md](../PRD_v0.md), [Phase 2 Complete](../PHASE_2_COMPLETE.md)

## Overview

Phase 3 adds the LLM extraction pipeline to Inkwell, transforming raw transcripts into structured, searchable markdown knowledge. This is the critical bridge between Phase 2 (transcription) and Phase 4 (interview mode). We implement a template-based extraction system with intelligent content categorization, multi-format output generation, and comprehensive metadata management.

**Key Principle**: After each unit of work, we pause to document lessons learned, experiments, research, and architectural decisions. Documentation is not an afterthought—it's an integral part of our development process that ensures accessibility and maintainability.

---

## Phase 3 Scope (from PRD)

**Core Requirements:**
- LLM extraction system using Claude/Gemini APIs
- Template-based content extraction
- Contextual template selection based on podcast category
- Markdown generation with proper formatting
- File output with episode directory structure

**Professional Grade Additions:**
- Template inheritance and composition
- Content validation and quality checks
- Flexible LLM provider abstraction (Claude, Gemini, local models)
- Batch extraction optimization
- Progress tracking for multi-template extraction
- Template debugging and preview modes
- Metadata extraction and cross-referencing
- Cost tracking and optimization
- Caching of extracted content

---

## Architecture Overview

### Extraction Flow

```
Transcript
    │
    ├─► Episode Analysis
    │     │
    │     ├─► Detect podcast category (tech, interview, general, etc.)
    │     ├─► Select applicable templates
    │     ├─► Extract episode metadata
    │     └─► Prepare context for LLM
    │
    ├─► Template Loading
    │     │
    │     ├─► Load default templates (summary, quotes, key-concepts)
    │     ├─► Load category-specific templates (tools-mentioned, books-mentioned)
    │     ├─► Load custom user templates
    │     └─► Resolve template inheritance
    │
    ├─► Content Extraction (per template)
    │     │
    │     ├─► Build prompt from template + transcript
    │     ├─► Call LLM API (Claude or Gemini)
    │     ├─► Parse structured response
    │     ├─► Validate extracted content
    │     ├─► Track costs and metrics
    │     └─► Cache result
    │
    ├─► Markdown Generation
    │     │
    │     ├─► Apply markdown formatting per template
    │     ├─► Generate frontmatter (YAML metadata)
    │     ├─► Apply output template (Jinja2)
    │     ├─► Validate markdown structure
    │     └─► Return formatted document
    │
    └─► File Output
          │
          ├─► Create episode directory (podcast-name-YYYY-MM-DD-title/)
          ├─► Write markdown files (summary.md, quotes.md, etc.)
          ├─► Write metadata file (.metadata.yaml)
          ├─► Generate index file (if configured)
          └─► Return output summary
```

### Module Structure

```
src/inkwell/
├── extraction/
│   ├── __init__.py
│   ├── models.py              # ExtractedContent, ExtractionResult data models
│   ├── templates.py           # Template loading and management
│   ├── template_selector.py  # Category detection and template selection
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── base.py           # Abstract base extractor
│   │   ├── claude.py         # Claude API extractor
│   │   ├── gemini.py         # Gemini API extractor
│   │   └── local.py          # Local model extractor (future)
│   ├── parsers.py            # Response parsing and validation
│   ├── cache.py              # Extraction result caching
│   └── manager.py            # High-level extraction orchestrator
├── output/
│   ├── __init__.py
│   ├── models.py             # OutputMetadata, EpisodeOutput models
│   ├── formatters/
│   │   ├── __init__.py
│   │   ├── markdown.py       # Markdown formatting
│   │   ├── frontmatter.py    # YAML frontmatter generation
│   │   └── templates.py      # Jinja2 template rendering
│   ├── writer.py             # File writing and directory management
│   └── validator.py          # Output validation
└── templates/
    ├── default/
    │   ├── summary.yaml
    │   ├── quotes.yaml
    │   └── key-concepts.yaml
    ├── categories/
    │   ├── tech/
    │   │   ├── tools-mentioned.yaml
    │   │   └── frameworks-mentioned.yaml
    │   └── interview/
    │       ├── books-mentioned.yaml
    │       └── people-mentioned.yaml
    └── output_templates/
        ├── default.md.j2
        └── obsidian.md.j2
```

---

## Detailed Implementation Plan

### Unit 1: Research & Architecture Decision Making

**Duration**: 3-4 hours
**Goal**: Make informed decisions about LLM APIs, template formats, and extraction strategies

#### Tasks:

1. **Research LLM APIs for Content Extraction**
   - Test Claude Sonnet for structured extraction
   - Test Gemini Pro for extraction quality
   - Compare extraction quality, cost, and latency
   - Test prompt engineering patterns (few-shot, chain-of-thought)
   - Document error scenarios (rate limits, malformed responses)

2. **Research Template Formats**
   - Evaluate YAML vs TOML vs JSON for template definition
   - Test Jinja2 for output templates
   - Research prompt templating libraries (LangChain, PromptLayer)
   - Identify template inheritance patterns
   - Document template validation requirements

3. **Research Content Extraction Patterns**
   - Test different prompt structures (JSON mode, structured output)
   - Evaluate few-shot learning for extraction quality
   - Test batch vs sequential extraction
   - Research streaming vs blocking API calls
   - Document edge cases (long transcripts, multi-topic episodes)

4. **Research Output Formats**
   - Review Obsidian markdown best practices
   - Test frontmatter formats (YAML, TOML)
   - Evaluate wikilink generation strategies
   - Research tag generation approaches
   - Document markdown linting requirements

#### Documentation Tasks:

**Create Research Document**: `docs/research/llm-extraction-comparison.md`
- Comparative analysis of Claude vs Gemini for extraction
- Pros/cons of each API
- Cost analysis (per extraction, per episode)
- Quality comparison with sample extractions
- Recommendations for default provider

**Create Research Document**: `docs/research/template-format-evaluation.md`
- Comparison of YAML, TOML, JSON for templates
- Template validation approaches
- Inheritance and composition patterns
- User customization workflows
- Recommendations for template format

**Create Research Document**: `docs/research/structured-extraction-patterns.md`
- Prompt engineering techniques
- JSON mode vs text parsing
- Few-shot learning effectiveness
- Error handling strategies
- Best practices for reliable extraction

**Create ADR**: `docs/adr/013-llm-provider-abstraction.md`
- **Decision**: Abstract LLM provider interface
- **Alternatives**: Hard-code Claude, hard-code Gemini, no abstraction
- **Rationale**: Flexibility for users, future-proof, testing easier
- **Consequences**: More complex implementation, need provider config

**Create ADR**: `docs/adr/014-template-format.md`
- **Decision**: YAML for template definition
- **Alternatives**: TOML, JSON, Python dataclasses
- **Rationale**: Human-readable, supports comments, widely known
- **Consequences**: Need YAML validation, potential parsing errors

**Create ADR**: `docs/adr/015-extraction-caching.md`
- **Decision**: Cache extracted content per template
- **Alternatives**: No caching, full episode caching, LLM-level caching
- **Rationale**: Avoid redundant API calls, enable re-generation
- **Consequences**: Cache invalidation complexity, storage cost

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-3-unit-1-research.md`
- Document research findings
- Summarize key decisions
- Note any surprises or gotchas discovered
- Link to research docs and ADRs
- Outline next steps

#### Experiments to Run:

**Create Experiment Log**: `docs/experiments/2025-11-07-claude-vs-gemini-extraction.md`
- Extract content from 5 sample episodes with both Claude and Gemini
- Compare quality (accuracy, completeness, format adherence)
- Measure cost per extraction
- Measure latency
- Document failure modes
- Results inform default LLM provider choice

**Create Experiment Log**: `docs/experiments/2025-11-07-prompt-engineering-effectiveness.md`
- Test different prompt structures (zero-shot, few-shot, chain-of-thought)
- Compare extraction quality across approaches
- Measure consistency (run same extraction 3x)
- Document optimal prompt patterns
- Results inform template design

**Create Experiment Log**: `docs/experiments/2025-11-07-extraction-batching.md`
- Test sequential extraction (one template at a time)
- Test batch extraction (multiple templates in one prompt)
- Test parallel extraction (concurrent API calls)
- Compare cost, latency, quality
- Results inform extraction strategy

#### Success Criteria:
- Clear understanding of LLM provider strengths/weaknesses
- All ADRs created with rationale
- Research documents comprehensive
- Experiment results documented
- Template format selected
- Ready to proceed with implementation

---

### Unit 2: Data Models & Template Schema

**Duration**: 3-4 hours
**Goal**: Define type-safe models for extraction system and template schema

#### Tasks:

1. **Create Template Models** (`extraction/models.py`)
```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from pathlib import Path

class TemplateVariable(BaseModel):
    """Variable that can be used in prompt template"""
    name: str
    description: str
    default: Optional[str] = None
    required: bool = True

class ExtractionTemplate(BaseModel):
    """Template for extracting content from transcript"""
    name: str  # e.g., "summary", "quotes"
    version: str = "1.0"
    description: str

    # Prompt configuration
    system_prompt: str
    user_prompt_template: str  # Can use {transcript}, {metadata} variables

    # Output configuration
    expected_format: Literal["json", "markdown", "yaml", "text"]
    output_schema: Optional[dict] = None  # JSON schema for validation

    # Template metadata
    category: Optional[str] = None  # e.g., "tech", "interview"
    applies_to: list[str] = Field(default_factory=lambda: ["all"])
    priority: int = 0  # Lower = runs first

    # LLM configuration
    model_preference: Optional[str] = None  # "claude", "gemini", etc.
    max_tokens: int = 2000
    temperature: float = 0.3

    # Variables
    variables: list[TemplateVariable] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure template name is filesystem-safe"""
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"Template name must be alphanumeric: {v}")
        return v

class ExtractedContent(BaseModel):
    """Content extracted by a template"""
    template_name: str
    content: str | dict  # Depends on expected_format
    metadata: dict = Field(default_factory=dict)

    # Quality metrics
    confidence: Optional[float] = None  # 0-1 confidence score
    warnings: list[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if content meets quality thresholds"""
        return len(self.warnings) == 0 and (
            self.confidence is None or self.confidence >= 0.7
        )

class ExtractionResult(BaseModel):
    """Result of extraction operation"""
    episode_url: str
    template_name: str

    success: bool
    extracted_content: Optional[ExtractedContent] = None
    error: Optional[str] = None

    # Metrics
    duration_seconds: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    provider: Optional[str] = None  # "claude", "gemini"

    from_cache: bool = False
    cache_key: Optional[str] = None
```

2. **Create Output Models** (`output/models.py`)
```python
from pydantic import BaseModel, Field
from datetime import datetime
from pathlib import Path

class EpisodeMetadata(BaseModel):
    """Metadata for a podcast episode"""
    podcast_name: str
    episode_title: str
    episode_url: str
    published_date: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Processing metadata
    processed_date: datetime = Field(default_factory=datetime.utcnow)
    transcription_source: str  # "youtube", "gemini", "cached"
    templates_applied: list[str] = Field(default_factory=list)

    # Cost tracking
    total_cost_usd: float = 0.0

    # Custom metadata
    custom_fields: dict = Field(default_factory=dict)

class OutputFile(BaseModel):
    """Represents a single output markdown file"""
    filename: str  # e.g., "summary.md"
    template_name: str
    content: str
    frontmatter: dict = Field(default_factory=dict)

class EpisodeOutput(BaseModel):
    """Complete output for an episode"""
    metadata: EpisodeMetadata
    output_dir: Path
    files: list[OutputFile] = Field(default_factory=list)

    # Stats
    total_files: int = 0
    total_size_bytes: int = 0

    def get_file(self, template_name: str) -> Optional[OutputFile]:
        """Get output file by template name"""
        for file in self.files:
            if file.template_name == template_name:
                return file
        return None
```

3. **Create Template Schema** (`templates/schema.yaml`)
```yaml
# Template schema definition
# This file documents the structure of extraction templates

template_schema:
  name: string  # Required, filesystem-safe
  version: string  # Semantic version
  description: string  # Human-readable description

  # Prompt configuration
  system_prompt: string  # System message for LLM
  user_prompt_template: string  # Jinja2 template for user prompt

  # Output configuration
  expected_format: enum  # json | markdown | yaml | text
  output_schema: object  # JSON schema (optional)

  # Template metadata
  category: string  # optional
  applies_to: list[string]  # Conditions for template application
  priority: integer  # Execution order (lower = earlier)

  # LLM configuration
  model_preference: string  # optional
  max_tokens: integer
  temperature: float

  # Variables
  variables:
    - name: string
      description: string
      default: string  # optional
      required: boolean
```

4. **Write Comprehensive Tests** (`tests/unit/test_extraction_models.py`)
   - Test template validation
   - Test template variable substitution
   - Test extracted content validation
   - Test metadata model serialization
   - Test edge cases (missing fields, invalid names)

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-3-unit-2-data-models.md`
- Document model design decisions
- Explain template schema structure
- Note challenges in modeling extraction data
- Document test coverage achieved
- Link to relevant code

**Create Research Document**: `docs/research/template-schema-design.md`
- Document schema requirements
- Explain field choices and validation
- Show example templates
- Document variable system
- Best practices for template authors

**Update**: `CLAUDE.md` (if needed)
- Add conventions for extraction module
- Document template authoring guidelines

#### Success Criteria:
- All models defined with comprehensive type hints
- Models validated with Pydantic
- Template schema documented
- 100% test coverage for model logic
- Clear documentation of model usage
- Devlog captures design decisions

---

### Unit 3: Template System

**Duration**: 4-5 hours
**Goal**: Implement template loading, validation, and management

#### Tasks:

1. **Implement TemplateLoader** (`extraction/templates.py`)
```python
from pathlib import Path
import yaml
from typing import Optional
from .models import ExtractionTemplate

class TemplateLoader:
    """Load and manage extraction templates"""

    def __init__(
        self,
        template_dirs: Optional[list[Path]] = None,
        user_template_dir: Optional[Path] = None,
    ):
        """
        Args:
            template_dirs: Built-in template directories
            user_template_dir: User custom template directory
        """
        self.template_dirs = template_dirs or self._get_default_dirs()
        self.user_template_dir = user_template_dir or self._get_user_dir()

        self._template_cache: dict[str, ExtractionTemplate] = {}

    def _get_default_dirs(self) -> list[Path]:
        """Get built-in template directories"""
        package_root = Path(__file__).parent.parent
        return [
            package_root / "templates" / "default",
            package_root / "templates" / "categories",
        ]

    def _get_user_dir(self) -> Path:
        """Get user template directory"""
        from inkwell.utils.paths import get_config_dir
        user_dir = get_config_dir() / "templates"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def load_template(self, name: str) -> ExtractionTemplate:
        """Load template by name"""
        # Check cache
        if name in self._template_cache:
            return self._template_cache[name]

        # Search for template file (user dir has priority)
        template_path = self._find_template(name)
        if not template_path:
            raise TemplateNotFoundError(f"Template not found: {name}")

        # Load and parse YAML
        with open(template_path) as f:
            data = yaml.safe_load(f)

        # Validate and create template
        template = ExtractionTemplate(**data)

        # Cache and return
        self._template_cache[name] = template
        return template

    def _find_template(self, name: str) -> Optional[Path]:
        """Find template file by name"""
        # Try user directory first
        user_path = self.user_template_dir / f"{name}.yaml"
        if user_path.exists():
            return user_path

        # Try built-in directories
        for template_dir in self.template_dirs:
            # Check direct file
            path = template_dir / f"{name}.yaml"
            if path.exists():
                return path

            # Check subdirectories (for categories)
            for subdir in template_dir.iterdir():
                if subdir.is_dir():
                    path = subdir / f"{name}.yaml"
                    if path.exists():
                        return path

        return None

    def list_templates(self, category: Optional[str] = None) -> list[str]:
        """List available template names"""
        templates = set()

        # Scan all directories
        all_dirs = [self.user_template_dir] + self.template_dirs
        for template_dir in all_dirs:
            if not template_dir.exists():
                continue

            # Scan template files
            for path in template_dir.rglob("*.yaml"):
                if path.name == "schema.yaml":
                    continue
                templates.add(path.stem)

        # Filter by category if specified
        if category:
            filtered = []
            for name in templates:
                template = self.load_template(name)
                if template.category == category or category in template.applies_to:
                    filtered.append(name)
            return sorted(filtered)

        return sorted(templates)

    def reload_templates(self) -> None:
        """Clear cache and reload all templates"""
        self._template_cache.clear()
```

2. **Implement Template Selector** (`extraction/template_selector.py`)
```python
from typing import Optional
from .models import ExtractionTemplate
from inkwell.feeds.models import Episode

class TemplateSelector:
    """Select appropriate templates for an episode"""

    def __init__(self, template_loader: TemplateLoader):
        self.loader = template_loader

    def select_templates(
        self,
        episode: Episode,
        category: Optional[str] = None,
        custom_templates: Optional[list[str]] = None,
    ) -> list[ExtractionTemplate]:
        """Select templates for episode extraction"""
        selected = []

        # Always include default templates
        for name in ["summary", "quotes", "key-concepts"]:
            try:
                template = self.loader.load_template(name)
                selected.append(template)
            except TemplateNotFoundError:
                logger.warning(f"Default template not found: {name}")

        # Add category-specific templates
        if category:
            category_templates = self.loader.list_templates(category=category)
            for name in category_templates:
                template = self.loader.load_template(name)
                if template not in selected:
                    selected.append(template)

        # Add custom templates
        if custom_templates:
            for name in custom_templates:
                template = self.loader.load_template(name)
                if template not in selected:
                    selected.append(template)

        # Sort by priority (lower = earlier)
        selected.sort(key=lambda t: t.priority)

        return selected

    def detect_category(self, episode: Episode, transcript: str) -> Optional[str]:
        """Auto-detect podcast category from content"""
        # This could use LLM or keyword matching
        # For now, simple keyword approach

        tech_keywords = ["software", "programming", "code", "developer", "API"]
        interview_keywords = ["guest", "author", "book", "conversation"]

        transcript_lower = transcript.lower()

        tech_score = sum(1 for kw in tech_keywords if kw in transcript_lower)
        interview_score = sum(1 for kw in interview_keywords if kw in transcript_lower)

        if tech_score > interview_score and tech_score >= 3:
            return "tech"
        elif interview_score > tech_score and interview_score >= 3:
            return "interview"

        return None
```

3. **Create Default Templates** (in `src/inkwell/templates/default/`)

4. **Write Comprehensive Tests** (`tests/unit/test_template_system.py`)
   - Test template loading from various directories
   - Test template caching
   - Test template validation
   - Test template selector
   - Test category detection
   - Test priority sorting

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-3-unit-3-template-system.md`
- Document template system architecture
- Explain template loading priority (user > built-in)
- Show example templates
- Document selector logic
- Note test coverage

**Create Lessons Learned**: `docs/lessons/2025-11-07-template-system.md`
- Document template design patterns
- YAML parsing gotchas
- Template validation challenges
- Best practices for template authors

**Create User Guide Section**: `docs/templates/README.md`
- Template authoring guide
- Variable system documentation
- Example templates
- Troubleshooting template issues

#### Success Criteria:
- Template loader fully functional
- Supports user and built-in templates
- Template selector working
- Default templates created
- 95%+ test coverage
- Comprehensive template documentation

---

### Unit 4: LLM Provider Abstraction

**Duration**: 4-5 hours
**Goal**: Create flexible abstraction for multiple LLM providers

#### Tasks:

1. **Create Abstract Base Extractor** (`extraction/extractors/base.py`)
```python
from abc import ABC, abstractmethod
from typing import Optional
from ..models import ExtractedContent, ExtractionTemplate

class BaseExtractor(ABC):
    """Abstract base class for LLM extractors"""

    @abstractmethod
    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict,
    ) -> ExtractedContent:
        """Extract content using template and transcript"""
        pass

    @abstractmethod
    def estimate_cost(
        self,
        template: ExtractionTemplate,
        transcript_length: int,
    ) -> float:
        """Estimate extraction cost in USD"""
        pass

    @abstractmethod
    def supports_structured_output(self) -> bool:
        """Whether provider supports structured output (JSON mode)"""
        pass
```

2. **Implement Claude Extractor** (`extraction/extractors/claude.py`)

3. **Implement Gemini Extractor** (`extraction/extractors/gemini.py`)

4. **Create Extractor Factory** (`extraction/extractors/__init__.py`)
```python
from typing import Optional
from .base import BaseExtractor
from .claude import ClaudeExtractor
from .gemini import GeminiExtractor

class ExtractorFactory:
    """Factory for creating LLM extractors"""

    @staticmethod
    def create(
        provider: str,
        api_key: str,
        **kwargs,
    ) -> BaseExtractor:
        """Create extractor for specified provider"""
        if provider == "claude":
            return ClaudeExtractor(api_key, **kwargs)
        elif provider == "gemini":
            return GeminiExtractor(api_key, **kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider}")
```

5. **Write Comprehensive Tests** (`tests/unit/test_extractors.py`)
   - Mock API calls for each provider
   - Test cost estimation
   - Test structured output parsing
   - Test error handling
   - Test provider factory

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-3-unit-4-llm-providers.md`
- Document provider abstraction design
- Explain factory pattern
- Show cost comparison
- Document API integration

**Create ADR**: `docs/adr/016-default-llm-provider.md`
- **Decision**: Default to Claude Sonnet for extraction
- **Alternatives**: Gemini, user choice required
- **Rationale**: Quality, structured output support, cost-effectiveness
- **Consequences**: Requires Anthropic API key

**Create Lessons Learned**: `docs/lessons/2025-11-07-llm-provider-abstraction.md`
- Document abstraction patterns
- API integration challenges
- Provider-specific quirks
- Best practices for multi-provider support

#### Success Criteria:
- Base extractor abstraction complete
- Claude extractor working
- Gemini extractor working
- Factory pattern functional
- 90%+ test coverage
- Clear provider documentation

---

### Unit 5: Content Extraction Engine

**Duration**: 5-6 hours
**Goal**: Implement core extraction logic with caching and validation

#### Tasks:

1. **Implement Response Parsers** (`extraction/parsers.py`)
```python
import json
import yaml
from typing import Any
from .models import ExtractedContent, ExtractionTemplate

class ResponseParser:
    """Parse and validate LLM responses"""

    @staticmethod
    def parse(
        response: str,
        template: ExtractionTemplate,
    ) -> ExtractedContent:
        """Parse response according to template format"""
        if template.expected_format == "json":
            content = ResponseParser._parse_json(response, template)
        elif template.expected_format == "yaml":
            content = ResponseParser._parse_yaml(response, template)
        elif template.expected_format == "markdown":
            content = response  # Already markdown
        else:  # text
            content = response.strip()

        # Validate against schema if provided
        warnings = []
        confidence = None

        if template.output_schema:
            warnings = ResponseParser._validate_schema(content, template.output_schema)
            confidence = 1.0 if len(warnings) == 0 else 0.5

        return ExtractedContent(
            template_name=template.name,
            content=content,
            warnings=warnings,
            confidence=confidence,
        )

    @staticmethod
    def _parse_json(response: str, template: ExtractionTemplate) -> dict:
        """Parse JSON response"""
        # Extract JSON from markdown code blocks if present
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ExtractionError(f"Invalid JSON response: {e}")

    @staticmethod
    def _parse_yaml(response: str, template: ExtractionTemplate) -> dict:
        """Parse YAML response"""
        try:
            return yaml.safe_load(response)
        except yaml.YAMLError as e:
            raise ExtractionError(f"Invalid YAML response: {e}")

    @staticmethod
    def _validate_schema(content: Any, schema: dict) -> list[str]:
        """Validate content against JSON schema"""
        # Use jsonschema library
        import jsonschema
        warnings = []

        try:
            jsonschema.validate(content, schema)
        except jsonschema.ValidationError as e:
            warnings.append(f"Schema validation failed: {e.message}")

        return warnings
```

2. **Implement Extraction Cache** (`extraction/cache.py`)
```python
import hashlib
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

class ExtractionCache:
    """Cache extracted content"""

    def __init__(self, cache_dir: Optional[Path] = None, ttl_days: int = 30):
        self.cache_dir = cache_dir or self._get_cache_dir()
        self.ttl_days = ttl_days
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_dir(self) -> Path:
        from inkwell.utils.paths import get_cache_dir
        return get_cache_dir() / "extractions"

    def _generate_cache_key(
        self,
        episode_url: str,
        template_name: str,
        template_version: str,
    ) -> str:
        """Generate cache key"""
        key_data = f"{episode_url}:{template_name}:{template_version}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(
        self,
        episode_url: str,
        template_name: str,
        template_version: str,
    ) -> Optional[ExtractedContent]:
        """Get cached extraction"""
        cache_key = self._generate_cache_key(episode_url, template_name, template_version)
        cache_path = self.cache_dir / f"{cache_key}.json"

        if not cache_path.exists():
            return None

        try:
            data = json.loads(cache_path.read_text())

            # Check TTL
            cached_at = datetime.fromisoformat(data["cached_at"])
            age = datetime.utcnow() - cached_at
            if age > timedelta(days=self.ttl_days):
                cache_path.unlink()
                return None

            return ExtractedContent(**data["content"])
        except Exception:
            cache_path.unlink()
            return None

    def set(
        self,
        episode_url: str,
        template_name: str,
        template_version: str,
        content: ExtractedContent,
    ) -> None:
        """Cache extraction"""
        cache_key = self._generate_cache_key(episode_url, template_name, template_version)
        cache_path = self.cache_dir / f"{cache_key}.json"

        data = {
            "cached_at": datetime.utcnow().isoformat(),
            "content": content.model_dump(),
        }

        cache_path.write_text(json.dumps(data, indent=2))
```

3. **Implement Extraction Manager** (`extraction/manager.py`)
```python
from typing import Optional
from inkwell.transcription.models import Transcript
from .models import ExtractionTemplate, ExtractionResult, ExtractedContent
from .templates import TemplateLoader
from .template_selector import TemplateSelector
from .extractors import ExtractorFactory
from .parsers import ResponseParser
from .cache import ExtractionCache

class ExtractionManager:
    """Orchestrate content extraction"""

    def __init__(
        self,
        llm_provider: str = "claude",
        api_key: Optional[str] = None,
        cache_enabled: bool = True,
    ):
        self.template_loader = TemplateLoader()
        self.template_selector = TemplateSelector(self.template_loader)
        self.extractor = ExtractorFactory.create(llm_provider, api_key)
        self.cache = ExtractionCache() if cache_enabled else None
        self.parser = ResponseParser()

    async def extract_all(
        self,
        transcript: Transcript,
        episode: Episode,
        category: Optional[str] = None,
        force_refresh: bool = False,
    ) -> dict[str, ExtractionResult]:
        """Extract content using all applicable templates"""
        # Select templates
        templates = self.template_selector.select_templates(episode, category)

        # Extract with each template
        results = {}
        for template in templates:
            result = await self.extract_one(
                transcript,
                episode,
                template,
                force_refresh,
            )
            results[template.name] = result

        return results

    async def extract_one(
        self,
        transcript: Transcript,
        episode: Episode,
        template: ExtractionTemplate,
        force_refresh: bool = False,
    ) -> ExtractionResult:
        """Extract content using single template"""
        import time

        start_time = time.time()

        # Check cache
        if self.cache and not force_refresh:
            cached = self.cache.get(
                episode.url,
                template.name,
                template.version,
            )
            if cached:
                return ExtractionResult(
                    episode_url=episode.url,
                    template_name=template.name,
                    success=True,
                    extracted_content=cached,
                    from_cache=True,
                )

        # Prepare metadata
        metadata = {
            "podcast_name": getattr(episode, "podcast_name", ""),
            "episode_title": episode.title,
            "duration": transcript.total_duration.total_seconds(),
        }

        try:
            # Extract with LLM
            response = await self.extractor.extract(
                template,
                transcript.full_text,
                metadata,
            )

            # Parse response
            extracted = self.parser.parse(response, template)

            # Cache result
            if self.cache and extracted.is_valid:
                self.cache.set(
                    episode.url,
                    template.name,
                    template.version,
                    extracted,
                )

            duration = time.time() - start_time
            cost = self.extractor.estimate_cost(template, len(transcript.full_text))

            return ExtractionResult(
                episode_url=episode.url,
                template_name=template.name,
                success=True,
                extracted_content=extracted,
                duration_seconds=duration,
                cost_usd=cost,
                provider=self.extractor.__class__.__name__,
            )

        except Exception as e:
            duration = time.time() - start_time
            return ExtractionResult(
                episode_url=episode.url,
                template_name=template.name,
                success=False,
                error=str(e),
                duration_seconds=duration,
            )
```

4. **Write Comprehensive Tests**
   - Test response parsing (JSON, YAML, Markdown)
   - Test schema validation
   - Test extraction caching
   - Test extraction manager orchestration
   - Mock all LLM calls

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-3-unit-5-extraction-engine.md`
- Document extraction flow
- Explain caching strategy
- Show parsing examples
- Document validation approach

**Create Lessons Learned**: `docs/lessons/2025-11-07-extraction-engine.md`
- Response parsing challenges
- Cache invalidation strategies
- Schema validation approaches
- Error handling patterns

#### Success Criteria:
- Extraction engine fully functional
- Response parsing robust
- Caching working correctly
- 95%+ test coverage
- Clear error messages

---

### Unit 6: Markdown Output System

**Duration**: 4-5 hours
**Goal**: Transform extracted content into formatted markdown files

#### Tasks:

1. **Implement Frontmatter Generator** (`output/formatters/frontmatter.py`)

2. **Implement Markdown Formatter** (`output/formatters/markdown.py`)

3. **Implement Jinja2 Template Renderer** (`output/formatters/templates.py`)

4. **Create Output Templates** (in `src/inkwell/templates/output_templates/`)

5. **Write Comprehensive Tests**

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-3-unit-6-markdown-output.md`

**Create Lessons Learned**: `docs/lessons/2025-11-07-markdown-generation.md`

#### Success Criteria:
- Markdown generation working
- Frontmatter properly formatted
- Template rendering functional
- 95%+ test coverage

---

### Unit 7: File Output Manager

**Duration**: 3-4 hours
**Goal**: Write organized markdown files to filesystem

#### Tasks:

1. **Implement File Writer** (`output/writer.py`)

2. **Implement Directory Manager**

3. **Implement Output Validator** (`output/validator.py`)

4. **Write Comprehensive Tests**

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-3-unit-7-file-output.md`

**Create ADR**: `docs/adr/017-output-directory-structure.md`

#### Success Criteria:
- File writing working
- Directory structure correct
- Atomic writes
- 95%+ test coverage

---

### Unit 8: CLI Integration

**Duration**: 3-4 hours
**Goal**: Expose extraction pipeline through CLI

#### Tasks:

1. **Add `fetch` Command** (`cli.py`)

2. **Add Progress Indicators**

3. **Add Cost Tracking Display**

4. **Write CLI Tests**

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-3-unit-8-cli-integration.md`

**Update USER_GUIDE.md**

#### Success Criteria:
- CLI command working
- Progress indicators smooth
- Cost tracking visible
- Tests passing

---

### Unit 9: Testing, Polish & Documentation

**Duration**: 4-5 hours
**Goal**: Comprehensive testing and documentation

#### Tasks:

1. **End-to-End Integration Tests**
2. **Performance Testing**
3. **Documentation Review**
4. **Manual Testing**

#### Documentation Tasks:

**Create Final Phase 3 Summary**: `docs/PHASE_3_COMPLETE.md`

**Create Comprehensive Lessons**: `docs/lessons/2025-11-07-phase-3-complete.md`

**Update CLAUDE.md**

**Create Architecture Diagram**: `docs/architecture/phase-3-extraction.md`

#### Success Criteria:
- 90%+ test coverage
- All tests passing
- Documentation complete
- Manual testing successful
- Ready for Phase 4

---

## Quality Gates

### Phase 3 is Complete When:

**Functionality:**
- [ ] Template system working (load, validate, select)
- [ ] LLM extraction working (Claude and Gemini)
- [ ] Response parsing and validation working
- [ ] Caching system working
- [ ] Markdown generation working
- [ ] File output working
- [ ] CLI commands functional

**Code Quality:**
- [ ] 90%+ test coverage
- [ ] All tests passing
- [ ] No mypy errors
- [ ] No ruff warnings
- [ ] Pre-commit hooks passing

**User Experience:**
- [ ] Clear progress indicators
- [ ] Cost transparency
- [ ] Quality markdown output
- [ ] Helpful error messages
- [ ] Works with real episodes

**Documentation:**
- [ ] All ADRs created
- [ ] All devlogs written
- [ ] Lessons learned documented
- [ ] Research docs complete
- [ ] User guide updated
- [ ] Template authoring guide complete
- [ ] PHASE_3_COMPLETE.md written

---

## Architecture Decision Records to Create

1. **ADR-013: LLM Provider Abstraction**
2. **ADR-014: Template Format (YAML)**
3. **ADR-015: Extraction Caching Strategy**
4. **ADR-016: Default LLM Provider (Claude)**
5. **ADR-017: Output Directory Structure**
6. **ADR-018: Frontmatter Format**

---

## Timeline Estimate

**Total Duration**: 12-15 days

- Unit 1 (Research): 0.5 days
- Unit 2 (Data Models): 0.5 days
- Unit 3 (Template System): 1 day
- Unit 4 (LLM Providers): 1 day
- Unit 5 (Extraction Engine): 1.5 days
- Unit 6 (Markdown Output): 1 day
- Unit 7 (File Output): 0.5 days
- Unit 8 (CLI): 0.5 days
- Unit 9 (Testing & Docs): 1 day
- Buffer: 2 days

---

## Notes for Implementation

1. **Documentation is Essential**: This phase has more complexity than Phase 2. Thorough documentation is critical.

2. **Template Quality Matters**: The quality of default templates directly impacts user value.

3. **Cost Awareness**: LLM extraction costs can add up. Always show estimates.

4. **Validation is Key**: Bad extractions are worse than no extractions. Validate aggressively.

5. **Cache Aggressively**: Extraction is expensive. Cache everything valid.

6. **User Customization**: Templates must be user-customizable without code changes.

7. **Test with Real Content**: Sample podcasts reveal edge cases automated tests miss.

---

## What Comes After Phase 3

**Phase 4: Interview Mode**
- Claude Agent SDK integration
- Interactive Q&A based on extracted content
- Personal notes generation
- Conversation state management

**Phase 5: Obsidian Integration & Polish**
- Wikilink generation
- Tag system
- Template customization UI
- Batch processing
- Performance optimization

---

**Ready to begin Phase 3 implementation! 🚀**
