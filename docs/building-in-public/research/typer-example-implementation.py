"""
Example implementation of flexible episode selection for Inkwell CLI.

This demonstrates the patterns researched in typer-flexible-argument-parsing.md
"""

import click
import typer
from typing import Optional, List, Dict, Any
from rich.progress import Progress, track
from rich.console import Console

# ============================================================================
# Custom ParamType for Episode Selection
# ============================================================================


class EpisodeSelector(click.ParamType):
    """
    Parse episode selection patterns:
    - "3" → position 3
    - "1-5" → range from 1 to 5
    - "1,3,7" → positions 1, 3, and 7
    - "AI security" → keyword search
    """

    name = "episode_selector"

    def convert(self, value, param, ctx) -> Optional[Dict[str, Any]]:
        """Convert string input to structured episode selector."""
        if value is None:
            return None

        # Already converted (e.g., default value)
        if isinstance(value, dict):
            return value

        value = value.strip()

        if not value:
            self.fail("Episode selector cannot be empty", param, ctx)

        # Try parsing as range (e.g., "1-5")
        result = self._try_parse_range(value, param, ctx)
        if result:
            return result

        # Try parsing as comma-separated list (e.g., "1,3,7")
        result = self._try_parse_list(value, param, ctx)
        if result:
            return result

        # Try parsing as single position (e.g., "3")
        result = self._try_parse_position(value, param, ctx)
        if result:
            return result

        # Fallback to keyword search
        return self._parse_keyword(value, param, ctx)

    def _try_parse_range(self, value: str, param, ctx) -> Optional[Dict[str, Any]]:
        """Parse range format: '1-5'"""
        if "-" not in value:
            return None

        parts = value.split("-")
        if len(parts) != 2:
            self.fail(
                f"Invalid range format: {value}. Expected format: '1-5'", param, ctx
            )

        if not all(p.strip().isdigit() for p in parts):
            return None  # Not a range, might be keyword with hyphen

        try:
            start = int(parts[0].strip())
            end = int(parts[1].strip())

            # Validation
            if start <= 0 or end <= 0:
                self.fail("Episode positions must be positive integers", param, ctx)

            if start > end:
                self.fail(
                    f"Invalid range: start ({start}) must be <= end ({end})", param, ctx
                )

            # Optional: prevent unreasonably large ranges
            if (end - start) > 100:
                self.fail("Range too large (max 100 episodes at once)", param, ctx)

            return {"type": "range", "start": start, "end": end}

        except ValueError:
            return None

    def _try_parse_list(self, value: str, param, ctx) -> Optional[Dict[str, Any]]:
        """Parse comma-separated list: '1,3,7'"""
        if "," not in value:
            return None

        parts = [p.strip() for p in value.split(",")]

        # Try parsing all parts as integers
        try:
            positions = [int(p) for p in parts if p]  # Skip empty strings

            if not positions:
                self.fail("Empty position list", param, ctx)

            # Validation
            if any(p <= 0 for p in positions):
                self.fail(
                    "All episode positions must be positive integers", param, ctx
                )

            positions = sorted(set(positions))

            return {"type": "list", "positions": positions}

        except ValueError:
            # Not all parts are integers, treat as keyword
            return None

    def _try_parse_position(self, value: str, param, ctx) -> Optional[Dict[str, Any]]:
        """Parse single position: '3'"""
        try:
            position = int(value)

            # Validation
            if position <= 0:
                self.fail("Episode position must be a positive integer", param, ctx)

            return {"type": "position", "value": position}

        except ValueError:
            return None

    def _parse_keyword(self, value: str, param, ctx) -> Dict[str, Any]:
        """Parse as keyword search (fallback)"""
        keyword = value.strip()

        # Validation
        if len(keyword) < 2:
            self.fail("Keyword search must be at least 2 characters", param, ctx)

        return {"type": "keyword", "value": keyword}


# ============================================================================
# Helper Functions
# ============================================================================


def validate_mutually_exclusive(*flags, names: List[str]) -> None:
    """
    Validate that at most one flag is set.

    Args:
        *flags: Flag values to check
        names: Corresponding flag names for error message

    Raises:
        typer.Exit: If more than one flag is set
    """
    set_flags = [
        name
        for name, flag in zip(names, flags)
        if flag is not None and flag is not False
    ]

    if len(set_flags) > 1:
        console = Console(stderr=True)
        console.print(
            f"[red]Error:[/red] {' and '.join(set_flags)} are mutually exclusive"
        )
        raise typer.Exit(1)


def select_episodes(all_episodes: List[Any], selector: Dict[str, Any]) -> List[Any]:
    """
    Select episodes based on parsed selector.

    Args:
        all_episodes: List of all available episodes
        selector: Parsed selector dict from EpisodeSelector

    Returns:
        List of selected episodes
    """
    console = Console()

    if selector["type"] == "range":
        start, end = selector["start"], selector["end"]

        if start > len(all_episodes):
            console.print(
                f"[yellow]Warning:[/yellow] Start position {start} "
                f"exceeds episode count ({len(all_episodes)})",
                err=True,
            )
            return []

        # Clamp end to available episodes
        actual_end = min(end, len(all_episodes))
        if actual_end < end:
            console.print(
                f"[yellow]Warning:[/yellow] Clamping end position from {end} "
                f"to {actual_end} (total episodes: {len(all_episodes)})",
                err=True,
            )

        return all_episodes[start - 1 : actual_end]

    elif selector["type"] == "list":
        positions = selector["positions"]
        selected = []
        invalid = []

        for pos in positions:
            if pos > len(all_episodes):
                invalid.append(pos)
            else:
                selected.append(all_episodes[pos - 1])

        if invalid:
            console.print(
                f"[yellow]Warning:[/yellow] Skipping invalid positions: "
                f"{', '.join(map(str, invalid))} "
                f"(total episodes: {len(all_episodes)})",
                err=True,
            )

        return selected

    elif selector["type"] == "position":
        pos = selector["value"]

        if pos > len(all_episodes):
            console.print(
                f"[yellow]Warning:[/yellow] Position {pos} exceeds "
                f"episode count ({len(all_episodes)})",
                err=True,
            )
            return []

        return [all_episodes[pos - 1]]

    else:  # keyword
        keyword = selector["value"].lower()
        selected = [
            ep
            for ep in all_episodes
            if keyword in ep.title.lower() or keyword in ep.description.lower()
        ]

        if not selected:
            console.print(
                f"[yellow]Warning:[/yellow] No episodes found matching '{keyword}'",
                err=True,
            )

        return selected


# ============================================================================
# Example CLI Command
# ============================================================================

app = typer.Typer()


@app.command()
def process(
    feed_url: Optional[str] = typer.Option(None, "--feed", "-f", help="RSS feed URL"),
    episode: Optional[Dict[str, Any]] = typer.Option(
        None,
        "--episode",
        "-e",
        click_type=EpisodeSelector(),
        help=(
            "Select episode(s): "
            "position (3), range (1-5), list (1,3,7), or keyword ('AI security')"
        ),
    ),
    latest: bool = typer.Option(False, "--latest", "-l", help="Process latest episode"),
    all_episodes: bool = typer.Option(
        False, "--all", help="Process all episodes in feed"
    ),
    interview: bool = typer.Option(
        False, "--interview", help="Enable interactive interview mode"
    ),
):
    """
    Process podcast episodes with flexible selection.

    Examples:
        # Process latest episode
        $ inkwell process --feed https://example.com/feed.xml --latest

        # Process episode at position 3
        $ inkwell process --feed https://example.com/feed.xml --episode 3

        # Process episodes 1 through 5
        $ inkwell process --feed https://example.com/feed.xml --episode 1-5

        # Process episodes at positions 1, 3, and 7
        $ inkwell process --feed https://example.com/feed.xml --episode 1,3,7

        # Search for episodes by keyword
        $ inkwell process --feed https://example.com/feed.xml --episode "AI security"
    """
    console = Console()

    validate_mutually_exclusive(
        episode, latest, all_episodes, names=["--episode", "--latest", "--all"]
    )

    # Mock: Fetch episodes from feed
    # In real implementation, this would use feedparser
    class MockEpisode:
        def __init__(self, title: str, description: str):
            self.title = title
            self.description = description

    mock_episodes = [
        MockEpisode("Episode 1: Introduction to Python", "Learn the basics"),
        MockEpisode("Episode 2: Advanced Python", "Deep dive into Python"),
        MockEpisode("Episode 3: AI and Machine Learning", "AI basics"),
        MockEpisode("Episode 4: Security Best Practices", "Keep your code safe"),
        MockEpisode("Episode 5: AI Security Concerns", "AI safety discussion"),
    ]

    if latest:
        selected = [mock_episodes[0]]
        console.print("[cyan]Processing latest episode[/cyan]")
    elif all_episodes:
        selected = mock_episodes
        console.print(f"[cyan]Processing all {len(selected)} episodes[/cyan]")
    elif episode:
        selected = select_episodes(mock_episodes, episode)
        console.print(f"[cyan]Processing {len(selected)} selected episode(s)[/cyan]")
    else:
        # Default: prompt user or show help
        console.print(
            "[yellow]No episode selection specified. Use --latest, --all, "
            "or --episode[/yellow]"
        )
        raise typer.Exit(0)

    if not selected:
        console.print("[red]No episodes to process[/red]")
        raise typer.Exit(1)

    # Process episodes with progress bar
    process_episodes_with_progress(selected, interview=interview)


def process_episodes_with_progress(episodes: List[Any], interview: bool = False):
    """
    Process episodes with Rich progress bars.

    Args:
        episodes: List of episodes to process
        interview: Whether to enable interview mode
    """
    console = Console()

    # Simple progress for single episode
    if len(episodes) == 1:
        console.print(f"\n[bold]Processing: {episodes[0].title}[/bold]")
        for step in track(
            ["Download", "Transcribe", "Extract", "Generate"],
            description="Progress",
        ):
            # Mock processing
            import time

            time.sleep(0.5)
            console.print(f"  ✓ {step}")

        if interview:
            console.print("  ✓ Interview")

        return

    # Multi-episode processing with detailed progress
    with Progress() as progress:
        overall_task = progress.add_task(
            "[cyan]Overall progress", total=len(episodes)
        )

        for i, episode in enumerate(episodes, 1):
            # Per-episode task
            episode_task = progress.add_task(
                f"[green]Episode {i}: {episode.title[:40]}...", total=100
            )

            # Simulate processing stages
            stages = [
                ("Download", 20),
                ("Transcribe", 40),
                ("Extract", 30),
                ("Generate", 10),
            ]

            if interview:
                stages.append(("Interview", 20))

            completed = 0
            for stage_name, stage_weight in stages:
                # Mock processing
                import time

                time.sleep(0.3)
                completed += stage_weight
                progress.update(episode_task, completed=completed)

            # Mark episode complete
            progress.update(overall_task, advance=1)

    console.print("\n[bold green]✓ All episodes processed successfully![/bold green]")


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    app()

    # Example runs (for documentation):
    """
    # Single position
    $ python example.py process --feed feed.xml --episode 3

    # Range
    $ python example.py process --feed feed.xml --episode 1-5

    # List
    $ python example.py process --feed feed.xml --episode 1,3,7

    # Keyword
    $ python example.py process --feed feed.xml --episode "AI security"

    # Latest
    $ python example.py process --feed feed.xml --latest

    # All
    $ python example.py process --feed feed.xml --all

    # With interview
    $ python example.py process --feed feed.xml --episode 3 --interview
    """
