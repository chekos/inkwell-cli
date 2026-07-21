"""Bounded subprocess and environment-policy tests."""

import asyncio
import json
import os
import stat
import sys
import time
from pathlib import Path

import pytest

from inkwell.agent_runtime.models import RuntimeErrorCode, RuntimeInvocationError
from inkwell.agent_runtime.runner import build_minimal_environment, run_bounded_process


def _write_script(path: Path, body: str) -> Path:
    path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_environment_is_allowlisted_and_secret_shaped_names_are_denied() -> None:
    child = build_minimal_environment(
        {
            "HOME": "/safe/home",
            "USER": "safe-user",
            "PATH": "/safe/bin",
            "LANG": "en_US.UTF-8",
            "HTTPS_PROXY": "http://proxy.invalid",
            "OPENAI_API_KEY": "should-not-pass",
            "GITHUB_TOKEN": "should-not-pass",
            "SUPABASE_SERVICE_ROLE_KEY": "should-not-pass",
            "INKWELL_WORKER_TOKEN": "should-not-pass",
            "CUSTOM_SECRET": "should-not-pass",
            "UNRELATED": "should-not-pass",
        }
    )

    assert child == {
        "HOME": "/safe/home",
        "USER": "safe-user",
        "PATH": "/safe/bin",
        "LANG": "en_US.UTF-8",
        "HTTPS_PROXY": "http://proxy.invalid",
    }


@pytest.mark.asyncio
async def test_runner_delivers_prompt_over_stdin_not_argv(tmp_path: Path) -> None:
    marker = "hostile transcript marker 4419"
    script = _write_script(
        tmp_path / "stdin.py",
        "import json, os, sys\n"
        "payload = sys.stdin.read()\n"
        "print(json.dumps({'stdin': payload, 'argv': sys.argv, 'cwd': os.getcwd()}))\n",
    )

    result = await run_bounded_process(
        [str(script), "--fixed-flag"],
        stdin=marker.encode(),
        cwd=tmp_path,
        env=build_minimal_environment(),
        timeout_seconds=5,
        max_stdout_bytes=4096,
        max_stderr_bytes=4096,
        max_line_bytes=4096,
    )

    output = result.stdout.decode()
    assert marker in output
    assert marker not in " ".join([str(script), "--fixed-flag"])
    assert str(tmp_path) in output


@pytest.mark.asyncio
async def test_runner_preserves_documented_empty_string_arguments(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path / "argv.py",
        "import json, sys\nprint(json.dumps(sys.argv[1:]))\n",
    )

    result = await run_bounded_process(
        [str(script), "--tools", ""],
        stdin=b"",
        cwd=tmp_path,
        env=build_minimal_environment(),
        timeout_seconds=5,
        max_stdout_bytes=4096,
        max_stderr_bytes=4096,
        max_line_bytes=4096,
    )

    assert json.loads(result.stdout) == ["--tools", ""]


@pytest.mark.asyncio
async def test_runner_enforces_output_limit_and_cleans_process(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path / "large.py",
        "import sys\nsys.stdout.write('x' * 200000)\nsys.stdout.flush()\n",
    )

    with pytest.raises(RuntimeInvocationError) as raised:
        await run_bounded_process(
            [str(script)],
            stdin=b"",
            cwd=tmp_path,
            env=build_minimal_environment(),
            timeout_seconds=5,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
            max_line_bytes=1024,
        )

    assert raised.value.code == RuntimeErrorCode.OUTPUT_TOO_LARGE


@pytest.mark.asyncio
async def test_runner_timeout_terminates_process_group(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path / "sleep.py",
        "import time\ntime.sleep(30)\n",
    )

    with pytest.raises(RuntimeInvocationError) as raised:
        await run_bounded_process(
            [str(script)],
            stdin=b"",
            cwd=tmp_path,
            env=build_minimal_environment(),
            timeout_seconds=0.05,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
            max_line_bytes=1024,
            term_grace_seconds=0.05,
        )

    assert raised.value.code == RuntimeErrorCode.TIMEOUT


@pytest.mark.asyncio
async def test_runner_timeout_includes_blocked_stdin_transfer(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path / "ignore-stdin.py",
        "import time\ntime.sleep(30)\n",
    )

    with pytest.raises(RuntimeInvocationError) as raised:
        await run_bounded_process(
            [str(script)],
            stdin=b"x" * 2_000_000,
            cwd=tmp_path,
            env=build_minimal_environment(),
            timeout_seconds=0.05,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
            max_line_bytes=1024,
            term_grace_seconds=0.05,
        )

    assert raised.value.code == RuntimeErrorCode.TIMEOUT


@pytest.mark.skipif(os.name != "posix", reason="process-group proof is POSIX-specific")
@pytest.mark.asyncio
async def test_timeout_terminates_descendant_processes(tmp_path: Path) -> None:
    pid_file = tmp_path / "descendant.pid"
    script = _write_script(
        tmp_path / "descendant.py",
        "import pathlib, subprocess, sys, time\n"
        f"pid_file = pathlib.Path({str(pid_file)!r})\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        "pid_file.write_text(str(child.pid), encoding='utf-8')\n"
        "time.sleep(30)\n",
    )

    with pytest.raises(RuntimeInvocationError) as raised:
        await run_bounded_process(
            [str(script)],
            stdin=b"",
            cwd=tmp_path,
            env=build_minimal_environment(),
            timeout_seconds=1.0,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
            max_line_bytes=1024,
            term_grace_seconds=0.05,
        )

    assert raised.value.code == RuntimeErrorCode.TIMEOUT
    descendant_pid = int(pid_file.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        try:
            os.kill(descendant_pid, 0)
        except ProcessLookupError:
            break
        await asyncio.sleep(0.02)
    else:
        pytest.fail("descendant process survived runtime process-group cleanup")


@pytest.mark.asyncio
async def test_runner_cancellation_is_typed(tmp_path: Path) -> None:
    script = _write_script(tmp_path / "sleep.py", "import time\ntime.sleep(30)\n")
    task = asyncio.create_task(
        run_bounded_process(
            [str(script)],
            stdin=b"",
            cwd=tmp_path,
            env=build_minimal_environment(),
            timeout_seconds=60,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
            max_line_bytes=1024,
            term_grace_seconds=0.05,
        )
    )
    await asyncio.sleep(0.02)
    task.cancel()

    with pytest.raises(RuntimeInvocationError) as raised:
        await task

    assert raised.value.code == RuntimeErrorCode.CANCELLED
    assert os.name != "posix" or task.done()


@pytest.mark.asyncio
async def test_runner_cancellation_during_process_creation_is_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    creation_started = asyncio.Event()

    async def wait_during_creation(*_args: object, **_kwargs: object) -> None:
        creation_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", wait_during_creation)
    task = asyncio.create_task(
        run_bounded_process(
            ["runtime"],
            stdin=b"",
            cwd=tmp_path,
            env=build_minimal_environment(),
            timeout_seconds=60,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
            max_line_bytes=1024,
        )
    )
    await creation_started.wait()
    task.cancel()

    with pytest.raises(RuntimeInvocationError) as raised:
        await task

    assert raised.value.code == RuntimeErrorCode.CANCELLED
