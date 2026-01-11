"""CLI commands for listing resources.

This module provides the `inkwell list` subcommand group for
listing feeds, templates, and episodes.
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from inkwell.config.manager import ConfigManager
from inkwell.config.schema import FeedConfig
from inkwell.extraction.templates import TemplateLoader
from inkwell.feeds.models import Episode
from inkwell.feeds.parser import RSSParser
from inkwell.utils.display import truncate_text, truncate_url
from inkwell.utils.errors import InkwellError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

# Maximum concurrent feed fetches to prevent connection exhaustion
MAX_CONCURRENT_FEEDS = 10

app = typer.Typer(
    name="list",
    help="List Inkwell resources (feeds, templates, episodes)",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def list_default(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
) -> None:
    """Show latest episode from each feed. Use subcommands for other resources."""
    if ctx.invoked_subcommand is None:
        _list_latest_impl(json_output=json_output)


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
        console.print(f"[red]✗[/red] Error: {e}")
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
        try:
            manager = ConfigManager()

            # Get feed config
            try:
                feed_config = manager.get_feed(name)
            except NotFoundError:
                if json_output:
                    print(json.dumps({"error": f"Feed '{name}' not found"}, indent=2))
                else:
                    console.print(f"[red]✗[/red] Feed '{escape(name)}' not found.")
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
                                "url": str(ep.url),
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
                    title = truncate_text(ep.title, 60)
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
            console.print(f"  inkwell fetch {escape(name)} --latest")
            console.print(f'  inkwell fetch {escape(name)} --episode "keyword"')

        except InkwellError as e:
            console.print(f"[red]✗[/red] Error: {e}")
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
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)


@dataclass
class LatestEpisodeResult:
    """Result of fetching latest episode from a feed."""

    feed_name: str
    success: bool
    episode: Episode | None = None
    error: str | None = None


async def _fetch_latest_for_feed(
    parser: RSSParser,
    name: str,
    feed_config: FeedConfig,
) -> LatestEpisodeResult:
    """Fetch latest episode from a single feed."""
    try:
        feed = await parser.fetch_feed(str(feed_config.url), feed_config.auth)
        episode = parser.get_latest_episode(feed, name)
        return LatestEpisodeResult(
            feed_name=name,
            success=True,
            episode=episode,
        )
    except ValidationError as e:
        # Empty feed - get_latest_episode raises ValidationError
        logger.debug(f"Feed '{name}' has no episodes: {e}")
        return LatestEpisodeResult(
            feed_name=name,
            success=True,
            error="No episodes yet",
        )
    except Exception as e:
        logger.debug(f"Failed to fetch latest from '{name}': {e}")
        return LatestEpisodeResult(
            feed_name=name,
            success=False,
            error=str(e),
        )


def _list_latest_impl(json_output: bool = False) -> None:
    """Fetch and display latest episode from each configured feed."""

    async def run_latest() -> None:
        try:
            manager = ConfigManager()
            feeds = manager.list_feeds()

            if not feeds:
                if json_output:
                    print(
                        json.dumps(
                            {"latest_episodes": [], "total_feeds": 0, "successful": 0, "failed": 0}
                        )
                    )
                else:
                    console.print("[yellow]No feeds configured yet.[/yellow]")
                    console.print("\nAdd a feed: [cyan]inkwell add <url> --name <name>[/cyan]")
                return

            parser = RSSParser()
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)

            async def fetch_with_limit(name: str, config: FeedConfig) -> LatestEpisodeResult:
                async with semaphore:
                    return await _fetch_latest_for_feed(parser, name, config)

            tasks = [fetch_with_limit(name, config) for name, config in feeds.items()]

            # Fetch all feeds in parallel (with concurrency limit)
            if json_output:
                results = await asyncio.gather(*tasks)
            else:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    progress.add_task(f"Fetching latest from {len(feeds)} feeds...", total=None)
                    results = await asyncio.gather(*tasks)

            # Sort by feed name
            results = sorted(results, key=lambda r: r.feed_name.lower())

            if json_output:
                _output_latest_json(results)
            else:
                _output_latest_table(results)

            # Exit 1 if all feeds failed
            if results and all(not r.success for r in results):
                sys.exit(1)

        except InkwellError as e:
            console.print(f"[red]✗[/red] Error: {e}")
            sys.exit(1)

    asyncio.run(run_latest())


@app.command("latest")
def list_latest(
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
) -> None:
    """Show the latest episode from each configured feed.

    Fetches all configured feeds in parallel and displays the most recent
    episode from each. Failed feeds are shown with error messages.

    Examples:
        inkwell list latest
        inkwell list latest --json
    """
    _list_latest_impl(json_output=json_output)


def _output_latest_table(results: list[LatestEpisodeResult]) -> None:
    """Display latest episodes in a table."""
    table = Table(title="Latest Episodes (All Feeds)")
    table.add_column("Feed", style="cyan", no_wrap=True)
    table.add_column("Title", style="white", max_width=50)
    table.add_column("Date", style="green", width=12)
    table.add_column("Duration", style="yellow", width=10)

    for result in results:
        if result.episode:
            title = truncate_text(result.episode.title, 50)
            date = result.episode.published.strftime("%Y-%m-%d")
            duration = result.episode.duration_formatted if result.episode.duration_seconds else "-"
            table.add_row(escape(result.feed_name), escape(title), date, duration)
        elif result.success:
            # Feed exists but has no episodes
            table.add_row(escape(result.feed_name), "[dim]No episodes yet[/dim]", "-", "-")
        else:
            # Feed fetch failed
            error = result.error or "Unknown error"
            error_msg = truncate_text(error, 40)
            table.add_row(
                escape(result.feed_name), f"[red]Error: {escape(error_msg)}[/red]", "-", "-"
            )

    console.print(table)

    # Summary
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    if failed == 0:
        console.print(f"\n[green]✓[/green] {successful} feeds fetched successfully")
    else:
        console.print(f"\n[yellow]⚠[/yellow] {successful} succeeded, {failed} failed")

    console.print("\n[bold]To fetch an episode:[/bold] inkwell fetch <feed-name> --latest")


def _output_latest_json(results: list[LatestEpisodeResult]) -> None:
    """Output latest episodes as JSON."""
    episodes = []
    for result in results:
        if result.episode:
            episodes.append(
                {
                    "feed": result.feed_name,
                    "status": "success",
                    "episode": {
                        "title": result.episode.title,
                        "date": result.episode.published.strftime("%Y-%m-%d"),
                        "duration": (
                            result.episode.duration_formatted
                            if result.episode.duration_seconds
                            else None
                        ),
                        "duration_seconds": result.episode.duration_seconds,
                        "url": str(result.episode.url),
                    },
                }
            )
        elif result.success:
            episodes.append(
                {
                    "feed": result.feed_name,
                    "status": "empty",
                    "error": "No episodes yet",
                }
            )
        else:
            episodes.append(
                {
                    "feed": result.feed_name,
                    "status": "error",
                    "error": result.error or "Unknown error",
                }
            )

    output = {
        "latest_episodes": episodes,
        "total_feeds": len(results),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
    }
    print(json.dumps(output, indent=2))
