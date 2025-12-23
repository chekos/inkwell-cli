"""Pipeline orchestrator for episode processing.

This module contains the core business logic for processing podcast episodes,
separated from CLI presentation concerns.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from inkwell.config.schema import GlobalConfig
from inkwell.extraction import ExtractionEngine
from inkwell.extraction.template_selector import TemplateSelector
from inkwell.extraction.templates import TemplateLoader
from inkwell.feeds.models import Episode
from inkwell.interview import conduct_interview_from_output
from inkwell.output import EpisodeMetadata, EpisodeOutput, OutputManager
from inkwell.transcription import TranscriptionManager
from inkwell.utils.api_keys import APIKeyError, get_validated_api_key
from inkwell.utils.costs import CostTracker
from inkwell.utils.datetime import now_utc
from inkwell.utils.errors import InkwellError
from inkwell.utils.url_metadata import (
    INBOX_PODCAST_NAME,
    create_fallback_title,
)

from .models import PipelineOptions, PipelineResult

if TYPE_CHECKING:
    from inkwell.extraction.models import (
        ExtractionResult,
        ExtractionSummary,
        ExtractionTemplate,
    )
    from inkwell.interview.simple_interviewer import SimpleInterviewResult
    from inkwell.transcription.models import TranscriptionResult

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Coordinates full episode processing pipeline.

    This class handles the business logic of processing podcast episodes,
    including transcription, extraction, and optional interview. It is
    independent of the CLI framework and can be used programmatically.

    Example:
        >>> config = ConfigManager().load_config()
        >>> orchestrator = PipelineOrchestrator(config)
        >>> options = PipelineOptions(
        ...     url="https://example.com/episode.mp3",
        ...     category="tech",
        ... )
        >>> result = await orchestrator.process_episode(options)
        >>> print(f"Cost: ${result.total_cost_usd:.4f}")
    """

    def __init__(self, config: GlobalConfig):
        """Initialize the pipeline orchestrator.

        Args:
            config: Global configuration object
        """
        self.config = config
        # Create shared cost tracker for entire pipeline
        self.cost_tracker = CostTracker()

    def _filter_templates_for_incremental(
        self,
        templates: list["ExtractionTemplate"],
        existing_output: EpisodeOutput,
    ) -> list["ExtractionTemplate"]:
        """Filter templates to only those that need processing.

        Templates are skipped if:
        - The output file exists AND
        - The template version matches the version in the existing file

        Templates are included if:
        - The output file doesn't exist (new template)
        - The template version differs (template was updated)
        - The version is "unknown" (migrated v1 data, needs regeneration)

        Args:
            templates: All requested templates
            existing_output: Loaded EpisodeOutput from existing directory

        Returns:
            List of templates that need processing
        """
        templates_to_process: list[ExtractionTemplate] = []
        existing_versions = existing_output.metadata.templates_versions

        for template in templates:
            existing_version = existing_versions.get(template.name)

            if existing_version is None:
                # Template doesn't exist in output - needs generation
                logger.debug(f"Template '{template.name}' not found, will generate")
                templates_to_process.append(template)
            elif existing_version == "unknown":
                # Migrated v1 data - treat as needing regeneration
                logger.debug(
                    f"Template '{template.name}' has unknown version, will regenerate"
                )
                templates_to_process.append(template)
            elif existing_version != template.version:
                # Version mismatch - needs regeneration
                logger.debug(
                    f"Template '{template.name}' version changed "
                    f"({existing_version} -> {template.version}), will regenerate"
                )
                templates_to_process.append(template)
            else:
                # Same version - skip
                logger.debug(
                    f"Template '{template.name}' v{template.version} unchanged, skipping"
                )

        return templates_to_process

    def _get_episode_directory(
        self,
        output_path: Path,
        episode_metadata: EpisodeMetadata,
    ) -> Path:
        """Calculate the episode output directory path.

        Args:
            output_path: Base output directory
            episode_metadata: Episode metadata

        Returns:
            Full path to episode directory (may not exist yet)
        """
        output_manager = OutputManager(output_dir=output_path)
        return output_manager._get_episode_directory_path(episode_metadata)

    async def process_episode(
        self,
        options: PipelineOptions,
        progress_callback: Callable[[str, dict], None] | None = None,
    ) -> PipelineResult:
        """Execute full episode processing pipeline.

        Steps:
        1. Transcribe audio (YouTube or Gemini)
        2. Select templates based on category
        3. Extract content with LLM
        4. Write output files
        5. Conduct interview (optional)

        Args:
            options: Pipeline configuration options
            progress_callback: Optional callback function for progress updates.
                             Called with (step_name: str, step_data: dict)

        Returns:
            PipelineResult with all outputs and costs

        Raises:
            InkwellError: If any pipeline step fails critically
        """
        # Determine output directory
        output_path = options.output_dir or self.config.default_output_dir

        # Step 1: Transcription
        if progress_callback:
            progress_callback("transcription_start", {})

        # Create sub-progress callback for transcription steps
        def transcription_progress(step: str, data: dict) -> None:
            if progress_callback:
                progress_callback("transcription_step", {"step": step, **data})

        transcript_result = await self._transcribe(
            options.url,
            auth_username=options.auth_username,
            auth_password=options.auth_password,
            progress_callback=transcription_progress,
        )

        if progress_callback:
            progress_callback(
                "transcription_complete",
                {
                    "source": transcript_result.transcript.source,
                    "duration_seconds": transcript_result.duration_seconds,
                    "word_count": len(transcript_result.transcript.full_text.split()),
                    "from_cache": transcript_result.from_cache,
                },
            )

        # Step 2: Template selection
        if progress_callback:
            progress_callback("template_selection_start", {})

        selected_templates = self._select_templates(
            options=options,
            transcript=transcript_result.transcript.full_text,
            episode_url=options.url,
        )

        # Create episode metadata (use values from options if available)
        # Fallbacks use _inbox for podcast and a readable title from URL
        episode_metadata = EpisodeMetadata(
            podcast_name=options.podcast_name or INBOX_PODCAST_NAME,
            episode_title=options.episode_title or create_fallback_title(options.url),
            episode_url=options.url,
            transcription_source=transcript_result.transcript.source,
        )

        if progress_callback:
            progress_callback(
                "template_selection_complete",
                {
                    "template_count": len(selected_templates),
                    "templates": [t.name for t in selected_templates],
                },
            )

        # Check for incremental mode (existing directory without --overwrite)
        existing_output: EpisodeOutput | None = None
        templates_to_process = selected_templates
        incremental_mode = False

        episode_dir = self._get_episode_directory(output_path, episode_metadata)
        if episode_dir.exists() and not options.overwrite:
            try:
                existing_output = EpisodeOutput.from_directory(episode_dir)
                templates_to_process = self._filter_templates_for_incremental(
                    selected_templates, existing_output
                )
                incremental_mode = True

                if progress_callback:
                    skipped_count = len(selected_templates) - len(templates_to_process)
                    progress_callback(
                        "incremental_mode",
                        {
                            "existing_dir": str(episode_dir),
                            "templates_to_process": len(templates_to_process),
                            "templates_skipped": skipped_count,
                            "skipped_templates": [
                                t.name
                                for t in selected_templates
                                if t not in templates_to_process
                            ],
                        },
                    )

                logger.info(
                    f"Incremental mode: {len(templates_to_process)}/{len(selected_templates)} "
                    f"templates need processing"
                )
            except (FileNotFoundError, ValueError) as e:
                # Directory exists but isn't a valid episode output
                logger.warning(f"Could not load existing output: {e}. Will overwrite.")
                incremental_mode = False

        # Step 3: Extraction
        if progress_callback:
            progress_callback("extraction_start", {})

        extraction_results, extraction_summary, extraction_cost = await self._extract_content(
            templates=templates_to_process,
            transcript=transcript_result.transcript.full_text,
            metadata=episode_metadata,
            provider=options.provider,
            skip_cache=options.skip_cache,
            dry_run=options.dry_run,
        )

        if progress_callback:
            progress_callback(
                "extraction_complete",
                {
                    "successful": extraction_summary.successful,
                    "failed": extraction_summary.failed,
                    "cached": extraction_summary.cached,
                    "cost_usd": extraction_cost,
                },
            )

        # Early exit for dry run
        if options.dry_run:
            # Create a minimal result for dry run
            dry_run_output = EpisodeOutput(
                directory=output_path / "dry-run",
                output_files=[],
            )
            return PipelineResult(
                episode_output=dry_run_output,
                transcript_result=transcript_result,
                extraction_results=[],
                extraction_summary=extraction_summary,
                interview_result=None,
                extraction_cost_usd=extraction_cost,
                interview_cost_usd=0.0,
            )

        # Step 4: Write output
        if progress_callback:
            progress_callback("output_start", {})

        if incremental_mode and existing_output is not None:
            # Incremental write - merge with existing
            episode_output = self._write_output_incremental(
                episode_dir=episode_dir,
                existing_output=existing_output,
                extraction_results=extraction_results,
                transcript=transcript_result.transcript.full_text,
                transcript_summary=transcript_result.transcript.summary,
            )
        else:
            # Full write
            episode_output = self._write_output(
                output_path=output_path,
                episode_metadata=episode_metadata,
                extraction_results=extraction_results,
                overwrite=options.overwrite,
                transcript=transcript_result.transcript.full_text,
                transcript_summary=transcript_result.transcript.summary,
            )

        if progress_callback:
            progress_callback(
                "output_complete",
                {
                    "file_count": len(episode_output.output_files),
                    "directory": str(episode_output.directory),
                    "incremental": incremental_mode,
                },
            )

        # Step 5: Interview (optional)
        interview_result = None
        interview_cost = 0.0

        if options.interview or self.config.interview.auto_start:
            if progress_callback:
                progress_callback("interview_start", {})

            try:
                interview_result, interview_cost = await self._conduct_interview(
                    options=options,
                    episode_output=episode_output,
                    episode_metadata=episode_metadata,
                    transcript_result=transcript_result,
                )

                if interview_result:
                    # Update metadata with interview info
                    template_name = (
                        options.interview_template or self.config.interview.default_template
                    )
                    format_style = options.interview_format or self.config.interview.format_style
                    self._update_metadata_with_interview(
                        episode_output=episode_output,
                        interview_result=interview_result,
                        interview_cost=interview_cost,
                        template_name=template_name,
                        format_style=format_style,
                    )

                if progress_callback:
                    question_count = len(interview_result.exchanges) if interview_result else 0
                    progress_callback(
                        "interview_complete",
                        {
                            "question_count": question_count,
                            "cost_usd": interview_cost,
                        },
                    )

            except KeyboardInterrupt:
                logger.info("Interview cancelled by user")
                if progress_callback:
                    progress_callback("interview_cancelled", {})
                # Continue to return result even if interview cancelled

            except Exception as e:
                logger.error(f"Interview failed: {e}")
                if progress_callback:
                    progress_callback("interview_failed", {"error": str(e)})
                # Continue to return result even if interview failed

        # Return complete result
        return PipelineResult(
            episode_output=episode_output,
            transcript_result=transcript_result,
            extraction_results=extraction_results,
            extraction_summary=extraction_summary,
            interview_result=interview_result,
            extraction_cost_usd=extraction_cost,
            interview_cost_usd=interview_cost,
        )

    async def _transcribe(
        self,
        url: str,
        auth_username: str | None = None,
        auth_password: str | None = None,
        progress_callback: Callable[[str, dict], None] | None = None,
    ) -> "TranscriptionResult":
        """Transcribe episode from URL.

        Args:
            url: Episode URL
            auth_username: Username for authenticated audio downloads (private feeds)
            auth_password: Password for authenticated audio downloads (private feeds)
            progress_callback: Optional callback for transcription sub-step progress

        Returns:
            TranscriptionResult

        Raises:
            InkwellError: If transcription fails
        """
        manager = TranscriptionManager(
            config=self.config.transcription, cost_tracker=self.cost_tracker
        )
        result = await manager.transcribe(
            url,
            use_cache=True,
            skip_youtube=False,
            auth_username=auth_username,
            auth_password=auth_password,
            progress_callback=progress_callback,
        )

        if not result.success:
            raise InkwellError(f"Transcription failed: {result.error}")

        assert result.transcript is not None
        return result

    def _select_templates(
        self,
        options: PipelineOptions,
        transcript: str,
        episode_url: str,
    ) -> list["ExtractionTemplate"]:
        """Select templates based on options and content.

        Args:
            options: Pipeline options
            transcript: Full transcript text
            episode_url: Episode URL

        Returns:
            List of selected templates
        """
        loader = TemplateLoader()
        selector = TemplateSelector(loader)

        # Parse custom templates if provided
        custom_template_list = None
        if options.templates:
            custom_template_list = [t.strip() for t in options.templates]

        # Create episode object for template selection
        episode = Episode(
            title=f"Episode from {episode_url}",
            url=episode_url,  # type: ignore
            published=now_utc(),
            description="",
            podcast_name="Unknown Podcast",
        )

        # Select templates
        selected_templates = selector.select_templates(
            episode=episode,
            category=options.category,
            custom_templates=custom_template_list,
            transcript=transcript,
        )

        return selected_templates

    async def _extract_content(
        self,
        templates: list["ExtractionTemplate"],
        transcript: str,
        metadata: EpisodeMetadata,
        provider: str | None,
        skip_cache: bool,
        dry_run: bool,
    ) -> tuple[list["ExtractionResult"], "ExtractionSummary", float]:
        """Extract content using templates and LLM.

        Args:
            templates: List of extraction templates
            transcript: Full transcript text
            metadata: Episode metadata
            provider: LLM provider (claude, gemini, or auto)
            skip_cache: Whether to skip extraction cache
            dry_run: Whether to only estimate cost

        Returns:
            Tuple of (extraction_results, extraction_summary, total_cost)
        """
        # Share Google API key between transcription and extraction
        # Extraction uses transcription.api_key as fallback if not explicitly set
        shared_gemini_key = (
            self.config.extraction.gemini_api_key or self.config.transcription.api_key
        )

        engine = ExtractionEngine(
            config=self.config.extraction,
            gemini_api_key=shared_gemini_key,
            cost_tracker=self.cost_tracker,
        )

        # Estimate cost
        estimated_cost = engine.estimate_total_cost(
            templates=templates,
            transcript=transcript,
        )

        # If dry run, return early with estimated cost
        if dry_run:
            from inkwell.extraction.models import ExtractionSummary

            summary = ExtractionSummary(
                total=len(templates),
                successful=0,
                failed=0,
                cached=0,
            )
            return [], summary, estimated_cost

        # Extract with batched API call
        extraction_results, extraction_summary = await engine.extract_all_batched(
            templates=templates,
            transcript=transcript,
            metadata=metadata.model_dump(),
            use_cache=not skip_cache,
        )

        total_cost = engine.get_total_cost()

        return extraction_results, extraction_summary, total_cost

    def _write_output(
        self,
        output_path: Path,
        episode_metadata: EpisodeMetadata,
        extraction_results: list["ExtractionResult"],
        overwrite: bool,
        transcript: str | None = None,
        transcript_summary: str | None = None,
    ) -> "EpisodeOutput":
        """Write output files to disk.

        Args:
            output_path: Base output directory
            episode_metadata: Episode metadata
            extraction_results: List of extraction results
            overwrite: Whether to overwrite existing directory
            transcript: Optional transcript text to include
            transcript_summary: Optional summary to include at top of transcript

        Returns:
            EpisodeOutput with directory and file list

        Raises:
            FileExistsError: If directory exists and overwrite is False
        """
        output_manager = OutputManager(output_dir=output_path)

        episode_output = output_manager.write_episode(
            episode_metadata=episode_metadata,
            extraction_results=extraction_results,
            overwrite=overwrite,
            transcript=transcript,
            transcript_summary=transcript_summary,
        )

        return episode_output

    def _write_output_incremental(
        self,
        episode_dir: Path,
        existing_output: EpisodeOutput,
        extraction_results: list["ExtractionResult"],
        transcript: str | None = None,
        transcript_summary: str | None = None,
    ) -> EpisodeOutput:
        """Write incremental updates to existing episode directory.

        Args:
            episode_dir: Existing episode directory
            existing_output: Loaded EpisodeOutput from existing directory
            extraction_results: New extraction results to merge
            transcript: Optional transcript (only written if not exists)
            transcript_summary: Optional summary for transcript

        Returns:
            EpisodeOutput with merged content
        """
        output_manager = OutputManager(output_dir=episode_dir.parent.parent)

        return output_manager.write_incremental_episode(
            episode_dir=episode_dir,
            existing_metadata=existing_output.metadata,
            new_extraction_results=extraction_results,
            transcript=transcript,
            transcript_summary=transcript_summary,
        )

    async def _conduct_interview(
        self,
        options: PipelineOptions,
        episode_output: EpisodeOutput,
        episode_metadata: EpisodeMetadata,
        transcript_result: "TranscriptionResult",
    ) -> tuple["SimpleInterviewResult | None", float]:
        """Conduct interactive interview with user.

        Args:
            options: Pipeline options
            episode_output: Episode output information
            episode_metadata: Episode metadata
            transcript_result: Transcription result

        Returns:
            Tuple of (interview_result, cost_usd)
        """
        # Get interview configuration
        questions = options.max_questions or self.config.interview.question_count

        # Validate Anthropic API key
        try:
            anthropic_key = get_validated_api_key("ANTHROPIC_API_KEY", "claude")
        except APIKeyError as e:
            logger.warning(f"Interview skipped - API key validation failed: {e}")
            return None, 0.0

        # Conduct interview using simplified interface
        try:
            interview_result = await conduct_interview_from_output(
                output_dir=episode_output.directory,
                episode_title=episode_metadata.episode_title,
                podcast_name=episode_metadata.podcast_name,
                api_key=anthropic_key,
                max_questions=questions,
                cost_tracker=self.cost_tracker,
            )
        except Exception as e:
            logger.error(f"Interview failed: {e}", exc_info=True)
            return None, 0.0

        # Save interview output
        interview_path = episode_output.directory / "my-notes.md"
        interview_path.write_text(interview_result.transcript)

        return interview_result, interview_result.total_cost

    def _update_metadata_with_interview(
        self,
        episode_output: "EpisodeOutput",
        interview_result: "SimpleInterviewResult",
        interview_cost: float,
        template_name: str,
        format_style: str,
    ) -> None:
        """Update episode metadata file with interview information.

        Args:
            episode_output: Episode output information
            interview_result: Interview result
            interview_cost: Interview cost in USD
            template_name: Interview template name (deprecated, kept for compatibility)
            format_style: Interview format style (deprecated, kept for compatibility)
        """
        metadata_path = episode_output.directory / ".metadata.yaml"
        if metadata_path.exists():
            metadata = yaml.safe_load(metadata_path.read_text())
            metadata["interview_conducted"] = True
            metadata["interview_template"] = "reflective"  # Always reflective now
            metadata["interview_format"] = "markdown"  # Always markdown now
            metadata["interview_questions"] = len(interview_result.exchanges)
            metadata["interview_cost_usd"] = interview_cost
            metadata_path.write_text(yaml.safe_dump(metadata, default_flow_style=False))
