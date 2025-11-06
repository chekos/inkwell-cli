"""CLI entry point for Inkwell."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from inkwell.config.manager import ConfigManager
from inkwell.config.schema import AuthConfig, FeedConfig
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
    category: Optional[str] = typer.Option(
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

            # Truncate long URLs
            url_str = str(feed.url)
            if len(url_str) > 50:
                url_display = url_str[:47] + "..."
            else:
                url_display = url_str

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
    key: Optional[str] = typer.Argument(None, help="Config key (for 'set' action)"),
    value: Optional[str] = typer.Argument(None, help="Config value (for 'set' action)"),
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

                if field_type == bool:
                    value_converted = value.lower() in ("true", "yes", "1")
                elif field_type == Path:
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


if __name__ == "__main__":
    app()
