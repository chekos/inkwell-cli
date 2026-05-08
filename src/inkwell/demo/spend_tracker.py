"""Monthly spend cap for the demo (m4 of OBRA-74).

The OBRA-73 plan budgets the demo at ``$50/month`` of API spend across
Gemini transcription + extraction. Once we've crossed that cap the
demo accepts emails (acquisition signal stays on) but refuses to run
the pipeline until the next calendar month. Spend is recorded after
each successful run from the worker.

The protocol matches the rate-limit module: a route-time check that
looks at the current month's accumulated cost, and a worker-time
record that adds to it. The Firestore implementation in a follow-up
issue lives under ``rate_limits/{YYYY-MM}/spend`` with an atomic
``Increment``.

Months reset at UTC midnight on day 1 — same convention as the daily
rate-limit counters so the operator runbook only has to know one
clock.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class SpendDecision:
    """Result of a spend-cap check before enqueueing a pipeline run."""

    paused: bool
    spent_usd: float
    cap_usd: float

    @property
    def remaining_usd(self) -> float:
        return max(self.cap_usd - self.spent_usd, 0.0)

    @property
    def user_message(self) -> str:
        if not self.paused:
            return ""
        return (
            "We've hit this month's API spend cap. The demo is paused "
            "until the budget resets. The CLI works against your own "
            "API key without any cap — see the install steps below."
        )


class SpendTracker(Protocol):
    """Monthly spend tracker the route + worker depend on."""

    async def check_cap(self, *, cap_usd: float) -> SpendDecision: ...

    async def record_spend(self, *, cost_usd: float) -> None: ...

    async def total_for_current_month(self) -> float: ...


class InMemorySpendTracker:
    """Process-local :class:`SpendTracker`.

    Single-instance only. The Firestore implementation will use a
    transactional ``Increment`` on ``rate_limits/{YYYY-MM}/spend``.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # Map of YYYY-MM -> accumulated USD.
        self._totals: dict[str, float] = {}

    async def check_cap(self, *, cap_usd: float) -> SpendDecision:
        month = _this_month()
        async with self._lock:
            self._trim(month)
            spent = self._totals.get(month, 0.0)
        return SpendDecision(
            paused=spent >= cap_usd,
            spent_usd=spent,
            cap_usd=cap_usd,
        )

    async def record_spend(self, *, cost_usd: float) -> None:
        if cost_usd <= 0:
            return
        month = _this_month()
        async with self._lock:
            self._trim(month)
            self._totals[month] = self._totals.get(month, 0.0) + cost_usd

    async def total_for_current_month(self) -> float:
        month = _this_month()
        async with self._lock:
            self._trim(month)
            return self._totals.get(month, 0.0)

    def _trim(self, current: str) -> None:
        stale = [m for m in self._totals if m != current]
        for m in stale:
            del self._totals[m]


def _this_month() -> str:
    """UTC YYYY-MM; spend counters reset at the start of each month."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m")
