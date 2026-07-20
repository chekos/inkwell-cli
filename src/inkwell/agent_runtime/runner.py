"""Bounded argv-only async subprocess execution."""

from __future__ import annotations

import asyncio
import os
import re
import signal
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .models import RuntimeErrorCode, RuntimeInvocationError

_ALLOWED_EXACT_ENV = {
    "HOME",
    "CODEX_HOME",
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
}
_SECRET_NAME = re.compile(
    r"(?:^|_)(?:API_?)?(?:KEY|TOKEN|SECRET|PASSWORD|PASS|CREDENTIALS?|AUTH)(?:$|_)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,})"
)


def build_minimal_environment(parent: Mapping[str, str] | None = None) -> dict[str, str]:
    """Create the allowlisted child environment without secret-shaped names."""
    source = parent if parent is not None else os.environ
    result: dict[str, str] = {}
    for name, value in source.items():
        if name not in _ALLOWED_EXACT_ENV or _SECRET_NAME.search(name):
            continue
        result[name] = value
    result.setdefault("PATH", os.defpath)
    result.setdefault("LANG", "C.UTF-8")
    return result


def sanitize_runtime_text(value: str, *, sensitive_inputs: Sequence[str] = ()) -> str:
    """Redact token-shaped values and caller-supplied payloads."""
    redacted = _SECRET_VALUE.sub("[REDACTED]", value)
    for sensitive in sensitive_inputs:
        if sensitive:
            redacted = redacted.replace(sensitive, "[REDACTED_INPUT]")
    return redacted[:4000]


@dataclass(frozen=True)
class ProcessResult:
    """Captured bounded process output."""

    returncode: int
    stdout: bytes
    stderr: bytes


class _OutputLimitExceededError(Exception):
    pass


async def _read_bounded(
    stream: asyncio.StreamReader,
    *,
    max_bytes: int,
    max_line_bytes: int,
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    current_line = 0
    while True:
        chunk = await stream.read(65_536)
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise _OutputLimitExceededError
        for byte in chunk:
            current_line = 0 if byte == 10 else current_line + 1
            if current_line > max_line_bytes:
                raise _OutputLimitExceededError
        chunks.append(chunk)


async def _write_stdin(
    stream: asyncio.StreamWriter,
    payload: bytes,
) -> None:
    """Write and close stdin while tolerating a child that exits early."""
    try:
        stream.write(payload)
        await stream.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        stream.close()
        try:
            await stream.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass


async def _terminate_process_group(
    process: asyncio.subprocess.Process,
    *,
    grace_seconds: float,
) -> None:
    if process.returncode is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:  # pragma: no cover - exercised on Windows CI when available
            process.terminate()
    except ProcessLookupError:
        await process.wait()
        return
    grace_wait = asyncio.create_task(process.wait())
    try:
        await asyncio.wait_for(asyncio.shield(grace_wait), timeout=grace_seconds)
        return
    except asyncio.TimeoutError:
        pass
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:  # pragma: no cover
            process.kill()
    except ProcessLookupError:
        await grace_wait
        return
    await grace_wait


async def run_bounded_process(
    argv: Sequence[str],
    *,
    stdin: bytes,
    cwd: Path,
    env: Mapping[str, str],
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
    max_line_bytes: int,
    term_grace_seconds: float = 2.0,
) -> ProcessResult:
    """Run an argv list with bounded I/O and deterministic group cleanup."""
    if not argv or not all(isinstance(part, str) and part for part in argv):
        raise ValueError("argv must be a non-empty sequence of strings")
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=dict(env),
        start_new_session=os.name == "posix",
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_task = asyncio.create_task(
        _read_bounded(
            process.stdout,
            max_bytes=max_stdout_bytes,
            max_line_bytes=max_line_bytes,
        )
    )
    stderr_task = asyncio.create_task(
        _read_bounded(
            process.stderr,
            max_bytes=max_stderr_bytes,
            max_line_bytes=max_line_bytes,
        )
    )
    wait_task = asyncio.create_task(process.wait())
    stdin_task = asyncio.create_task(_write_stdin(process.stdin, stdin))
    completion = asyncio.gather(stdin_task, wait_task, stdout_task, stderr_task)
    try:
        _, _, stdout, stderr = await asyncio.wait_for(
            asyncio.shield(completion),
            timeout=timeout_seconds,
        )
        return ProcessResult(process.returncode or 0, stdout, stderr)
    except _OutputLimitExceededError as exc:
        await _terminate_process_group(process, grace_seconds=term_grace_seconds)
        raise RuntimeInvocationError(
            RuntimeErrorCode.OUTPUT_TOO_LARGE,
            "Local runtime output exceeded the configured safety limit.",
        ) from exc
    except asyncio.TimeoutError as exc:
        await _terminate_process_group(process, grace_seconds=term_grace_seconds)
        raise RuntimeInvocationError(
            RuntimeErrorCode.TIMEOUT,
            "Local runtime exceeded the configured timeout.",
        ) from exc
    except asyncio.CancelledError as exc:
        await _terminate_process_group(process, grace_seconds=term_grace_seconds)
        raise RuntimeInvocationError(
            RuntimeErrorCode.CANCELLED,
            "Local runtime invocation was cancelled.",
        ) from exc
    finally:
        if process.returncode is None:
            await _terminate_process_group(process, grace_seconds=term_grace_seconds)
        await asyncio.gather(completion, return_exceptions=True)
        # asyncio has no public Process.close(). Closing its transport prevents
        # unread, limit-exceeded pipes from surviving the event loop on Python 3.10.
        transport = getattr(process, "_transport", None)
        if transport is not None:
            transport.close()
        await asyncio.sleep(0)
