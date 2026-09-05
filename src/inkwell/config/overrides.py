"""Non-persistent configuration overrides for explicit local extraction."""

from inkwell.config.schema import GlobalConfig, PluginConfig
from inkwell.utils.errors import ValidationError


def with_local_extraction_overrides(
    config: GlobalConfig,
    *,
    extractor: str | None,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> GlobalConfig:
    """Return an independent run config; never persist or enable a disabled plugin.

    Model IDs and reasoning levels are checked for compatibility by the selected
    installed runtime, rather than keeping a second provider catalog here.
    """
    result = config.model_copy(deep=True)
    if model is None and reasoning_effort is None:
        return result
    if extractor not in {"codex", "claude-code"}:
        raise ValidationError("Model overrides require --extractor codex or claude-code.")
    if reasoning_effort is not None and extractor != "codex":
        raise ValidationError("Reasoning effort overrides require --extractor codex.")
    plugin = result.plugins.setdefault(extractor, PluginConfig())
    for name, value, limit in [("model", model, 200), ("reasoning_effort", reasoning_effort, 80)]:
        if value is None:
            continue
        if not value.strip() or len(value.strip()) > limit:
            raise ValidationError(f"{name} must contain 1 to {limit} nonblank characters.")
        plugin.config[name] = value.strip()
    return result
