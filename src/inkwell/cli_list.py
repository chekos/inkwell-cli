"""CLI commands for listing resources.

This module provides the `inkwell list` subcommand group for
listing feeds, templates, and episodes.
"""

import asyncio
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from inkwell.config.manager import ConfigManager
from inkwell.extraction.templates import TemplateLoader
from inkwell.feeds.parser import RSSParser
from inkwell.utils.display import truncate_url
from inkwell.utils.errors import InkwellError, NotFoundError

app = typer.Typer(
    name="list",
    help="List Inkwell resources (feeds, templates, episodes)",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def list_default(ctx: typer.Context) -> None:
    """List resources. Defaults to feeds if no subcommand given."""
    if ctx.invoked_subcommand is None:
        _list_feeds_impl()


@app.command("feeds")
def list_feeds() -> None:
    """List all configured podcast feeds.

    Displays a table showing feed names, URLs, authentication status, and categories.
    """
    _list_feeds_impl()


@app.command("templates")
def list_templates() -> None:
    """List available extraction templates.

    Shows all built-in and user-defined templates with their descriptions.
    """
    try:
        loader = TemplateLoader()
        names = loader.list_templates()

        if not names:
            console.print("[yellow]No templates found.[/yellow]")
            return

        table = Table(title="[bold]Extraction Templates[/bold]")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Description")

        for name in names:
            try:
                info = loader.get_template_info(name)
                table.add_row(name, info.get("description", "-"))
            except Exception:
                table.add_row(name, "[dim]failed to load[/dim]")

        console.print(table)
        console.print(f"\n[dim]Total: {len(names)} template(s)[/dim]")

    except InkwellError as e:
        console.print(f"[red]x[/red] Error: {e}")
        sys.exit(1)


@app.command("episodes")
def list_episodes(
    name: Annotated[str, typer.Argument(help="Feed name to list episodes from")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of episodes to show")] = 10,
) -> None:
    """List episodes from a configured feed.

    Examples:
        inkwell list episodes my-podcast

        inkwell list episodes my-podcast --limit 20
    """

    async def run_episodes() -> None:
        try:
            manager = ConfigManager()

            # Get feed config
            try:
                feed_config = manager.get_feed(name)
            except NotFoundError:
                console.print(f"[red]x[/red] Feed '{name}' not found.")
                console.print("  Use [cyan]inkwell list feeds[/cyan] to see configured feeds.")
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
                    duration = ep.duration_formatted if ep.duration_seconds else "-"
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
            console.print(f"[red]x[/red] Error: {e}")
            sys.exit(1)

    asyncio.run(run_episodes())


def _list_feeds_impl() -> None:
    """Display configured feeds."""
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
            auth_status = "Yes" if feed.auth.type != "none" else "-"
            category_display = feed.category or "-"
            url_display = truncate_url(str(feed.url), max_length=50)

            table.add_row(name, url_display, auth_status, category_display)

        console.print(table)
        console.print(f"\n[dim]Total: {len(feeds)} feed(s)[/dim]")

    except InkwellError as e:
        console.print(f"[red]x[/red] Error: {e}")
        sys.exit(1)
