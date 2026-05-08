"""Configuration for the public try-it demo.

These values are intentionally **not** wired into the CLI's
``GlobalConfig``. The demo is a separate surface with stricter, locked-in
defaults that the OBRA-73 plan calls out as non-negotiable:

- Force a budget extractor (Gemini Flash / Flash-Lite).
- Cap audio at 30 minutes.
- Daily and monthly run caps.
- A kill switch (``DEMO_PIPELINE_ENABLED=false``) that pauses processing
  without a redeploy.
- Allowlisted templates only (``summary``, ``quotes``, ``key-concepts``).

Most settings are read from environment variables prefixed
``INKWELL_DEMO_`` so production overrides land cleanly through Cloud Run
env vars or Secret Manager mounts. The kill switch is the one exception:
OBRA-74 fixes its name as ``DEMO_PIPELINE_ENABLED`` (un-prefixed) and
that is what the operations runbook documents, so :attr:`DemoConfig.enabled`
accepts both ``DEMO_PIPELINE_ENABLED`` (canonical) and
``INKWELL_DEMO_ENABLED`` (consistency alias). They are loaded once and
cached so a hot worker container doesn't re-parse env on every job.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# These are the canonical demo template names. They map 1:1 to existing
# CLI templates so we don't fork content. Adding to this list requires a
# code change — the demo deliberately does not honor user-supplied
# template selection.
DEMO_ALLOWED_TEMPLATES: tuple[str, ...] = ("summary", "quotes", "key-concepts")

# Cap audio length the demo will accept. The 30-minute number comes from
# the OBRA-73 plan: it matches both Cloud Tasks' max HTTP timeout and the
# budget envelope we're underwriting for v1.
DEMO_MAX_DURATION_SECONDS_DEFAULT: int = 30 * 60

# Default budget extractor. Hard-coded in the demo; the CLI's higher
# quality default (Gemini 3 Pro) blows the $50/mo cap on its own.
DEMO_FORCED_EXTRACTOR_DEFAULT: str = "gemini"
DEMO_FORCED_EXTRACTION_MODEL_DEFAULT: str = "gemini-2.5-flash"


class DemoConfig(BaseSettings):
    """Runtime configuration for the demo web service.

    Values come from ``INKWELL_DEMO_*`` env vars (or a `.env` file
    locally). Defaults match the OBRA-73 plan; production overrides only
    need to set secrets and the kill switch.
    """

    model_config = SettingsConfigDict(
        env_prefix="INKWELL_DEMO_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=True,
        # OBRA-74 acceptance criterion #4 names the env var as
        # DEMO_PIPELINE_ENABLED (no prefix). The INKWELL_DEMO_ENABLED
        # form is kept as an alias so operators who follow the prefix
        # convention also get the kill switch.
        validation_alias=AliasChoices("DEMO_PIPELINE_ENABLED", "INKWELL_DEMO_ENABLED"),
        description=(
            "Master kill switch. When false, the API accepts emails but "
            "refuses to run the pipeline."
        ),
    )

    forced_extractor: str = Field(
        default=DEMO_FORCED_EXTRACTOR_DEFAULT,
        description="Plugin name forced for extraction (always Gemini for the demo).",
    )
    forced_extraction_model: str = Field(
        default=DEMO_FORCED_EXTRACTION_MODEL_DEFAULT,
        description="Gemini model forced for extraction in the demo.",
    )

    max_duration_seconds: int = Field(
        default=DEMO_MAX_DURATION_SECONDS_DEFAULT,
        ge=60,
        le=60 * 60,
        description="Hard cap on episode/video duration accepted by the demo.",
    )

    daily_run_cap: int = Field(
        default=20,
        ge=1,
        description="Global cap on successful runs/day until real cost data exists.",
    )
    daily_runs_per_email: int = Field(
        default=1,
        ge=1,
        description="Successful runs allowed per email address per day.",
    )
    daily_attempts_per_ip: int = Field(
        default=3,
        ge=1,
        description="Total attempts (success or failure) allowed per IP per day.",
    )

    monthly_spend_cap_usd: float = Field(
        default=50.0,
        gt=0,
        description="Soft monthly spend cap. Once hit, processing pauses.",
    )

    consent_version: str = Field(
        default="v1",
        description="Version label written alongside captured emails.",
    )

    allowed_templates: tuple[str, ...] = Field(
        default=DEMO_ALLOWED_TEMPLATES,
        description="Templates the demo is allowed to render. Not user-toggleable.",
    )

    @field_validator("forced_extractor")
    @classmethod
    def _validate_forced_extractor(cls, value: str) -> str:
        # Only Gemini is in the demo budget envelope. The CLI can offer
        # claude/gemini, but the demo must not switch on user input.
        if value != "gemini":
            raise ValueError("Demo extractor must be 'gemini' — Claude is not in the demo budget.")
        return value

    @field_validator("allowed_templates")
    @classmethod
    def _validate_allowed_templates(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("allowed_templates must be non-empty")
        return tuple(value)


@lru_cache(maxsize=1)
def get_demo_config() -> DemoConfig:
    """Return the process-wide demo config singleton."""
    return DemoConfig()
