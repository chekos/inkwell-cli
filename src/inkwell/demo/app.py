"""FastAPI app for the public try-it demo (m3 of OBRA-74).

This is the public face of the demo. It:

- serves a single Jinja-rendered page with email-gate + URL field
- accepts ``POST /jobs`` with email + url, runs the m1 classifier
  synchronously, persists the job, and dispatches the m2 pipeline
  asynchronously
- exposes ``GET /jobs/{id}`` for the polling frontend
- exposes ``POST /_internal/jobs/{id}/run`` so m5's Cloud Tasks worker
  can drive jobs out-of-process behind a shared-secret header
- honors the OBRA-74 kill switch (``DEMO_PIPELINE_ENABLED=false``) by
  refusing to enqueue while still recording the email

Storage and dispatch live behind protocols so m4 can swap in Firestore
and m5 can swap in Cloud Tasks without touching the route layer.
"""

# NB: this module deliberately does NOT use ``from __future__ import
# annotations``. FastAPI's ``Depends(local_callable)`` pattern relies on
# Python evaluating the ``Annotated[...]`` expression at function-
# definition time so the ``Depends`` object captures the closed-over
# provider. Future annotations would defer that evaluation, and by the
# time FastAPI tries to resolve the type hint via ``get_type_hints`` the
# local provider would no longer be in scope.

import logging
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from email.utils import parseaddr
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from inkwell.config.manager import ConfigManager
from inkwell.config.schema import GlobalConfig
from inkwell.demo.classifier import DemoUrlError, classify_demo_url
from inkwell.demo.config import DemoConfig, get_demo_config
from inkwell.demo.dispatcher import Dispatcher, InProcessDispatcher
from inkwell.demo.email_store import EmailStore, InMemoryEmailStore
from inkwell.demo.hashing import hash_with_salt
from inkwell.demo.jobs import DemoJob, InMemoryJobStore, JobStatus, JobStore
from inkwell.demo.rate_limits import InMemoryRateLimiter, RateLimiter
from inkwell.demo.service import (
    DemoDurationBackstopError,
    DemoPipelineDisabledError,
    process_demo_job,
)
from inkwell.demo.spend_tracker import InMemorySpendTracker, SpendTracker
from inkwell.utils.errors import InkwellError

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"

# OBRA-77 routes the in-process dispatcher target at this header. The
# route compares with secrets.compare_digest so a missing/empty secret
# can't be matched against a request that also forgot the header.
_WORKER_SECRET_HEADER = "X-Demo-Worker-Secret"


# ---------------------------------------------------------------------------
# response shapes
# ---------------------------------------------------------------------------


class DemoNoteFileOut(BaseModel):
    """One rendered markdown file in the demo response."""

    template: str
    filename: str
    title: str
    markdown: str


class DemoResultPayloadOut(BaseModel):
    """Pydantic mirror of :class:`inkwell.demo.payload.DemoResultPayload`."""

    podcast_name: str
    episode_title: str
    episode_url: str
    duration_seconds: float | None = None
    transcription_source: str
    files: list[DemoNoteFileOut]
    extraction_cost_usd: float
    total_cost_usd: float


class JobAccepted(BaseModel):
    """Returned from ``POST /jobs`` after a job is enqueued."""

    job_id: str = Field(..., description="Server-issued opaque job identifier.")
    status: JobStatus = Field(..., description="Initial job status.")


class MaintenanceResponse(BaseModel):
    """Returned from ``POST /jobs`` when the kill switch is set.

    The email is still recorded so we keep acquisition signal during
    the pause window (per OBRA-74 hard requirement #5).
    """

    status: str = Field(default="maintenance")
    detail: str


class JobStatusResponse(BaseModel):
    """The shape ``GET /jobs/{id}`` returns to the polling frontend."""

    job_id: str
    status: JobStatus
    submitted_url: str
    payload: DemoResultPayloadOut | None = None
    error_code: str | None = None
    error_message: str | None = None
    cost_usd: float | None = None


# ---------------------------------------------------------------------------
# request validation
# ---------------------------------------------------------------------------


def _normalize_email(raw: str) -> str:
    """Reject obviously bad emails. Real validation lives in m4 (Firestore)."""
    candidate = (raw or "").strip()
    _name, address = parseaddr(candidate)
    if not address or "@" not in address or address.startswith("@") or address.endswith("@"):
        raise DemoUrlError(
            "We need a valid email to run the demo.",
            reason="invalid_email",
        )
    return address.lower()


def _client_ip(request: Request, *, trusted_proxy_count: int) -> str:
    """Extract the per-rate-limit client IP from a request.

    Cloud Run terminates TLS at a Google Cloud Load Balancer that
    *appends* one entry to the end of ``X-Forwarded-For`` containing
    the real client IP. The LEFTmost values are attacker-controlled —
    clients can put anything they want there. The codex P1 on PR #77
    flagged the original leftmost-takes-all implementation as a
    rate-limit bypass.

    Algorithm: with ``N = trusted_proxy_count`` we expect the rightmost
    ``N`` entries to come from our own LB chain. The ``N``-from-the-end
    entry (``parts[-N]``) is the real client IP — it's the leftmost
    entry our chain appended, attacker cannot influence its position.

    Falls back to the socket peer when ``X-Forwarded-For`` is absent,
    when there are fewer entries than ``trusted_proxy_count``, or when
    ``trusted_proxy_count == 0`` (direct-internet deploys without an
    LB — no LB means no trusted XFF). The value is hashed with the
    demo salt before storage; we never persist the raw IP.
    """
    if trusted_proxy_count > 0:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if len(parts) >= trusted_proxy_count:
                return parts[-trusted_proxy_count]
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def _refuse(status_code: int, reason: str, message: str) -> JSONResponse:
    """Compact rate-limit refusal payload — same shape on every counter."""
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"reason": reason, "message": message}},
    )


# ---------------------------------------------------------------------------
# worker
# ---------------------------------------------------------------------------


WorkerCallable = Callable[[str], Awaitable[None]]


def _build_worker(
    *,
    job_store: JobStore,
    rate_limiter: RateLimiter,
    spend_tracker: SpendTracker,
    demo_config: DemoConfig,
    global_config: GlobalConfig,
) -> WorkerCallable:
    """Return a worker callable bound to the supplied dependencies.

    The dispatcher invokes the returned callable per job id. We keep
    the binding lazy so tests can construct an ``InMemoryJobStore`` and
    a ``DemoConfig`` for assertion without touching real API keys.

    On a successful run the worker also records the spend (monthly cap)
    and the per-email + global success counters (daily caps) — both
    side-effects belong on the worker so a Cloud Tasks retry that
    races a fresh attempt doesn't double-count.
    """

    async def _worker(job_id: str) -> None:
        job = await job_store.get(job_id)
        if job is None:
            logger.warning("worker received unknown job %s", job_id)
            return

        # Atomic QUEUED -> RUNNING transition. If the claim fails the
        # job is already RUNNING / COMPLETE / FAILED — bail out without
        # spending again. Cloud Tasks delivers at-least-once and this
        # is the primary defense against duplicate deliveries
        # re-running a finished job.
        if not await job_store.try_claim_for_run(job_id):
            logger.info("worker skipped already-claimed job %s", job_id)
            return

        try:
            classified = classify_demo_url(job.submitted_url)
            result = await process_demo_job(
                classified,
                demo_config=demo_config,
                global_config=global_config,
            )
        except DemoUrlError as exc:
            await job_store.mark_failed(
                job_id,
                error_code=exc.reason,
                error_message=exc.user_message,
            )
            return
        except DemoPipelineDisabledError as exc:
            # Should never reach the worker — POST /jobs short-circuits
            # on the kill switch — but if a Cloud Tasks delivery beats
            # the env-var update we still surface a clean error.
            await job_store.mark_failed(
                job_id,
                error_code="demo_pipeline_disabled",
                error_message=str(exc),
            )
            return
        except DemoDurationBackstopError as exc:
            await job_store.mark_failed(
                job_id,
                error_code="duration_backstop_triggered",
                error_message=str(exc),
            )
            return
        except InkwellError as exc:
            logger.exception("pipeline error on job %s", job_id)
            await job_store.mark_failed(
                job_id,
                error_code=type(exc).__name__,
                error_message="The pipeline failed. Please try a different URL.",
            )
            return
        except Exception:
            logger.exception("unexpected worker error on job %s", job_id)
            await job_store.mark_failed(
                job_id,
                error_code="unexpected_error",
                error_message="Something went wrong. Please try again.",
            )
            return

        await job_store.mark_complete(
            job_id,
            payload=result.payload,
            cost_usd=result.total_cost_usd,
        )
        # Side-effects only after mark_complete so a crash mid-write
        # never reports a job as complete with stale counters.
        await spend_tracker.record_spend(cost_usd=result.total_cost_usd)
        await rate_limiter.record_success(email_hash=job.email_hash)
        logger.info("demo job %s complete cost=$%.4f", job_id, result.total_cost_usd)

    return _worker


# ---------------------------------------------------------------------------
# app factory
# ---------------------------------------------------------------------------


def create_app(
    *,
    demo_config: DemoConfig | None = None,
    global_config: GlobalConfig | None = None,
    job_store: JobStore | None = None,
    email_store: EmailStore | None = None,
    rate_limiter: RateLimiter | None = None,
    spend_tracker: SpendTracker | None = None,
    dispatcher: Dispatcher | None = None,
    worker_secret: str | None = None,
) -> FastAPI:
    """Construct the FastAPI app for the demo.

    All keyword args have sensible production defaults but every one of
    them is overridable so tests can inject fakes without monkey-patching.

    Args:
        demo_config: Loaded :class:`DemoConfig`. Defaults to the
            cached singleton from :func:`get_demo_config`.
        global_config: Inkwell :class:`GlobalConfig` for the pipeline
            (API keys, defaults). Loaded via :class:`ConfigManager` if
            omitted.
        job_store: :class:`JobStore` implementation. Defaults to
            in-memory; the Firestore swap lands in a follow-up issue.
        email_store: :class:`EmailStore` implementation. Defaults to
            in-memory; same Firestore-swap path.
        rate_limiter: :class:`RateLimiter` implementation. Defaults to
            in-memory daily counters.
        spend_tracker: :class:`SpendTracker` implementation. Defaults
            to in-memory monthly accumulator.
        dispatcher: :class:`Dispatcher` implementation. Defaults to
            in-process asyncio tasks; m5 swaps in Cloud Tasks.
        worker_secret: Shared secret expected on the
            ``X-Demo-Worker-Secret`` header for the internal worker
            route. ``None`` (the default) **disables** the route — m5
            generates a real secret in Secret Manager.
    """
    config = demo_config or get_demo_config()
    global_cfg = global_config or ConfigManager().load_config()
    store: JobStore = job_store or InMemoryJobStore()
    emails: EmailStore = email_store or InMemoryEmailStore()
    limiter: RateLimiter = rate_limiter or InMemoryRateLimiter()
    spend: SpendTracker = spend_tracker or InMemorySpendTracker()

    worker = _build_worker(
        job_store=store,
        rate_limiter=limiter,
        spend_tracker=spend,
        demo_config=config,
        global_config=global_cfg,
    )
    dispatch: Dispatcher = dispatcher or InProcessDispatcher(worker=worker, job_store=store)

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            close = getattr(dispatch, "aclose", None)
            if close is not None:
                await close()

    app = FastAPI(
        title="Inkwell Demo",
        version="0.1.0",
        lifespan=_lifespan,
        docs_url=None,  # demo doesn't need /docs in production
        redoc_url=None,
    )
    templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # ---- shared dependency providers (closed over factory state) ----

    def get_store() -> JobStore:
        return store

    def get_dispatch() -> Dispatcher:
        return dispatch

    def get_config() -> DemoConfig:
        return config

    def require_worker_secret(
        provided: Annotated[str | None, Header(alias=_WORKER_SECRET_HEADER)] = None,
    ) -> None:
        # The route is only registered when worker_secret is set, so
        # ``worker_secret is None`` is unreachable here. Asserting for
        # mypy + defensive future-proofing.
        assert worker_secret is not None  # noqa: S101
        if not provided or not secrets.compare_digest(worker_secret, provided):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid worker secret",
            )

    # ---- routes ----

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "consent_version": config.consent_version,
                "kill_switch_active": not config.enabled,
                "max_duration_minutes": config.max_duration_seconds // 60,
            },
        )

    @app.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
    async def create_job(
        request: Request,
        store: Annotated[JobStore, Depends(get_store)],
        dispatcher: Annotated[Dispatcher, Depends(get_dispatch)],
        config: Annotated[DemoConfig, Depends(get_config)],
        email: Annotated[str, Form(...)],
        url: Annotated[str, Form(...)],
    ) -> JSONResponse:
        # OBRA-74 hard requirement #5: capture the email *before* any
        # refusal path so a kill switch / rate limit / spend cap pause
        # still preserves acquisition signal. Email format errors do
        # short-circuit, but anything that gets past _normalize_email
        # is recorded.
        try:
            normalized_email = _normalize_email(email)
        except DemoUrlError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"reason": exc.reason, "message": exc.user_message},
            ) from exc

        await emails.capture(
            email=normalized_email,
            salt=config.hash_salt,
            consent_version=config.consent_version,
        )

        # Run the cheap classifier synchronously so users get immediate
        # feedback on bad URLs instead of polling for a failure. Bad
        # URLs do not consume a per-IP attempt — there's no point
        # punishing a typo.
        try:
            classify_demo_url(url)
        except DemoUrlError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"reason": exc.reason, "message": exc.user_message},
            ) from exc

        # Now the request looks credible. Burn one of the IP's daily
        # attempts (failures count too — that's the OBRA-73 contract).
        ip_hash = hash_with_salt(
            _client_ip(request, trusted_proxy_count=config.trusted_proxy_count),
            salt=config.hash_salt,
        )
        ip_decision = await limiter.record_attempt_and_check(
            ip_hash=ip_hash,
            cap=config.daily_attempts_per_ip,
        )
        if not ip_decision.allowed:
            return _refuse(
                status.HTTP_429_TOO_MANY_REQUESTS,
                ip_decision.outcome.value,
                ip_decision.user_message,
            )

        # Per-email success quota — read-only check, the success isn't
        # consumed until the worker confirms the run completed.
        email_hash = hash_with_salt(normalized_email, salt=config.hash_salt)
        email_decision = await limiter.check_email_quota(
            email_hash=email_hash,
            cap=config.daily_runs_per_email,
        )
        if not email_decision.allowed:
            return _refuse(
                status.HTTP_429_TOO_MANY_REQUESTS,
                email_decision.outcome.value,
                email_decision.user_message,
            )

        # Global daily success cap.
        global_decision = await limiter.check_global_cap(cap=config.daily_run_cap)
        if not global_decision.allowed:
            return _refuse(
                status.HTTP_429_TOO_MANY_REQUESTS,
                global_decision.outcome.value,
                global_decision.user_message,
            )

        # Monthly spend cap.
        spend_decision = await spend.check_cap(cap_usd=config.monthly_spend_cap_usd)
        if spend_decision.paused:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=MaintenanceResponse(detail=spend_decision.user_message).model_dump(),
            )

        job = await store.create(email=normalized_email, url=url, salt=config.hash_salt)

        if not config.enabled:
            # Kill switch on: email is already captured above. Mark
            # the job failed so it shows in admin/audit views and
            # return the maintenance response.
            await store.mark_failed(
                job.id,
                error_code="demo_pipeline_disabled",
                error_message=(
                    "The demo is paused for maintenance. We saved your email "
                    "and will let you know when it's back."
                ),
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=MaintenanceResponse(
                    detail="The demo is paused for maintenance.",
                ).model_dump(),
            )

        await dispatcher.dispatch(job.id)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=JobAccepted(job_id=job.id, status=JobStatus.QUEUED).model_dump(),
        )

    @app.get("/jobs/{job_id}")
    async def get_job(
        job_id: str, store: Annotated[JobStore, Depends(get_store)]
    ) -> JobStatusResponse:
        job = await store.get(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
        return _job_to_response(job)

    # The internal worker route is only registered when a secret is
    # configured. Without that, even a 405 from a wrong-method probe
    # would advertise the route's existence (Diego's m3 review point);
    # not registering at all keeps the route surface clean for dev /
    # preview deploys that don't run a Cloud Tasks worker.
    if worker_secret is not None:

        @app.post("/_internal/jobs/{job_id}/run", dependencies=[Depends(require_worker_secret)])
        async def run_job_internal(
            job_id: str, store: Annotated[JobStore, Depends(get_store)]
        ) -> dict[str, str]:
            job = await store.get(job_id)
            if job is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
            # ``worker()`` is itself idempotent — ``try_claim_for_run``
            # short-circuits a second delivery — so we just call it.
            # Returning 200 even for the no-op skip path is correct
            # behavior: Cloud Tasks should NOT retry.
            await worker(job_id)
            return {"status": "ok", "job_id": job_id}

    return app


def _job_to_response(job: DemoJob) -> JobStatusResponse:
    payload_out: DemoResultPayloadOut | None = None
    if job.payload is not None:
        payload_out = DemoResultPayloadOut(
            podcast_name=job.payload.podcast_name,
            episode_title=job.payload.episode_title,
            episode_url=job.payload.episode_url,
            duration_seconds=job.payload.duration_seconds,
            transcription_source=job.payload.transcription_source,
            files=[
                DemoNoteFileOut(
                    template=f.template,
                    filename=f.filename,
                    title=f.title,
                    markdown=f.markdown,
                )
                for f in job.payload.files
            ],
            extraction_cost_usd=job.payload.extraction_cost_usd,
            total_cost_usd=job.payload.total_cost_usd,
        )

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        submitted_url=job.submitted_url,
        payload=payload_out,
        error_code=job.error_code,
        error_message=job.error_message,
        cost_usd=job.cost_usd,
    )
