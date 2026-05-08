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


def test_max_duration_is_clamped_to_one_hour() -> None:
    """Cloud Tasks max HTTP timeout is 30 minutes; enforce a guardrail upstream."""
    with pytest.raises(PydanticValidationError):
        DemoConfig(max_duration_seconds=60 * 60 + 1)


def test_kill_switch_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`INKWELL_DEMO_ENABLED=false` flips the kill switch without code changes."""
    monkeypatch.setenv("INKWELL_DEMO_ENABLED", "false")
    config = DemoConfig()
    assert config.enabled is False


def test_can_override_caps_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INKWELL_DEMO_DAILY_RUN_CAP", "5")
    monkeypatch.setenv("INKWELL_DEMO_MONTHLY_SPEND_CAP_USD", "10")
    config = DemoConfig()
    assert config.daily_run_cap == 5
    assert config.monthly_spend_cap_usd == pytest.approx(10.0)
