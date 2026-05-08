"""Glue between :mod:`inkwell.demo` and :class:`PipelineOrchestrator`.

This module owns the demo-only invariants that the OBRA-73 plan calls
out as non-negotiable for the public try-it surface:

- The Gemini extractor model is forced down to ``gemini-2.5-flash``.
  The CLI's higher-quality default (``gemini-3-pro-preview``) blows the
  $50/mo demo budget on its own.
- Pipeline output lands in a per-job temporary directory that is
  removed after the markdown payload is serialized — the demo never
  persists a vault.
- Only the templates listed in
  :attr:`DemoConfig.allowed_templates` are produced and surfaced.
- A post-transcription duration backstop aborts before any extraction
  spend if the real audio length disagrees with the yt-dlp/iTunes
  metadata that the resolver trusted.

The Cloud Run worker imports this module and calls
:func:`configure_demo_runtime` once at process start, then dispatches
:func:`process_demo_job` per Cloud Tasks delivery. The worker is
configured for ``--concurrency=1`` (m5) so the class-level model pin
isn't a thread-safety hazard.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from inkwell.config.schema import GlobalConfig
from inkwell.demo.classifier import ClassifiedUrl
from inkwell.demo.config import DemoConfig
from inkwell.demo.payload import DemoResultPayload, build_demo_payload
from inkwell.demo.resolver import ResolvedDemoSource, resolve_demo_source
from inkwell.extraction.extractors.gemini import GeminiExtractor
from inkwell.pipeline.models import PipelineOptions, PipelineResult
from inkwell.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)


class DemoPipelineDisabledError(RuntimeError):
    """Raised when :data:`DemoConfig.enabled` is ``False``.

    The kill switch (``INKWELL_DEMO_ENABLED=false``) lets us pause
    processing without a redeploy. Callers should catch this and return
    the user-facing maintenance response.
    """


class DemoDurationBackstopError(RuntimeError):
    """Raised when the post-transcription duration check rejects a job.

    The resolver trusts metadata; this fires when the real audio turns
    out to be longer than the cap. Wrapped by :func:`process_demo_job`
    so callers see a single failure surface.
    """


@dataclass(frozen=True)
class DemoJobResult:
    """Result of a successful :func:`process_demo_job` call.

    Attributes:
        payload: Frontend-shaped :class:`DemoResultPayload`.
        resolved_source: Source metadata captured before the pipeline
            ran. Useful for logging and Firestore (m4).
        total_cost_usd: Realized total cost for this run, taken from
            :attr:`PipelineResult.total_cost_usd`.
    """

    payload: DemoResultPayload
    resolved_source: ResolvedDemoSource
    total_cost_usd: float


def configure_demo_runtime(demo_config: DemoConfig) -> None:
    """Pin the Gemini extractor model to the demo's forced flash variant.

    Idempotent: safe to call at FastAPI startup and again at the top of
    every job. The Cloud Run worker runs single-threaded per container
    instance (concurrency=1) so the class-attribute mutation is safe.

    Args:
        demo_config: Demo runtime configuration whose
            ``forced_extraction_model`` is applied.
    """
    target_model = demo_config.forced_extraction_model
    if GeminiExtractor.MODEL != target_model:
        logger.info(
            "Pinning GeminiExtractor.MODEL for demo runtime: %s -> %s",
            GeminiExtractor.MODEL,
            target_model,
        )
        GeminiExtractor.MODEL = target_model


async def process_demo_job(
    classified_url: ClassifiedUrl,
    *,
    demo_config: DemoConfig,
    global_config: GlobalConfig,
) -> DemoJobResult:
    """Run a classified demo URL through the full inkwell pipeline.

    The demo invariants are enforced here before
    :class:`PipelineOrchestrator` is invoked so we fail closed rather
    than ship a degraded result:

    1. Reject immediately if ``demo_config.enabled`` is ``False``.
    2. Re-pin :attr:`GeminiExtractor.MODEL` (defensive — startup should
       have already done this).
    3. Resolve the URL via :func:`resolve_demo_source`, which rejects
       audio over the duration cap based on cheap metadata.
    4. Run the orchestrator into a per-job ``tempfile.TemporaryDirectory``
       with the demo-allowlisted templates only. The temp directory is
       cleaned up automatically on success or failure.
    5. Verify the post-transcription duration before returning. If the
       real audio is longer than the cap, raise so callers can refund
       the daily counter and report the truthy duration.

    Args:
        classified_url: Output of :func:`classify_demo_url` for the
            user-supplied URL.
        demo_config: Demo runtime configuration.
        global_config: Project :class:`GlobalConfig` (API keys,
            transcription/extraction config, etc.). The CLI's
            ``ConfigManager`` builds this; the demo passes through
            whatever the FastAPI app loads.

    Returns:
        :class:`DemoJobResult` carrying the JSON-serializable frontend
        payload plus the resolved source and realized cost.

    Raises:
        DemoPipelineDisabledError: When the kill switch is set.
        DemoUrlError: Re-raised from the resolver when a URL can't be
            run (invalid duration, unreachable feed, etc.).
        DemoDurationBackstopError: When real audio exceeds the cap.
        InkwellError: Re-raised from the orchestrator on transcription
            or extraction failures.
    """
    if not demo_config.enabled:
        raise DemoPipelineDisabledError("Demo pipeline is paused (INKWELL_DEMO_ENABLED=false).")

    configure_demo_runtime(demo_config)

    resolved = await resolve_demo_source(classified_url, demo_config=demo_config)

    with tempfile.TemporaryDirectory(prefix="inkwell-demo-") as tmpdir:
        options = _build_pipeline_options(
            resolved=resolved,
            demo_config=demo_config,
            output_dir=Path(tmpdir),
        )

        backstop = _DurationBackstop(
            cap_seconds=demo_config.max_duration_seconds,
            metadata_duration_seconds=resolved.duration_seconds,
        )

        orchestrator = PipelineOrchestrator(global_config)
        result: PipelineResult = await orchestrator.process_episode(
            options,
            progress_callback=backstop,
        )

        payload = build_demo_payload(
            episode_output=result.episode_output,
            config=demo_config,
            extraction_cost_usd=result.extraction_cost_usd,
            total_cost_usd=result.total_cost_usd,
        )

    return DemoJobResult(
        payload=payload,
        resolved_source=resolved,
        total_cost_usd=result.total_cost_usd,
    )


def _build_pipeline_options(
    *,
    resolved: ResolvedDemoSource,
    demo_config: DemoConfig,
    output_dir: Path,
) -> PipelineOptions:
    """Assemble :class:`PipelineOptions` with demo-locked invariants."""
    return PipelineOptions(
        url=resolved.pipeline_url,
        templates=list(demo_config.allowed_templates),
        output_dir=output_dir,
        overwrite=True,
        skip_cache=True,
        interview=False,
        episode_title=resolved.episode_title,
        podcast_name=resolved.podcast_name,
        extractor=demo_config.forced_extractor,
    )


class _DurationBackstop:
    """Progress callback that aborts before extraction if audio is too long.

    The resolver guards on metadata; this guards on the real audio that
    transcription just measured. We raise inside the
    ``transcription_complete`` step so the orchestrator stops before
    spending any LLM extraction budget.

    Reads ``media_duration_seconds`` from the orchestrator payload, not
    ``duration_seconds`` — the latter carries
    :attr:`TranscriptionResult.duration_seconds`, which is wall-clock
    transcription time, not media length.
    """

    __slots__ = ("_cap_seconds", "_metadata_duration_seconds")

    def __init__(self, *, cap_seconds: int, metadata_duration_seconds: int) -> None:
        self._cap_seconds = cap_seconds
        self._metadata_duration_seconds = metadata_duration_seconds

    def __call__(self, step: str, data: dict) -> None:
        if step != "transcription_complete":
            return
        actual_duration = data.get("media_duration_seconds")
        if not isinstance(actual_duration, (int, float)):
            return
        if actual_duration > self._cap_seconds:
            cap_minutes = self._cap_seconds // 60
            raise DemoDurationBackstopError(
                f"Audio is longer than the {cap_minutes}-minute demo cap "
                f"(metadata claimed {self._metadata_duration_seconds}s, "
                f"transcription reported {int(actual_duration)}s)."
            )


__all__ = [
    "DemoDurationBackstopError",
    "DemoJobResult",
    "DemoPipelineDisabledError",
    "configure_demo_runtime",
    "process_demo_job",
]
