"""Daily rate limits for the demo (m4 of OBRA-74).

The OBRA-73 plan locks three counters that we track per UTC day:

- ``daily_attempts_per_ip`` (default ``3``) — every submission that
  passes URL classification counts. Failures count too; the goal is to
  cap a single IP from spamming us, not to reward bad URLs.
- ``daily_runs_per_email`` (default ``1``) — successful runs only.
  Multiple submissions are allowed if the earlier ones failed; only the
  successful run consumes the quota.
- ``daily_run_cap`` (default ``20``) — global success ceiling, applied
  before we enqueue. Once we have real cost data the operator widens
  this in :class:`DemoConfig`.

The protocol exposes one *check-and-record* call per counter so a
Firestore implementation can do the work in a single transactional
increment instead of two round trips. ``record_success`` is separate
because it fires from the worker, not from the route handler.

Day boundaries are UTC midnight to keep counters deterministic across
Cloud Run regions and for testing. The in-memory implementation keys
counters by ``(<counter-name>, <YYYY-MM-DD>, <hash-or-global>)`` and
trims old entries opportunistically; Firestore will use TTL fields.
"""

from __future__ import annotations

import asyncio
import enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


class RateLimitOutcome(str, enum.Enum):
    """Why a rate-limit decision allowed or refused a submission."""

    ALLOWED = "allowed"
    IP_ATTEMPTS_EXHAUSTED = "ip_attempts_exhausted"
    EMAIL_ALREADY_USED = "email_already_used"
    GLOBAL_CAP_EXHAUSTED = "global_cap_exhausted"


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of a rate-limit check."""

    allowed: bool
    outcome: RateLimitOutcome
    user_message: str
    """User-safe message the route layer surfaces verbatim."""


_ALLOWED = RateLimitDecision(
    allowed=True,
    outcome=RateLimitOutcome.ALLOWED,
    user_message="",
)


def _ip_exhausted_message(cap: int) -> str:
    return (
        f"You've hit the daily limit of {cap} attempts from your IP. "
        "Try again tomorrow or use the CLI in the meantime."
    )


def _email_used_message() -> str:
    return (
        "This email already ran a demo today. The CLI does the same thing "
        "without the daily cap if you want more — see the install steps below."
    )


def _global_cap_message() -> str:
    return (
        "We've hit the global demo cap for today. Try again tomorrow or "
        "install the CLI to keep going now."
    )


class RateLimiter(Protocol):
    """Daily rate-limit protocol the route + worker depend on."""

    async def record_attempt_and_check(
        self,
        *,
        ip_hash: str,
        cap: int,
    ) -> RateLimitDecision:
        """Increment the IP attempt counter and decide whether to proceed.

        The increment happens unconditionally so a refused submission
        still burns one attempt of the IP's daily allowance. Returns
        :class:`RateLimitOutcome.IP_ATTEMPTS_EXHAUSTED` if the counter
        is now over ``cap``.
        """
        ...

    async def check_email_quota(
        self,
        *,
        email_hash: str,
        cap: int,
    ) -> RateLimitDecision:
        """Read-only check on the per-email success counter.

        Does NOT increment — the success is reserved by
        :meth:`record_success` from the worker only when the pipeline
        actually completes.
        """
        ...

    async def check_global_cap(self, *, cap: int) -> RateLimitDecision: ...

    async def record_success(self, *, email_hash: str) -> None:
        """Bump the per-email and global success counters atomically."""
        ...


class InMemoryRateLimiter:
    """Process-local :class:`RateLimiter`.

    Single-instance only. The Firestore implementation in a follow-up
    issue keys counters by ``rate_limits/{day}/{counter}/{key}`` and
    uses ``Increment`` for the atomic update.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # Counters keyed by (date, counter_name, key).
        self._counters: dict[tuple[str, str, str], int] = {}

    async def record_attempt_and_check(
        self,
        *,
        ip_hash: str,
        cap: int,
    ) -> RateLimitDecision:
        day = _today()
        async with self._lock:
            self._trim(day)
            count = self._counters.get((day, "ip_attempts", ip_hash), 0) + 1
            self._counters[(day, "ip_attempts", ip_hash)] = count
        if count > cap:
            return RateLimitDecision(
                allowed=False,
                outcome=RateLimitOutcome.IP_ATTEMPTS_EXHAUSTED,
                user_message=_ip_exhausted_message(cap),
            )
        return _ALLOWED

    async def check_email_quota(
        self,
        *,
        email_hash: str,
        cap: int,
    ) -> RateLimitDecision:
        day = _today()
        async with self._lock:
            self._trim(day)
            count = self._counters.get((day, "email_successes", email_hash), 0)
        if count >= cap:
            return RateLimitDecision(
                allowed=False,
                outcome=RateLimitOutcome.EMAIL_ALREADY_USED,
                user_message=_email_used_message(),
            )
        return _ALLOWED

    async def check_global_cap(self, *, cap: int) -> RateLimitDecision:
        day = _today()
        async with self._lock:
            self._trim(day)
            count = self._counters.get((day, "global_successes", ""), 0)
        if count >= cap:
            return RateLimitDecision(
                allowed=False,
                outcome=RateLimitOutcome.GLOBAL_CAP_EXHAUSTED,
                user_message=_global_cap_message(),
            )
        return _ALLOWED

    async def record_success(self, *, email_hash: str) -> None:
        day = _today()
        async with self._lock:
            self._trim(day)
            self._counters[(day, "email_successes", email_hash)] = (
                self._counters.get((day, "email_successes", email_hash), 0) + 1
            )
            self._counters[(day, "global_successes", "")] = (
                self._counters.get((day, "global_successes", ""), 0) + 1
            )

    def _trim(self, today: str) -> None:
        # Drop counters from prior days. Cheap because we only keep at
        # most a handful of keys per day and trim on every mutation
        # under the lock.
        stale = [key for key in self._counters if key[0] != today]
        for key in stale:
            del self._counters[key]


def _today() -> str:
    """UTC YYYY-MM-DD; counters reset at midnight UTC."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
