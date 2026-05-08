"""Demo job store + in-memory implementation.

The OBRA-73 plan splits the demo storage layer into two stages:

- m3 (this file) — an in-memory store that lives for the lifetime of
  the Cloud Run instance. Good enough for one box, plenty for tests
  and local dev, but loses every job on restart and doesn't share
  state across instances.
- m4 — a Firestore-backed implementation that satisfies the
  ``emails`` / ``demo_jobs`` / ``rate_limits`` schema in the plan and
  carries job state across instance churn.

m3 keeps both behind :class:`JobStore` so m4's swap is a single import
change in ``app.py``. The route layer never sees ``InMemoryJobStore``
directly.
"""

from __future__ import annotations

import asyncio
import enum
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from inkwell.demo.payload import DemoResultPayload


class JobStatus(str, enum.Enum):
    """Lifecycle states the frontend polls and renders against."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


# Status values that the frontend should *stop polling* on. Anything
# else is treated as "still working".
TERMINAL_STATUSES = frozenset({JobStatus.COMPLETE, JobStatus.FAILED})


@dataclass
class DemoJob:
    """A single demo run as recorded in the store.

    ``email_hash`` and ``url_hash`` are the persistent shape the
    Firestore schema in m4 expects; we hash up front so logs and
    in-memory snapshots can't accidentally leak the raw email.
    """

    id: str
    email_hash: str
    url_hash: str
    submitted_url: str
    submitted_at: float
    status: JobStatus = JobStatus.QUEUED
    payload: DemoResultPayload | None = None
    error_code: str | None = None
    error_message: str | None = None
    completed_at: float | None = None
    cost_usd: float | None = None
    extra: dict[str, object] = field(default_factory=dict)


class JobStore(Protocol):
    """Storage protocol the route layer depends on.

    Implementations must be safe to call from inside an ``asyncio`` task
    spawned by the FastAPI route handler. The in-memory implementation
    achieves that with a single ``asyncio.Lock``; the Firestore
    implementation in m4 will rely on Firestore's own atomic updates.
    """

    async def create(self, *, email: str, url: str) -> DemoJob: ...

    async def get(self, job_id: str) -> DemoJob | None: ...

    async def try_claim_for_run(self, job_id: str) -> bool:
        """Atomically transition the job from ``QUEUED`` to ``RUNNING``.

        Returns ``True`` only if the caller now owns execution of this
        job. Returns ``False`` for unknown jobs and for jobs already in
        ``RUNNING`` / ``COMPLETE`` / ``FAILED`` — the caller MUST skip
        any pipeline work in those cases.

        This is the idempotency primitive for the internal worker
        route. Cloud Tasks delivers at-least-once and retries any
        non-2xx response, so duplicate deliveries (or a retry after a
        transient blip) must not re-spend the per-job budget. m4's
        Firestore implementation will back this with a transactional
        update against ``demo_jobs/{id}``.
        """
        ...

    async def mark_complete(
        self,
        job_id: str,
        *,
        payload: DemoResultPayload,
        cost_usd: float,
    ) -> None: ...

    async def mark_failed(
        self,
        job_id: str,
        *,
        error_code: str,
        error_message: str,
    ) -> None: ...


class InMemoryJobStore:
    """Process-local :class:`JobStore`. Single-instance only.

    Suitable for m3 (one Cloud Run revision, ``--concurrency=1``) and
    for tests. Replaced by the Firestore implementation in m4.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, DemoJob] = {}
        self._lock = asyncio.Lock()

    async def create(self, *, email: str, url: str) -> DemoJob:
        job = DemoJob(
            id=uuid.uuid4().hex,
            email_hash=_hash(email.strip().lower()),
            url_hash=_hash(url.strip()),
            submitted_url=url,
            submitted_at=time.time(),
        )
        async with self._lock:
            self._jobs[job.id] = job
        return job

    async def get(self, job_id: str) -> DemoJob | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def try_claim_for_run(self, job_id: str) -> bool:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status is not JobStatus.QUEUED:
                # Already claimed (RUNNING) or finished (COMPLETE/FAILED).
                # The caller skips its work — this is what makes a
                # second Cloud Tasks delivery harmless.
                return False
            job.status = JobStatus.RUNNING
            return True

    async def mark_complete(
        self,
        job_id: str,
        *,
        payload: DemoResultPayload,
        cost_usd: float,
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = JobStatus.COMPLETE
            job.payload = payload
            job.cost_usd = cost_usd
            job.completed_at = time.time()

    async def mark_failed(
        self,
        job_id: str,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = JobStatus.FAILED
            job.error_code = error_code
            job.error_message = error_message
            job.completed_at = time.time()


def _hash(value: str) -> str:
    """SHA-256 hex digest of an unsalted lowercased string.

    m4 layers a per-deploy salt on top via Secret Manager. For m3 the
    raw hash is sufficient — the goal here is "don't print the email
    into logs", not cross-deploy unlinkability.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
