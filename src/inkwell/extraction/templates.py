"""Template loading and management system.

This module provides functionality for loading, validating, and managing
extraction templates from YAML files.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..utils.errors import NotFoundError
from ..utils.errors import ValidationError as InkwellValidationError
from .models import ExtractionTemplate

logger = logging.getLogger(__name__)


class TemplateLoader:
    """Load and manage extraction templates.

    Templates are loaded from YAML files and validated using Pydantic models.
    The loader searches in multiple directories with priority order:
    1. User templates (~/.config/inkwell/templates/)
    2. Built-in templates (package templates/)

    Example:
        >>> loader = TemplateLoader()
        >>> template = loader.load_template("summary")
        >>> templates = loader.list_templates()
    """

    def __init__(
        self,
        template_dirs: list[Path] | None = None,
        user_template_dir: Path | None = None,
    ):
        """Initialize template loader.

        Args:
            template_dirs: Built-in template directories (default: package templates/)
            user_template_dir: User custom template directory (default: XDG config)
        """
        self.template_dirs = template_dirs or self._get_default_dirs()
        self.user_template_dir = user_template_dir or self._get_user_dir()

        # Template cache: name -> template
        self._template_cache: dict[str, ExtractionTemplate] = {}

        logger.debug(
            f"TemplateLoader initialized with dirs: {self.template_dirs}, "
            f"user_dir: {self.user_template_dir}"
        )

    def _get_default_dirs(self) -> list[Path]:
        """Get built-in template directories.

        Returns:
            List of paths to built-in template directories
        """
        package_root = Path(__file__).parent.parent
        return [
            package_root / "templates" / "default",
            package_root / "templates" / "categories",
        ]

    def _get_user_dir(self) -> Path:
        """Get user template directory.

        Creates directory if it doesn't exist.

        Returns:
            Path to user template directory
        """
        from inkwell.utils.paths import get_config_dir

        user_dir = get_config_dir() / "templates"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def load_template(self, name: str) -> ExtractionTemplate:
        """Load template by name.

        Searches for template in user directory first, then built-in directories.
        Results are cached for subsequent requests.

        Args:
            name: Template name (without .yaml extension)

        Returns:
            Loaded and validated template

        Raises:
            TemplateNotFoundError: If template file not found
            TemplateLoadError: If template fails to load or validate
        """
        # Check cache first
        if name in self._template_cache:
            logger.debug(f"Template '{name}' loaded from cache")
            return self._template_cache[name]

        # Find template file
        template_path = self._find_template(name)
        if not template_path:
            raise NotFoundError(
                "Template", f"Template '{name}' not found in any template directory"
            )

        # Load and validate template
        try:
            template = self._load_template_file(template_path)
        except Exception as e:
            raise InkwellValidationError(
                f"Failed to load template '{name}' from {template_path}: {e}"
            ) from e

        # Cache and return
        self._template_cache[name] = template
        logger.info(f"Loaded template '{name}' from {template_path}")
        return template

    def _find_template(self, name: str) -> Path | None:
        """Find template file by name.

        Searches in user directory first, then built-in directories.

        Args:
            name: Template name (without .yaml extension)

        Returns:
            Path to template file if found, None otherwise
        """
        # Try user directory first (highest priority)
        user_path = self.user_template_dir / f"{name}.yaml"
        if user_path.exists():
            logger.debug(f"Found user template: {user_path}")
            return user_path

        # Try built-in directories
        for template_dir in self.template_dirs:
            if not template_dir.exists():
                continue

            # Check direct file
            path = template_dir / f"{name}.yaml"
            if path.exists():
                logger.debug(f"Found built-in template: {path}")
                return path

            # Check subdirectories (for categories)
            for subdir in template_dir.iterdir():
                if subdir.is_dir():
                    path = subdir / f"{name}.yaml"
                    if path.exists():
                        logger.debug(f"Found category template: {path}")
                        return path

        logger.debug(f"Template '{name}' not found in any directory")
        return None

    def _load_template_file(self, path: Path) -> ExtractionTemplate:
        """Load and validate template from YAML file.

        Args:
            path: Path to template YAML file

        Returns:
            Validated extraction template

        Raises:
            yaml.YAMLError: If YAML parsing fails
            ValidationError: If template validation fails
        """
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise InkwellValidationError(f"Invalid YAML syntax in {path}: {e}") from e

        if not isinstance(data, dict):
            raise InkwellValidationError(
                f"Template file must contain a YAML object, got {type(data)}"
            )

        try:
            template = ExtractionTemplate(**data)
        except ValidationError as e:
            # Format validation errors nicely
            errors = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                errors.append(f"  {field}: {error['msg']}")
            error_msg = "Template validation failed:\n" + "\n".join(errors)
            raise InkwellValidationError(error_msg) from e

        return template

    def list_templates(self, category: str | None = None) -> list[str]:
        """List available template names.

        Args:
            category: Optional category to filter by

        Returns:
            Sorted list of template names
        """
        templates = set()

        # Scan all directories
        all_dirs = [self.user_template_dir] + self.template_dirs
        for template_dir in all_dirs:
            if not template_dir.exists():
                continue

            # Scan template files
            for path in template_dir.rglob("*.yaml"):
                # Skip schema files
                if path.name == "schema.yaml":
                    continue
                templates.add(path.stem)

        # Filter by category if specified
        if category:
            filtered = []
            for name in templates:
                try:
                    template = self.load_template(name)
                    if template.category == category or category in template.applies_to:
                        filtered.append(name)
                except Exception as e:
                    logger.warning(f"Failed to load template '{name}' for filtering: {e}")
            return sorted(filtered)

        return sorted(templates)

    def reload_templates(self) -> None:
        """Clear cache and reload all templates.

        Useful after templates have been modified on disk.
        """
        self._template_cache.clear()
        logger.info("Template cache cleared")

    def validate_template(self, path: Path) -> tuple[bool, str | None]:
        """Validate a template file without loading it.

        Args:
            path: Path to template YAML file

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self._load_template_file(path)
            return (True, None)
        except Exception as e:
            return (False, str(e))

    def get_template_info(self, name: str) -> dict[str, Any]:
        """Get metadata about a template without fully loading it.

        Args:
            name: Template name

        Returns:
            Dictionary with template metadata

        Raises:
            TemplateNotFoundError: If template not found
        """
        template = self.load_template(name)
        return {
            "name": template.name,
            "version": template.version,
            "description": template.description,
            "category": template.category,
            "applies_to": template.applies_to,
            "expected_format": template.expected_format,
            "model_preference": template.model_preference,
        }
