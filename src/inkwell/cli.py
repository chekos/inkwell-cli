"""CLI entry point for Inkwell."""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from inkwell.config.manager import ConfigManager
from inkwell.config.schema import AuthConfig, FeedConfig
from inkwell.extraction import ExtractionEngine
from inkwell.extraction.template_selector import TemplateSelector
from inkwell.extraction.templates import TemplateLoader
from inkwell.feeds.models import Episode
from inkwell.interview import InterviewManager
from inkwell.interview.models import InterviewGuidelines
from inkwell.output import EpisodeMetadata, OutputManager
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


@app.command("fetch")
def fetch_command(
    url: str = typer.Argument(..., help="Episode URL to process"),
    output_dir: Path | None = typer.Option(
        None, "--output", "-o", help="Output directory (default: ~/inkwell-notes)"
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
    skip_cache: bool = typer.Option(
        False, "--skip-cache", help="Skip extraction cache"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show cost estimate without extracting"
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Overwrite existing episode directory"
    ),
    interview: bool = typer.Option(
        False, "--interview", help="Conduct interactive interview after extraction"
    ),
    interview_template: str | None = typer.Option(
        None, "--interview-template", help="Interview template: reflective, analytical, creative (default: from config)"
    ),
    interview_format: str | None = typer.Option(
        None, "--interview-format", help="Output format: structured, narrative, qa (default: from config)"
    ),
    max_questions: int | None = typer.Option(
        None, "--max-questions", help="Maximum number of interview questions (default: from config)"
    ),
    no_resume: bool = typer.Option(
        False, "--no-resume", help="Don't resume previous interview session"
    ),
) -> None:
    """Fetch and process a podcast episode.

    Complete pipeline: transcribe → extract → generate markdown → write files → [optional interview]

    Examples:
        inkwell fetch https://youtube.com/watch?v=xyz

        inkwell fetch https://example.com/ep1.mp3 --templates summary,quotes

        inkwell fetch https://... --category tech --provider claude

        inkwell fetch https://... --dry-run  # Cost estimate only

        inkwell fetch https://... --interview  # With interactive interview

        inkwell fetch https://... --interview --interview-template analytical
    """

    async def run_fetch() -> None:
        try:
            config = ConfigManager().load_config()
            output_path = output_dir or config.default_output_dir

            # Determine total steps
            will_interview = interview or config.interview.auto_start
            total_steps = 5 if will_interview else 4

            console.print("[bold cyan]Inkwell Extraction Pipeline[/bold cyan]\n")

            # Step 1: Transcribe
            console.print(f"[bold]Step 1/{total_steps}:[/bold] Transcribing episode...")

            transcription_manager = TranscriptionManager()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Transcribing...", total=None)

                result = await transcription_manager.transcribe(
                    url, use_cache=True, skip_youtube=False
                )

                progress.update(task, completed=True)

            if not result.success:
                console.print(f"[red]✗[/red] Transcription failed: {result.error}")
                sys.exit(1)

            assert result.transcript is not None

            console.print(f"[green]✓[/green] Transcribed ({result.transcript.source})")
            console.print(f"  Duration: {result.duration_seconds:.1f}s")
            console.print(f"  Words: ~{len(result.transcript.full_text.split())}")

            # Step 2: Select templates
            console.print(f"\n[bold]Step 2/{total_steps}:[/bold] Selecting templates...")

            loader = TemplateLoader()
            selector = TemplateSelector(loader=loader)

            # Parse custom templates if provided
            custom_template_list = None
            if templates:
                custom_template_list = [t.strip() for t in templates.split(",")]

            # Create episode object for template selection
            episode = Episode(
                title=f"Episode from {url}",
                url=url,  # type: ignore
                published=datetime.now(),
                description="",
                podcast_name="Unknown Podcast",  # Would come from RSS in real implementation
            )

            # Create episode metadata for output
            episode_metadata = EpisodeMetadata(
                podcast_name=episode.podcast_name,
                episode_title=episode.title,
                episode_url=url,
                transcription_source=result.transcript.source,
            )

            # Select templates
            selected_templates = selector.select_templates(
                episode=episode,
                category=category,
                custom_templates=custom_template_list,
                transcript=result.transcript.full_text,
            )

            console.print(f"[green]✓[/green] Selected {len(selected_templates)} templates:")
            for tmpl in selected_templates:
                console.print(f"  • {tmpl.name} (priority: {tmpl.priority})")

            # Step 3: Extract
            console.print(f"\n[bold]Step 3/{total_steps}:[/bold] Extracting content...")

            # Initialize extraction engine
            engine = ExtractionEngine(
                default_provider=provider or "gemini"
            )

            # Estimate cost
            estimated_cost = engine.estimate_total_cost(
                templates=selected_templates,
                transcript=result.transcript.full_text,
            )

            console.print(f"  Estimated cost: [yellow]${estimated_cost:.4f}[/yellow]")

            if dry_run:
                console.print("\n[yellow]Dry run mode - stopping here[/yellow]")
                console.print(f"Total estimated cost: ${estimated_cost:.4f}")
                return

            # Extract with progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Extracting content...", total=None)

                extraction_results = await engine.extract_all(
                    templates=selected_templates,
                    transcript=result.transcript.full_text,
                    metadata=episode_metadata.model_dump(),
                    use_cache=not skip_cache,
                )

                progress.update(task, completed=True)

            # Report extraction results
            cached_count = sum(1 for r in extraction_results if r.provider == "cache")
            console.print(f"[green]✓[/green] Extracted {len(extraction_results)} templates")
            if cached_count > 0:
                console.print(f"  • {cached_count} from cache (saved ${engine.get_total_cost():.4f})")
            console.print(f"  • Total cost: [yellow]${engine.get_total_cost():.4f}[/yellow]")

            # Step 4: Write output
            console.print(f"\n[bold]Step 4/{total_steps}:[/bold] Writing markdown files...")

            output_manager = OutputManager(output_dir=output_path)

            episode_output = output_manager.write_episode(
                episode_metadata=episode_metadata,
                extraction_results=extraction_results,
                overwrite=overwrite,
            )

            console.print(f"[green]✓[/green] Wrote {len(episode_output.output_files)} files")
            console.print(f"  Directory: [cyan]{episode_output.directory}[/cyan]")

            # Step 5: Interview (optional)
            interview_cost = 0.0
            interview_conducted = False

            if interview or config.interview.auto_start:
                console.print("\n[bold]Step 5/5:[/bold] Conducting interview...")

                try:
                    # Get interview configuration
                    template_name = interview_template or config.interview.default_template
                    format_style = interview_format or config.interview.format_style
                    questions = max_questions or config.interview.question_count

                    # Create guidelines from config
                    guidelines = None
                    if config.interview.guidelines:
                        guidelines = InterviewGuidelines(text=config.interview.guidelines)

                    # Check for Anthropic API key
                    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
                    if not anthropic_key:
                        console.print("[yellow]⚠[/yellow] ANTHROPIC_API_KEY not set. Skipping interview.")
                        console.print("[dim]  Set your key: export ANTHROPIC_API_KEY=your-key[/dim]")
                    else:
                        # Initialize interview manager
                        interview_manager = InterviewManager(
                            api_key=anthropic_key,
                            model=config.interview.model
                        )

                        # Conduct interview
                        interview_result = await interview_manager.conduct_interview(
                            episode_url=url,
                            episode_title=episode_metadata.episode_title,
                            podcast_name=episode_metadata.podcast_name,
                            output_dir=episode_output.directory,
                            template_name=template_name,
                            max_questions=questions,
                            guidelines=guidelines,
                            format_style=format_style,
                            resume_session_id=None if no_resume else None,  # TODO: Session discovery
                        )

                        # Save interview output
                        interview_path = episode_output.directory / "my-notes.md"
                        interview_path.write_text(interview_result.transcript)

                        console.print(f"[green]✓[/green] Interview complete")
                        console.print(f"  Questions: {len(interview_result.exchanges)}")
                        console.print(f"  Saved to: my-notes.md")

                        interview_cost = interview_result.total_cost
                        interview_conducted = True

                        # Update metadata with interview info
                        metadata_path = episode_output.directory / ".metadata.yaml"
                        if metadata_path.exists():
                            metadata = yaml.safe_load(metadata_path.read_text())
                            metadata["interview_conducted"] = True
                            metadata["interview_template"] = template_name
                            metadata["interview_format"] = format_style
                            metadata["interview_questions"] = len(interview_result.exchanges)
                            metadata["interview_cost_usd"] = interview_cost
                            metadata_path.write_text(yaml.safe_dump(metadata, default_flow_style=False))

                except KeyboardInterrupt:
                    console.print("\n[yellow]Interview cancelled by user[/yellow]")
                    # Continue to summary even if interview cancelled
                except Exception as e:
                    console.print(f"[red]✗[/red] Interview failed: {e}")
                    console.print("[dim]  Extraction completed successfully, continuing...[/dim]")

            # Summary
            console.print("\n[bold green]✓ Complete![/bold green]")

            # Format output directory path for display
            try:
                # Try to show path relative to current directory
                output_display = str(episode_output.directory.relative_to(Path.cwd()))
            except ValueError:
                # If not under cwd, show absolute path
                output_display = str(episode_output.directory)

            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("Key", style="dim")
            table.add_column("Value", style="white")

            table.add_row("Episode:", episode_metadata.episode_title)
            table.add_row("Templates:", f"{len(extraction_results)}")

            if interview_conducted:
                total_cost = engine.get_total_cost() + interview_cost
                table.add_row("Extraction cost:", f"${engine.get_total_cost():.4f}")
                table.add_row("Interview cost:", f"${interview_cost:.4f}")
                table.add_row("Total cost:", f"${total_cost:.4f}")
                table.add_row("Interview:", "✓ Completed")
            else:
                table.add_row("Total cost:", f"${engine.get_total_cost():.4f}")

            table.add_row("Output:", output_display)

            console.print(table)

        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled by user[/yellow]")
            sys.exit(130)
        except FileExistsError as e:
            console.print(f"\n[red]✗[/red] {e}")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[red]✗[/red] Error: {e}")
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
    episode: str | None = typer.Option(
        None, "--episode", "-e", help="Filter by episode title"
    ),
    days: int | None = typer.Option(
        None, "--days", "-d", help="Show costs from last N days"
    ),
    recent: int | None = typer.Option(
        None, "--recent", "-r", help="Show N most recent operations"
    ),
    clear: bool = typer.Option(
        False, "--clear", help="Clear all cost history"
    ),
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
    from datetime import timedelta

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
            since = datetime.utcnow() - timedelta(days=days)

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
        stats_table.add_row("Total Cost:", f"[bold yellow]${summary.total_cost_usd:.4f}[/bold yellow]")

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
