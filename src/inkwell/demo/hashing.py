"""SHA-256 hashing with a per-deploy salt.

Centralizes the rule that **every** stored identifier (email address,
IP address, URL key) goes through this helper before it lands in
Firestore or any in-memory counter that survives a request boundary.
The salt is loaded once from :class:`DemoConfig` and rotating it (in
the runbook for an abuse incident) invalidates all rate-limit counters
without touching code.

The hash is unkeyed SHA-256 over ``salt:value`` rather than HMAC. We're
not authenticating anything — the goal is "make stored values opaque
to anyone who reads a Firestore export and break cross-deploy
correlation when we rotate the salt." Plain SHA-256 with a salt prefix
is exactly that, in fewer characters.
"""

from __future__ import annotations

import hashlib

_SEPARATOR = b":"


def hash_with_salt(value: str, *, salt: str) -> str:
    """Return the salted SHA-256 hex digest of ``value``.

    Args:
        value: Identifier to hash. Caller is expected to normalize
            (lowercase + strip) before passing if equivalence under
            those operations matters — this helper does *not* alter
            the input.
        salt: Per-deploy salt loaded from
            :attr:`DemoConfig.hash_salt`. Required keyword so call
            sites cannot accidentally pass an unsalted hash.

    Returns:
        Hexadecimal SHA-256 digest as a 64-character string.
    """
    digest = hashlib.sha256()
    digest.update(salt.encode("utf-8"))
    digest.update(_SEPARATOR)
    digest.update(value.encode("utf-8"))
    return digest.hexdigest()
