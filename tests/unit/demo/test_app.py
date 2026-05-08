"""Integration tests for the demo FastAPI app (m3 / OBRA-77).

These tests use ``fastapi.testclient.TestClient`` against an app
constructed with stub :class:`JobStore` / :class:`Dispatcher` / pipeline
worker so they never touch real API keys, real Firestore, or real
audio. The route-level invariants verified here are:

- ``GET /healthz`` works
- ``GET /`` renders the index template
- ``POST /jobs`` rejects bad email
- ``POST /jobs`` rejects URLs the m1 classifier refuses
- ``POST /jobs`` accepted path enqueues a job and returns the id
- ``GET /jobs/{id}`` returns 404 for unknown ids
- ``GET /jobs/{id}`` returns the in-memory state and any payload
- ``POST /jobs`` honors the kill switch and returns 503 + email-saved
- ``POST /_internal/jobs/{id}/run`` returns 404 when not configured
- ``POST /_internal/jobs/{id}/run`` returns 401 with wrong secret
- ``POST /_internal/jobs/{id}/run`` runs the worker with the right secret
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from inkwell.config.schema import GlobalConfig
from inkwell.demo.app import create_app
from inkwell.demo.classifier import ClassifiedUrl, UrlKind
from inkwell.demo.config import DemoConfig
from inkwell.demo.dispatcher import Dispatcher
from inkwell.demo.jobs import InMemoryJobStore, JobStatus, JobStore
from inkwell.demo.payload import DemoNoteFile, DemoResultPayload
from inkwell.demo.service import DemoJobResult


class _RecordingDispatcher:
    """Captures dispatch calls without spawning asyncio tasks."""

    def __init__(self) -> None:
        self.dispatched: list[str] = []

    async def dispatch(self, job_id: str) -> None:
        self.dispatched.append(job_id)


@pytest.fixture
def demo_config() -> DemoConfig:
    return DemoConfig()


@pytest.fixture
def disabled_demo_config() -> DemoConfig:
    return DemoConfig(enabled=False)


@pytest.fixture
def global_config() -> GlobalConfig:
    # Defaults are enough for tests — we never actually run the pipeline.
    return GlobalConfig()


@pytest.fixture
def store() -> JobStore:
    return InMemoryJobStore()


@pytest.fixture
def dispatcher() -> _RecordingDispatcher:
    return _RecordingDispatcher()


def _make_client(
    *,
    demo_config: DemoConfig,
    global_config: GlobalConfig,
    store: JobStore,
    dispatcher: Dispatcher,
    worker_secret: str | None = None,
) -> TestClient:
    app = create_app(
        demo_config=demo_config,
        global_config=global_config,
        job_store=store,
        dispatcher=dispatcher,
        worker_secret=worker_secret,
    )
    return TestClient(app)


def _payload() -> DemoResultPayload:
    return DemoResultPayload(
        podcast_name="Acme",
        episode_title="Ep 1",
        episode_url="https://example.com/audio.mp3",
        duration_seconds=600.0,
        transcription_source="gemini",
        files=[
            DemoNoteFile(
                template="summary",
                filename="summary.md",
                title="Summary",
                markdown="# Summary",
            )
        ],
        extraction_cost_usd=0.04,
        total_cost_usd=0.07,
    )


# ---------------------------------------------------------------------------
# trivial routes
# ---------------------------------------------------------------------------


class TestHealthz:
    def test_returns_ok(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: JobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
        ) as client:
            response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestIndex:
    def test_renders_html(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: JobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
        ) as client:
            response = client.get("/")
        assert response.status_code == 200
        assert "Inkwell" in response.text
        assert "Make notes" in response.text
        assert 'name="email"' in response.text
        assert 'name="url"' in response.text


# ---------------------------------------------------------------------------
# POST /jobs
# ---------------------------------------------------------------------------


class TestPostJobs:
    def test_rejects_bad_email(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: JobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
        ) as client:
            response = client.post(
                "/jobs",
                data={"email": "not-an-email", "url": "https://example.com/feed.rss"},
            )
        assert response.status_code == 400
        assert response.json()["detail"]["reason"] == "invalid_email"
        assert dispatcher.dispatched == []

    def test_rejects_classifier_blocked_url(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: JobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
        ) as client:
            response = client.post(
                "/jobs",
                data={
                    "email": "user@example.com",
                    "url": "http://127.0.0.1/feed.rss",
                },
            )
        assert response.status_code == 400
        # The classifier raised — exact reason depends on which guard
        # triggered first. Check the user message instead.
        assert "private" in response.json()["detail"]["message"].lower() or (
            "local" in response.json()["detail"]["message"].lower()
        )
        assert dispatcher.dispatched == []

    def test_accepts_valid_submission_and_dispatches(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: JobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
        ) as client:
            response = client.post(
                "/jobs",
                data={
                    "email": "user@example.com",
                    "url": "https://example.com/feed.rss",
                },
            )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == JobStatus.QUEUED.value
        assert body["job_id"]
        assert dispatcher.dispatched == [body["job_id"]]

    def test_kill_switch_returns_maintenance_and_records_email(
        self,
        disabled_demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: InMemoryJobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        with _make_client(
            demo_config=disabled_demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
        ) as client:
            response = client.post(
                "/jobs",
                data={
                    "email": "user@example.com",
                    "url": "https://example.com/feed.rss",
                },
            )
        assert response.status_code == 503
        assert response.json()["status"] == "maintenance"
        # No work dispatched, but we did record the job (with email
        # hash) so acquisition signal isn't lost.
        assert dispatcher.dispatched == []
        assert len(store._jobs) == 1


# ---------------------------------------------------------------------------
# GET /jobs/{id}
# ---------------------------------------------------------------------------


class TestGetJob:
    def test_unknown_id_returns_404(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: JobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
        ) as client:
            response = client.get("/jobs/does-not-exist")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_completed_job_with_payload(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: InMemoryJobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        # Pre-populate a completed job and verify the response shape.
        job = await store.create(
            email="user@example.com",
            url="https://example.com/feed.rss",
            salt="test-salt",
        )
        await store.mark_complete(job.id, payload=_payload(), cost_usd=0.07)

        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
        ) as client:
            response = client.get(f"/jobs/{job.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == JobStatus.COMPLETE.value
        assert body["cost_usd"] == 0.07
        assert body["payload"]["files"][0]["template"] == "summary"
        assert body["payload"]["files"][0]["markdown"] == "# Summary"


# ---------------------------------------------------------------------------
# POST /_internal/jobs/{id}/run
# ---------------------------------------------------------------------------


class TestInternalWorkerRoute:
    def test_route_not_registered_when_no_secret_configured(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: JobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        # Diego's m3 review: when worker_secret is None the route must
        # not be registered at all. A 405 from a wrong-method probe
        # would otherwise leak the route's existence.
        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
            worker_secret=None,
        ) as client:
            post_response = client.post("/_internal/jobs/abc/run")
            get_response = client.get("/_internal/jobs/abc/run")
        # Both methods 404 — no Allow header advertising POST.
        assert post_response.status_code == 404
        assert get_response.status_code == 404
        assert "allow" not in {k.lower() for k in get_response.headers.keys()}

    def test_rejects_wrong_secret(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: JobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
            worker_secret="real-secret",
        ) as client:
            response = client.post(
                "/_internal/jobs/abc/run",
                headers={"X-Demo-Worker-Secret": "wrong"},
            )
        assert response.status_code == 401

    def test_rejects_missing_secret_header(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: JobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
            worker_secret="real-secret",
        ) as client:
            response = client.post("/_internal/jobs/abc/run")
        assert response.status_code == 401

    def test_unknown_job_returns_404_with_valid_secret(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: JobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
            worker_secret="real-secret",
        ) as client:
            response = client.post(
                "/_internal/jobs/does-not-exist/run",
                headers={"X-Demo-Worker-Secret": "real-secret"},
            )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_drives_worker_with_valid_secret(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: InMemoryJobStore,
        dispatcher: _RecordingDispatcher,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Mock process_demo_job so the worker doesn't try to hit real
        # YouTube / RSS / Gemini.
        async def fake_process_demo_job(
            classified: ClassifiedUrl,
            *,
            demo_config: DemoConfig,
            global_config: GlobalConfig,
        ) -> DemoJobResult:
            assert classified.kind is UrlKind.PUBLIC_RSS
            return DemoJobResult(
                payload=_payload(),
                resolved_source=Any,  # type: ignore[arg-type]
                total_cost_usd=0.07,
            )

        monkeypatch.setattr("inkwell.demo.app.process_demo_job", fake_process_demo_job)

        # Pre-create a job so the worker has something to drive.
        job = await store.create(
            email="user@example.com",
            url="https://example.com/feed.rss",
            salt="test-salt",
        )

        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
            worker_secret="real-secret",
        ) as client:
            response = client.post(
                f"/_internal/jobs/{job.id}/run",
                headers={"X-Demo-Worker-Secret": "real-secret"},
            )

        assert response.status_code == 200
        # Worker ran end-to-end; job is now complete.
        completed = await store.get(job.id)
        assert completed is not None
        assert completed.status is JobStatus.COMPLETE
        assert completed.payload is not None
        assert completed.cost_usd == 0.07

    @pytest.mark.asyncio
    async def test_duplicate_delivery_is_idempotent(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: InMemoryJobStore,
        dispatcher: _RecordingDispatcher,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Diego's m3 review (blocking): Cloud Tasks delivers
        # at-least-once, so a duplicate delivery for a completed job
        # must NOT re-spend. The internal route must short-circuit on
        # any non-QUEUED status.
        call_count = {"n": 0}

        async def fake_process_demo_job(
            classified: ClassifiedUrl,
            *,
            demo_config: DemoConfig,
            global_config: GlobalConfig,
        ) -> DemoJobResult:
            call_count["n"] += 1
            return DemoJobResult(
                payload=_payload(),
                resolved_source=Any,  # type: ignore[arg-type]
                total_cost_usd=0.07,
            )

        monkeypatch.setattr("inkwell.demo.app.process_demo_job", fake_process_demo_job)

        job = await store.create(
            email="user@example.com",
            url="https://example.com/feed.rss",
            salt="test-salt",
        )

        with _make_client(
            demo_config=demo_config,
            global_config=global_config,
            store=store,
            dispatcher=dispatcher,
            worker_secret="real-secret",
        ) as client:
            first = client.post(
                f"/_internal/jobs/{job.id}/run",
                headers={"X-Demo-Worker-Secret": "real-secret"},
            )
            second = client.post(
                f"/_internal/jobs/{job.id}/run",
                headers={"X-Demo-Worker-Secret": "real-secret"},
            )

        # Both deliveries return 200 so Cloud Tasks doesn't retry.
        assert first.status_code == 200
        assert second.status_code == 200
        # But the pipeline only ran once.
        assert call_count["n"] == 1
        # Job state is final.
        completed = await store.get(job.id)
        assert completed is not None
        assert completed.status is JobStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_concurrent_delivery_only_runs_once(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        store: InMemoryJobStore,
        dispatcher: _RecordingDispatcher,
    ) -> None:
        # Even with two concurrent claims of a fresh QUEUED job, only
        # one transition succeeds — the other returns False without
        # mutating state.
        job = await store.create(
            email="user@example.com",
            url="https://example.com/feed.rss",
            salt="test-salt",
        )
        first = await store.try_claim_for_run(job.id)
        second = await store.try_claim_for_run(job.id)
        assert first is True
        assert second is False
        # Unknown ids never claim.
        assert await store.try_claim_for_run("nope") is False
