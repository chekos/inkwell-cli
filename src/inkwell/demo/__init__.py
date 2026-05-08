"""Demo web service adapter for the inkwell pipeline.

Wraps :class:`inkwell.pipeline.PipelineOrchestrator` for the public try-it
demo (OBRA-70 / OBRA-74). Hard limits live in submodules; nothing in this
package touches the CLI.
"""

from inkwell.demo.classifier import (
    ClassifiedUrl,
    DemoUrlError,
    UrlKind,
    classify_demo_url,
)
from inkwell.demo.config import DemoConfig, get_demo_config
from inkwell.demo.payload import DemoNoteFile, DemoResultPayload, build_demo_payload

__all__ = [
    "ClassifiedUrl",
    "DemoConfig",
    "DemoNoteFile",
    "DemoResultPayload",
    "DemoUrlError",
    "UrlKind",
    "build_demo_payload",
    "classify_demo_url",
    "get_demo_config",
]
