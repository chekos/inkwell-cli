"""CLI entry point for Inkwell."""

import asyncio
import json
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import typer
from pydantic import HttpUrl
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from inkwell.config.logging import setup_logging
from inkwell.config.manager import ConfigManager, normalize_feed_name, slugify_feed_name
from inkwell.config.schema import AuthConfig, FeedConfig
from inkwell.extraction.templates import TemplateLoader
from inkwell.feeds.models import Episode
from inkwell.feeds.parser import MAX_EPISODES_PER_SELECTION, RSSParser
from inkwell.feeds.youtube_resolver import (
    ResolvedFeed,
    channel_id_from_feed_url,
    is_youtube_playlist_url,
    is_youtube_url,
    resolve_youtube_url,
)
from inkwell.ingestion import (
    ContentSource,
    ContentSourceKind,
    InputResolver,
    OCRMode,
    extract_article_text_from_url,
    extract_source_text_from_image,
    extract_source_text_from_pdf,
)
from inkwell.pipeline import PipelineOptions, PipelineOrchestrator, PipelineResult
from inkwell.transcription import CostEstimate, TranscriptionManager, TranscriptionResult
from inkwell.utils.datetime import now_utc
from inkwell.utils.errors import (
    ConfigError,
    InkwellError,
    NotFoundError,
    ValidationError,
)
from inkwell.utils.progress import PipelineProgress
from inkwell.utils.url_metadata import derive_readable_title_from_url

app = typer.Typer(
    name="inkwell",
    help="Transform podcast episodes into structured markdown notes",
    no_args_is_help=True,
)
console = Console()
# Secondary console routed to stderr so agents capturing stdout can isolate
# the structured result (the summary table) from operational chatter (hints,
# post-fetch save notices).
err_console = Console(stderr=True)

_LOCAL_TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
_LOCAL_PDF_EXTENSIONS = {".pdf"}
_LOCAL_IMAGE_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".pbm",
    ".pgm",
    ".png",
    ".pnm",
    ".ppm",
    ".tif",
    ".tiff",
    ".webp",
}
_LOCAL_MEDIA_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".avi",
    ".flac",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".oga",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
}


def _register_subcommands() -> None:
    """Register subcommand apps (lazy import to avoid circular deps)."""
    from inkwell.cli_list import app as list_app
    from inkwell.cli_plugins import app as plugins_app

    app.add_typer(list_app, name="list")
    app.add_typer(plugins_app, name="plugins")


# Register subcommand apps
_register_subcommands()


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose (DEBUG) logging"),
    log_file: Path | None = typer.Option(None, "--log-file", help="Write logs to file"),
) -> None:
    """Inkwell - Transform podcasts into structured markdown notes."""
    setup_logging(verbose=verbose, log_file=log_file)


@app.command("version")
def show_version() -> None:
    """Show version information."""
    from inkwell import __version__

    console.print(f"[bold cyan]Inkwell CLI[/bold cyan] v{__version__}")


def _should_show_save_feed_hint(*, url: str, input_was_url: bool) -> bool:
    """Decide whether to print the --save-feed hint after a YouTube fetch.

    The sole callsite already guards on `not save_feed`; this helper just
    covers the remaining two conditions (URL-shaped input + YouTube host).
    Suppressed for saved-feed-name lookups and non-YouTube URLs.
    """
    return input_was_url and is_youtube_url(url)


def _slugify(s: str) -> str:
    """Collapse any string into a [a-z0-9-] feed-name slug."""
    return slugify_feed_name(s)


def _normalize_feed_name(name: str) -> str:
    """Normalize user-supplied feed names to stable CLI identifiers."""
    return normalize_feed_name(name)


def _parse_extra_templates(value: str | None) -> list[str]:
    """Parse a comma-separated --extra-templates value."""
    if value is None:
        return []
    return [template.strip() for template in value.split(",") if template.strip()]


def _dedupe_template_names(names: list[str]) -> list[str]:
    """Deduplicate template names while preserving user-provided order."""
    seen: set[str] = set()
    deduped = []
    for name in names:
        if name not in seen:
            seen.add(name)
            deduped.append(name)
    return deduped


def _validate_template_names(names: list[str]) -> None:
    """Validate template names against built-in and user templates."""
    if not names:
        return

    available = set(TemplateLoader().list_templates())
    missing = [name for name in names if name not in available]
    if missing:
        raise ValidationError(
            f"Unknown template(s): {', '.join(missing)}",
            suggestion="Run 'inkwell list templates' to see available templates.",
        )


def _parse_and_validate_extra_templates(value: str | None) -> list[str]:
    """Parse, dedupe, and validate --extra-templates."""
    templates = _dedupe_template_names(_parse_extra_templates(value))
    _validate_template_names(templates)
    return templates


def _is_local_text_path(path: Path) -> bool:
    """Return True for local text inputs supported in Phase 6."""
    return path.suffix.lower() in _LOCAL_TEXT_EXTENSIONS


def _is_local_pdf_path(path: Path) -> bool:
    """Return True for local PDF inputs."""
    return path.suffix.lower() in _LOCAL_PDF_EXTENSIONS


def _is_local_image_path(path: Path) -> bool:
    """Return True for local image formats supported by the OCR extra."""
    return path.suffix.lower() in _LOCAL_IMAGE_EXTENSIONS


def _is_local_media_path(path: Path) -> bool:
    """Return True for local media inputs supported in Phase 6."""
    return path.suffix.lower() in _LOCAL_MEDIA_EXTENSIONS


def _read_text_source_file(path: Path) -> str:
    """Read a local text/markdown source file with user-facing errors."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ValidationError(
            f"Local text file is not valid UTF-8: {path}",
            suggestion="Save the file as UTF-8 text or markdown and try again.",
        ) from e
    except OSError as e:
        raise ValidationError(f"Could not read local file: {path}") from e

    if not text.strip():
        raise ValidationError("Local text file is empty")
    return text


def _print_json_payload(payload: dict[str, Any]) -> None:
    """Print a JSON payload to stdout with stable formatting."""
    # Deliberate machine-readable command output, not an application log sink.
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
    sys.stdout.write("\n")


def _validate_machine_output_options(*, json_output: bool, plain: bool) -> None:
    """Ensure only one machine-readable output mode is active."""
    if json_output and plain:
        raise ValidationError(
            "--json and --plain are mutually exclusive",
            suggestion="Choose one output mode.",
        )


def _source_input_payload(source: ContentSource, normalized_value: str | None = None) -> dict:
    """Build the shared input portion of machine-readable CLI responses."""
    return {
        "raw": source.raw_input,
        "normalized": normalized_value or source.value,
        "kind": source.kind.value,
    }


def _transcription_payload(result: TranscriptionResult) -> dict[str, Any]:
    """Build the transcription portion of a machine-readable response."""
    transcript = result.transcript
    word_count = 0
    language = None
    source = None
    media_duration_seconds = None
    if transcript is not None:
        word_count = transcript.word_count or len(transcript.full_text.split())
        language = transcript.language
        source = transcript.source
        media_duration_seconds = transcript.duration_seconds

    return {
        "source": source,
        "attempts": result.attempts,
        "duration_seconds": result.duration_seconds,
        "media_duration_seconds": media_duration_seconds,
        "from_cache": result.from_cache,
        "language": language,
        "word_count": word_count,
        "cost_usd": result.cost_usd,
    }


def _transcribe_json_payload(
    *,
    source: ContentSource,
    result: TranscriptionResult,
    output: Path | None,
) -> dict[str, Any]:
    """Build the JSON envelope for `inkwell transcribe --json`."""
    transcript = result.transcript
    files = []
    if output is not None:
        files.append(
            {
                "filename": output.name,
                "template": None,
                "path": str(output),
                "size_bytes": output.stat().st_size if output.exists() else None,
            }
        )

    return {
        "schema_version": 1,
        "command": "transcribe",
        "status": "success" if result.success else "error",
        "input": _source_input_payload(source),
        "output_directory": None,
        "output": {
            "path": str(output) if output else None,
        },
        "files": files,
        "templates": [],
        "transcription": _transcription_payload(result),
        "cache_hits": {
            "transcript": result.from_cache,
            "extractions": 0,
        },
        "transcript": transcript.full_text if transcript else None,
        "costs": {
            "transcription_usd": result.cost_usd,
            "total_usd": result.cost_usd,
        },
        "error": result.error,
    }


def _fetch_result_payload(result: PipelineResult) -> dict[str, Any]:
    """Build one fetch result entry for machine-readable responses."""
    episode_output = result.episode_output
    transcript_result = result.transcript_result
    metadata = episode_output.metadata
    output_dir = episode_output.directory

    files = [
        {
            "filename": output_file.filename,
            "template": output_file.template_name,
            "path": str(output_dir / output_file.filename),
            "size_bytes": output_file.size_bytes,
        }
        for output_file in episode_output.output_files
    ]

    extraction_templates = [
        {
            "name": extraction_result.template_name,
            "version": extraction_result.template_version,
            "success": extraction_result.success,
            "provider": extraction_result.provider,
            "model": extraction_result.model,
            "bypassed": extraction_result.bypassed,
            "bypass_reason": extraction_result.bypass_reason,
            "from_cache": extraction_result.from_cache,
            "cost_usd": extraction_result.cost_usd,
            "cost_known": extraction_result.cost_known,
            "billing": extraction_result.billing,
            "runtime": extraction_result.runtime,
            "error": extraction_result.error,
            "error_code": extraction_result.error_code,
        }
        for extraction_result in result.extraction_results
    ]

    return {
        "status": "success",
        "episode": {
            "podcast_name": metadata.podcast_name,
            "episode_title": metadata.episode_title,
            "episode_url": metadata.episode_url,
        },
        "output": {
            "directory": str(output_dir),
            "files": files,
        },
        "templates": extraction_templates,
        "transcription": _transcription_payload(transcript_result),
        "extraction": {
            "total": result.extraction_summary.total,
            "successful": result.extraction_summary.successful,
            "failed": result.extraction_summary.failed,
            "cached": result.extraction_summary.cached,
        },
        "cache_hits": {
            "transcript": transcript_result.from_cache,
            "extractions": result.extraction_summary.cached,
        },
        "costs": {
            "transcription_usd": transcript_result.cost_usd,
            "extraction_usd": result.extraction_cost_usd,
            "interview_usd": result.interview_cost_usd,
            "total_usd": transcript_result.cost_usd + result.total_cost_usd,
            "total_known": result.total_cost_known,
            "unknown_operations": sum(
                1 for item in result.extraction_results if not item.cost_known
            ),
        },
        "interview": {
            "completed": result.interview_result is not None,
            "cost_usd": result.interview_cost_usd,
        },
        "source_extraction": metadata.custom_fields.get("source_extraction"),
    }


def _fetch_json_payload(
    *,
    source: ContentSource,
    normalized_input: str,
    output_dir: Path,
    latest: bool,
    count: int | None,
    episode: str | None,
    results: list[PipelineResult],
) -> dict[str, Any]:
    """Build the JSON envelope for `inkwell fetch --json`."""
    result_payloads = [_fetch_result_payload(result) for result in results]
    files = [file for item in result_payloads for file in item["output"]["files"]]
    templates = [template for item in result_payloads for template in item["templates"]]
    return {
        "schema_version": 1,
        "command": "fetch",
        "status": "success",
        "input": {
            **_source_input_payload(source, normalized_input),
            "selector": {
                "latest": latest,
                "count": count,
                "episode": episode,
            },
        },
        "output_directory": str(output_dir),
        "summary": {
            "requested": len(results),
            "succeeded": len(result_payloads),
            "failed": 0,
            "total_cost_usd": sum(item["costs"]["total_usd"] for item in result_payloads),
            "total_cost_known": all(item["costs"]["total_known"] for item in result_payloads),
            "unknown_cost_operations": sum(
                item["costs"]["unknown_operations"] for item in result_payloads
            ),
        },
        "files": files,
        "templates": templates,
        "cache_hits": {
            "transcripts": sum(1 for item in result_payloads if item["cache_hits"]["transcript"]),
            "extractions": sum(item["cache_hits"]["extractions"] for item in result_payloads),
        },
        "results": result_payloads,
        "errors": [],
        "warnings": [],
    }


def _fetch_error_json_payload(
    error: InkwellError,
    *,
    requested: int,
    completed_results: list[PipelineResult],
) -> dict[str, Any]:
    """Build the stable fetch failure envelope without exposing provider output."""
    result_payloads = [_fetch_result_payload(result) for result in completed_results]
    files = [file for item in result_payloads for file in item["output"]["files"]]
    templates = [template for item in result_payloads for template in item["templates"]]
    succeeded = len(result_payloads)
    requested = max(requested, succeeded + 1)
    return {
        "schema_version": 1,
        "command": "fetch",
        "status": "error",
        "summary": {
            "requested": requested,
            "succeeded": succeeded,
            "failed": requested - succeeded,
            "total_cost_usd": sum(item["costs"]["total_usd"] for item in result_payloads),
            "total_cost_known": all(item["costs"]["total_known"] for item in result_payloads),
            "unknown_cost_operations": sum(
                item["costs"]["unknown_operations"] for item in result_payloads
            ),
        },
        "files": files,
        "templates": templates,
        "cache_hits": {
            "transcripts": sum(1 for item in result_payloads if item["cache_hits"]["transcript"]),
            "extractions": sum(item["cache_hits"]["extractions"] for item in result_payloads),
        },
        "results": result_payloads,
        "errors": [
            {
                "code": str(error.details.get("code", "inkwell_error")),
                "message": error.message,
                "suggestion": error.suggestion,
            }
        ],
        "warnings": [],
    }


def _validate_extract_only_options(
    *,
    json_output: bool,
    dry_run: bool,
    interview: bool,
    interview_template: str | None,
    interview_format: str | None,
    max_questions: int | None,
    no_resume: bool,
    resume_session: str | None,
    podcast_name: str | None,
    templates: str | None,
    category: str | None,
    provider: str | None,
    extractor: str | None,
    skip_cache: bool,
    save_feed: bool,
) -> None:
    """Reject fetch options that do not apply to transcript-only extraction."""
    conflicts = []
    if json_output:
        conflicts.append("--json")
    if dry_run:
        conflicts.append("--dry-run")
    if interview:
        conflicts.append("--interview")
    if interview_template:
        conflicts.append("--interview-template")
    if interview_format:
        conflicts.append("--interview-format")
    if max_questions is not None:
        conflicts.append("--max-questions")
    if no_resume:
        conflicts.append("--no-resume")
    if resume_session:
        conflicts.append("--resume-session")
    if podcast_name:
        conflicts.append("--podcast-name")
    if templates:
        conflicts.append("--templates")
    if category:
        conflicts.append("--category")
    if provider:
        conflicts.append("--provider")
    if extractor:
        conflicts.append("--extractor")
    if skip_cache:
        conflicts.append("--skip-cache")
    if save_feed:
        conflicts.append("--save-feed")

    if conflicts:
        raise ValidationError(
            f"--extract cannot be combined with {', '.join(conflicts)}",
            suggestion=(
                "Use regular 'inkwell fetch' for structured extraction, or run "
                "'inkwell fetch SOURCE --extract' for transcript-only output."
            ),
        )


def _resolve_cache_targets(
    *,
    transcripts: bool,
    extractions: bool,
    media: bool,
    all_targets: bool,
) -> dict[str, bool]:
    """Resolve cache target flags while preserving transcript-only defaults."""
    if all_targets:
        return {"transcripts": True, "extractions": True, "media": True}

    targets = {
        "transcripts": transcripts,
        "extractions": extractions,
        "media": media,
    }
    if not any(targets.values()):
        targets["transcripts"] = True
    return targets


def _format_deleted_bytes(bytes_deleted: int) -> str:
    """Format deleted byte counts for cache command output."""
    return f"{bytes_deleted / 1024 / 1024:.2f} MB"


def _confirm_cache_deletion(*, force: bool, message: str) -> bool:
    """Confirm destructive cache actions unless explicitly forced."""
    if force:
        return True
    return bool(typer.confirm(message))


def _extract_transcript_output_path(
    *,
    output_dir: Path,
    title: str | None,
    url: str,
    used_filenames: set[str],
    overwrite: bool,
) -> Path:
    """Choose an output path for a transcript-only extraction file."""
    readable_title = title or derive_readable_title_from_url(url) or "transcript"
    base_name = _slugify(readable_title) or "transcript"
    filename = f"{base_name}.transcript.md"
    path = output_dir / filename

    if filename not in used_filenames and path.exists() and not overwrite:
        raise FileExistsError(f"Transcript already exists: {path} (use --overwrite to replace it)")

    suffix = 2
    while filename in used_filenames:
        filename = f"{base_name}-{suffix}.transcript.md"
        path = output_dir / filename
        suffix += 1

    if path.exists() and not overwrite:
        raise FileExistsError(f"Transcript already exists: {path} (use --overwrite to replace it)")

    used_filenames.add(filename)
    return path


def _derive_feed_name(resolved: ResolvedFeed, existing: set[str]) -> str:
    """Auto-derive a feed name from channel metadata when --feed-name is omitted.

    Preference: slugified channel name → channel_id from the feed URL →
    generic "youtube-feed". Collisions are disambiguated with a numeric
    suffix so `--save-feed` can always succeed when the URL is valid.
    """
    candidate = ""
    if resolved.channel_name:
        candidate = _slugify(resolved.channel_name)
    if not candidate:
        # Pure URL-shape branch, or slugification produced an empty string.
        # Fall back to the channel_id carried in the feed URL query string.
        cid_list = parse_qs(urlparse(resolved.feed_url).query).get("channel_id", [])
        if cid_list and cid_list[0]:
            candidate = cid_list[0].lower()
    if not candidate:
        candidate = "youtube-feed"

    if candidate not in existing:
        return candidate
    i = 2
    while f"{candidate}-{i}" in existing:
        i += 1
    return f"{candidate}-{i}"


def _find_existing_youtube_feed(
    feeds: dict[str, FeedConfig],
    resolved: ResolvedFeed,
) -> str | None:
    """Return an existing feed name for the resolved channel, if one exists."""
    target_channel_id = channel_id_from_feed_url(resolved.feed_url)
    if target_channel_id is None:
        return None

    for existing_name, feed_config in feeds.items():
        if channel_id_from_feed_url(str(feed_config.url)) == target_channel_id:
            return existing_name
    return None


@app.command("add")
def add_feed(
    url: str = typer.Argument(
        ...,
        help=(
            "RSS feed URL or YouTube URL (watch, @handle, /channel/UC…, youtu.be). "
            "YouTube URLs are auto-resolved to the channel's RSS feed. Playlist URLs are rejected."
        ),
    ),
    feed_name: str = typer.Option(
        ...,
        "--feed-name",
        "--name",
        "-n",
        help="Feed identifier name. --name is kept as a backward-compatible alias.",
    ),
    auth: bool = typer.Option(False, "--auth", help="Prompt for authentication"),
    category: str | None = typer.Option(
        None, "--category", "-c", help="Feed category (e.g., tech, interview)"
    ),
    extra_templates: str | None = typer.Option(
        None,
        "--extra-templates",
        "-t",
        help=(
            "Additional templates to run for this feed, added to category defaults. "
            "Comma-separated."
        ),
    ),
) -> None:
    """Add a new podcast feed.

    Examples:
        inkwell add https://example.com/feed.rss --feed-name my-podcast

        inkwell add https://private.com/feed.rss --feed-name private --auth
    """

    async def run_add_feed() -> None:
        manager = ConfigManager()

        # Collect auth credentials if needed
        auth_config = AuthConfig(type="none")
        if auth:
            console.print("\n[bold]Authentication required[/bold]")
            auth_type: str = typer.prompt(
                "Auth type",
                type=str,
                default="basic",
            )

            if auth_type not in ["basic", "bearer"]:
                console.print("[red]✗[/red] Invalid auth type. Must be 'basic' or 'bearer'")
                sys.exit(1)

            if auth_type == "basic":
                username = typer.prompt("Username")
                password = typer.prompt("Password", hide_input=True)
                auth_config = AuthConfig(type="basic", username=username, password=password)
            elif auth_type == "bearer":
                token = typer.prompt("Bearer token", hide_input=True)
                auth_config = AuthConfig(type="bearer", token=token)

        # Resolve YouTube URLs of any shape to the channel's media-RSS feed.
        # Non-YouTube URLs pass through as-is (resolver returns None).
        resolved = await resolve_youtube_url(url)
        feed_url = resolved.feed_url if resolved else url
        custom_templates = _parse_and_validate_extra_templates(extra_templates)

        feed_config = FeedConfig(
            url=HttpUrl(feed_url),
            auth=auth_config,
            category=category,
            custom_templates=custom_templates,
        )

        stored_name = manager.add_feed(feed_name, feed_config)

        console.print(f"\n[green]✓[/green] Feed '[bold]{stored_name}[/bold]' added successfully")
        if stored_name != feed_name:
            console.print(f"[dim]  Normalized feed name from '{feed_name}'[/dim]")
        # Surface the stored URL when it differs from what the user typed so
        # they can spot a mis-resolved channel without running `inkwell list`.
        if feed_url != url:
            console.print(f"[dim]  Resolved to {feed_url}[/dim]")
        if custom_templates:
            console.print(f"[dim]  Extra templates: {', '.join(custom_templates)}[/dim]")
        if auth:
            console.print("[dim]  Credentials encrypted and stored securely[/dim]")

    try:
        asyncio.run(run_add_feed())
    except ValidationError as e:
        console.print(f"[red]✗[/red] {e.message}")
        if e.suggestion:
            console.print(f"[dim]  {e.suggestion}[/dim]")
        sys.exit(1)
    except ConfigError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


@app.command("rename")
def rename_feed(
    old_name: str = typer.Argument(..., help="Current feed name"),
    new_name: str = typer.Argument(..., help="New feed name"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite an existing feed name"),
) -> None:
    """Rename a podcast feed without losing URL, auth, or category settings."""
    try:
        manager = ConfigManager()
        normalized_new_name = _normalize_feed_name(new_name)
        manager.rename_feed(old_name, new_name, overwrite=force)
        console.print(
            f"[green]✓[/green] Feed '[bold]{old_name}[/bold]' renamed to "
            f"'[bold]{normalized_new_name}[/bold]'"
        )
        if normalized_new_name != new_name:
            console.print(f"[dim]  Normalized feed name from '{new_name}'[/dim]")
    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        if e.suggestion:
            console.print(f"[dim]  {e.suggestion}[/dim]")
        sys.exit(1)


@app.command("remove")
def remove_feed(
    name: str = typer.Argument(..., help="Feed name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """Remove a podcast feed.

    Examples:
        inkwell remove my-podcast

        inkwell remove my-podcast --force  # Skip confirmation
    """
    try:
        manager = ConfigManager()

        try:
            feed = manager.get_feed(name)
        except NotFoundError:
            console.print(f"[red]✗[/red] Feed '[bold]{name}[/bold]' not found")
            console.print("\nAvailable feeds:")
            feeds = manager.list_feeds()
            for feed_name in feeds.keys():
                console.print(f"  • {feed_name}")
            sys.exit(1)

        # Confirm removal
        if not force:
            console.print(f"\nFeed: [bold]{name}[/bold]")
            console.print(f"URL:  [dim]{feed.url}[/dim]")
            confirm: bool = typer.confirm("\nAre you sure you want to remove this feed?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        manager.remove_feed(name)
        console.print(f"[green]✓[/green] Feed '[bold]{name}[/bold]' removed")

    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


@app.command("config")
def config_command(
    action: str = typer.Argument(..., help="Action: show, edit, set, or feed"),
    key: str | None = typer.Argument(None, help="Config key (for 'set' action)"),
    value: str | None = typer.Argument(None, help="Config value (for 'set' action)"),
    extra_templates: str | None = typer.Option(
        None,
        "--extra-templates",
        "-t",
        help=(
            "For 'feed': additional templates to run for this feed, added to "
            "category defaults. Pass an empty string to clear."
        ),
    ),
) -> None:
    """Manage Inkwell configuration.

    Actions:
        show: Display current configuration
        edit: Open config file in $EDITOR
        set:  Set a configuration value
        feed: Update per-feed settings

    Examples:
        inkwell config show

        inkwell config edit

        inkwell config set log_level DEBUG

        inkwell config feed my-podcast --extra-templates books-mentioned,step-by-step-plan

        inkwell config feed my-podcast --extra-templates ""
    """
    try:
        manager = ConfigManager()

        if action == "show":
            config = manager.load_config()

            console.print("\n[bold]Inkwell Configuration[/bold]\n")

            table = Table(show_header=False, box=None)
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Config file", str(manager.config_file))
            table.add_row("Feeds file", str(manager.feeds_file))
            table.add_row("", "")
            table.add_row("Output directory", str(config.default_output_dir))
            table.add_row("Log level", config.log_level)
            table.add_row("YouTube check", "✓" if config.transcription.youtube_check else "✗")
            table.add_row("Transcription model", config.transcription.model_name)
            table.add_row("Interview model", config.interview.model)
            table.add_row(
                "Media cache",
                (
                    f"enabled, {config.cache.media.max_mb} MB, {config.cache.media.ttl_days} days"
                    if config.cache.media.enabled
                    else "disabled"
                ),
            )
            table.add_row("", "")

            # API key status - simplified to show the two keys that matter
            import os as os_module

            google_key = (
                config.transcription.api_key
                or config.extraction.gemini_api_key
                or os_module.getenv("GOOGLE_API_KEY")
            )
            anthropic_key = config.extraction.claude_api_key or os_module.getenv(
                "ANTHROPIC_API_KEY"
            )

            def key_status(key: str | None, env_var: str) -> str:
                """Format API key status with source indicator."""
                if key:
                    masked = f"{'•' * 8}{key[-4:]}"
                    if os_module.getenv(env_var) == key:
                        return f"[green]✓[/green] {masked} [dim](${env_var})[/dim]"
                    return f"[green]✓[/green] {masked} [dim](config)[/dim]"
                return f"[yellow]not set[/yellow] [dim](${env_var})[/dim]"

            table.add_row("Google API key", key_status(google_key, "GOOGLE_API_KEY"))
            table.add_row("[dim]  └ used for[/dim]", "[dim]transcription + extraction[/dim]")
            table.add_row("Anthropic API key", key_status(anthropic_key, "ANTHROPIC_API_KEY"))
            table.add_row("[dim]  └ used for[/dim]", "[dim]interview mode[/dim]")

            console.print(table)

        elif action == "edit":
            import subprocess

            # Define whitelist of allowed editors
            allowed_editors = {
                "nano",
                "vim",
                "vi",
                "emacs",
                "code",
                "subl",
                "gedit",
                "kate",
                "notepad",
                "notepad++",
                "atom",
                "micro",
                "helix",
                "nvim",
                "ed",
            }

            editor = os.environ.get("EDITOR", "nano")

            # Extract just the executable name (handle paths like /usr/bin/vim)
            editor_name = Path(editor).name

            if editor_name not in allowed_editors:
                console.print(f"[red]✗[/red] Unsupported editor: {editor}")
                console.print(f"Allowed editors: {', '.join(sorted(allowed_editors))}")
                console.print("Set EDITOR environment variable to a supported editor.")
                console.print(f"Or edit manually: {manager.config_file}")
                sys.exit(1)

            console.print(f"Opening {manager.config_file} in {editor}...")

            try:
                subprocess.run([editor, str(manager.config_file)], check=True)
                console.print("[green]✓[/green] Config file updated")
            except subprocess.CalledProcessError:
                console.print("[red]✗[/red] Editor exited with error")
                sys.exit(1)
            except FileNotFoundError:
                console.print(f"[red]✗[/red] Editor '{editor}' not found")
                console.print(
                    f"Set EDITOR environment variable or edit manually: {manager.config_file}"
                )
                sys.exit(1)

        elif action == "set":
            if not key or not value:
                console.print("[red]✗[/red] Usage: inkwell config set <key> <value>")
                sys.exit(1)

            config = manager.load_config()

            key_parts = key.split(".")

            if len(key_parts) == 1:
                # Top-level key
                if hasattr(config, key):
                    field_type = type(getattr(config, key))

                    value_converted: bool | Path | str
                    if field_type is bool:
                        value_converted = value.lower() in ("true", "yes", "1")
                    elif field_type is Path:
                        value_converted = Path(value)
                    else:
                        value_converted = value

                    setattr(config, key, value_converted)
                    manager.save_config(config)

                    console.print(
                        f"[green]✓[/green] Set [cyan]{key}[/cyan] = [yellow]{value}[/yellow]"
                    )
                else:
                    console.print(f"[red]✗[/red] Unknown config key: {key}")
                    console.print("\nAvailable keys:")
                    for field_name in config.model_fields.keys():
                        console.print(f"  • {field_name}")
                    console.print("\nNested keys (use dot notation):")
                    console.print("  • transcription.api_key")
                    console.print("  • extraction.gemini_api_key")
                    console.print("  • extraction.claude_api_key")
                    console.print("  • cache.media.enabled")
                    sys.exit(1)
            elif len(key_parts) in {2, 3}:
                # Nested key (e.g., transcription.api_key or cache.media.enabled)
                parent_key, *child_path = key_parts

                if not hasattr(config, parent_key):
                    console.print(f"[red]✗[/red] Unknown config section: {parent_key}")
                    console.print(
                        "\nAvailable sections: transcription, extraction, interview, cache"
                    )
                    sys.exit(1)

                parent_obj = getattr(config, parent_key)

                for nested_key in child_path[:-1]:
                    if not hasattr(parent_obj, nested_key):
                        console.print(
                            f"[red]✗[/red] Unknown key '{nested_key}' in section '{parent_key}'"
                        )
                        sys.exit(1)
                    parent_obj = getattr(parent_obj, nested_key)

                child_key = child_path[-1]
                if not hasattr(parent_obj, child_key):
                    console.print(
                        f"[red]✗[/red] Unknown key '{child_key}' in section '{parent_key}'"
                    )
                    console.print(f"\nAvailable keys in {parent_key}:")
                    for field_name in parent_obj.model_fields.keys():
                        console.print(f"  • {parent_key}.{field_name}")
                    sys.exit(1)

                field_type = (
                    type(getattr(parent_obj, child_key))
                    if getattr(parent_obj, child_key) is not None
                    else str
                )

                value_converted_nested: bool | float | int | str
                if field_type is bool:
                    value_converted_nested = value.lower() in ("true", "yes", "1")
                elif field_type is float:
                    value_converted_nested = float(value)
                elif field_type is int:
                    value_converted_nested = int(value)
                else:
                    value_converted_nested = value

                setattr(parent_obj, child_key, value_converted_nested)
                manager.save_config(config)

                # Special handling for API keys - secure masking + delight
                if "api_key" in child_key.lower():
                    masked = f"{'•' * 12}{value[-4:]}"
                    console.print(f"[green]✓[/green] API key configured: [dim]{masked}[/dim]")
                    console.print(f"  [dim]Saved to {parent_key} settings[/dim]")
                else:
                    console.print(
                        f"[green]✓[/green] Set [cyan]{key}[/cyan] = "
                        f"[yellow]{value_converted_nested}[/yellow]"
                    )
            else:
                console.print(f"[red]✗[/red] Invalid key format: {key}")
                console.print(
                    "Use 'key' for top-level or dot notation for nested values "
                    "(e.g., transcription.api_key or cache.media.enabled)"
                )
                sys.exit(1)

        elif action == "feed":
            if not key or extra_templates is None:
                console.print(
                    "[red]✗[/red] Usage: inkwell config feed <name> --extra-templates <list>"
                )
                console.print('[dim]  Pass --extra-templates "" to clear extra templates.[/dim]')
                sys.exit(1)

            feed_config = manager.get_feed(key)
            custom_templates = _parse_and_validate_extra_templates(extra_templates)
            manager.update_feed(
                key,
                feed_config.model_copy(update={"custom_templates": custom_templates}),
            )

            if custom_templates:
                console.print(
                    f"[green]✓[/green] Set extra templates for [cyan]{key}[/cyan]: "
                    f"[yellow]{', '.join(custom_templates)}[/yellow]"
                )
            else:
                console.print(f"[green]✓[/green] Cleared extra templates for [cyan]{key}[/cyan]")

        else:
            console.print(f"[red]✗[/red] Unknown action: {action}")
            console.print("Valid actions: show, edit, set, feed")
            sys.exit(1)

    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


@app.command("transcribe")
def transcribe_command(
    url: str = typer.Argument(..., help="Episode URL to transcribe"),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output file path (default: print to stdout)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force re-transcription (bypass cache)"
    ),
    skip_youtube: bool = typer.Option(
        False, "--skip-youtube", help="Skip YouTube, use Gemini directly"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print a JSON envelope to stdout; progress and warnings go to stderr.",
    ),
    plain: bool = typer.Option(
        False,
        "--plain",
        help="Print only transcript text to stdout; progress and warnings go to stderr.",
    ),
) -> None:
    """Transcribe a podcast episode.

    Uses multi-tier strategy:
    1. Check cache (unless --force)
    2. Try YouTube transcript (free, unless --skip-youtube)
    3. Fall back to audio download + Gemini (costs money)

    Examples:
        inkwell transcribe https://youtube.com/watch?v=xyz

        inkwell transcribe https://example.com/episode.mp3 --output transcript.txt

        inkwell transcribe https://youtube.com/watch?v=xyz --force
    """
    machine_output = json_output or plain
    status_console = err_console if machine_output else console

    def confirm_cost(estimate: CostEstimate) -> bool:
        """Confirm Gemini transcription cost with user."""
        status_console.print(
            f"\n[yellow]⚠[/yellow] Gemini transcription will cost approximately "
            f"[bold]{estimate.formatted_cost}[/bold]"
        )
        status_console.print(f"[dim]File size: {estimate.file_size_mb:.1f} MB[/dim]")
        return typer.confirm("Proceed with transcription?", err=machine_output)

    async def run_transcription() -> None:
        try:
            _validate_machine_output_options(json_output=json_output, plain=plain)

            config_manager = ConfigManager()
            config = config_manager.load_config()
            input_source = InputResolver().resolve(url)
            transcribe_url = input_source.url or input_source.value

            manager = TranscriptionManager(
                config=config.transcription,
                media_cache=config.cache.media,
                cost_confirmation_callback=confirm_cost,
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=status_console,
            ) as progress:
                task = progress.add_task("Transcribing...", total=None)

                result = await manager.transcribe(
                    transcribe_url, use_cache=not force, skip_youtube=skip_youtube
                )

                progress.update(task, completed=True)

            if not result.success:
                status_console.print(f"[red]✗[/red] Transcription failed: {result.error}")
                sys.exit(1)

            assert result.transcript is not None

            # Display metadata
            status_console.print("\n[green]✓[/green] Transcription complete")
            status_console.print(f"[dim]Source: {result.transcript.source}[/dim]")
            status_console.print(f"[dim]Language: {result.transcript.language}[/dim]")
            status_console.print(f"[dim]Duration: {result.duration_seconds:.1f}s[/dim]")

            if result.cost_usd > 0:
                status_console.print(f"[dim]Cost: ${result.cost_usd:.4f}[/dim]")

            if result.from_cache:
                status_console.print("[dim]✓ Retrieved from cache[/dim]")

            transcript_text = result.transcript.full_text

            # Output
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(transcript_text)
                status_console.print(f"\n[cyan]→[/cyan] Saved to {output}")

            if json_output:
                _print_json_payload(
                    _transcribe_json_payload(
                        source=input_source,
                        result=result,
                        output=output,
                    )
                )
            elif plain:
                print(transcript_text)
            elif not output:
                console.print("\n" + "=" * 80)
                console.print(transcript_text)
                console.print("=" * 80)

        except KeyboardInterrupt:
            status_console.print("\n[yellow]Cancelled by user[/yellow]")
            sys.exit(130)
        except InkwellError as e:
            status_console.print(f"[red]✗[/red] Error: {e}")
            sys.exit(1)
        except Exception as e:
            status_console.print(f"[red]✗[/red] Error: {e}")
            sys.exit(1)

    asyncio.run(run_transcription())


@app.command("cache")
def cache_command(
    action: str = typer.Argument(
        ...,
        help="Action: stats, clear, clear-expired, enforce-media-policy",
    ),
    transcripts: bool = typer.Option(
        False,
        "--transcripts",
        help="Target transcript cache entries",
    ),
    extractions: bool = typer.Option(
        False,
        "--extractions",
        help="Target extraction cache entries",
    ),
    media: bool = typer.Option(
        False,
        "--media",
        help="Target downloaded media/audio cache files",
    ),
    all_targets: bool = typer.Option(
        False,
        "--all",
        help="Target transcript, extraction, and media caches",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation for destructive cache actions",
    ),
) -> None:
    """Manage local caches.

    Actions:
        stats:                Show cache statistics
        clear:                Clear selected caches
        clear-expired:        Remove expired transcript/extraction entries
        enforce-media-policy: Apply media cache TTL/size policy

    Examples:
        inkwell cache stats

        inkwell cache clear --transcripts

        inkwell cache clear --extractions --force

        inkwell cache clear --media --force

        inkwell cache enforce-media-policy --force
    """
    try:
        from inkwell.audio.downloader import AudioDownloader
        from inkwell.extraction.cache import ExtractionCache

        manager = TranscriptionManager()

        if action == "stats":
            stats = manager.cache_stats()
            extraction_stats = asyncio.run(ExtractionCache().get_stats())
            audio_stats = AudioDownloader.cache_stats()

            console.print("\n[bold]Transcript Cache Statistics[/bold]\n")

            table = Table(show_header=False, box=None)
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Total entries", str(stats["total"]))
            table.add_row("Valid", str(stats["valid"]))
            table.add_row("Expired", str(stats["expired"]))
            table.add_row("Size", f"{stats['size_bytes'] / 1024 / 1024:.2f} MB")
            table.add_row("Format version", str(stats.get("cache_format_version", "unknown")))
            table.add_row("Cache directory", stats["cache_dir"])

            console.print(table)

            if stats["sources"]:
                console.print("\n[bold]By Source:[/bold]")
                for source, count in stats["sources"].items():
                    console.print(f"  • {source}: {count}")

            console.print("\n[bold]Extraction Cache Statistics[/bold]\n")

            extraction_table = Table(show_header=False, box=None)
            extraction_table.add_column("Key", style="cyan")
            extraction_table.add_column("Value", style="white")

            extraction_table.add_row("Total entries", str(extraction_stats["total_entries"]))
            extraction_table.add_row("Size", f"{extraction_stats['total_size_mb']:.2f} MB")
            extraction_table.add_row(
                "Oldest entry age",
                f"{extraction_stats['oldest_entry_age_days']:.1f} days",
            )
            extraction_table.add_row(
                "Format version",
                str(extraction_stats.get("cache_format_version", "unknown")),
            )
            extraction_table.add_row("Cache directory", extraction_stats["cache_dir"])

            console.print(extraction_table)

            if extraction_stats["templates"]:
                console.print("\n[bold]By Template:[/bold]")
                for template_name, count in extraction_stats["templates"].items():
                    console.print(f"  • {template_name}: {count}")

            if extraction_stats["providers"]:
                console.print("\n[bold]By Provider:[/bold]")
                for provider_name, count in extraction_stats["providers"].items():
                    console.print(f"  • {provider_name}: {count}")

            console.print("\n[bold]Media Cache Statistics[/bold]\n")

            media_table = Table(show_header=False, box=None)
            media_table.add_column("Key", style="cyan")
            media_table.add_column("Value", style="white")

            media_table.add_row("Total files", str(audio_stats["total"]))
            media_table.add_row("Size", f"{audio_stats['size_bytes'] / 1024 / 1024:.2f} MB")
            media_table.add_row(
                "Format version",
                str(audio_stats.get("cache_format_version", "unknown")),
            )
            media_table.add_row("Cache directory", audio_stats["cache_dir"])

            console.print(media_table)

            if audio_stats["extensions"]:
                console.print("\n[bold]By Extension:[/bold]")
                for extension, count in audio_stats["extensions"].items():
                    console.print(f"  • {extension}: {count}")

        elif action == "clear":
            targets = _resolve_cache_targets(
                transcripts=transcripts,
                extractions=extractions,
                media=media,
                all_targets=all_targets,
            )
            selected = [name for name, selected in targets.items() if selected]
            if not _confirm_cache_deletion(
                force=force,
                message=f"\nClear selected caches ({', '.join(selected)})?",
            ):
                console.print("[yellow]Cancelled[/yellow]")
                return

            if targets["transcripts"]:
                count = manager.clear_cache()
                console.print(f"[green]✓[/green] Cleared {count} transcript cache entries")

            if targets["extractions"]:
                count = asyncio.run(ExtractionCache().clear())
                console.print(f"[green]✓[/green] Cleared {count} extraction cache entries")

            if targets["media"]:
                media_result = AudioDownloader.clear_cache()
                console.print(
                    "[green]✓[/green] Cleared "
                    f"{media_result['files_deleted']} media cache files "
                    f"({_format_deleted_bytes(media_result['bytes_deleted'])})"
                )

        elif action == "clear-expired":
            if all_targets:
                targets = {"transcripts": True, "extractions": True}
            elif transcripts or extractions:
                targets = {"transcripts": transcripts, "extractions": extractions}
            elif media:
                targets = {"transcripts": False, "extractions": False}
            else:
                targets = {"transcripts": True, "extractions": False}

            if media or all_targets:
                console.print(
                    "[yellow]Media cache expiration is handled by "
                    "inkwell cache enforce-media-policy.[/yellow]"
                )

            if targets["transcripts"]:
                count = manager.clear_expired_cache()
                console.print(f"[green]✓[/green] Removed {count} expired transcript cache entries")

            if targets["extractions"]:
                count = asyncio.run(ExtractionCache().clear_expired())
                console.print(f"[green]✓[/green] Removed {count} expired extraction cache entries")

        elif action == "enforce-media-policy":
            if not _confirm_cache_deletion(
                force=force,
                message="\nEnforce media cache TTL/size policy now?",
            ):
                console.print("[yellow]Cancelled[/yellow]")
                return

            media_config = ConfigManager().load_config().cache.media
            downloader = AudioDownloader(
                cache_enabled=media_config.enabled,
                cache_max_mb=media_config.max_mb,
                cache_ttl_days=media_config.ttl_days,
            )
            result = downloader.enforce_cache_policy()
            console.print(
                "[green]✓[/green] Enforced media cache policy: "
                f"{result['expired_files']} expired files, "
                f"{result['size_files']} size-limit files, "
                f"{_format_deleted_bytes(result['bytes_deleted'])} deleted"
            )

        else:
            console.print(f"[red]✗[/red] Unknown action: {action}")
            console.print("Valid actions: stats, clear, clear-expired, enforce-media-policy")
            sys.exit(1)

    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


@app.command("fetch")
def fetch_command(
    url_or_feed: str = typer.Argument(
        ..., help="Episode URL, configured feed name, or local media/document/image file"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Base directory for output (default: ~/inkwell-notes)"
    ),
    podcast_name: str | None = typer.Option(
        None,
        "--podcast-name",
        "-n",
        help="Podcast name for output directory (overrides auto-detection)",
    ),
    latest: bool = typer.Option(False, "--latest", "-l", help="Fetch the latest episode from feed"),
    count: int | None = typer.Option(
        None,
        "--count",
        min=1,
        help="Process the N latest episodes from a feed",
    ),
    episode: str | None = typer.Option(
        None,
        "--episode",
        "-e",
        help="Position (3), range (1-5), list (1,3,7), or title keyword",
    ),
    templates: str | None = typer.Option(
        None, "--templates", "-t", help="Comma-separated template names (default: auto)"
    ),
    category: str | None = typer.Option(
        None, "--category", "-c", help="Episode category (auto-detected if not specified)"
    ),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="LLM provider: claude, gemini, auto (default: auto)"
    ),
    skip_cache: bool = typer.Option(False, "--skip-cache", help="Skip extraction cache"),
    force_extraction: bool = typer.Option(
        False,
        "--force-extraction",
        help="Run LLM extraction even when short-content bypass would apply",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show cost estimate without extracting"),
    extract_only: bool = typer.Option(
        False,
        "--extract",
        help="Emit transcript text only; skip structured extraction, interview, and note output.",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Overwrite existing episode directory"
    ),
    interview: bool = typer.Option(
        False, "--interview", help="Conduct interactive interview after extraction"
    ),
    interview_template: str | None = typer.Option(
        None,
        "--interview-template",
        help="Interview template: reflective, analytical, creative (default: from config)",
    ),
    interview_format: str | None = typer.Option(
        None,
        "--interview-format",
        help="Output format: structured, narrative, qa (default: from config)",
    ),
    max_questions: int | None = typer.Option(
        None, "--max-questions", help="Maximum number of interview questions (default: from config)"
    ),
    no_resume: bool = typer.Option(
        False, "--no-resume", help="Don't resume previous interview session"
    ),
    resume_session: str | None = typer.Option(
        None, "--resume-session", help="Resume specific interview session by ID"
    ),
    extractor: str | None = typer.Option(
        None,
        "--extractor",
        help=("Force extraction plugin: claude, gemini, or explicit local claude-code/codex"),
        envvar="INKWELL_EXTRACTOR",
    ),
    transcriber: str | None = typer.Option(
        None,
        "--transcriber",
        help="Force specific transcription plugin (e.g., youtube, gemini)",
        envvar="INKWELL_TRANSCRIBER",
    ),
    ocr_mode: OCRMode = typer.Option(
        OCRMode.AUTO,
        "--ocr-mode",
        case_sensitive=False,
        help="Local OCR behavior for images/PDFs: auto, always, or never",
    ),
    ocr_engine: str | None = typer.Option(
        None,
        "--ocr-engine",
        help="Force a local OCR plugin (default: tesseract)",
        envvar="INKWELL_OCR",
    ),
    ocr_language: str = typer.Option(
        "eng",
        "--ocr-language",
        help="Tesseract language code(s), for example eng, spa, or eng+spa",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print a JSON envelope to stdout; progress and warnings go to stderr.",
    ),
    plain: bool = typer.Option(
        False,
        "--plain",
        help="Print only generated output directory path(s) to stdout.",
    ),
    save_feed: bool = typer.Option(
        False,
        "--save-feed",
        help=(
            "Also save this video's channel as a feed (YouTube URLs only). "
            "Auto-names from channel metadata unless --feed-name is set."
        ),
    ),
    feed_name: str | None = typer.Option(
        None,
        "--feed-name",
        help="Feed name for --save-feed (optional; derived from channel metadata if omitted).",
    ),
) -> None:
    """Fetch and process a podcast episode.

    Complete pipeline: transcribe → extract → generate markdown → write files → [optional interview]

    Examples:
        inkwell fetch my-podcast --latest

        inkwell fetch my-podcast --episode "AI security"

        inkwell fetch https://youtube.com/watch?v=xyz

        inkwell fetch https://example.com/ep1.mp3 --templates summary,quotes

        inkwell fetch https://... --category tech --provider claude

        inkwell fetch https://... --dry-run  # Cost estimate only

        inkwell fetch https://... --interview  # With interactive interview

        inkwell fetch https://... --interview --interview-template analytical

        inkwell fetch https://... --extractor claude  # Force Claude extractor

        inkwell fetch ./source.txt --extractor codex --force-extraction  # Explicit local Codex

        inkwell fetch ./source.txt --extractor claude-code --force-extraction  # Local Claude

        inkwell fetch https://... --transcriber gemini  # Force Gemini transcriber

        inkwell fetch ./scan.png  # Local OCR into normal note output

        inkwell fetch ./document.pdf --ocr-mode auto --ocr-language eng
    """

    async def run_fetch() -> None:
        nonlocal url_or_feed
        machine_output = json_output or plain or extract_only
        status_console = err_console if machine_output else console
        processed_results: list[PipelineResult] = []
        requested_count = 1
        extract_transcripts: list[str] = []
        extract_output_paths: list[Path] = []
        extract_used_filenames: set[str] = set()
        try:
            _validate_machine_output_options(json_output=json_output, plain=plain)
            if extract_only:
                _validate_extract_only_options(
                    json_output=json_output,
                    dry_run=dry_run,
                    interview=interview,
                    interview_template=interview_template,
                    interview_format=interview_format,
                    max_questions=max_questions,
                    no_resume=no_resume,
                    resume_session=resume_session,
                    podcast_name=podcast_name,
                    templates=templates,
                    category=category,
                    provider=provider,
                    extractor=extractor,
                    skip_cache=skip_cache,
                    save_feed=save_feed,
                )

            manager = ConfigManager()
            config = manager.load_config()
            selected_extractor = extractor or os.environ.get("INKWELL_EXTRACTOR")
            if selected_extractor in {"claude-code", "codex"}:
                local_plugin = config.plugins.get(selected_extractor)
                configured_model = (
                    local_plugin.config.get("model") if local_plugin is not None else None
                )
                if not isinstance(configured_model, str) or not configured_model.strip():
                    message = (
                        "The Local Claude extractor requires an explicit model."
                        if selected_extractor == "claude-code"
                        else "The Codex extractor requires an explicit model."
                    )
                    raise ConfigError(
                        message,
                        details={
                            "code": "model_required",
                            "extractor": selected_extractor,
                        },
                        suggestion=(
                            f"Run `inkwell plugins configure {selected_extractor} "
                            "model MODEL_ID`, "
                            "then validate it."
                        ),
                    )
            base_output_dir = output_dir or config.default_output_dir

            # --feed-name is metadata for --save-feed; it has no meaning
            # on its own and silently ignoring it would mislead scripts into
            # thinking the channel was persisted.
            if feed_name is not None and not save_feed:
                raise ValidationError(
                    "--feed-name has no effect without --save-feed",
                    suggestion=(
                        "Add --save-feed to persist the channel, or drop "
                        "--feed-name if you meant a one-time fetch."
                    ),
                )

            input_source = InputResolver().resolve(url_or_feed)
            if input_source.is_url and input_source.url:
                # Normalize scheme-less URL-shaped inputs up-front so the
                # --save-feed guard and the feed-name lookup both see the same
                # URL. Feed names never contain both `.` and `/`, so this is
                # unambiguous. Without this, `www.youtube.com/watch?v=X
                # --save-feed` would be rejected as "not YouTube" even though
                # the same input works in plain fetch mode.
                url_or_feed = input_source.url

            # Resolve feed name to episode URL if needed
            url = url_or_feed
            resolved_category = category
            # Auth credentials for private feeds (passed to audio downloader)
            auth_username: str | None = None
            auth_password: str | None = None
            feed_extra_templates: list[str] = []
            # Episode from RSS feed (if applicable)
            ep: Episode | None = None
            source_text: str | None = None
            source_kind: str | None = None
            source_metadata: dict[str, Any] | None = None
            source_episode_title: str | None = None
            source_podcast_name: str | None = None
            # Set when the argument resolves to a configured feed (and we fan
            # out into its episodes); stays None for direct-URL mode.
            selected_episodes: list[Episode] | None = None

            is_url = input_source.is_url

            if is_url and count is not None:
                raise ValidationError(
                    "--count only works with saved feeds",
                    suggestion=(
                        "Use 'inkwell add <feed-url> --feed-name <name>' first, "
                        "then run 'inkwell fetch <name> --count N'."
                    ),
                )

            # Pre-fetch validation for --save-feed (fail fast, before the
            # long-running pipeline starts).
            if save_feed:
                if not is_url or not is_youtube_url(url_or_feed):
                    raise ValidationError(
                        "--save-feed only supports YouTube URLs currently",
                        suggestion=(
                            "For non-YouTube sources, use "
                            "'inkwell add <feed-url> --name <name>' instead."
                        ),
                    )
                # Fail fast on playlists before the pipeline runs. Without this
                # the playlist-rejection inside resolve_youtube_url only fires
                # *after* transcription/extraction completes, wasting API spend.
                if is_youtube_playlist_url(url_or_feed):
                    raise ValidationError(
                        "Playlist URLs aren't supported yet — try the channel URL instead",
                        suggestion=(
                            "Visit the playlist on YouTube and copy the channel's "
                            "@handle or /channel/UC… URL from the creator."
                        ),
                    )

            # Pre-resolve YouTube URLs so we can reuse yt-dlp metadata
            # (channel + video title) and avoid a second yt-dlp call in the
            # post-fetch --save-feed block.
            pre_resolved: ResolvedFeed | None = None
            if is_url and is_youtube_url(url_or_feed) and not is_youtube_playlist_url(url_or_feed):
                try:
                    pre_resolved = await resolve_youtube_url(url_or_feed)
                except ValidationError:
                    # Resolution can fail for private/region-blocked videos;
                    # the audio downloader will surface a clearer error. Don't
                    # pre-empt it here — just fall back to "Unknown Podcast".
                    pre_resolved = None

            if input_source.kind == ContentSourceKind.LOCAL_FILE:
                local_path = input_source.path or Path(input_source.value)
                local_path = local_path.expanduser()
                if _is_local_text_path(local_path):
                    source_text = _read_text_source_file(local_path)
                    source_kind = "local_text"
                    source_episode_title = local_path.stem
                    source_podcast_name = "Local Files"
                    url = str(local_path)
                elif _is_local_pdf_path(local_path):
                    source_result = extract_source_text_from_pdf(
                        local_path,
                        ocr_mode=ocr_mode,
                        ocr_engine=ocr_engine,
                        ocr_language=ocr_language,
                    )
                    source_text = source_result.text
                    source_kind = source_result.source_kind
                    source_metadata = source_result.provenance()
                    source_episode_title = local_path.stem
                    source_podcast_name = "Documents"
                    url = str(local_path)
                    for source_warning in source_result.warnings:
                        status_console.print(f"[yellow]⚠[/yellow] {source_warning}")
                    input_source = ContentSource(
                        raw_input=input_source.raw_input,
                        kind=ContentSourceKind.PDF,
                        value=str(local_path),
                        path=local_path,
                    )
                elif _is_local_image_path(local_path):
                    source_result = extract_source_text_from_image(
                        local_path,
                        ocr_mode=ocr_mode,
                        ocr_engine=ocr_engine,
                        ocr_language=ocr_language,
                    )
                    source_text = source_result.text
                    source_kind = source_result.source_kind
                    source_metadata = source_result.provenance()
                    source_episode_title = local_path.stem
                    source_podcast_name = "Images"
                    url = str(local_path)
                    input_source = ContentSource(
                        raw_input=input_source.raw_input,
                        kind=ContentSourceKind.IMAGE,
                        value=str(local_path),
                        path=local_path,
                    )
                elif _is_local_media_path(local_path):
                    source_episode_title = local_path.stem
                    source_podcast_name = "Local Files"
                    url = str(local_path)
                else:
                    raise ValidationError(
                        f"Unsupported local file type: {local_path.suffix or '<none>'}",
                        suggestion=(
                            "Use local audio/video, .txt, .md, PDF, PNG, JPEG, TIFF, "
                            "BMP, GIF, WebP, or PNM files. Video slide extraction remains separate."
                        ),
                    )

            elif input_source.kind == ContentSourceKind.STDIN:
                source_text = sys.stdin.read()
                if not source_text.strip():
                    raise ValidationError("Stdin input is empty")
                source_kind = "stdin"
                source_episode_title = "stdin"
                source_podcast_name = "Stdin"
                url = "stdin://input"

            elif input_source.kind == ContentSourceKind.URL:
                source_url = input_source.url or input_source.value
                source_text = extract_article_text_from_url(source_url)
                source_kind = "article"
                source_episode_title = derive_readable_title_from_url(source_url)
                source_podcast_name = "Articles"
                url = source_url
                input_source = ContentSource(
                    raw_input=input_source.raw_input,
                    kind=ContentSourceKind.ARTICLE,
                    value=source_url,
                    url=source_url,
                )

            elif not is_url:
                # Treat as feed name - look up in configured feeds
                try:
                    feed_config = manager.get_feed(url_or_feed)
                except NotFoundError as e:
                    if input_source.kind == ContentSourceKind.UNKNOWN_URL:
                        raise ValidationError(
                            f"Unsupported URL input: {input_source.value}",
                            suggestion="Use an http(s) media URL or a saved feed name.",
                        ) from e

                    status_console.print(f"[red]✗[/red] Feed '{url_or_feed}' not found.")
                    status_console.print("  Use [cyan]inkwell list[/cyan] to see configured feeds.")
                    status_console.print("  Or provide a direct episode URL.")
                    sys.exit(1)
                else:
                    selection_modes = (
                        int(latest) + int(episode is not None) + int(count is not None)
                    )
                    if selection_modes > 1:
                        raise ValidationError(
                            "--latest, --episode, and --count are mutually exclusive",
                            suggestion="Choose one feed selection mode",
                        )

                    if count is not None and count > MAX_EPISODES_PER_SELECTION:
                        raise ValidationError(
                            f"--count {count} exceeds maximum of {MAX_EPISODES_PER_SELECTION}",
                            suggestion="Select fewer episodes or use multiple smaller requests",
                        )

                    # Found the feed - need --latest, --episode, or --count flag
                    if selection_modes == 0:
                        status_console.print(
                            f"[red]✗[/red] Feed '{url_or_feed}' requires "
                            "--latest, --episode, or --count flag."
                        )
                        status_console.print("\nUsage:")
                        status_console.print(f"  inkwell fetch {url_or_feed} --latest")
                        status_console.print(f"  inkwell fetch {url_or_feed} --count 5")
                        status_console.print(f'  inkwell fetch {url_or_feed} --episode "keyword"')
                        sys.exit(1)

                    # Fetch and parse the RSS feed
                    status_console.print(f"[bold]Fetching feed:[/bold] {url_or_feed}")
                    parser = RSSParser()

                    with status_console.status("[bold]Parsing RSS feed...[/bold]"):
                        feed = await parser.fetch_feed(str(feed_config.url), feed_config.auth)

                    if latest:
                        selected_episodes = [parser.get_latest_episode(feed, url_or_feed)]
                        status_console.print(
                            f"[green]✓[/green] Latest episode: {selected_episodes[0].title}"
                        )
                    elif count is not None:
                        selected_episodes = parser.get_latest_episodes(feed, url_or_feed, count)
                        status_console.print(
                            f"[green]✓[/green] Found {len(selected_episodes)} episodes"
                        )
                    else:
                        # episode is guaranteed to be set when not using --latest
                        assert episode is not None, "Episode selector required"
                        selected_episodes = parser.parse_and_fetch_episodes(
                            feed, episode, url_or_feed
                        )
                        if len(selected_episodes) == 1:
                            status_console.print(
                                f"[green]✓[/green] Found episode: {selected_episodes[0].title}"
                            )
                        else:
                            status_console.print(
                                f"[green]✓[/green] Found {len(selected_episodes)} episodes"
                            )

                    if not resolved_category and feed_config.category:
                        resolved_category = feed_config.category
                    feed_extra_templates = feed_config.custom_templates

                    # Extract auth credentials for audio download (basic auth only)
                    if feed_config.auth and feed_config.auth.type == "basic":
                        auth_username = feed_config.auth.username
                        auth_password = feed_config.auth.password

            # For feed mode: selected_episodes set by RSS parsing above.
            # For URL mode: run once with ep=None.
            episodes_to_process: list[Episode | None] = (
                list(selected_episodes) if selected_episodes is not None else [None]
            )
            requested_count = len(episodes_to_process)

            # Process each episode
            for ep in episodes_to_process:
                if ep is not None:
                    url = str(ep.url)
                    if len(episodes_to_process) > 1:
                        status_console.print(f"\n[bold cyan]Processing:[/bold cyan] {ep.title}")

                # Determine if interview will be included for progress display
                will_interview = interview or config.interview.auto_start

                # Extract episode metadata if available from feed parsing
                episode_title: str | None = None
                detected_podcast_name: str | None = None
                if ep is not None:
                    episode_title = ep.title
                    detected_podcast_name = ep.podcast_name or url_or_feed
                elif source_episode_title is not None:
                    episode_title = source_episode_title
                    detected_podcast_name = source_podcast_name
                elif pre_resolved is not None and pre_resolved.episode_title:
                    # Direct YouTube URL: when yt-dlp provides a video title,
                    # use it so direct-URL capture folders are readable.
                    episode_title = pre_resolved.episode_title

                if extract_only:
                    if source_text is not None:
                        transcript_text = source_text
                    else:
                        transcription_manager = TranscriptionManager(
                            config=config.transcription,
                            media_cache=config.cache.media,
                        )

                        extract_substeps = {
                            "checking_cache": "Checking transcript cache...",
                            "trying_youtube": "Trying YouTube transcript...",
                            "downloading_audio": "Downloading audio...",
                            "transcribing_gemini": "Transcribing with Gemini...",
                            "transcribing_gemini_youtube": (
                                "Transcribing YouTube URL with Gemini..."
                            ),
                            "caching_result": "Caching transcript...",
                        }

                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            console=status_console,
                        ) as progress:
                            task = progress.add_task("Extracting transcript...", total=None)

                            def handle_extract_progress(step: str, _data: dict) -> None:
                                progress.update(task, description=extract_substeps.get(step, step))

                            transcript_result = await transcription_manager.transcribe(
                                url,
                                use_cache=True,
                                auth_username=auth_username,
                                auth_password=auth_password,
                                progress_callback=handle_extract_progress,
                                transcriber_override=transcriber,
                            )
                            progress.update(task, completed=True)

                        if not transcript_result.success or transcript_result.transcript is None:
                            raise InkwellError(
                                "Transcript extraction failed",
                                suggestion=transcript_result.error,
                            )

                        transcript_text = transcript_result.transcript.full_text

                    if output_dir is not None:
                        output_dir.mkdir(parents=True, exist_ok=True)
                        transcript_path = _extract_transcript_output_path(
                            output_dir=output_dir,
                            title=episode_title,
                            url=url,
                            used_filenames=extract_used_filenames,
                            overwrite=overwrite,
                        )
                        transcript_path.write_text(transcript_text, encoding="utf-8")
                        extract_output_paths.append(transcript_path)
                        status_console.print(f"[green]✓[/green] Wrote {transcript_path}")
                    else:
                        extract_transcripts.append(transcript_text)

                    continue

                # Compute effective output directory
                effective_output_dir = base_output_dir

                # Note: No longer skipping existing episodes here.
                # The orchestrator handles incremental mode: if the episode directory exists
                # and --overwrite is not set, it will only regenerate templates that are
                # missing or have updated versions.

                # Show output directory upfront
                status_console.print("[bold cyan]Inkwell Extraction Pipeline[/bold cyan]")
                status_console.print(f"[dim]Output: {effective_output_dir}[/dim]\n")
                template_names = (
                    [t.strip() for t in templates.split(",") if t.strip()] if templates else []
                )
                if feed_extra_templates:
                    template_names = _dedupe_template_names(
                        [*template_names, *feed_extra_templates]
                    )

                options = PipelineOptions(
                    url=url,
                    category=resolved_category,
                    templates=template_names or None,
                    provider=provider,
                    interview=interview,
                    no_resume=no_resume,
                    resume_session=resume_session,
                    output_dir=output_dir,
                    skip_cache=skip_cache,
                    dry_run=dry_run,
                    overwrite=overwrite,
                    interview_template=interview_template,
                    interview_format=interview_format,
                    max_questions=max_questions,
                    auth_username=auth_username,
                    auth_password=auth_password,
                    episode_title=episode_title,
                    podcast_name=podcast_name or detected_podcast_name,
                    source_text=source_text,
                    source_kind=source_kind,
                    source_metadata=source_metadata,
                    extractor=extractor,
                    transcriber=transcriber,
                    force_extraction=force_extraction,
                )

                orchestrator = PipelineOrchestrator(config)

                pipeline_progress = PipelineProgress(
                    console=status_console,
                    include_interview=will_interview,
                )

                # Map transcription sub-steps to user-friendly messages
                transcription_substeps = {
                    "checking_cache": "Checking cache...",
                    "trying_youtube": "Trying YouTube (free)...",
                    "downloading_audio": "Downloading audio...",
                    "transcribing_gemini": "Transcribing with Gemini...",
                    "caching_result": "Caching result...",
                }

                completion_details: dict[str, object] = {}

                # Progress callback for pipeline stages
                def handle_progress(step_name: str, step_data: dict[str, Any]) -> None:
                    nonlocal completion_details

                    if step_name == "transcription_start":
                        pipeline_progress.start_stage("transcribe")

                    elif step_name == "transcription_step":
                        substep = step_data.get("step", "")
                        message = transcription_substeps.get(substep, substep)
                        pipeline_progress.update_substep("transcribe", message)

                    elif step_name == "transcription_complete":
                        source = step_data["source"]
                        if step_data.get("from_cache"):
                            summary = "from cache"
                        else:
                            summary = f"via {source}"
                        pipeline_progress.complete_stage("transcribe", summary)
                        completion_details["words"] = step_data["word_count"]

                    elif step_name == "template_selection_start":
                        pipeline_progress.start_stage("select")

                    elif step_name == "template_selection_complete":
                        count = step_data["template_count"]
                        pipeline_progress.complete_stage("select", f"{count} templates")
                        completion_details["templates"] = step_data["templates"]

                    elif step_name == "extraction_start":
                        pipeline_progress.start_stage("extract")
                        pipeline_progress.update_substep("extract", "Processing...")

                    elif step_name == "extraction_complete":
                        success = step_data["successful"]
                        failed = step_data["failed"]
                        if failed > 0:
                            pipeline_progress.complete_stage(
                                "extract", f"{success}/{success + failed} ok"
                            )
                        else:
                            pipeline_progress.complete_stage("extract", f"{success} templates")
                        completion_details["cost"] = step_data["cost_usd"]
                        completion_details["cached"] = step_data["cached"]
                        completion_details["failed"] = failed

                    elif step_name == "output_start":
                        pipeline_progress.start_stage("write")

                    elif step_name == "output_complete":
                        file_count = step_data["file_count"]
                        pipeline_progress.complete_stage("write", f"{file_count} files")
                        completion_details["directory"] = step_data["directory"]

                    elif step_name == "interview_start":
                        pipeline_progress.start_stage("interview")

                    elif step_name == "interview_complete":
                        pipeline_progress.complete_stage(
                            "interview", f"{step_data['question_count']} questions"
                        )

                    elif step_name == "interview_cancelled":
                        pipeline_progress.complete_stage("interview", "skipped")

                    elif step_name == "interview_failed":
                        pipeline_progress.fail_stage("interview", step_data.get("error", ""))

                # Execute pipeline with progress display
                # Suppress logs during progress display to avoid interfering with
                # Rich's cursor movement (logs between refreshes cause line duplication)
                loggers_to_suppress = [
                    "inkwell",
                    "google",
                    "google_genai",
                    "httpx",
                    "urllib3",
                    "httpcore",
                ]
                original_levels: dict[str, int] = {}
                for logger_name in loggers_to_suppress:
                    logger = logging.getLogger(logger_name)
                    original_levels[logger_name] = logger.level
                    logger.setLevel(logging.ERROR)

                try:
                    with pipeline_progress:
                        result = await orchestrator.process_episode(
                            options=options,
                            progress_callback=handle_progress,
                        )
                finally:
                    for logger_name, level in original_levels.items():
                        logging.getLogger(logger_name).setLevel(level)

                # Display summary
                status_console.print("\n[bold green]✓ Complete![/bold green]")

                # Format output directory path for display
                try:
                    output_display = str(result.episode_output.directory.relative_to(Path.cwd()))
                except ValueError:
                    output_display = str(result.episode_output.directory)

                table = Table(show_header=False, box=None, padding=(0, 2))
                table.add_column("Key", style="dim")
                table.add_column("Value", style="white")

                table.add_row("Episode:", result.episode_output.directory.name)
                table.add_row("Templates:", f"{len(result.extraction_results)}")

                if result.interview_result:
                    extraction_cost_display = (
                        f"${result.extraction_cost_usd:.4f}"
                        if getattr(result, "extraction_cost_known", True)
                        else "unknown (runtime-managed)"
                    )
                    table.add_row("Extraction cost:", extraction_cost_display)
                    table.add_row("Interview cost:", f"${result.interview_cost_usd:.4f}")
                    table.add_row(
                        "Total cost:",
                        (
                            f"${result.total_cost_usd:.4f}"
                            if getattr(result, "total_cost_known", True)
                            else "partial known total; runtime-managed amount unknown"
                        ),
                    )
                    table.add_row("Interview:", "✓ Completed")
                else:
                    table.add_row(
                        "Total cost:",
                        (
                            f"${result.extraction_cost_usd:.4f}"
                            if getattr(result, "extraction_cost_known", True)
                            else "unknown (runtime-managed)"
                        ),
                    )

                table.add_row("Output:", output_display)

                status_console.print(table)
                processed_results.append(result)

                # Post-fetch: save channel as a feed (--save-feed) or show
                # a hint about --save-feed on raw YouTube URL fetches.
                if save_feed:
                    try:
                        # Reuse the pre-resolved tuple from line ~824 — we
                        # already paid for a yt-dlp round-trip to set the
                        # podcast name, no need to pay for another one here.
                        resolved = pre_resolved or await resolve_youtube_url(url_or_feed)
                        if resolved is None:
                            raise ValidationError("Couldn't save feed: URL isn't a YouTube URL")
                        existing_feeds = manager.list_feeds()
                        existing_match = _find_existing_youtube_feed(existing_feeds, resolved)
                        if existing_match is not None:
                            err_console.print(
                                f"[yellow]Channel already saved as "
                                f"'[bold]{existing_match}[/bold]'[/yellow]"
                            )
                        else:
                            # Auto-derive the feed name when --feed-name is omitted.
                            # The user pasted a YouTube URL; they shouldn't have to
                            # know a good feed name up front.
                            if feed_name is None:
                                existing = set(existing_feeds.keys())
                                effective_name = _derive_feed_name(resolved, existing)
                                display_name = resolved.channel_name
                            else:
                                effective_name = _normalize_feed_name(feed_name)
                                display_name = feed_name if effective_name != feed_name else None
                            stored_name = manager.add_feed(
                                effective_name,
                                FeedConfig(
                                    url=HttpUrl(resolved.feed_url),
                                    display_name=display_name,
                                    auth=AuthConfig(type="none"),
                                ),
                            )
                            err_console.print(
                                f"[green]✓[/green] Saved channel as feed "
                                f"'[bold]{stored_name}[/bold]'"
                            )
                            if feed_name is None:
                                err_console.print(
                                    f"[dim]  Auto-named from channel metadata. "
                                    f"To rename: [cyan]inkwell rename {stored_name} "
                                    f"<new-name>[/cyan]. "
                                    f"Pass [cyan]--feed-name[/cyan] next time to skip "
                                    f"this.[/dim]"
                                )
                    except (ValidationError, ConfigError) as e:
                        err_console.print(f"[yellow]⚠[/yellow] Couldn't save feed: {e}")
                elif _should_show_save_feed_hint(url=url_or_feed, input_was_url=is_url):
                    err_console.print(
                        "\n[dim]Want to track this channel? Re-run with "
                        "[cyan]--save-feed[/cyan] to save it as a feed.[/dim]"
                    )

            if extract_only:
                if output_dir is None:
                    print("\n\n".join(extract_transcripts))
                elif plain:
                    print("\n".join(str(path) for path in extract_output_paths))
                return

            if json_output:
                _print_json_payload(
                    _fetch_json_payload(
                        source=input_source,
                        normalized_input=url_or_feed,
                        output_dir=base_output_dir,
                        latest=latest,
                        count=count,
                        episode=episode,
                        results=processed_results,
                    )
                )
            elif plain:
                print(
                    "\n".join(str(result.episode_output.directory) for result in processed_results)
                )

        except KeyboardInterrupt:
            status_console.print("\n[yellow]Cancelled by user[/yellow]")
            sys.exit(130)
        except FileExistsError as e:
            status_console.print(f"\n[red]✗[/red] {e}")
            sys.exit(1)
        except InkwellError as e:
            if json_output and not plain:
                _print_json_payload(
                    _fetch_error_json_payload(
                        e,
                        requested=requested_count,
                        completed_results=processed_results,
                    )
                )
                raise typer.Exit(1) from e
            # Print message and suggestion separately so agents parsing
            # line-by-line can capture both cleanly (matches add_feed's pattern).
            status_console.print(f"\n[red]✗[/red] {e.message}")
            if e.suggestion:
                status_console.print(f"[dim]  {e.suggestion}[/dim]")
            sys.exit(1)
        except Exception as e:
            status_console.print(f"\n[red]✗[/red] Unexpected error: {e}")
            import traceback

            status_console.print(f"[dim]{traceback.format_exc()}[/dim]")
            sys.exit(1)

    asyncio.run(run_fetch())


@app.command("costs")
def costs_command(
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Filter by provider (gemini, claude)"
    ),
    operation: str | None = typer.Option(
        None, "--operation", "-o", help="Filter by operation type"
    ),
    episode: str | None = typer.Option(None, "--episode", "-e", help="Filter by episode title"),
    days: int | None = typer.Option(None, "--days", "-d", help="Show costs from last N days"),
    recent: int | None = typer.Option(None, "--recent", "-r", help="Show N most recent operations"),
    clear: bool = typer.Option(False, "--clear", help="Clear all cost history"),
) -> None:
    """View API cost tracking and usage statistics.

    Examples:
        # Show all costs
        $ inkwell costs

        # Show costs by provider
        $ inkwell costs --provider gemini

        # Show costs for specific episode
        $ inkwell costs --episode "Building Better Software"

        # Show costs from last 7 days
        $ inkwell costs --days 7

        # Show 10 most recent operations
        $ inkwell costs --recent 10

        # Clear all cost history
        $ inkwell costs --clear
    """

    from rich.panel import Panel

    from inkwell.utils.costs import CostTracker

    try:
        tracker = CostTracker()

        if clear:
            if typer.confirm("Are you sure you want to clear all cost history?"):
                tracker.clear()
                console.print("[green]✓[/green] Cost history cleared")
            else:
                console.print("Cancelled")
            return

        if recent:
            recent_usage = tracker.get_recent_usage(limit=recent)

            if not recent_usage:
                console.print("[yellow]No usage history found[/yellow]")
                return

            console.print(f"\n[bold]Recent {len(recent_usage)} Operations:[/bold]\n")

            table = Table(show_header=True)
            table.add_column("Date", style="cyan")
            table.add_column("Provider", style="magenta")
            table.add_column("Operation", style="blue")
            table.add_column("Episode", style="green", max_width=40)
            table.add_column("Tokens", style="white", justify="right")
            table.add_column("Cost", style="yellow", justify="right")

            for usage in recent_usage:
                date_str = usage.timestamp.strftime("%Y-%m-%d %H:%M")
                episode_str = usage.episode_title or "-"
                tokens_str = f"{usage.total_tokens:,}"
                cost_str = (
                    f"${usage.cost_usd:.4f}" if usage.cost_known else "unknown (runtime-managed)"
                )

                table.add_row(
                    date_str,
                    usage.provider,
                    usage.operation,
                    episode_str,
                    tokens_str,
                    cost_str,
                )

            console.print(table)
            known_subtotal = sum(u.cost_usd for u in recent_usage if u.cost_known)
            unknown_count = sum(1 for u in recent_usage if not u.cost_known)
            total_label = f"${known_subtotal:.4f}"
            if unknown_count:
                total_label += f" known + {unknown_count} runtime-managed"
            console.print(f"\n[bold]Total:[/bold] {total_label}")
            return

        since = None
        if days:
            since = now_utc() - timedelta(days=days)

        summary = tracker.get_summary(
            provider=provider,
            operation=operation,
            episode_title=episode,
            since=since,
        )

        if summary.total_operations == 0:
            console.print("[yellow]No usage found matching filters[/yellow]")
            return

        # Display summary
        console.print("\n[bold cyan]API Cost Summary[/bold cyan]\n")

        # Overall stats
        stats_table = Table(show_header=False, box=None, padding=(0, 2))
        stats_table.add_column("Metric", style="bold")
        stats_table.add_column("Value", style="white")

        stats_table.add_row("Total Operations:", f"{summary.total_operations:,}")
        stats_table.add_row("Total Tokens:", f"{summary.total_tokens:,}")
        stats_table.add_row("Input Tokens:", f"{summary.total_input_tokens:,}")
        stats_table.add_row("Output Tokens:", f"{summary.total_output_tokens:,}")
        total_cost_label = f"${summary.total_cost_usd:.4f}"
        if not summary.total_cost_known:
            total_cost_label += f" known + {summary.unknown_cost_operations} runtime-managed"
        stats_table.add_row("Total Cost:", f"[bold yellow]{total_cost_label}[/bold yellow]")

        console.print(Panel(stats_table, title="Overall", border_style="blue"))

        # Breakdown by provider
        if summary.costs_by_provider:
            console.print("\n[bold]By Provider:[/bold]")
            provider_table = Table(show_header=False, box=None, padding=(0, 2))
            provider_table.add_column("Provider", style="magenta")
            provider_table.add_column("Known Cost", style="yellow", justify="right")

            for prov, cost in sorted(
                summary.costs_by_provider.items(), key=lambda x: x[1], reverse=True
            ):
                provider_table.add_row(prov, f"${cost:.4f}")

            console.print(provider_table)

        # Breakdown by operation
        if summary.costs_by_operation:
            console.print("\n[bold]By Operation:[/bold]")
            op_table = Table(show_header=False, box=None, padding=(0, 2))
            op_table.add_column("Operation", style="blue")
            op_table.add_column("Known Cost", style="yellow", justify="right")

            for op, cost in sorted(
                summary.costs_by_operation.items(), key=lambda x: x[1], reverse=True
            ):
                op_table.add_row(op, f"${cost:.4f}")

            console.print(op_table)

        # Breakdown by episode (top 10)
        if summary.costs_by_episode:
            console.print("\n[bold]By Episode (Top 10):[/bold]")
            episode_table = Table(show_header=False, box=None, padding=(0, 2))
            episode_table.add_column("Episode", style="green", max_width=50)
            episode_table.add_column("Known Cost", style="yellow", justify="right")

            sorted_episodes = sorted(
                summary.costs_by_episode.items(), key=lambda x: x[1], reverse=True
            )
            for ep, cost in sorted_episodes[:10]:
                episode_table.add_row(ep, f"${cost:.4f}")

            if len(sorted_episodes) > 10:
                console.print(f"\n[dim]... and {len(sorted_episodes) - 10} more episodes[/dim]")

            console.print(episode_table)

        console.print()

    except Exception as e:
        console.print(f"\n[red]✗[/red] Error: {e}")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    app()
