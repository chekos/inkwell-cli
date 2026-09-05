"""Per-run extraction overrides preserve saved and concurrent configuration."""

import pytest

from inkwell.config.overrides import with_local_extraction_overrides
from inkwell.config.schema import GlobalConfig, PluginConfig
from inkwell.utils.errors import ValidationError


def test_overrides_copy_nested_config_without_enabling_disabled_plugin():
    original = GlobalConfig(
        plugins={
            "codex": PluginConfig(
                enabled=False, config={"model": "saved-model", "timeout_seconds": 600}
            )
        }
    )
    run = with_local_extraction_overrides(
        original, extractor="codex", model="run-model", reasoning_effort="high"
    )
    assert run.plugins["codex"].config == {
        "model": "run-model",
        "reasoning_effort": "high",
        "timeout_seconds": 600,
    }
    assert not run.plugins["codex"].enabled
    assert original.plugins["codex"].config == {"model": "saved-model", "timeout_seconds": 600}
    next_run = with_local_extraction_overrides(original, extractor="codex")
    assert next_run.plugins["codex"].config["model"] == "saved-model"


@pytest.mark.parametrize(
    ("extractor", "model", "effort"),
    [
        (None, "model", None),
        ("gemini", "model", None),
        ("claude-code", None, "high"),
        ("codex", " ", None),
        ("codex", None, " "),
    ],
)
def test_rejects_ambiguous_or_unsupported_override(extractor, model, effort):
    with pytest.raises(ValidationError):
        with_local_extraction_overrides(
            GlobalConfig(), extractor=extractor, model=model, reasoning_effort=effort
        )


def test_claude_code_model_can_be_overridden_without_saved_plugin():
    config = with_local_extraction_overrides(
        GlobalConfig(), extractor="claude-code", model="explicit-claude-model"
    )
    assert config.plugins["claude-code"].config == {"model": "explicit-claude-model"}
