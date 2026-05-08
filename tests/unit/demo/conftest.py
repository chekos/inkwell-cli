"""Shared fixtures for demo tests."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def stub_classifier_dns_to_public_ip() -> Iterator[None]:
    """Auto-stub the classifier's DNS lookup to a known-public IP.

    The classifier (OBRA-81) calls ``socket.getaddrinfo`` on the
    user-supplied host so hostnames that resolve to RFC1918 / loopback /
    link-local space (DNS rebinding, attacker-controlled DNS, internal
    split-horizon resolvers) are rejected at submission time. Most tests
    use placeholder domains like ``example.com``; we don't want CI runs
    to depend on real DNS, so this fixture returns ``93.184.216.34`` (a
    canonical public address) by default. Tests that exercise the
    rejection path patch the same target with their own ``side_effect``.
    """

    def _resolve(_host: str, *_args: Any, **_kwargs: Any) -> list[Any]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]

    with patch("inkwell.demo.classifier.socket.getaddrinfo", side_effect=_resolve):
        yield
