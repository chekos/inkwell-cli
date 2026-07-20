"""Fail-closed Claude Code CLI runtime backend."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from jsonschema import SchemaError as JSONSchemaDefinitionError
from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate as validate_json_schema

from .models import (
    RuntimeBilling,
    RuntimeErrorCode,
    RuntimeInvocationError,
    RuntimeProvenance,
    RuntimeReadiness,
    RuntimeRequest,
    RuntimeResponse,
    RuntimeUsage,
)
from .runner import build_minimal_environment, run_bounded_process, sanitize_runtime_text

CLAUDE_CODE_PROTOCOL_VERSION = 1
# This is the first release whose complete invocation profile Inkwell tested.
MIN_SUPPORTED_VERSION = (2, 1, 215)
MAX_SUPPORTED_VERSION = (3, 0, 0)
REQUIRED_CAPABILITIES = (
    "auth-status-json",
    "disable-slash-commands",
    "json-schema",
    "no-session-persistence",
    "permission-mode-dontAsk",
    "safe-mode",
    "strict-mcp-config",
    "tools-empty",
)


def _parse_version(value: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _parse_auth_status(value: str) -> tuple[bool, str | None]:
    """Return only subscription readiness and a non-identifying auth class."""
    try:
        payload = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return False, None
    if not isinstance(payload, dict):
        return False, None
    logged_in = payload.get("loggedIn") is True
    auth_method = payload.get("authMethod")
    api_provider = payload.get("apiProvider")
    if logged_in and auth_method == "claude.ai" and api_provider == "firstParty":
        return True, "claude_subscription"
    return False, None


def _int_field(value: Any) -> int:
    """Parse a non-negative integer without accepting bools or floats."""
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


class ClaudeCodeRuntimeBackend:
    """Invoke a separately installed Claude CLI using saved subscription OAuth."""

    def __init__(self, executable: str = "claude") -> None:
        self.executable = executable

    async def _probe_command(self, *args: str) -> tuple[int, str, str]:
        executable = shutil.which(self.executable)
        if executable is None:
            return 127, "", ""
        with tempfile.TemporaryDirectory(prefix="inkwell-claude-code-probe-") as temp_dir:
            os.chmod(temp_dir, 0o700)
            result = await run_bounded_process(
                [executable, *args],
                stdin=b"",
                cwd=Path(temp_dir),
                env=build_minimal_environment(),
                timeout_seconds=20,
                max_stdout_bytes=1_048_576,
                max_stderr_bytes=1_048_576,
                max_line_bytes=262_144,
            )
        return (
            result.returncode,
            result.stdout.decode("utf-8", "replace"),
            result.stderr.decode("utf-8", "replace"),
        )

    async def probe(self) -> RuntimeReadiness:
        """Probe only version and secret-free auth status; never run inference."""
        executable = shutil.which(self.executable)
        required = list(REQUIRED_CAPABILITIES)
        if executable is None:
            return RuntimeReadiness(
                runtime="claude-code-cli",
                ready=False,
                installed=False,
                authenticated=False,
                supported=False,
                executable=self.executable,
                error_code=RuntimeErrorCode.MISSING_EXECUTABLE,
                reason="Claude CLI executable was not found.",
                recovery_command="Install Claude Code and authenticate it independently.",
                required_capabilities=required,
            )

        version_rc, version_out, version_err = await self._probe_command("--version")
        parsed_version = _parse_version(version_out or version_err)
        version = ".".join(str(part) for part in parsed_version) if parsed_version else None
        supported = (
            version_rc == 0
            and parsed_version is not None
            and MIN_SUPPORTED_VERSION <= parsed_version < MAX_SUPPORTED_VERSION
        )
        if not supported:
            return RuntimeReadiness(
                runtime="claude-code-cli",
                ready=False,
                installed=True,
                authenticated=False,
                supported=False,
                executable=executable,
                version=version,
                error_code=RuntimeErrorCode.UNSUPPORTED_VERSION,
                reason="Claude Code version is outside the tested compatibility range.",
                recovery_command="Update Claude Code and retry validation.",
                required_capabilities=required,
            )

        auth_rc, auth_out, _ = await self._probe_command("auth", "status", "--json")
        authenticated, auth_class = _parse_auth_status(auth_out)
        ready = auth_rc == 0 and authenticated
        return RuntimeReadiness(
            runtime="claude-code-cli",
            ready=ready,
            installed=True,
            authenticated=ready,
            supported=True,
            executable=executable,
            version=version,
            auth_class=auth_class,
            error_code=None if ready else RuntimeErrorCode.NOT_AUTHENTICATED,
            reason=(
                None
                if ready
                else "Claude CLI does not report a saved first-party subscription login."
            ),
            recovery_command=(
                None if ready else "Authenticate Claude Code independently, then retry validation."
            ),
            required_capabilities=required,
        )

    def build_argv(
        self,
        *,
        executable: str,
        output_schema_json: str,
        requested_model: str,
    ) -> list[str]:
        """Construct the tested local-only, no-tool profile without prompt data."""
        return [
            executable,
            "-p",
            "--safe-mode",
            "--tools",
            "",
            "--disallowedTools",
            "mcp__*",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--permission-mode",
            "dontAsk",
            "--disable-slash-commands",
            "--no-session-persistence",
            "--setting-sources",
            "",
            "--output-format",
            "json",
            "--json-schema",
            output_schema_json,
            "--model",
            requested_model,
            "--system-prompt",
            (
                "Perform only the supplied text extraction. Return the requested "
                "structured output. Do not access tools, files, MCP servers, skills, "
                "commands, hooks, agents, or external context."
            ),
        ]

    async def invoke(self, request: RuntimeRequest) -> RuntimeResponse:
        """Run Claude Code in a private workspace and validate its JSON result."""
        prompt_bytes = request.prompt.encode("utf-8")
        try:
            output_schema_json = json.dumps(
                request.output_schema,
                separators=(",", ":"),
                sort_keys=True,
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeInvocationError(
                RuntimeErrorCode.SCHEMA_INVALID,
                "Runtime output schema was not valid JSON.",
            ) from exc
        if len(prompt_bytes) + len(output_schema_json.encode("utf-8")) > request.max_input_bytes:
            raise RuntimeInvocationError(
                RuntimeErrorCode.INPUT_TOO_LARGE,
                "Runtime input exceeded the configured safety limit.",
            )
        readiness = await self.probe()
        if not readiness.ready:
            raise RuntimeInvocationError(
                readiness.error_code or RuntimeErrorCode.NOT_AUTHENTICATED,
                readiness.reason or "Claude CLI is not ready.",
                recovery_command=readiness.recovery_command,
            )
        assert readiness.executable is not None
        assert readiness.version is not None
        assert readiness.auth_class is not None

        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="inkwell-claude-code-") as temp_dir:
            workspace = Path(temp_dir)
            os.chmod(workspace, 0o700)
            argv = self.build_argv(
                executable=readiness.executable,
                output_schema_json=output_schema_json,
                requested_model=request.requested_model,
            )
            result = await run_bounded_process(
                argv,
                stdin=prompt_bytes,
                cwd=workspace,
                env=build_minimal_environment(),
                timeout_seconds=request.timeout_seconds,
                max_stdout_bytes=request.max_stdout_bytes,
                max_stderr_bytes=request.max_stderr_bytes,
                max_line_bytes=request.max_line_bytes,
            )
            stderr = sanitize_runtime_text(
                result.stderr.decode("utf-8", "replace"),
                sensitive_inputs=(request.prompt,),
            )
            if result.returncode != 0:
                lowered = stderr.lower()
                code = (
                    RuntimeErrorCode.PERMISSION_DENIED
                    if "permission denied" in lowered or "operation not permitted" in lowered
                    else RuntimeErrorCode.NONZERO_EXIT
                )
                raise RuntimeInvocationError(
                    code,
                    "Claude CLI exited without a valid result.",
                    details={"exit_code": result.returncode},
                )
            return self._parse_response(
                result.stdout,
                request=request,
                version=readiness.version,
                auth_class=readiness.auth_class,
                duration_seconds=time.monotonic() - start,
            )

    def _parse_response(
        self,
        stdout: bytes,
        *,
        request: RuntimeRequest,
        version: str,
        auth_class: str,
        duration_seconds: float,
    ) -> RuntimeResponse:
        try:
            payload = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeInvocationError(
                RuntimeErrorCode.MALFORMED_PROTOCOL,
                "Claude CLI emitted malformed JSON.",
            ) from exc
        if not isinstance(payload, dict) or payload.get("type") != "result":
            raise RuntimeInvocationError(
                RuntimeErrorCode.MALFORMED_PROTOCOL,
                "Claude CLI emitted an invalid terminal result.",
            )
        if payload.get("subtype") != "success":
            raise RuntimeInvocationError(
                RuntimeErrorCode.TURN_FAILED,
                "Claude CLI did not report a successful terminal result.",
            )
        if payload.get("is_error") is True:
            raise RuntimeInvocationError(
                RuntimeErrorCode.TURN_FAILED,
                "Claude CLI reported a failed result.",
            )
        if "structured_output" not in payload:
            raise RuntimeInvocationError(
                RuntimeErrorCode.MISSING_TERMINAL_STATE,
                "Claude CLI did not emit structured terminal output.",
            )

        model_usage = payload.get("modelUsage")
        if not isinstance(model_usage, dict) or len(model_usage) != 1:
            raise RuntimeInvocationError(
                RuntimeErrorCode.MODEL_MISMATCH,
                "Claude CLI did not report exactly one effective model.",
            )
        effective_model = next(iter(model_usage))
        if not isinstance(effective_model, str) or not effective_model.strip():
            raise RuntimeInvocationError(
                RuntimeErrorCode.MODEL_MISMATCH,
                "Claude CLI reported an invalid effective model.",
            )

        final_value = payload["structured_output"]
        try:
            validate_json_schema(instance=final_value, schema=request.output_schema)
        except (JSONSchemaValidationError, JSONSchemaDefinitionError) as exc:
            raise RuntimeInvocationError(
                RuntimeErrorCode.SCHEMA_INVALID,
                "Claude CLI final output did not match the requested schema.",
            ) from exc
        if request.application_validator is not None:
            try:
                request.application_validator(final_value)
            except Exception as exc:
                raise RuntimeInvocationError(
                    RuntimeErrorCode.APPLICATION_INVALID,
                    "Claude CLI final output failed application validation.",
                ) from exc

        raw_usage = payload.get("usage")
        raw_usage = raw_usage if isinstance(raw_usage, dict) else {}
        usage = RuntimeUsage(
            input_tokens=(
                _int_field(raw_usage.get("input_tokens"))
                + _int_field(raw_usage.get("cache_creation_input_tokens"))
            ),
            cached_input_tokens=_int_field(raw_usage.get("cache_read_input_tokens")),
            output_tokens=_int_field(raw_usage.get("output_tokens")),
        )
        num_turns = _int_field(payload.get("num_turns"))
        if num_turns < 1:
            raise RuntimeInvocationError(
                RuntimeErrorCode.MALFORMED_PROTOCOL,
                "Claude CLI reported an invalid turn count.",
            )
        provenance = RuntimeProvenance(
            kind="claude-code-cli",
            version=version,
            protocol_version=CLAUDE_CODE_PROTOCOL_VERSION,
            requested_model=request.requested_model,
            effective_model=effective_model,
            auth_class=auth_class,
            billing_class="subscription_limits",
        )
        return RuntimeResponse(
            final_value=final_value,
            terminal_status="completed",
            lifecycle_events=["result.success"],
            attempts=[f"claude-code:{effective_model}:turns={num_turns}"],
            usage=usage,
            provenance=provenance,
            billing=RuntimeBilling(mode="runtime_managed", amount_usd=None),
            duration_seconds=duration_seconds,
        )
