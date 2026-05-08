"""Tests for demo configuration invariants.

These tests pin the OBRA-73 hard requirements to actual code: forced
extractor, audio cap, kill switch default, allowlisted templates.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from inkwell.demo.config import (
    DEMO_ALLOWED_TEMPLATES,
    DEMO_FORCED_EXTRACTION_MODEL_DEFAULT,
    DEMO_FORCED_EXTRACTOR_DEFAULT,
    DEMO_MAX_DURATION_SECONDS_DEFAULT,
    DemoConfig,
)


def test_defaults_match_obra_73_plan() -> None:
    config = DemoConfig()

    # Hard requirement: 30-minute audio cap
    assert config.max_duration_seconds == 30 * 60
    assert DEMO_MAX_DURATION_SECONDS_DEFAULT == 30 * 60

    # Hard requirement: kill switch defaults to ON for safety in dev,
    # production overrides via env var
    assert config.enabled is True

    # Hard requirement: forced budget extractor
    assert config.forced_extractor == "gemini"
    assert config.forced_extractor == DEMO_FORCED_EXTRACTOR_DEFAULT

    # Hard requirement: cheap Gemini Flash model, not the CLI's Gemini 3 Pro
    assert config.forced_extraction_model.startswith("gemini-2.5-flash") or (
        config.forced_extraction_model.startswith("gemini-flash")
    )
    assert config.forced_extraction_model == DEMO_FORCED_EXTRACTION_MODEL_DEFAULT

    # Hard requirement: monthly spend cap ~$50
    assert config.monthly_spend_cap_usd == pytest.approx(50.0)

    # Hard requirement: rate limits
    assert config.daily_run_cap == 20
    assert config.daily_runs_per_email == 1
    assert config.daily_attempts_per_ip == 3

    # Hard requirement: only allowlisted templates
    assert config.allowed_templates == DEMO_ALLOWED_TEMPLATES
    assert set(config.allowed_templates) == {"summary", "quotes", "key-concepts"}


def test_extractor_must_be_gemini() -> None:
    """The demo budget envelope assumes Gemini Flash; reject Claude explicitly."""
    with pytest.raises(PydanticValidationError):
        DemoConfig(forced_extractor="claude")


def test_allowed_templates_cannot_be_empty() -> None:
    with pytest.raises(PydanticValidationError):
        DemoConfig(allowed_templates=())


def test_max_duration_is_clamped_to_thirty_minutes() -> None:
    """OBRA-81 P2: env override may not exceed the documented 30-minute cap.

    The 30-minute number matches both the demo budget envelope and the
    Cloud Tasks HTTP dispatch ceiling. An operator raising
    INKWELL_DEMO_MAX_DURATION_SECONDS past 1800 used to validate (the
    field allowed up to 3600); now the validator refuses any value over
    1800 so widening the cap requires a code change.
    """
    # Exactly at the cap is accepted.
    DemoConfig(max_duration_seconds=30 * 60)

    # Anything over the cap is refused, including values that the prior
    # 1-hour ceiling silently allowed.
    for over_cap in (30 * 60 + 1, 45 * 60, 60 * 60):
        with pytest.raises(PydanticValidationError):
            DemoConfig(max_duration_seconds=over_cap)


def test_max_duration_env_override_cannot_widen_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """OBRA-81 P2: the env-var path enforces the same 30-minute ceiling."""
    monkeypatch.setenv("INKWELL_DEMO_MAX_DURATION_SECONDS", str(45 * 60))
    with pytest.raises(PydanticValidationError):
        DemoConfig()


def test_allowed_templates_env_override_cannot_widen_allowlist() -> None:
    """OBRA-81 P2: env override may narrow the canonical allowlist but never widen it.

    The canonical allowlist is code-defined: an operator must not be
    able to silently re-enable internal or high-cost templates that
    blow the demo budget envelope. Validation rejects supersets and
    names the offending templates.
    """
    with pytest.raises(PydanticValidationError) as excinfo:
        DemoConfig(allowed_templates=("summary", "evil"))
    assert "evil" in str(excinfo.value)


def test_allowed_templates_can_be_narrowed() -> None:
    """Operators can still subset the allowlist (e.g., disable quotes)."""
    config = DemoConfig(allowed_templates=("summary",))
    assert config.allowed_templates == ("summary",)


def test_allowed_templates_env_override_rejects_superset(monkeypatch: pytest.MonkeyPatch) -> None:
    """The env-var path enforces the same subset constraint."""
    # Pydantic-settings parses comma-separated lists for tuple fields.
    monkeypatch.setenv("INKWELL_DEMO_ALLOWED_TEMPLATES", '["summary","evil"]')
    with pytest.raises(PydanticValidationError) as excinfo:
        DemoConfig()
    assert "evil" in str(excinfo.value)


def test_kill_switch_via_canonical_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DEMO_PIPELINE_ENABLED=false` flips the kill switch.

    OBRA-74 acceptance criterion #4 fixes this exact env var name.
    """
    monkeypatch.delenv("INKWELL_DEMO_ENABLED", raising=False)
    monkeypatch.setenv("DEMO_PIPELINE_ENABLED", "false")
    config = DemoConfig()
    assert config.enabled is False


def test_kill_switch_via_prefixed_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """`INKWELL_DEMO_ENABLED=false` is accepted as an alias for consistency."""
    monkeypatch.delenv("DEMO_PIPELINE_ENABLED", raising=False)
    monkeypatch.setenv("INKWELL_DEMO_ENABLED", "false")
    config = DemoConfig()
    assert config.enabled is False


def test_canonical_env_takes_precedence_over_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both are set, the OBRA-74 canonical name wins."""
    monkeypatch.setenv("DEMO_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("INKWELL_DEMO_ENABLED", "false")
    config = DemoConfig()
    assert config.enabled is True


def test_can_override_caps_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INKWELL_DEMO_DAILY_RUN_CAP", "5")
    monkeypatch.setenv("INKWELL_DEMO_MONTHLY_SPEND_CAP_USD", "10")
    config = DemoConfig()
    assert config.daily_run_cap == 5
    assert config.monthly_spend_cap_usd == pytest.approx(10.0)
