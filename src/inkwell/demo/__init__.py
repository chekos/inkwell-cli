"""Demo web service adapter for the inkwell pipeline.

Wraps :class:`inkwell.pipeline.PipelineOrchestrator` for the public try-it
demo (OBRA-70 / OBRA-74). Hard limits live in submodules; nothing in this
package touches the CLI.
"""

from inkwell.demo.classifier import (
    ClassifiedUrl,
    DemoUrlError,
    UrlKind,
    assert_demo_safe_url,
    classify_demo_url,
)
from inkwell.demo.config import DemoConfig, get_demo_config
from inkwell.demo.payload import DemoNoteFile, DemoResultPayload, build_demo_payload
from inkwell.demo.resolver import ResolvedDemoSource, resolve_demo_source
from inkwell.demo.service import (
    DemoDurationBackstopError,
    DemoJobResult,
    DemoPipelineDisabledError,
    configure_demo_runtime,
    process_demo_job,
)

__all__ = [
    "ClassifiedUrl",
    "DemoConfig",
    "DemoDurationBackstopError",
    "DemoJobResult",
    "DemoNoteFile",
    "DemoPipelineDisabledError",
    "DemoResultPayload",
    "DemoUrlError",
    "ResolvedDemoSource",
    "UrlKind",
    "assert_demo_safe_url",
    "build_demo_payload",
    "classify_demo_url",
    "configure_demo_runtime",
    "get_demo_config",
    "process_demo_job",
    "resolve_demo_source",
]
