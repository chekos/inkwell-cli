"""CLI commands for listing resources.

This module provides the `inkwell list` subcommand group for
listing feeds, templates, and episodes.
"""

import asyncio
import json
import logging
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from inkwell.config.manager import ConfigManager
from inkwell.extraction.templates import TemplateLoader
from inkwell.feeds.parser import RSSParser
from inkwell.utils.display import truncate_url
from inkwell.utils.errors import InkwellError, NotFoundError

logger = logging.getLogger(__name__)

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
def list_feeds(
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
) -> None:
    """List all configured podcast feeds.

    Displays a table showing feed names, URLs, authentication status, and categories.
    """
    _list_feeds_impl(json_output=json_output)


@app.command("templates")
def list_templates(
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
) -> None:
    """List available extraction templates.

    Shows all built-in and user-defined templates with their descriptions.
    """
    try:
        loader = TemplateLoader()
        names = loader.list_templates()

        if json_output:
            templates_data = []
            for name in names:
                try:
                    info = loader.get_template_info(name)
                    description = info.get("description", "")
                    templates_data.append({"name": name, "description": description})
                except Exception as e:
                    logger.debug(f"Failed to load template '{name}': {e}")
                    templates_data.append({"name": name, "description": "failed to load"})
            result = {"templates": templates_data, "total": len(names)}
            print(json.dumps(result, indent=2))
            return

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
            except Exception as e:
                logger.debug(f"Failed to load template '{name}': {e}")
                table.add_row(name, "[dim]failed to load[/dim]")

        console.print(table)
        console.print(f"\n[dim]Total: {len(names)} template(s)[/dim]")

    except InkwellError as e:
        console.print(f"[red]x[/red] Error: {e}")
        sys.exit(1)


@app.command("episodes")
def list_episodes(
    name: Annotated[str, typer.Argument(help="Feed name to list episodes from")],
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Number of episodes to show (1-1000)", min=1, max=1000),
    ] = 10,
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
) -> None:
    """List episodes from a configured feed.

    Examples:
        inkwell list episodes my-podcast

        inkwell list episodes my-podcast --limit 20
    """

    async def run_episodes() -> None:
        nonlocal json_output
        try:
            manager = ConfigManager()

            # Get feed config
            try:
                feed_config = manager.get_feed(name)
            except NotFoundError:
                if json_output:
                    print(json.dumps({"error": f"Feed '{name}' not found"}, indent=2))
                else:
                    console.print(f"[red]x[/red] Feed '{escape(name)}' not found.")
                    console.print("  Use [cyan]inkwell list feeds[/cyan] to see configured feeds.")
                sys.exit(1)

            # Fetch and parse the RSS feed
            if not json_output:
                console.print(f"[bold]Fetching episodes from:[/bold] {escape(name)}\n")
            parser = RSSParser()

            if json_output:
                feed = await parser.fetch_feed(str(feed_config.url), feed_config.auth)
            else:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    progress.add_task("Parsing RSS feed...", total=None)
                    feed = await parser.fetch_feed(str(feed_config.url), feed_config.auth)

            if json_output:
                episodes_data = []
                for entry in feed.entries[:limit]:
                    try:
                        ep = parser.extract_episode_metadata(entry, name)
                        episodes_data.append(
                            {
                                "title": ep.title,
                                "date": ep.published.strftime("%Y-%m-%d"),
                                "duration": ep.duration_formatted if ep.duration_seconds else None,
                                "url": ep.audio_url,
                            }
                        )
                    except Exception as e:
                        logger.debug(f"Failed to parse entry: {e}")
                result = {
                    "feed": name,
                    "episodes": episodes_data,
                    "total": len(feed.entries),
                    "showing": min(limit, len(feed.entries)),
                }
                print(json.dumps(result, indent=2))
                return

            # Display episodes in a table
            table = Table(title=f"Episodes from {escape(name)}", show_lines=True)
            table.add_column("#", style="dim", width=4)
            table.add_column("Title", style="cyan", max_width=60)
            table.add_column("Date", style="green", width=12)
            table.add_column("Duration", style="yellow", width=10)

            skipped = 0
            for i, entry in enumerate(feed.entries[:limit], 1):
                try:
                    ep = parser.extract_episode_metadata(entry, name)
                    # Truncate title if too long
                    title = ep.title[:57] + "..." if len(ep.title) > 60 else ep.title
                    date = ep.published.strftime("%Y-%m-%d")
                    duration = ep.duration_formatted if ep.duration_seconds else "-"
                    table.add_row(str(i), title, date, duration)
                except Exception as e:
                    logger.debug(f"Failed to parse entry {i}: {e}")
                    skipped += 1

            console.print(table)
            if skipped > 0:
                console.print(f"[dim]({skipped} entries could not be parsed)[/dim]")
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


def _list_feeds_impl(json_output: bool = False) -> None:
    """Display configured feeds."""
    try:
        manager = ConfigManager()
        feeds = manager.list_feeds()

        if json_output:
            feeds_data = []
            for name, feed in feeds.items():
                auth_type = feed.auth.type if feed.auth.type != "none" else "none"
                feeds_data.append(
                    {
                        "name": name,
                        "url": str(feed.url),
                        "auth": auth_type,
                        "category": feed.category or "",
                    }
                )
            result = {"feeds": feeds_data, "total": len(feeds)}
            print(json.dumps(result, indent=2))
            return

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
