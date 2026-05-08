"""Email capture for the public try-it demo.

OBRA-74 hard requirement #5: every submission records the email
*before* anything else can refuse it (kill switch, rate limit, spend
cap). The collected emails are the primary acquisition signal during
the try-it window — losing them on a refusal path defeats the whole
strategy.

This module isolates that contract behind :class:`EmailStore` so the
in-memory implementation we ship in m4 can be swapped for the
Firestore-backed implementation without touching the route layer. The
Firestore schema in the OBRA-73 plan is::

    emails/{emailHash}: {
        email: <plaintext, only stored once>,
        firstSeenAt: <timestamp>,
        latestSeenAt: <timestamp>,
        source: "try_it_demo",
        consentVersion: <DemoConfig.consent_version>,
        requestCount: <int>,
    }

The in-memory implementation keeps the same field set so the swap is a
direct mapping.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Protocol

from inkwell.demo.hashing import hash_with_salt

_DEFAULT_SOURCE = "try_it_demo"


@dataclass
class EmailRecord:
    """Single emails-collection row.

    The plaintext ``email`` is stored exactly once — m4's Firestore
    schema flags it as PII and rotates the hash salt as the abuse
    response, leaving the plaintext column untouched until we hand it
    to an ESP. Storing both lets us correlate within a deploy without
    leaking identity to anyone who only has post-rotation hashes.
    """

    email_hash: str
    email: str
    first_seen_at: float
    latest_seen_at: float
    source: str
    consent_version: str
    request_count: int = 1
    extra: dict[str, object] = field(default_factory=dict)


class EmailStore(Protocol):
    """Storage protocol for captured emails."""

    async def capture(
        self,
        *,
        email: str,
        salt: str,
        consent_version: str,
        source: str = _DEFAULT_SOURCE,
    ) -> EmailRecord:
        """Insert or update the email row and return the persisted state."""
        ...

    async def get(self, email_hash: str) -> EmailRecord | None: ...


class InMemoryEmailStore:
    """Process-local :class:`EmailStore`.

    Single-instance only; appropriate for tests and local dev. The
    Firestore implementation in a follow-up issue maps these methods
    onto a transactional update against ``emails/{email_hash}``.
    """

    def __init__(self) -> None:
        self._rows: dict[str, EmailRecord] = {}
        self._lock = asyncio.Lock()

    async def capture(
        self,
        *,
        email: str,
        salt: str,
        consent_version: str,
        source: str = _DEFAULT_SOURCE,
    ) -> EmailRecord:
        normalized = email.strip().lower()
        email_hash = hash_with_salt(normalized, salt=salt)
        now = time.time()

        async with self._lock:
            existing = self._rows.get(email_hash)
            if existing is None:
                record = EmailRecord(
                    email_hash=email_hash,
                    email=normalized,
                    first_seen_at=now,
                    latest_seen_at=now,
                    source=source,
                    consent_version=consent_version,
                    request_count=1,
                )
                self._rows[email_hash] = record
                return record

            existing.latest_seen_at = now
            existing.request_count += 1
            # Consent version may bump between deploys; record the
            # latest the user saw on submit so we can prove acceptance
            # of the current copy if challenged.
            existing.consent_version = consent_version
            return existing

    async def get(self, email_hash: str) -> EmailRecord | None:
        async with self._lock:
            return self._rows.get(email_hash)
