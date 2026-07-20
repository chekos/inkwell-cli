"""Typed models shared by local agent-runtime backends."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RuntimeErrorCode(str, Enum):
    """Stable public failures for local runtime execution."""

    MISSING_EXECUTABLE = "runtime_missing_executable"
    UNSUPPORTED_VERSION = "runtime_unsupported_version"
    UNSUPPORTED_CAPABILITY = "runtime_unsupported_capability"
    NOT_AUTHENTICATED = "runtime_not_authenticated"
    STATE_UNWRITABLE = "runtime_state_unwritable"
    MODEL_REQUIRED = "runtime_model_required"
    MODEL_MISMATCH = "runtime_model_mismatch"
    INPUT_TOO_LARGE = "runtime_input_too_large"
    OUTPUT_TOO_LARGE = "runtime_output_too_large"
    TIMEOUT = "runtime_timeout"
    CANCELLED = "runtime_cancelled"
    NONZERO_EXIT = "runtime_nonzero_exit"
    MALFORMED_PROTOCOL = "runtime_malformed_protocol"
    MISSING_TERMINAL_STATE = "runtime_missing_terminal_state"
    TURN_FAILED = "runtime_turn_failed"
    SCHEMA_INVALID = "runtime_schema_invalid"
    APPLICATION_INVALID = "runtime_application_invalid"
    PERMISSION_DENIED = "runtime_permission_denied"


class RuntimeInvocationError(Exception):
    """Sanitized runtime failure with a stable public code."""

    def __init__(
        self,
        code: RuntimeErrorCode,
        message: str,
        *,
        recovery_command: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.recovery_command = recovery_command
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Return a machine-readable, secret-free error."""
        return {
            "code": self.code.value,
            "message": self.message,
            "recovery_command": self.recovery_command,
            "details": self.details,
        }


class RuntimeUsage(BaseModel):
    """Token usage reported by a runtime."""

    input_tokens: int = Field(0, ge=0)
    cached_input_tokens: int = Field(0, ge=0)
    output_tokens: int = Field(0, ge=0)
    reasoning_output_tokens: int = Field(0, ge=0)

    @property
    def total_tokens(self) -> int:
        """Return non-cached input plus output token usage."""
        return self.input_tokens + self.output_tokens


class RuntimeBilling(BaseModel):
    """Honest monetary state for one runtime call."""

    mode: Literal["known", "estimated", "runtime_managed"]
    amount_usd: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_amount(self) -> RuntimeBilling:
        """Known and estimated billing require an amount."""
        if self.mode in {"known", "estimated"} and self.amount_usd is None:
            raise ValueError(f"{self.mode} billing requires amount_usd")
        if self.mode == "runtime_managed" and self.amount_usd is not None:
            raise ValueError("runtime-managed billing must not claim a USD amount")
        return self


class RuntimeProvenance(BaseModel):
    """Runtime and model identity used for cache and result provenance."""

    kind: str
    version: str
    protocol_version: int = Field(1, ge=1)
    requested_model: str
    effective_model: str
    auth_class: str
    billing_class: str


class RuntimeReadiness(BaseModel):
    """Secret-free runtime readiness result."""

    schema_version: int = 1
    runtime: str
    ready: bool
    installed: bool
    authenticated: bool
    supported: bool
    executable: str | None = None
    version: str | None = None
    auth_class: str | None = None
    error_code: RuntimeErrorCode | None = None
    reason: str | None = None
    recovery_command: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)


class RuntimeRequest(BaseModel):
    """One bounded, schema-constrained runtime request."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    prompt: str
    output_schema: dict[str, Any]
    requested_model: str
    timeout_seconds: float = Field(180.0, gt=0, le=3600)
    max_input_bytes: int = Field(8_000_000, ge=1, le=10_000_000)
    max_stdout_bytes: int = Field(8_388_608, ge=1024, le=64 * 1024 * 1024)
    max_stderr_bytes: int = Field(1_048_576, ge=1024, le=16 * 1024 * 1024)
    max_line_bytes: int = Field(1_048_576, ge=1024, le=8 * 1024 * 1024)
    task_metadata: dict[str, str] = Field(default_factory=dict)
    application_validator: Callable[[Any], None] | None = Field(default=None, exclude=True)

    @field_validator("requested_model")
    @classmethod
    def require_model(cls, value: str) -> str:
        """Reject implicit or ambiguous model selection."""
        value = value.strip()
        if not value:
            raise ValueError("requested_model must be explicit")
        return value

    @field_validator("prompt")
    @classmethod
    def require_prompt(cls, value: str) -> str:
        """Reject an empty task."""
        if not value.strip():
            raise ValueError("prompt must not be empty")
        return value


class RuntimeResponse(BaseModel):
    """Validated terminal response from a local runtime."""

    final_value: Any
    terminal_status: Literal["completed"]
    lifecycle_events: list[str] = Field(default_factory=list)
    attempts: list[str] = Field(default_factory=list)
    usage: RuntimeUsage = Field(default_factory=RuntimeUsage)
    provenance: RuntimeProvenance
    billing: RuntimeBilling
    duration_seconds: float = Field(ge=0)
