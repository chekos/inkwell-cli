"""Modal entry point for Inkwell web imports."""

from __future__ import annotations

import os
from typing import Any

import modal
from fastapi import HTTPException, Request

from workers.inkwell.worker import ImportJobPayload, run_import_job

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .uv_sync(".", extras=["worker"])
    .add_local_python_source("inkwell", "workers")
    .add_local_dir("src/inkwell/templates", remote_path="/root/inkwell/templates")
)
secret = modal.Secret.from_name("inkwell-worker")
app = modal.App(name="inkwell-worker", image=image, secrets=[secret])


@app.function(timeout=1800)
def process_import(payload: dict[str, Any]) -> dict[str, Any]:
    """Run an import in a long-lived Modal function."""

    return run_import_job(payload, worker_run_id=modal.current_function_call_id())


@app.function(timeout=60)
@modal.fastapi_endpoint(method="POST", docs=True)
async def start_import(request: Request) -> dict[str, Any]:
    """Authenticate and enqueue an import job from the web app."""

    _authorize(request)
    payload_data = await request.json()
    payload = ImportJobPayload.model_validate(payload_data)
    call = process_import.spawn(payload.model_dump(mode="json", by_alias=True))

    return {"ok": True, "workerRunId": call.object_id}


def _authorize(request: Request) -> None:
    expected_token = os.getenv("INKWELL_WORKER_TOKEN")
    if not expected_token:
        return

    authorization = request.headers.get("authorization")
    if authorization != f"Bearer {expected_token}":
        raise HTTPException(status_code=401, detail="Unauthorized")
