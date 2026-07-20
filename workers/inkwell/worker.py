"""Supabase-backed worker adapter for web import jobs."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from inkwell.config.schema import (
    ExtractionConfig,
    GlobalConfig,
    InterviewConfig,
    TranscriptionConfig,
)
from inkwell.output.models import OutputFile
from inkwell.pipeline import PipelineOptions, PipelineOrchestrator
from inkwell.pipeline.models import PipelineResult

logger = logging.getLogger(__name__)


class ImportJobPayload(BaseModel):
    """Payload sent by the Vercel web app to Modal."""

    model_config = ConfigDict(populate_by_name=True)

    job_id: UUID = Field(alias="jobId")
    user_id: UUID = Field(alias="userId")
    url: str = Field(min_length=1, max_length=4096)
    category: str | None = Field(default=None, max_length=100)
    templates: list[str] | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("url must be an HTTP(S) URL")
        return value

    @field_validator("templates")
    @classmethod
    def clean_templates(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None

        cleaned = [template.strip() for template in value if template.strip()]
        return cleaned or None


class ImportJobRecord(BaseModel):
    """Subset of the import job row needed by the worker."""

    id: UUID
    source_id: UUID = Field(alias="source_id")
    status: str


class SupabaseJobStore:
    """Small Supabase REST client scoped to worker job mutations."""

    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.client = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))

    @classmethod
    def from_env(cls) -> SupabaseJobStore:
        supabase_url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not supabase_url:
            raise RuntimeError("SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL is required")

        if not service_role_key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required")

        return cls(supabase_url=supabase_url, service_role_key=service_role_key)

    def close(self) -> None:
        self.client.close()

    def get_job(self, payload: ImportJobPayload) -> ImportJobRecord:
        rows = self._request(
            "GET",
            "/rest/v1/import_jobs",
            params={
                "id": f"eq.{payload.job_id}",
                "user_id": f"eq.{payload.user_id}",
                "select": "id,source_id,status",
            },
        ).json()

        if not rows:
            raise RuntimeError(f"Import job not found: {payload.job_id}")

        return ImportJobRecord.model_validate(rows[0])

    def update_job(
        self,
        payload: ImportJobPayload,
        *,
        status: str | None = None,
        stage: str | None = None,
        worker_run_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        updates: dict[str, str] = {}

        if status is not None:
            updates["status"] = status
        if stage is not None:
            updates["stage"] = stage
        if worker_run_id is not None:
            updates["worker_run_id"] = worker_run_id
        if error_code is not None:
            updates["error_code"] = error_code
        if error_message is not None:
            updates["error_message"] = _truncate(error_message, 2000)
        if started_at is not None:
            updates["started_at"] = started_at.isoformat()
        if finished_at is not None:
            updates["finished_at"] = finished_at.isoformat()

        if not updates:
            return

        self._request(
            "PATCH",
            "/rest/v1/import_jobs",
            params={
                "id": f"eq.{payload.job_id}",
                "user_id": f"eq.{payload.user_id}",
            },
            json=updates,
            prefer="return=minimal",
        )

    def update_source(self, payload: ImportJobPayload, source_id: UUID, *, title: str) -> None:
        self._request(
            "PATCH",
            "/rest/v1/sources",
            params={
                "id": f"eq.{source_id}",
                "user_id": f"eq.{payload.user_id}",
            },
            json={
                "source_type": "episode",
                "title": title,
            },
            prefer="return=minimal",
        )

    def upsert_note(
        self,
        payload: ImportJobPayload,
        *,
        source_id: UUID,
        title: str,
        body_markdown: str,
        summary: str | None,
        metadata: dict[str, Any],
    ) -> None:
        self._request(
            "POST",
            "/rest/v1/notes",
            params={"on_conflict": "import_job_id"},
            json={
                "user_id": str(payload.user_id),
                "source_id": str(source_id),
                "import_job_id": str(payload.job_id),
                "title": title,
                "body_markdown": body_markdown,
                "summary": summary,
                "metadata": metadata,
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> httpx.Response:
        headers = {
            "apikey": self.service_role_key,
            "authorization": f"Bearer {self.service_role_key}",
            "content-type": "application/json",
        }

        if prefer:
            headers["prefer"] = prefer

        response = self.client.request(
            method,
            f"{self.supabase_url}{path}",
            params=params,
            json=json,
            headers=headers,
        )
        response.raise_for_status()
        return response


def run_import_job(
    payload_data: dict[str, Any],
    *,
    worker_run_id: str | None = None,
) -> dict[str, Any]:
    """Run one import job and persist the result to Supabase."""

    payload = ImportJobPayload.model_validate(payload_data)
    store = SupabaseJobStore.from_env()

    try:
        return asyncio.run(_run_import_job(payload, store, worker_run_id=worker_run_id))
    finally:
        store.close()


async def _run_import_job(
    payload: ImportJobPayload,
    store: SupabaseJobStore,
    *,
    worker_run_id: str | None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    store.update_job(
        payload,
        status="running",
        stage="fetching_source",
        worker_run_id=worker_run_id,
        started_at=now,
    )

    try:
        job = store.get_job(payload)
        with tempfile.TemporaryDirectory(prefix="inkwell-web-") as tmp_dir:
            output_dir = Path(tmp_dir) / "output"
            result = await _process_with_pipeline(
                payload,
                output_dir=output_dir,
                progress_callback=_progress_callback(payload, store),
            )

            title, body_markdown, summary, metadata = build_note_from_result(result)
            store.update_source(payload, job.source_id, title=title)
            store.upsert_note(
                payload,
                source_id=job.source_id,
                title=title,
                body_markdown=body_markdown,
                summary=summary,
                metadata=metadata,
            )

        store.update_job(
            payload,
            status="succeeded",
            stage="done",
            finished_at=datetime.now(timezone.utc),
        )
        return {"ok": True, "jobId": str(payload.job_id), "title": title}

    except Exception as exc:
        store.update_job(
            payload,
            status="failed",
            error_code=exc.__class__.__name__,
            error_message=str(exc),
            finished_at=datetime.now(timezone.utc),
        )
        raise


async def _process_with_pipeline(
    payload: ImportJobPayload,
    *,
    output_dir: Path,
    progress_callback: Callable[[str, dict[str, Any]], None],
) -> PipelineResult:
    config = build_worker_config(output_dir)
    orchestrator = PipelineOrchestrator(config, allow_local_runtime=False)
    episode_title = await _resolve_episode_title(payload.url)
    options = PipelineOptions(
        url=payload.url,
        category=payload.category,
        templates=payload.templates,
        episode_title=episode_title,
        output_dir=output_dir,
        overwrite=True,
        interview=False,
    )
    return await orchestrator.process_episode(options, progress_callback=progress_callback)


def build_worker_config(output_dir: Path) -> GlobalConfig:
    """Build an Inkwell config from Modal environment variables."""

    google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_AI_API_KEY")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    extraction_provider = os.getenv("INKWELL_EXTRACTION_PROVIDER", "gemini")
    if extraction_provider not in {"claude", "gemini"}:
        extraction_provider = "gemini"

    return GlobalConfig(
        default_output_dir=output_dir,
        transcription=TranscriptionConfig(api_key=google_api_key),
        extraction=ExtractionConfig(
            default_provider=extraction_provider,
            claude_api_key=anthropic_api_key,
            gemini_api_key=google_api_key,
        ),
        interview=InterviewConfig(enabled=False, auto_start=False),
    )


async def _resolve_episode_title(url: str) -> str | None:
    """Resolve a friendly title for direct web imports when cheap metadata exists."""

    if not _is_youtube_url(url):
        return None

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
            )
            response.raise_for_status()
            title = response.json().get("title")
    except Exception as exc:
        logger.warning("Could not resolve YouTube oEmbed title: %s", exc)
        return None

    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def _is_youtube_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname
    except ValueError:
        return False
    return (host or "").lower() in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
    }


def build_note_from_result(result: PipelineResult) -> tuple[str, str, str | None, dict[str, Any]]:
    """Convert filesystem-oriented pipeline output into one library note row."""

    episode_output = result.episode_output
    title = episode_output.metadata.episode_title
    markdown_files = [
        output_file
        for output_file in episode_output.output_files
        if not output_file.filename.startswith("_")
    ]
    if not markdown_files:
        markdown_files = list(episode_output.output_files)

    body_markdown = _assemble_note_body(title, episode_output.metadata.episode_url, markdown_files)
    summary = _extract_summary(markdown_files)
    metadata = _metadata_from_result(result)

    return title, body_markdown, summary, metadata


def _assemble_note_body(title: str, source_url: str, files: list[OutputFile]) -> str:
    parts = [f"# {title}", "", f"[Source]({source_url})"]

    for output_file in files:
        heading = _filename_to_heading(output_file.filename)
        content = _strip_frontmatter(output_file.content).strip()
        if not content:
            continue

        parts.extend(["", f"## {heading}", "", content])

    return "\n".join(parts).strip() + "\n"


def _extract_summary(files: list[OutputFile]) -> str | None:
    summary_file = next(
        (output_file for output_file in files if output_file.template_name == "summary"),
        None,
    )
    if summary_file is None:
        return None

    summary = _strip_frontmatter(summary_file.content).strip()
    return _truncate(summary, 1600) if summary else None


def _metadata_from_result(result: PipelineResult) -> dict[str, Any]:
    output = result.episode_output
    transcript = result.transcript_result.transcript

    return {
        "episode": output.metadata.model_dump(mode="json"),
        "transcription": {
            "source": transcript.source if transcript else None,
            "duration_seconds": result.transcript_result.duration_seconds,
            "from_cache": result.transcript_result.from_cache,
        },
        "extraction": {
            "successful": result.extraction_summary.successful,
            "failed": result.extraction_summary.failed,
            "cached": result.extraction_summary.cached,
            "cost_usd": result.extraction_cost_usd,
            "total_cost_usd": result.total_cost_usd,
        },
        "files": [
            {
                "filename": output_file.filename,
                "template": output_file.template_name,
                "size_bytes": output_file.size_bytes,
            }
            for output_file in output.output_files
        ],
        "worker": "modal",
    }


def _progress_callback(
    payload: ImportJobPayload,
    store: SupabaseJobStore,
) -> Callable[[str, dict[str, Any]], None]:
    stages = {
        "transcription_start": "extracting_transcript",
        "template_selection_start": "generating_notes",
        "extraction_start": "generating_notes",
        "output_start": "saving_result",
    }
    last_stage: dict[str, str | None] = {"value": None}

    def callback(step_name: str, _data: dict[str, Any]) -> None:
        stage = stages.get(step_name)
        if stage is None or stage == last_stage["value"]:
            return

        last_stage["value"] = stage
        store.update_job(payload, status="running", stage=stage)

    return callback


def _strip_frontmatter(markdown: str) -> str:
    if not markdown.startswith("---\n"):
        return markdown

    parts = markdown.split("---\n", 2)
    if len(parts) < 3:
        return markdown

    return parts[2].lstrip()


def _filename_to_heading(filename: str) -> str:
    stem = Path(filename).stem
    return stem.replace("-", " ").replace("_", " ").title()


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value

    return value[: max_length - 3].rstrip() + "..."
