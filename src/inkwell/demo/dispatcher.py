"""Indirection between the FastAPI route layer and the demo worker.

The OBRA-73 plan splits work dispatch into two stages:

- m3 (this file) — :class:`InProcessDispatcher` runs the work as an
  ``asyncio.Task`` on the same Cloud Run instance that accepted the
  POST. Sufficient for one box and the local dev loop.
- m5 — :class:`CloudTasksDispatcher` enqueues an HTTP-target task that
  hits the internal worker route on a separate Cloud Run revision so
  the public-facing instance can return immediately.

Routes depend on :class:`Dispatcher`; swapping implementations is a
single line in ``app.py``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from inkwell.demo.jobs import JobStore

logger = logging.getLogger(__name__)


# A worker callable runs the actual pipeline for a single job id. The
# route layer hands one of these to the dispatcher when it builds the
# ``InProcessDispatcher``; m5 will register a different worker that
# does an HTTP POST to the internal route.
WorkerCallable = Callable[[str], Awaitable[None]]


class Dispatcher(Protocol):
    """Schedule a job for execution after the POST has been ACKed."""

    async def dispatch(self, job_id: str) -> None: ...


class InProcessDispatcher:
    """Execute jobs as ``asyncio.Task`` on the current event loop.

    Tracks live tasks so they don't get garbage-collected mid-flight
    (asyncio's docs explicitly warn about that). Tasks self-deregister
    when they finish.
    """

    def __init__(self, *, worker: WorkerCallable, job_store: JobStore) -> None:
        self._worker = worker
        self._job_store = job_store
        self._tasks: set[asyncio.Task[None]] = set()

    async def dispatch(self, job_id: str) -> None:
        task = asyncio.create_task(self._run(job_id), name=f"demo-job-{job_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, job_id: str) -> None:
        try:
            await self._worker(job_id)
        except Exception:
            # The worker is responsible for marking the job failed in
            # the store. We log here so a bare exception (which
            # shouldn't happen but might in panicky paths) doesn't
            # vanish silently into the asyncio loop.
            logger.exception("In-process worker raised for job %s", job_id)
            await self._job_store.mark_failed(
                job_id,
                error_code="worker_unhandled_exception",
                error_message="The worker crashed before it could record an error.",
            )

    async def aclose(self) -> None:
        """Wait for in-flight tasks to finish.

        Called from FastAPI's lifespan shutdown so a Cloud Run revision
        rotation doesn't strand a job mid-pipeline. We do *not* cancel
        — partial cleanup is more dangerous than overrunning shutdown.
        """
        if not self._tasks:
            return
        await asyncio.gather(*self._tasks, return_exceptions=True)
