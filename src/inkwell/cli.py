"""CLI entry point for Inkwell."""

import asyncio
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from inkwell.config.manager import ConfigManager
from inkwell.config.schema import AuthConfig, FeedConfig
from inkwell.transcription import CostEstimate, TranscriptionManager
from inkwell.utils.display import truncate_url
from inkwell.utils.errors import (
    DuplicateFeedError,
    FeedNotFoundError,
    InkwellError,
    InvalidConfigError,
)

app = typer.Typer(
    name="inkwell",
    help="Transform podcast episodes into structured markdown notes",
    no_args_is_help=True,
)
console = Console()


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
            auth_type = typer.prompt(
                "Auth type",
                type=typer.Choice(["basic", "bearer"]),
                default="basic",
            )

            if auth_type == "basic":
                username = typer.prompt("Username")
                password = typer.prompt("Password", hide_input=True)
                auth_config = AuthConfig(
                    type="basic", username=username, password=password
                )
            elif auth_type == "bearer":
                token = typer.prompt("Bearer token", hide_input=True)
                auth_config = AuthConfig(type="bearer", token=token)

        # Create feed config
        feed_config = FeedConfig(
            url=url,  # type: ignore
            auth=auth_config,
            category=category,
        )

        # Add feed
        manager.add_feed(name, feed_config)

        console.print(
            f"\n[green]✓[/green] Feed '[bold]{name}[/bold]' added successfully"
        )
        if auth:
            console.print(
                "[dim]  Credentials encrypted and stored securely[/dim]"
            )

    except DuplicateFeedError as e:
        console.print(f"[red]✗[/red] {e}")
        console.print(
            f"[dim]  Use 'inkwell remove {name}' first, or choose a different name[/dim]"
        )
        sys.exit(1)
    except InvalidConfigError as e:
        console.print(f"[red]✗[/red] Invalid URL: {e}")
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
            console.print(
                "[yellow]No feeds configured yet.[/yellow]"
            )
            console.print(
                "\nAdd a feed: [cyan]inkwell add <url> --name <name>[/cyan]"
            )
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
        console.print(
            f"\n[dim]Total: {len(feeds)} feed(s)[/dim]"
        )

    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


@app.command("remove")
def remove_feed(
    name: str = typer.Argument(..., help="Feed name to remove"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Skip confirmation prompt"
    ),
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
        except FeedNotFoundError:
            console.print(
                f"[red]✗[/red] Feed '[bold]{name}[/bold]' not found"
            )
            console.print("\nAvailable feeds:")
            feeds = manager.list_feeds()
            for feed_name in feeds.keys():
                console.print(f"  • {feed_name}")
            sys.exit(1)

        # Confirm removal
        if not force:
            console.print(f"\nFeed: [bold]{name}[/bold]")
            console.print(f"URL:  [dim]{feed.url}[/dim]")
            confirm = typer.confirm("\nAre you sure you want to remove this feed?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        # Remove feed
        manager.remove_feed(name)
        console.print(
            f"[green]✓[/green] Feed '[bold]{name}[/bold]' removed"
        )

    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


@app.command("config")
def config_command(
    action: str = typer.Argument(
        ..., help="Action: show, edit, or set <key> <value>"
    ),
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
            table.add_row("YouTube check", "✓" if config.youtube_check else "✗")
            table.add_row("Transcription model", config.transcription_model)
            table.add_row("Interview model", config.interview_model)

            console.print(table)

        elif action == "edit":
            import os
            import subprocess

            editor = os.environ.get("EDITOR", "nano")
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
                console.print(
                    "[red]✗[/red] Usage: inkwell config set <key> <value>"
                )
                sys.exit(1)

            config = manager.load_config()

            # Handle setting config values
            if hasattr(config, key):
                # Get the field type to do proper conversion
                field_type = type(getattr(config, key))

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
                sys.exit(1)

        else:
            console.print(
                f"[red]✗[/red] Unknown action: {action}"
            )
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
            # Initialize manager with cost confirmation
            manager = TranscriptionManager(cost_confirmation_callback=confirm_cost)

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
            table.add_row(
                "Size", f"{stats['size_bytes'] / 1024 / 1024:.2f} MB"
            )
            table.add_row("Cache directory", stats["cache_dir"])

            console.print(table)

            if stats["sources"]:
                console.print("\n[bold]By Source:[/bold]")
                for source, count in stats["sources"].items():
                    console.print(f"  • {source}: {count}")

        elif action == "clear":
            confirm = typer.confirm("\nAre you sure you want to clear all cached transcripts?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

            count = manager.clear_cache()
            console.print(f"[green]✓[/green] Cleared {count} cache entries")

        elif action == "clear-expired":
            count = manager.clear_expired_cache()
            console.print(
                f"[green]✓[/green] Removed {count} expired cache entries"
            )

        else:
            console.print(f"[red]✗[/red] Unknown action: {action}")
            console.print("Valid actions: stats, clear, clear-expired")
            sys.exit(1)

    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    app()
