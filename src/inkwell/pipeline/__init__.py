"""Pipeline orchestration for episode processing.

This package contains the core business logic for processing podcast episodes,
separated from CLI presentation concerns.
"""

from .models import PipelineOptions, PipelineResult
from .orchestrator import PipelineOrchestrator

__all__ = [
    "PipelineOptions",
    "PipelineResult",
    "PipelineOrchestrator",
]
