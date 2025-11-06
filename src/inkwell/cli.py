"""CLI entry point for Inkwell."""

import typer

app = typer.Typer(
    name="inkwell",
    help="Transform podcast episodes into structured markdown notes",
    no_args_is_help=True,
)


@app.command("version")
def show_version() -> None:
    """Show version information."""
    from inkwell import __version__

    typer.echo(f"Inkwell CLI v{__version__}")


# Placeholder commands for future implementation
@app.command("add")
def add_feed() -> None:
    """Add a new podcast feed (not yet implemented)."""
    typer.echo("Coming soon in Day 5!")


@app.command("list")
def list_feeds() -> None:
    """List all configured feeds (not yet implemented)."""
    typer.echo("Coming soon in Day 5!")


if __name__ == "__main__":
    app()
