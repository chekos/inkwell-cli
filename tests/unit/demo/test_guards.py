"""Tests for the m4 guard layer: email capture, rate limits, spend cap.

These tests stand the FastAPI app up with in-memory backends and
exercise the guard sequence via ``TestClient``. They specifically
verify the OBRA-74 acceptance contract that the email is captured even
when the request is later refused (kill switch, rate limit, spend cap).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from inkwell.config.schema import GlobalConfig
from inkwell.demo.app import create_app
from inkwell.demo.classifier import ClassifiedUrl
from inkwell.demo.config import DemoConfig
from inkwell.demo.email_store import InMemoryEmailStore
from inkwell.demo.hashing import hash_with_salt
from inkwell.demo.jobs import InMemoryJobStore
from inkwell.demo.payload import DemoNoteFile, DemoResultPayload
from inkwell.demo.rate_limits import InMemoryRateLimiter
from inkwell.demo.service import DemoJobResult
from inkwell.demo.spend_tracker import InMemorySpendTracker

_TEST_SALT = "test-salt-deadbeef"


class _RecordingDispatcher:
    def __init__(self) -> None:
        self.dispatched: list[str] = []

    async def dispatch(self, job_id: str) -> None:
        self.dispatched.append(job_id)


@pytest.fixture
def demo_config() -> DemoConfig:
    return DemoConfig(hash_salt=_TEST_SALT)


@pytest.fixture
def global_config() -> GlobalConfig:
    return GlobalConfig()


def _build(
    demo_config: DemoConfig,
    global_config: GlobalConfig,
    *,
    email_store: InMemoryEmailStore | None = None,
    rate_limiter: InMemoryRateLimiter | None = None,
    spend_tracker: InMemorySpendTracker | None = None,
    job_store: InMemoryJobStore | None = None,
) -> tuple[TestClient, dict[str, Any]]:
    es = email_store or InMemoryEmailStore()
    rl = rate_limiter or InMemoryRateLimiter()
    st = spend_tracker or InMemorySpendTracker()
    js = job_store or InMemoryJobStore()
    dispatcher = _RecordingDispatcher()
    app = create_app(
        demo_config=demo_config,
        global_config=global_config,
        job_store=js,
        email_store=es,
        rate_limiter=rl,
        spend_tracker=st,
        dispatcher=dispatcher,
    )
    return TestClient(app), {
        "email_store": es,
        "rate_limiter": rl,
        "spend_tracker": st,
        "job_store": js,
        "dispatcher": dispatcher,
    }


def _payload() -> DemoResultPayload:
    return DemoResultPayload(
        podcast_name="Acme",
        episode_title="Ep 1",
        episode_url="https://example.com/audio.mp3",
        duration_seconds=600.0,
        transcription_source="gemini",
        files=[
            DemoNoteFile(template="summary", filename="summary.md", title="Summary", markdown="x")
        ],
        extraction_cost_usd=0.04,
        total_cost_usd=0.07,
    )


# ---------------------------------------------------------------------------
# email capture
# ---------------------------------------------------------------------------


class TestEmailCapture:
    def test_captures_email_on_successful_submission(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
    ) -> None:
        client, deps = _build(demo_config, global_config)
        with client:
            response = client.post(
                "/jobs",
                data={"email": "user@example.com", "url": "https://example.com/feed.rss"},
            )
        assert response.status_code == 202
        email_hash = hash_with_salt("user@example.com", salt=_TEST_SALT)
        record = deps["email_store"]._rows.get(email_hash)  # noqa: SLF001
        assert record is not None
        assert record.email == "user@example.com"
        assert record.consent_version == demo_config.consent_version
        assert record.request_count == 1

    def test_captures_email_when_kill_switch_active(
        self,
        global_config: GlobalConfig,
    ) -> None:
        # OBRA-74 hard requirement #5 explicitly: capture the email even
        # when processing is paused.
        config = DemoConfig(hash_salt=_TEST_SALT, enabled=False)
        client, deps = _build(config, global_config)
        with client:
            response = client.post(
                "/jobs",
                data={"email": "u@example.com", "url": "https://example.com/feed.rss"},
            )
        assert response.status_code == 503
        assert response.json()["status"] == "maintenance"
        assert len(deps["email_store"]._rows) == 1  # noqa: SLF001

    def test_does_not_capture_invalid_email(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
    ) -> None:
        client, deps = _build(demo_config, global_config)
        with client:
            response = client.post(
                "/jobs",
                data={"email": "not-an-email", "url": "https://example.com/feed.rss"},
            )
        assert response.status_code == 400
        assert deps["email_store"]._rows == {}  # noqa: SLF001

    def test_increments_request_count_on_repeat_submission(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
    ) -> None:
        # Increase the per-email + per-IP cap so two submissions both pass.
        config = DemoConfig(
            hash_salt=_TEST_SALT,
            daily_attempts_per_ip=10,
            daily_runs_per_email=10,
        )
        client, deps = _build(config, global_config)
        with client:
            for _ in range(2):
                client.post(
                    "/jobs",
                    data={"email": "u@example.com", "url": "https://example.com/feed.rss"},
                )
        records = list(deps["email_store"]._rows.values())  # noqa: SLF001
        assert len(records) == 1
        assert records[0].request_count == 2


# ---------------------------------------------------------------------------
# rate limits
# ---------------------------------------------------------------------------


class TestRateLimits:
    def test_ip_attempt_cap_returns_429(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
    ) -> None:
        # Default is 3 attempts/IP/day; the 4th attempt must be refused.
        client, deps = _build(demo_config, global_config)
        with client:
            for _ in range(demo_config.daily_attempts_per_ip):
                ok = client.post(
                    "/jobs",
                    data={"email": "u@example.com", "url": "https://example.com/feed.rss"},
                )
                # Each one returns 202 OR 429 (email cap kicks in after 1) —
                # we only care that the IP cap kicks in eventually.
                assert ok.status_code in (202, 429)
            blocked = client.post(
                "/jobs",
                data={"email": "u@example.com", "url": "https://example.com/feed.rss"},
            )
        assert blocked.status_code == 429
        assert blocked.json()["detail"]["reason"] == "ip_attempts_exhausted"

    def test_email_quota_returns_429_after_success(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
    ) -> None:
        # Pre-record a success for the email so the read-only quota
        # check refuses the next submission. We bypass the route layer
        # for the success because the InMemoryRateLimiter exposes the
        # ``record_success`` primitive directly.
        client, deps = _build(demo_config, global_config)
        rl = deps["rate_limiter"]
        email_hash = hash_with_salt("u@example.com", salt=_TEST_SALT)

        async def _seed() -> None:
            await rl.record_success(email_hash=email_hash)

        import asyncio

        asyncio.get_event_loop().run_until_complete(_seed())

        with client:
            response = client.post(
                "/jobs",
                data={"email": "u@example.com", "url": "https://example.com/feed.rss"},
            )
        assert response.status_code == 429
        assert response.json()["detail"]["reason"] == "email_already_used"

    def test_global_cap_returns_429(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
    ) -> None:
        # Tiny global cap so we can prove the third decision tier
        # without burning the email or IP counters.
        config = DemoConfig(
            hash_salt=_TEST_SALT,
            daily_run_cap=1,
            daily_attempts_per_ip=10,
            daily_runs_per_email=10,
        )
        client, deps = _build(config, global_config)
        rl = deps["rate_limiter"]

        async def _seed_global() -> None:
            # Use a different email so the email-quota check passes.
            await rl.record_success(email_hash="other-email-hash")

        import asyncio

        asyncio.get_event_loop().run_until_complete(_seed_global())

        with client:
            response = client.post(
                "/jobs",
                data={"email": "u@example.com", "url": "https://example.com/feed.rss"},
            )
        assert response.status_code == 429
        assert response.json()["detail"]["reason"] == "global_cap_exhausted"

    def test_classifier_failure_does_not_burn_ip_attempt(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
    ) -> None:
        # Bad URLs should not consume the per-IP attempt budget.
        config = DemoConfig(hash_salt=_TEST_SALT, daily_attempts_per_ip=1)
        client, deps = _build(config, global_config)
        with client:
            bad = client.post(
                "/jobs",
                data={"email": "u@example.com", "url": "http://127.0.0.1/feed.rss"},
            )
            assert bad.status_code == 400
            # IP attempt counter is still 0 — the next valid submission
            # passes the IP check.
            ok = client.post(
                "/jobs",
                data={"email": "u@example.com", "url": "https://example.com/feed.rss"},
            )
        assert ok.status_code == 202

    def test_uses_x_forwarded_for_for_ip_hash(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
    ) -> None:
        # Cloud Run forwards real client IPs in X-Forwarded-For. Two
        # different XFF values should each have their own attempt
        # budget (i.e. the second submission isn't blocked even though
        # the underlying TCP peer is the same TestClient).
        config = DemoConfig(hash_salt=_TEST_SALT, daily_attempts_per_ip=1)
        client, _ = _build(config, global_config)
        with client:
            r1 = client.post(
                "/jobs",
                data={"email": "u1@example.com", "url": "https://example.com/feed.rss"},
                headers={"X-Forwarded-For": "203.0.113.10"},
            )
            r2 = client.post(
                "/jobs",
                data={"email": "u2@example.com", "url": "https://example.com/feed.rss"},
                headers={"X-Forwarded-For": "203.0.113.20"},
            )
        assert r1.status_code == 202
        assert r2.status_code == 202


# ---------------------------------------------------------------------------
# spend cap
# ---------------------------------------------------------------------------


class TestSpendCap:
    def test_spend_cap_pauses_with_503(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
    ) -> None:
        config = DemoConfig(hash_salt=_TEST_SALT, monthly_spend_cap_usd=1.0)
        client, deps = _build(config, global_config)
        st = deps["spend_tracker"]

        async def _seed_spend() -> None:
            await st.record_spend(cost_usd=1.0)

        import asyncio

        asyncio.get_event_loop().run_until_complete(_seed_spend())

        with client:
            response = client.post(
                "/jobs",
                data={"email": "u@example.com", "url": "https://example.com/feed.rss"},
            )
        assert response.status_code == 503
        assert response.json()["status"] == "maintenance"
        # Email was still captured.
        assert len(deps["email_store"]._rows) == 1  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_worker_records_spend_and_success(
        self,
        demo_config: DemoConfig,
        global_config: GlobalConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Mock the pipeline so the worker reaches mark_complete.
        async def fake_process_demo_job(
            classified: ClassifiedUrl,
            *,
            demo_config: DemoConfig,
            global_config: GlobalConfig,
        ) -> DemoJobResult:
            return DemoJobResult(
                payload=_payload(),
                resolved_source=Any,  # type: ignore[arg-type]
                total_cost_usd=0.07,
            )

        monkeypatch.setattr("inkwell.demo.app.process_demo_job", fake_process_demo_job)

        client, deps = _build(demo_config, global_config)
        # We need the internal-route entrypoint to drive the worker
        # synchronously; rebuild with worker_secret set.
        es = InMemoryEmailStore()
        rl = InMemoryRateLimiter()
        st = InMemorySpendTracker()
        js = InMemoryJobStore()
        app = create_app(
            demo_config=demo_config,
            global_config=global_config,
            job_store=js,
            email_store=es,
            rate_limiter=rl,
            spend_tracker=st,
            dispatcher=_RecordingDispatcher(),
            worker_secret="real-secret",
        )
        client = TestClient(app)

        job = await js.create(
            email="u@example.com",
            url="https://example.com/feed.rss",
            salt=_TEST_SALT,
        )

        with client:
            response = client.post(
                f"/_internal/jobs/{job.id}/run",
                headers={"X-Demo-Worker-Secret": "real-secret"},
            )
        assert response.status_code == 200

        # Spend tracker took the hit.
        assert await st.total_for_current_month() == pytest.approx(0.07)
        # Email's per-day success counter ticked over (1 of 1), so a
        # second submission for the same email today would now refuse.
        decision = await rl.check_email_quota(
            email_hash=job.email_hash,
            cap=demo_config.daily_runs_per_email,
        )
        assert decision.allowed is False
