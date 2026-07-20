"""Fail-closed Codex CLI runtime backend."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

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

CODEX_PROTOCOL_VERSION = 1
MIN_SUPPORTED_VERSION = (0, 144, 0)
REQUIRED_DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "computer_use",
    "goals",
    "hooks",
    "in_app_browser",
    "multi_agent",
    "plugins",
    "shell_tool",
    "unified_exec",
)


def _parse_version(value: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _auth_class(value: str) -> str | None:
    lowered = value.lower()
    if "chatgpt" in lowered:
        return "chatgpt"
    if "api key" in lowered:
        return "api_key"
    if "logged in" in lowered or "authenticated" in lowered:
        return "other_supported"
    return None


class CodexRuntimeBackend:
    """Invoke a user-installed Codex CLI without inspecting its auth state."""

    def __init__(self, executable: str = "codex") -> None:
        self.executable = executable

    async def _probe_command(self, *args: str) -> tuple[int, str, str]:
        executable = shutil.which(self.executable)
        if executable is None:
            return 127, "", ""
        with tempfile.TemporaryDirectory(prefix="inkwell-codex-probe-") as temp_dir:
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
        """Check install, version, auth status, and fail-closed feature controls."""
        executable = shutil.which(self.executable)
        required = list(REQUIRED_DISABLED_FEATURES)
        if executable is None:
            return RuntimeReadiness(
                runtime="codex-cli",
                ready=False,
                installed=False,
                authenticated=False,
                supported=False,
                executable=self.executable,
                error_code=RuntimeErrorCode.MISSING_EXECUTABLE,
                reason="Codex CLI executable was not found.",
                recovery_command="Install Codex CLI, then run: codex login",
                required_capabilities=required,
            )

        version_rc, version_out, version_err = await self._probe_command("--version")
        version_text = version_out or version_err
        parsed_version = _parse_version(version_text)
        version = ".".join(str(part) for part in parsed_version) if parsed_version else None
        supported_version = (
            version_rc == 0
            and parsed_version is not None
            and MIN_SUPPORTED_VERSION <= parsed_version < (1, 0, 0)
        )
        if not supported_version:
            return RuntimeReadiness(
                runtime="codex-cli",
                ready=False,
                installed=True,
                authenticated=False,
                supported=False,
                executable=executable,
                version=version,
                error_code=RuntimeErrorCode.UNSUPPORTED_VERSION,
                reason="Codex CLI version is outside the tested compatibility range.",
                recovery_command="Update Codex CLI and retry validation.",
                required_capabilities=required,
            )

        features_rc, features_out, _ = await self._probe_command("features", "list")
        available = {
            line.split()[0]
            for line in features_out.splitlines()
            if len(line.split()) >= 3 and line.split()[1] == "stable"
        }
        missing = sorted(set(REQUIRED_DISABLED_FEATURES) - available)
        if features_rc != 0 or missing:
            return RuntimeReadiness(
                runtime="codex-cli",
                ready=False,
                installed=True,
                authenticated=False,
                supported=False,
                executable=executable,
                version=version,
                error_code=RuntimeErrorCode.UNSUPPORTED_CAPABILITY,
                reason=(
                    "Required fail-closed Codex controls are unavailable"
                    + (f": {', '.join(missing)}" if missing else ".")
                ),
                recovery_command="Update Codex CLI and retry validation.",
                required_capabilities=required,
            )

        auth_rc, auth_out, auth_err = await self._probe_command("login", "status")
        auth = _auth_class(auth_out or auth_err)
        authenticated = auth_rc == 0 and auth is not None
        return RuntimeReadiness(
            runtime="codex-cli",
            ready=authenticated,
            installed=True,
            authenticated=authenticated,
            supported=True,
            executable=executable,
            version=version,
            auth_class=auth,
            error_code=None if authenticated else RuntimeErrorCode.NOT_AUTHENTICATED,
            reason=None if authenticated else "Codex CLI is not authenticated.",
            recovery_command=None if authenticated else "codex login",
            required_capabilities=required,
        )

    def build_argv(
        self,
        *,
        executable: str,
        workspace: Path,
        schema_file: Path,
        result_file: Path,
        requested_model: str,
    ) -> list[str]:
        """Construct the tested no-tool profile. Prompt input is deliberately absent."""
        argv = [
            executable,
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--strict-config",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "-C",
            str(workspace),
            "--model",
            requested_model,
            "--output-schema",
            str(schema_file),
            "--output-last-message",
            str(result_file),
            "-c",
            'web_search="disabled"',
            "-c",
            'approval_policy="never"',
            "-c",
            'shell_environment_policy.inherit="none"',
        ]
        for feature in REQUIRED_DISABLED_FEATURES:
            argv.extend(["--disable", feature])
        return argv

    async def invoke(self, request: RuntimeRequest) -> RuntimeResponse:
        """Run Codex in a private workspace and validate its terminal response."""
        prompt_bytes = request.prompt.encode("utf-8")
        if len(prompt_bytes) > request.max_input_bytes:
            raise RuntimeInvocationError(
                RuntimeErrorCode.INPUT_TOO_LARGE,
                "Runtime input exceeded the configured safety limit.",
            )
        readiness = await self.probe()
        if not readiness.ready:
            raise RuntimeInvocationError(
                readiness.error_code or RuntimeErrorCode.NOT_AUTHENTICATED,
                readiness.reason or "Codex CLI is not ready.",
                recovery_command=readiness.recovery_command,
            )
        assert readiness.executable is not None
        assert readiness.version is not None
        assert readiness.auth_class is not None

        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="inkwell-codex-") as temp_dir:
            workspace = Path(temp_dir)
            os.chmod(workspace, 0o700)
            schema_file = workspace / "output.schema.json"
            result_file = workspace / "final.json"
            schema_file.write_text(json.dumps(request.output_schema), encoding="utf-8")
            os.chmod(schema_file, 0o600)
            result_file.touch(mode=0o600)
            os.chmod(result_file, 0o600)
            argv = self.build_argv(
                executable=readiness.executable,
                workspace=workspace,
                schema_file=schema_file,
                result_file=result_file,
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
                if "permission denied" in lowered or "operation not permitted" in lowered:
                    code = RuntimeErrorCode.PERMISSION_DENIED
                elif "database" in lowered and (
                    "read-only" in lowered or "writ" in lowered or "permission" in lowered
                ):
                    code = RuntimeErrorCode.STATE_UNWRITABLE
                else:
                    code = RuntimeErrorCode.NONZERO_EXIT
                raise RuntimeInvocationError(
                    code,
                    "Codex CLI exited without a valid result.",
                    details={"exit_code": result.returncode},
                )
            response = self._parse_response(
                result.stdout,
                result_file=result_file,
                request=request,
                version=readiness.version,
                auth_class=readiness.auth_class,
                duration_seconds=time.monotonic() - start,
            )
            return response

    def _parse_response(
        self,
        stdout: bytes,
        *,
        result_file: Path,
        request: RuntimeRequest,
        version: str,
        auth_class: str,
        duration_seconds: float,
    ) -> RuntimeResponse:
        event_types: list[str] = []
        terminal = False
        usage = RuntimeUsage()
        for raw_line in stdout.splitlines():
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise RuntimeInvocationError(
                    RuntimeErrorCode.MALFORMED_PROTOCOL,
                    "Codex CLI emitted malformed JSONL.",
                ) from exc
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                raise RuntimeInvocationError(
                    RuntimeErrorCode.MALFORMED_PROTOCOL,
                    "Codex CLI emitted an invalid lifecycle event.",
                )
            event_type = event["type"]
            event_types.append(event_type)
            reported_model = event.get("model")
            if isinstance(reported_model, str) and reported_model != request.requested_model:
                raise RuntimeInvocationError(
                    RuntimeErrorCode.MODEL_MISMATCH,
                    "Codex CLI reported an unexpected effective model.",
                )
            item = event.get("item")
            item_failed = (
                event_type == "item.completed"
                and isinstance(item, dict)
                and item.get("type") == "error"
            )
            if event_type in {"turn.failed", "error"} or item_failed:
                raise RuntimeInvocationError(
                    RuntimeErrorCode.TURN_FAILED,
                    "Codex CLI reported a failed turn.",
                )
            if event_type == "turn.completed":
                terminal = True
                raw_usage = event.get("usage") or {}
                usage = RuntimeUsage(
                    input_tokens=int(raw_usage.get("input_tokens", 0)),
                    cached_input_tokens=int(raw_usage.get("cached_input_tokens", 0)),
                    output_tokens=int(raw_usage.get("output_tokens", 0)),
                    reasoning_output_tokens=int(raw_usage.get("reasoning_output_tokens", 0)),
                )
        if not terminal:
            raise RuntimeInvocationError(
                RuntimeErrorCode.MISSING_TERMINAL_STATE,
                "Codex CLI did not emit a completed terminal event.",
            )
        try:
            if result_file.stat().st_size > request.max_stdout_bytes:
                raise RuntimeInvocationError(
                    RuntimeErrorCode.OUTPUT_TOO_LARGE,
                    "Local runtime output exceeded the configured safety limit.",
                )
            final_value = json.loads(result_file.read_bytes().decode("utf-8"))
        except RuntimeInvocationError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeInvocationError(
                RuntimeErrorCode.MALFORMED_PROTOCOL,
                "Codex CLI did not write a parseable final document.",
            ) from exc
        try:
            validate_json_schema(instance=final_value, schema=request.output_schema)
        except (JSONSchemaValidationError, JSONSchemaDefinitionError) as exc:
            raise RuntimeInvocationError(
                RuntimeErrorCode.SCHEMA_INVALID,
                "Codex CLI final output did not match the requested schema.",
            ) from exc
        if request.application_validator is not None:
            try:
                request.application_validator(final_value)
            except Exception as exc:
                raise RuntimeInvocationError(
                    RuntimeErrorCode.APPLICATION_INVALID,
                    "Codex CLI final output failed application validation.",
                ) from exc

        # This protocol selects an explicit model and permits no fallback configuration.
        # Current JSONL does not expose a separate effective-model field, so the selected
        # explicit model is the only unambiguous effective identity.
        provenance = RuntimeProvenance(
            kind="codex-cli",
            version=version,
            protocol_version=CODEX_PROTOCOL_VERSION,
            requested_model=request.requested_model,
            effective_model=request.requested_model,
            auth_class=auth_class,
            billing_class="runtime_managed",
        )
        return RuntimeResponse(
            final_value=final_value,
            terminal_status="completed",
            lifecycle_events=event_types,
            attempts=["codex-cli"],
            usage=usage,
            provenance=provenance,
            billing=RuntimeBilling(mode="runtime_managed", amount_usd=None),
            duration_seconds=duration_seconds,
        )
