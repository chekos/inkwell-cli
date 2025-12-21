"""CLI entry point for Inkwell."""

import asyncio
import logging
import os
import re
import sys
from datetime import timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from inkwell.config.logging import setup_logging
from inkwell.config.manager import ConfigManager
from inkwell.config.schema import AuthConfig, FeedConfig
from inkwell.feeds.models import Episode
from inkwell.feeds.parser import RSSParser
from inkwell.pipeline import PipelineOptions, PipelineOrchestrator
from inkwell.transcription import CostEstimate, TranscriptionManager
from inkwell.utils.datetime import now_utc
from inkwell.utils.display import truncate_url
from inkwell.utils.errors import (
    ConfigError,
    InkwellError,
    NotFoundError,
    ValidationError,
)
from inkwell.utils.progress import PipelineProgress

app = typer.Typer(
    name="inkwell",
    help="Transform podcast episodes into structured markdown notes",
    no_args_is_help=True,
)
console = Console()


def _compute_episode_dir_path(
    output_dir: Path,
    podcast_name: str,
    episode_title: str,
    published_date: str,
) -> Path:
    """Compute expected episode directory path.

    This replicates the logic from EpisodeMetadata for early checking.
    Structure: output_dir/podcast-slug/YYYY-MM-DD-episode-slug/
    """
    # Slugify podcast name
    podcast_slug = re.sub(r"[^\w\s-]", "", podcast_name.lower())
    podcast_slug = re.sub(r"[-\s]+", "-", podcast_slug).strip("-")

    # Slugify episode title
    title_slug = re.sub(r"[^\w\s-]", "", episode_title.lower())
    title_slug = re.sub(r"[-\s]+", "-", title_slug).strip("-")

    # Truncate if too long
    if len(title_slug) > 50:
        title_slug = title_slug[:50].rstrip("-")

    # Episode slug is date + title
    episode_slug = f"{published_date}-{title_slug}"

    # Sanitize each component (same as OutputManager)
    podcast_slug = podcast_slug.replace("..", "").replace("\0", "")
    episode_slug = episode_slug.replace("..", "").replace("\0", "")

    return output_dir / podcast_slug / episode_slug


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose (DEBUG) logging"),
    log_file: Path | None = typer.Option(None, "--log-file", help="Write logs to file"),
) -> None:
    """Inkwell - Transform podcasts into structured markdown notes."""
    # Initialize logging before any command runs
    setup_logging(verbose=verbose, log_file=log_file)


@app.command("version")
def show_version() -> None:
    """Show version information."""
    from inkwell import __version__

    console.print(f"[bold cyan]Inkwell CLI[/bold cyan] v{__version__}")


@app.command("add")
def add_feed(
    url: str = typer.Argument(..., help="RSS feed URL"),
    name: str = typer.Option(..., "--name", "-n", help="Feed identifier name"),
    auth: bool = typer.Option(False, "--auth", help="Prompt for authentication"),
    category: str | None = typer.Option(
        None, "--category", "-c", help="Feed category (e.g., tech, interview)"
    ),
) -> None:
    """Add a new podcast feed.

    Examples:
        inkwell add https://example.com/feed.rss --name my-podcast

        inkwell add https://private.com/feed.rss --name private --auth
    """
    try:
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

            # Validate auth_type
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

        # Create feed config
        from pydantic import HttpUrl

        feed_config = FeedConfig(
            url=HttpUrl(url),
            auth=auth_config,
            category=category,
        )

        # Add feed
        manager.add_feed(name, feed_config)

        console.print(f"\n[green]✓[/green] Feed '[bold]{name}[/bold]' added successfully")
        if auth:
            console.print("[dim]  Credentials encrypted and stored securely[/dim]")

    except ValidationError as e:
        console.print(f"[red]✗[/red] {e}")
        if e.suggestion:
            console.print(f"[dim]  {e.suggestion}[/dim]")
        sys.exit(1)
    except ConfigError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


@app.command("list")
def list_feeds() -> None:
    """List all configured podcast feeds.

    Displays a table showing feed names, URLs, authentication status, and categories.
    """
    try:
        manager = ConfigManager()
        feeds = manager.list_feeds()

        if not feeds:
            console.print("[yellow]No feeds configured yet.[/yellow]")
            console.print("\nAdd a feed: [cyan]inkwell add <url> --name <name>[/cyan]")
            return

        # Create table
        table = Table(title="[bold]Configured Podcast Feeds[/bold]")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("URL", style="blue")
        table.add_column("Auth", justify="center", style="yellow")
        table.add_column("Category", style="green")

        # Add rows
        for name, feed in feeds.items():
            auth_status = "✓" if feed.auth.type != "none" else "—"
            category_display = feed.category or "—"
            url_display = truncate_url(str(feed.url), max_length=50)

            table.add_row(name, url_display, auth_status, category_display)

        console.print(table)
        console.print(f"\n[dim]Total: {len(feeds)} feed(s)[/dim]")

    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
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

        # Check if feed exists
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

        # Remove feed
        manager.remove_feed(name)
        console.print(f"[green]✓[/green] Feed '[bold]{name}[/bold]' removed")

    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


@app.command("episodes")
def episodes_command(
    name: str = typer.Argument(..., help="Feed name to list episodes from"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of episodes to show"),
) -> None:
    """List episodes from a configured feed.

    Examples:
        inkwell episodes my-podcast

        inkwell episodes my-podcast --limit 20
    """

    async def run_episodes() -> None:
        try:
            manager = ConfigManager()

            # Get feed config
            try:
                feed_config = manager.get_feed(name)
            except NotFoundError:
                console.print(f"[red]✗[/red] Feed '{name}' not found.")
                console.print("  Use [cyan]inkwell list[/cyan] to see configured feeds.")
                sys.exit(1)

            # Fetch and parse the RSS feed
            console.print(f"[bold]Fetching episodes from:[/bold] {name}\n")
            parser = RSSParser()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Parsing RSS feed...", total=None)
                feed = await parser.fetch_feed(str(feed_config.url), feed_config.auth)

            # Display episodes in a table
            table = Table(title=f"Episodes from {name}", show_lines=True)
            table.add_column("#", style="dim", width=4)
            table.add_column("Title", style="cyan", max_width=60)
            table.add_column("Date", style="green", width=12)
            table.add_column("Duration", style="yellow", width=10)

            for i, entry in enumerate(feed.entries[:limit], 1):
                try:
                    ep = parser.extract_episode_metadata(entry, name)
                    # Truncate title if too long
                    title = ep.title[:57] + "..." if len(ep.title) > 60 else ep.title
                    date = ep.published.strftime("%Y-%m-%d")
                    duration = ep.duration_formatted if ep.duration_seconds else "—"
                    table.add_row(str(i), title, date, duration)
                except Exception:
                    # Skip entries that fail to parse
                    pass

            console.print(table)
            shown = min(limit, len(feed.entries))
            total = len(feed.entries)
            console.print(f"\n[dim]Showing {shown} of {total} episodes[/dim]")
            console.print("\n[bold]To fetch an episode:[/bold]")
            console.print(f"  inkwell fetch {name} --latest")
            console.print(f'  inkwell fetch {name} --episode "keyword"')

        except InkwellError as e:
            console.print(f"[red]✗[/red] Error: {e}")
            sys.exit(1)

    asyncio.run(run_episodes())


@app.command("config")
def config_command(
    action: str = typer.Argument(..., help="Action: show, edit, or set <key> <value>"),
    key: str | None = typer.Argument(None, help="Config key (for 'set' action)"),
    value: str | None = typer.Argument(None, help="Config value (for 'set' action)"),
) -> None:
    """Manage Inkwell configuration.

    Actions:
        show: Display current configuration
        edit: Open config file in $EDITOR
        set:  Set a configuration value

    Examples:
        inkwell config show

        inkwell config edit

        inkwell config set log_level DEBUG
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
                    # Check if it came from env or config
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

            # Validate editor against whitelist
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

            # Handle nested keys (e.g., transcription.api_key)
            key_parts = key.split(".")

            if len(key_parts) == 1:
                # Top-level key
                if hasattr(config, key):
                    # Get the field type to do proper conversion
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
                    sys.exit(1)
            elif len(key_parts) == 2:
                # Nested key (e.g., transcription.api_key)
                parent_key, child_key = key_parts

                if not hasattr(config, parent_key):
                    console.print(f"[red]✗[/red] Unknown config section: {parent_key}")
                    console.print("\nAvailable sections: transcription, extraction, interview")
                    sys.exit(1)

                parent_obj = getattr(config, parent_key)

                if not hasattr(parent_obj, child_key):
                    console.print(
                        f"[red]✗[/red] Unknown key '{child_key}' in section '{parent_key}'"
                    )
                    console.print(f"\nAvailable keys in {parent_key}:")
                    for field_name in parent_obj.model_fields.keys():
                        console.print(f"  • {parent_key}.{field_name}")
                    sys.exit(1)

                # Get field type for conversion
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
                    "Use 'key' for top-level or 'section.key' for nested "
                    "(e.g., transcription.api_key)"
                )
                sys.exit(1)

        else:
            console.print(f"[red]✗[/red] Unknown action: {action}")
            console.print("Valid actions: show, edit, set")
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

    def confirm_cost(estimate: CostEstimate) -> bool:
        """Confirm Gemini transcription cost with user."""
        console.print(
            f"\n[yellow]⚠[/yellow] Gemini transcription will cost approximately "
            f"[bold]{estimate.formatted_cost}[/bold]"
        )
        console.print(f"[dim]File size: {estimate.file_size_mb:.1f} MB[/dim]")
        return typer.confirm("Proceed with transcription?")

    async def run_transcription() -> None:
        try:
            # Load config to get transcription model
            config_manager = ConfigManager()
            config = config_manager.load_config()

            # Initialize manager with cost confirmation and config model
            manager = TranscriptionManager(
                model_name=config.transcription_model, cost_confirmation_callback=confirm_cost
            )

            # Run transcription with progress indicator
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Transcribing...", total=None)

                result = await manager.transcribe(
                    url, use_cache=not force, skip_youtube=skip_youtube
                )

                progress.update(task, completed=True)

            # Handle result
            if not result.success:
                console.print(f"[red]✗[/red] Transcription failed: {result.error}")
                sys.exit(1)

            assert result.transcript is not None

            # Display metadata
            console.print("\n[green]✓[/green] Transcription complete")
            console.print(f"[dim]Source: {result.transcript.source}[/dim]")
            console.print(f"[dim]Language: {result.transcript.language}[/dim]")
            console.print(f"[dim]Duration: {result.duration_seconds:.1f}s[/dim]")

            if result.cost_usd > 0:
                console.print(f"[dim]Cost: ${result.cost_usd:.4f}[/dim]")

            if result.from_cache:
                console.print("[dim]✓ Retrieved from cache[/dim]")

            # Get transcript text
            transcript_text = result.transcript.full_text

            # Output
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(transcript_text)
                console.print(f"\n[cyan]→[/cyan] Saved to {output}")
            else:
                console.print("\n" + "=" * 80)
                console.print(transcript_text)
                console.print("=" * 80)

        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled by user[/yellow]")
            sys.exit(130)
        except Exception as e:
            console.print(f"[red]✗[/red] Error: {e}")
            sys.exit(1)

    # Run async function
    asyncio.run(run_transcription())


@app.command("cache")
def cache_command(
    action: str = typer.Argument(..., help="Action: stats, clear, clear-expired"),
) -> None:
    """Manage transcript cache.

    Actions:
        stats:         Show cache statistics
        clear:         Clear all cached transcripts
        clear-expired: Remove expired cache entries

    Examples:
        inkwell cache stats

        inkwell cache clear
    """
    try:
        manager = TranscriptionManager()

        if action == "stats":
            stats = manager.cache_stats()

            console.print("\n[bold]Transcript Cache Statistics[/bold]\n")

            table = Table(show_header=False, box=None)
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Total entries", str(stats["total"]))
            table.add_row("Valid", str(stats["valid"]))
            table.add_row("Expired", str(stats["expired"]))
            table.add_row("Size", f"{stats['size_bytes'] / 1024 / 1024:.2f} MB")
            table.add_row("Cache directory", stats["cache_dir"])

            console.print(table)

            if stats["sources"]:
                console.print("\n[bold]By Source:[/bold]")
                for source, count in stats["sources"].items():
                    console.print(f"  • {source}: {count}")

        elif action == "clear":
            confirm: bool = typer.confirm(
                "\nAre you sure you want to clear all cached transcripts?"
            )
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

            count = manager.clear_cache()
            console.print(f"[green]✓[/green] Cleared {count} cache entries")

        elif action == "clear-expired":
            count = manager.clear_expired_cache()
            console.print(f"[green]✓[/green] Removed {count} expired cache entries")

        else:
            console.print(f"[red]✗[/red] Unknown action: {action}")
            console.print("Valid actions: stats, clear, clear-expired")
            sys.exit(1)

    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


@app.command("fetch")
def fetch_command(
    url_or_feed: str = typer.Argument(..., help="Episode URL or configured feed name"),
    output_dir: Path | None = typer.Option(
        None, "--output", "-o", help="Output directory (default: ~/inkwell-notes)"
    ),
    latest: bool = typer.Option(False, "--latest", "-l", help="Fetch the latest episode from feed"),
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
    dry_run: bool = typer.Option(False, "--dry-run", help="Show cost estimate without extracting"),
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
    """

    async def run_fetch() -> None:
        try:
            # Load configuration
            manager = ConfigManager()
            config = manager.load_config()

            # Resolve feed name to episode URL if needed
            url = url_or_feed
            resolved_category = category
            # Auth credentials for private feeds (passed to audio downloader)
            auth_username: str | None = None
            auth_password: str | None = None
            # Episode from RSS feed (if applicable)
            ep: Episode | None = None

            # Check if url_or_feed is a configured feed name (not a URL)
            is_url = url_or_feed.startswith(("http://", "https://", "www."))

            if not is_url:
                # Treat as feed name - look up in configured feeds
                try:
                    feed_config = manager.get_feed(url_or_feed)
                except NotFoundError:
                    # Not a configured feed, maybe it's still a URL without scheme
                    if "." in url_or_feed and "/" in url_or_feed:
                        # Looks like a URL, assume https
                        url = f"https://{url_or_feed}"
                    else:
                        console.print(f"[red]✗[/red] Feed '{url_or_feed}' not found.")
                        console.print("  Use [cyan]inkwell list[/cyan] to see configured feeds.")
                        console.print("  Or provide a direct episode URL.")
                        sys.exit(1)
                else:
                    # Found the feed - need --latest or --episode flag
                    if not latest and not episode:
                        console.print(
                            f"[red]✗[/red] Feed '{url_or_feed}' requires "
                            "--latest or --episode flag."
                        )
                        console.print("\nUsage:")
                        console.print(f"  inkwell fetch {url_or_feed} --latest")
                        console.print(f'  inkwell fetch {url_or_feed} --episode "keyword"')
                        sys.exit(1)

                    # Fetch and parse the RSS feed
                    console.print(f"[bold]Fetching feed:[/bold] {url_or_feed}")
                    parser = RSSParser()

                    with console.status("[bold]Parsing RSS feed...[/bold]"):
                        feed = await parser.fetch_feed(str(feed_config.url), feed_config.auth)

                    # Get the episode(s)
                    if latest:
                        selected_episodes = [parser.get_latest_episode(feed, url_or_feed)]
                        console.print(
                            f"[green]✓[/green] Latest episode: {selected_episodes[0].title}"
                        )
                    else:
                        selected_episodes = parser.parse_and_fetch_episodes(
                            feed, episode, url_or_feed
                        )
                        if len(selected_episodes) == 1:
                            console.print(
                                f"[green]✓[/green] Found episode: {selected_episodes[0].title}"
                            )
                        else:
                            console.print(
                                f"[green]✓[/green] Found {len(selected_episodes)} episodes"
                            )
                            console.print(
                                f"[yellow]⚠[/yellow] Batch processing not yet supported. "
                                f"Found {len(selected_episodes)} episodes, processing first one only."
                            )
                            console.print(
                                "[dim]  Tip: Use a single position or unique keyword to select one episode.[/dim]"
                            )

                    # For single episode, show details
                    if len(selected_episodes) == 1:
                        ep = selected_episodes[0]
                        console.print(f"  Published: {ep.published.strftime('%Y-%m-%d')}")
                        if ep.duration_seconds:
                            console.print(f"  Duration: {ep.duration_formatted}")
                        console.print()

                    # Use the first episode for initial setup (batch will iterate)
                    ep = selected_episodes[0]

                    # Use the episode's audio URL
                    url = str(ep.url)

                    # Use feed's category if not overridden
                    if not resolved_category and feed_config.category:
                        resolved_category = feed_config.category

                    # Extract auth credentials for audio download (basic auth only)
                    if feed_config.auth and feed_config.auth.type == "basic":
                        auth_username = feed_config.auth.username
                        auth_password = feed_config.auth.password

            # Determine if interview will be included for progress display
            will_interview = interview or config.interview.auto_start

            # Extract episode metadata if available from feed parsing
            episode_title: str | None = None
            podcast_name: str | None = None
            if ep is not None:
                episode_title = ep.title
                podcast_name = ep.podcast_name or url_or_feed

            # Compute effective output directory
            effective_output_dir = output_dir or config.default_output_dir

            # Early check: if we have episode metadata, check if directory already exists
            if episode_title and podcast_name and ep is not None and not overwrite:
                expected_dir = _compute_episode_dir_path(
                    output_dir=effective_output_dir,
                    podcast_name=podcast_name,
                    episode_title=episode_title,
                    published_date=ep.published.strftime("%Y-%m-%d"),
                )
                if expected_dir.exists():
                    console.print(
                        f"\n[yellow]⚠[/yellow]  Episode already processed: "
                        f"[cyan]{expected_dir.name}[/cyan]"
                    )
                    console.print(f"   [dim]{expected_dir}[/dim]\n")
                    console.print("   Options:")
                    console.print("   • Use [cyan]--overwrite[/cyan] to re-process")
                    console.print(
                        f"   • View existing notes: [cyan]ls {expected_dir}[/cyan]"
                    )
                    sys.exit(0)  # Exit cleanly, not an error

            # Show output directory upfront
            console.print("[bold cyan]Inkwell Extraction Pipeline[/bold cyan]")
            console.print(f"[dim]Output: {effective_output_dir}[/dim]\n")

            # Create pipeline options from CLI arguments
            options = PipelineOptions(
                url=url,
                category=resolved_category,
                templates=[t.strip() for t in templates.split(",")] if templates else None,
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
                podcast_name=podcast_name,
            )

            # Create orchestrator
            orchestrator = PipelineOrchestrator(config)

            # Use PipelineProgress for Docker-style multi-stage display
            # with auto-updating elapsed time
            pipeline_progress = PipelineProgress(
                console=console,
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

            # Track results for summary display after progress
            completion_details: dict[str, object] = {}

            # Progress callback for pipeline stages
            from typing import Any

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
                    pipeline_progress.complete_stage("write", f"{step_data['file_count']} files")
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
            # Suppress INFO logs during progress display to avoid cluttering the UI
            inkwell_logger = logging.getLogger("inkwell")
            original_level = inkwell_logger.level
            inkwell_logger.setLevel(logging.WARNING)

            try:
                with pipeline_progress:
                    result = await orchestrator.process_episode(
                        options=options,
                        progress_callback=handle_progress,
                    )
            finally:
                # Restore original log level
                inkwell_logger.setLevel(original_level)

            # Display summary
            console.print("\n[bold green]✓ Complete![/bold green]")

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
                table.add_row("Extraction cost:", f"${result.extraction_cost_usd:.4f}")
                table.add_row("Interview cost:", f"${result.interview_cost_usd:.4f}")
                table.add_row("Total cost:", f"${result.total_cost_usd:.4f}")
                table.add_row("Interview:", "✓ Completed")
            else:
                table.add_row("Total cost:", f"${result.extraction_cost_usd:.4f}")

            table.add_row("Output:", output_display)

            console.print(table)

        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled by user[/yellow]")
            sys.exit(130)
        except FileExistsError as e:
            console.print(f"\n[red]✗[/red] {e}")
            sys.exit(1)
        except InkwellError as e:
            console.print(f"\n[red]✗[/red] Error: {e}")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[red]✗[/red] Unexpected error: {e}")
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            sys.exit(1)

    # Run async function
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

        # Handle clear
        if clear:
            if typer.confirm("Are you sure you want to clear all cost history?"):
                tracker.clear()
                console.print("[green]✓[/green] Cost history cleared")
            else:
                console.print("Cancelled")
            return

        # Handle recent
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
                cost_str = f"${usage.cost_usd:.4f}"

                table.add_row(
                    date_str,
                    usage.provider,
                    usage.operation,
                    episode_str,
                    tokens_str,
                    cost_str,
                )

            console.print(table)
            console.print(f"\n[bold]Total:[/bold] ${sum(u.cost_usd for u in recent_usage):.4f}")
            return

        # Calculate since date if days provided
        since = None
        if days:
            since = now_utc() - timedelta(days=days)

        # Get summary with filters
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
        stats_table.add_row(
            "Total Cost:", f"[bold yellow]${summary.total_cost_usd:.4f}[/bold yellow]"
        )

        console.print(Panel(stats_table, title="Overall", border_style="blue"))

        # Breakdown by provider
        if summary.costs_by_provider:
            console.print("\n[bold]By Provider:[/bold]")
            provider_table = Table(show_header=False, box=None, padding=(0, 2))
            provider_table.add_column("Provider", style="magenta")
            provider_table.add_column("Cost", style="yellow", justify="right")

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
            op_table.add_column("Cost", style="yellow", justify="right")

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
            episode_table.add_column("Cost", style="yellow", justify="right")

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
