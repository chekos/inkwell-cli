"""Unit tests for template loader."""

from pathlib import Path

import pytest

from inkwell.extraction.models import ExtractionTemplate
from inkwell.extraction.templates import TemplateLoader
from inkwell.utils.errors import NotFoundError
from inkwell.utils.errors import ValidationError as InkwellValidationError


@pytest.fixture
def temp_template_dir(tmp_path: Path) -> Path:
    """Create temporary directory for test templates."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    return template_dir


@pytest.fixture
def valid_template_yaml() -> str:
    """Return valid template YAML."""
    return """
name: test-template
version: "1.0"
description: "Test template for unit tests"
system_prompt: "You are a test assistant."
user_prompt_template: "Process: {{ transcript }}"
expected_format: json
max_tokens: 1000
temperature: 0.2
"""


@pytest.fixture
def invalid_template_yaml() -> str:
    """Return invalid template YAML (missing required fields)."""
    return """
name: invalid
description: "Missing required fields"
"""


class TestTemplateLoader:
    """Tests for TemplateLoader class."""

    def test_create_loader_default_dirs(self) -> None:
        """Test creating loader with default directories."""
        loader = TemplateLoader()

        assert loader.user_template_dir is not None
        assert loader.template_dirs is not None
        assert len(loader.template_dirs) > 0

    def test_create_loader_custom_dirs(self, tmp_path: Path) -> None:
        """Test creating loader with custom directories."""
        user_dir = tmp_path / "user"
        template_dir = tmp_path / "templates"

        loader = TemplateLoader(
            user_template_dir=user_dir,
            template_dirs=[template_dir],
        )

        assert loader.user_template_dir == user_dir
        assert template_dir in loader.template_dirs

    def test_load_template_from_file(
        self, temp_template_dir: Path, valid_template_yaml: str
    ) -> None:
        """Test loading template from YAML file."""
        # Create test template file
        template_file = temp_template_dir / "test-template.yaml"
        template_file.write_text(valid_template_yaml)

        loader = TemplateLoader(
            user_template_dir=temp_template_dir,
            template_dirs=[],
        )

        template = loader.load_template("test-template")

        assert isinstance(template, ExtractionTemplate)
        assert template.name == "test-template"
        assert template.version == "1.0"
        assert template.max_tokens == 1000
        assert template.temperature == 0.2

    def test_load_template_caching(self, temp_template_dir: Path, valid_template_yaml: str) -> None:
        """Test that templates are cached after first load."""
        template_file = temp_template_dir / "test-template.yaml"
        template_file.write_text(valid_template_yaml)

        loader = TemplateLoader(
            user_template_dir=temp_template_dir,
            template_dirs=[],
        )

        # Load template twice
        template1 = loader.load_template("test-template")
        template2 = loader.load_template("test-template")

        # Should be same cached instance
        assert template1 is template2
        assert len(loader._template_cache) == 1

    def test_load_template_user_overrides_builtin(
        self, tmp_path: Path, valid_template_yaml: str
    ) -> None:
        """Test that user templates override built-in templates."""
        user_dir = tmp_path / "user"
        builtin_dir = tmp_path / "builtin"
        user_dir.mkdir()
        builtin_dir.mkdir()

        # Create template in both directories with different versions
        user_template = user_dir / "summary.yaml"
        user_template.write_text(valid_template_yaml.replace('"1.0"', '"2.0"'))

        builtin_template = builtin_dir / "summary.yaml"
        builtin_template.write_text(valid_template_yaml)

        loader = TemplateLoader(
            user_template_dir=user_dir,
            template_dirs=[builtin_dir],
        )

        template = loader.load_template("summary")

        # Should load user template (v2.0) not builtin (v1.0)
        assert template.version == "2.0"

    def test_load_template_not_found(self, temp_template_dir: Path) -> None:
        """Test loading non-existent template raises error."""
        loader = TemplateLoader(
            user_template_dir=temp_template_dir,
            template_dirs=[],
        )

        with pytest.raises(NotFoundError) as exc_info:
            loader.load_template("nonexistent")

        assert "not found" in str(exc_info.value).lower()

    def test_load_invalid_yaml(self, temp_template_dir: Path, invalid_template_yaml: str) -> None:
        """Test loading invalid YAML raises validation error."""
        template_file = temp_template_dir / "invalid.yaml"
        template_file.write_text(invalid_template_yaml)

        loader = TemplateLoader(
            user_template_dir=temp_template_dir,
            template_dirs=[],
        )

        with pytest.raises(InkwellValidationError):
            loader.load_template("invalid")

    def test_load_malformed_yaml(self, temp_template_dir: Path) -> None:
        """Test loading malformed YAML raises error."""
        template_file = temp_template_dir / "malformed.yaml"
        template_file.write_text("invalid: yaml: content: [[[")

        loader = TemplateLoader(
            user_template_dir=temp_template_dir,
            template_dirs=[],
        )

        with pytest.raises(Exception):  # YAML parsing error
            loader.load_template("malformed")

    def test_list_templates_empty(self, temp_template_dir: Path) -> None:
        """Test listing templates from user dir (empty) plus built-in templates."""
        loader = TemplateLoader(
            user_template_dir=temp_template_dir,
            template_dirs=[],
        )

        templates = loader.list_templates()
        # Should list built-in templates even when user dir is empty
        assert len(templates) >= 5  # At least the 5 built-in templates

    def test_list_templates_multiple(self, tmp_path: Path, valid_template_yaml: str) -> None:
        """Test listing multiple templates."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        # Create multiple template files
        (template_dir / "summary.yaml").write_text(valid_template_yaml)
        (template_dir / "quotes.yaml").write_text(valid_template_yaml)
        (template_dir / "concepts.yaml").write_text(valid_template_yaml)

        loader = TemplateLoader(
            user_template_dir=template_dir,
            template_dirs=[],
        )

        templates = loader.list_templates()

        # Should include user templates plus built-in templates
        assert len(templates) >= 3
        assert "summary" in templates
        assert "quotes" in templates
        assert "concepts" in templates

    def test_list_templates_deduplicated(self, tmp_path: Path, valid_template_yaml: str) -> None:
        """Test that duplicate template names are deduplicated."""
        user_dir = tmp_path / "user"
        builtin_dir = tmp_path / "builtin"
        user_dir.mkdir()
        builtin_dir.mkdir()

        # Create same template in both directories
        (user_dir / "summary.yaml").write_text(valid_template_yaml)
        (builtin_dir / "summary.yaml").write_text(valid_template_yaml)

        loader = TemplateLoader(
            user_template_dir=user_dir,
            template_dirs=[builtin_dir],
        )

        templates = loader.list_templates()

        # Should only list "summary" once
        assert templates.count("summary") == 1

    def test_list_templates_by_category(self, tmp_path: Path) -> None:
        """Test filtering templates by category."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        # Create templates with different categories
        tech_template = """
name: tools
version: "1.0"
description: "Tech template"
category: tech
system_prompt: "Test"
user_prompt_template: "Test"
expected_format: json
"""
        interview_template = """
name: books
version: "1.0"
description: "Interview template"
category: interview
system_prompt: "Test"
user_prompt_template: "Test"
expected_format: json
"""

        (template_dir / "tools.yaml").write_text(tech_template)
        (template_dir / "books.yaml").write_text(interview_template)

        loader = TemplateLoader(
            user_template_dir=template_dir,
            template_dirs=[],
        )

        # List all templates (includes built-in templates too)
        all_templates = loader.list_templates()
        assert len(all_templates) >= 2
        assert "tools" in all_templates
        assert "books" in all_templates

        # List tech templates only (includes built-in tech templates)
        tech_templates = loader.list_templates(category="tech")
        assert len(tech_templates) >= 1
        assert "tools" in tech_templates

        # List interview templates only (includes built-in interview templates)
        interview_templates = loader.list_templates(category="interview")
        assert len(interview_templates) >= 1
        assert "books" in interview_templates

    def test_load_template_from_category_dir(self, tmp_path: Path) -> None:
        """Test loading template from category subdirectory."""
        category_dir = tmp_path / "categories" / "tech"
        category_dir.mkdir(parents=True)

        template_yaml = """
name: tools-mentioned
version: "1.0"
description: "Extract tools"
category: tech
system_prompt: "Test"
user_prompt_template: "Test"
expected_format: json
"""
        (category_dir / "tools-mentioned.yaml").write_text(template_yaml)

        loader = TemplateLoader(
            user_template_dir=None,
            template_dirs=[tmp_path / "categories"],
        )

        template = loader.load_template("tools-mentioned")
        assert template.name == "tools-mentioned"
        assert template.category == "tech"

    def test_clear_cache(self, temp_template_dir: Path, valid_template_yaml: str) -> None:
        """Test clearing template cache."""
        template_file = temp_template_dir / "test-template.yaml"
        template_file.write_text(valid_template_yaml)

        loader = TemplateLoader(
            user_template_dir=temp_template_dir,
            template_dirs=[],
        )

        # Load template (caches it)
        template1 = loader.load_template("test-template")
        assert len(loader._template_cache) == 1

        # Load again - should return same cached instance
        template2 = loader.load_template("test-template")
        assert template1 is template2
        assert len(loader._template_cache) == 1

    def test_load_builtin_templates(self) -> None:
        """Test loading actual built-in templates."""
        loader = TemplateLoader()

        # Should be able to load default templates
        summary = loader.load_template("summary")
        assert summary.name == "summary"
        assert summary.expected_format == "markdown"

        quotes = loader.load_template("quotes")
        assert quotes.name == "quotes"
        assert quotes.expected_format == "json"

        concepts = loader.load_template("key-concepts")
        assert concepts.name == "key-concepts"

    def test_load_category_templates(self) -> None:
        """Test loading actual category templates."""
        loader = TemplateLoader()

        # Should be able to load category-specific templates
        tools = loader.load_template("tools-mentioned")
        assert tools.name == "tools-mentioned"
        assert tools.category == "tech"

        books = loader.load_template("books-mentioned")
        assert books.name == "books-mentioned"
        assert books.category == "interview"

    def test_list_all_builtin_templates(self) -> None:
        """Test listing all built-in templates."""
        loader = TemplateLoader()

        templates = loader.list_templates()

        # Should include at least the 5 default templates we created
        assert "summary" in templates
        assert "quotes" in templates
        assert "key-concepts" in templates
        assert "tools-mentioned" in templates
        assert "books-mentioned" in templates
        assert len(templates) >= 5

    def test_template_validation_name(self, temp_template_dir: Path) -> None:
        """Test that invalid template names are rejected."""
        invalid_name_yaml = """
name: "invalid@name!"
version: "1.0"
description: "Test"
system_prompt: "Test"
user_prompt_template: "Test"
expected_format: json
"""
        template_file = temp_template_dir / "invalid.yaml"
        template_file.write_text(invalid_name_yaml)

        loader = TemplateLoader(
            user_template_dir=temp_template_dir,
            template_dirs=[],
        )

        with pytest.raises(InkwellValidationError) as exc_info:
            loader.load_template("invalid")

        assert "alphanumeric" in str(exc_info.value).lower()

    def test_template_validation_jinja2(self, temp_template_dir: Path) -> None:
        """Test that invalid Jinja2 templates are rejected."""
        invalid_jinja_yaml = """
name: test
version: "1.0"
description: "Test"
system_prompt: "Test"
user_prompt_template: "Hello {{ unclosed"
expected_format: json
"""
        template_file = temp_template_dir / "test.yaml"
        template_file.write_text(invalid_jinja_yaml)

        loader = TemplateLoader(
            user_template_dir=temp_template_dir,
            template_dirs=[],
        )

        with pytest.raises(InkwellValidationError) as exc_info:
            loader.load_template("test")

        assert "jinja2" in str(exc_info.value).lower()
