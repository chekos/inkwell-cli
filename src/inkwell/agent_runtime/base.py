"""Provider-neutral local agent-runtime interface."""

from typing import Protocol

from .models import RuntimeReadiness, RuntimeRequest, RuntimeResponse


class AgentRuntimeBackend(Protocol):
    """A secret-blind, cancellable local runtime backend."""

    async def probe(self) -> RuntimeReadiness:
        """Return readiness without inference or credential-file access."""
        ...

    async def invoke(self, request: RuntimeRequest) -> RuntimeResponse:
        """Run one bounded request and return a validated response."""
        ...
