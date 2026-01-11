# feat: Add `inkwell list latest` command to show latest episode from each feed

**Type:** Enhancement
**Created:** 2025-01-11

## Overview

Add a new `inkwell list latest` subcommand that fetches and displays the most recent episode from each configured feed. This provides a quick "what's new across all my podcasts" overview without needing to check each feed individually.

## Problem Statement

Currently, to see the latest episode from each feed, users must run `inkwell list episodes <feed>` separately for each configured feed. With multiple feeds, this is tedious and slow. Users want a single command to see "what's new" across all their podcasts.

## Proposed Solution

Add `inkwell list latest` following the existing subcommand pattern:

```bash
inkwell list latest              # Show latest episode from each feed
inkwell list latest --json       # JSON output for scripts/agents
```

**Output Example (Table):**
```
Latest Episodes (All Feeds)

Feed            Title                                      Date         Duration
--------------  -----------------------------------------  -----------  --------
tech-podcast    Episode 100: The Future of AI              2025-01-10   45:30
news-daily      Morning Update: January 11                 2025-01-11   15:00
interviews      Deep Dive with Jane Doe                    2025-01-08   1:02:15

✓ 3 feeds fetched successfully

To fetch an episode: inkwell fetch <feed-name> --latest
```

## Technical Approach

### Architecture

Follows the existing pattern in `cli_list.py`:

```
src/inkwell/
  cli_list.py    # Add list_latest() command
```

### Key Implementation Details

1. **Parallel Fetching**: Use `asyncio.gather()` with `return_exceptions=True` for concurrent feed fetching with error tolerance

2. **Error Handling**: Continue processing all feeds even if some fail; show partial results with error annotations

3. **Progress Display**: Show spinner while fetching (suppressed in JSON mode)

4. **Exit Codes**:
   - 0: All feeds succeeded
   - 1: All feeds failed
   - 0: Partial success (some succeeded, some failed) - prioritize showing results

### Command Interface

```python
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
```

### JSON Output Schema

```json
{
  "latest_episodes": [
    {
      "feed": "tech-podcast",
      "status": "success",
      "episode": {
        "title": "Episode 100: The Future of AI",
        "date": "2025-01-10",
        "duration": "45:30",
        "url": "https://..."
      }
    },
    {
      "feed": "broken-feed",
      "status": "error",
      "error": "Authentication failed"
    }
  ],
  "total_feeds": 3,
  "successful": 2,
  "failed": 1
}
```

### Edge Cases

| Case | Behavior |
|------|----------|
| No feeds configured | Show "No feeds configured" message, exit 0 |
| Feed has no episodes | Show feed with "No episodes yet" status |
| Feed fetch fails | Show feed with error message, continue others |
| All feeds fail | Show all errors, exit 1 |
| Single feed | Same table format, single row |

## Acceptance Criteria

- [ ] `inkwell list latest` shows latest episode from each configured feed
- [ ] `inkwell list latest --json` outputs valid JSON with the schema above
- [ ] Feeds are fetched in parallel for performance
- [ ] Failed feeds show error message but don't block other feeds
- [ ] Empty feeds show "No episodes yet" instead of crashing
- [ ] Progress spinner shown during fetch (suppressed in JSON mode)
- [ ] `inkwell list --help` shows the new `latest` subcommand
- [ ] Tests cover: no feeds, all succeed, partial failure, all fail, empty feed

## MVP Implementation

### cli_list.py additions

```python
# src/inkwell/cli_list.py

from dataclasses import dataclass
from inkwell.utils.errors import ValidationError  # Add to existing imports

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


@app.command("latest")
def list_latest(
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
) -> None:
    """Show the latest episode from each configured feed."""

    async def run_latest() -> None:
        manager = ConfigManager()
        feeds = manager.list_feeds()

        if not feeds:
            if json_output:
                print(json.dumps({"latest_episodes": [], "total_feeds": 0, "successful": 0, "failed": 0}))
            else:
                console.print("[yellow]No feeds configured yet.[/yellow]")
                console.print("\nAdd a feed: [cyan]inkwell add <url> --name <name>[/cyan]")
            return

        parser = RSSParser()
        tasks = [_fetch_latest_for_feed(parser, name, config) for name, config in feeds.items()]

        # Fetch all feeds in parallel
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
        if all(not r.success for r in results):
            sys.exit(1)

    asyncio.run(run_latest())


def _output_latest_table(results: list[LatestEpisodeResult]) -> None:
    """Display latest episodes in a table."""
    table = Table(title="Latest Episodes (All Feeds)")
    table.add_column("Feed", style="cyan", no_wrap=True)
    table.add_column("Title", style="white", max_width=50)
    table.add_column("Date", style="green", width=12)
    table.add_column("Duration", style="yellow", width=10)

    for result in results:
        if result.episode:
            title = result.episode.title[:47] + "..." if len(result.episode.title) > 50 else result.episode.title
            date = result.episode.published.strftime("%Y-%m-%d")
            duration = result.episode.duration_formatted if result.episode.duration_seconds else "-"
            table.add_row(result.feed_name, title, date, duration)
        elif result.success:
            # Feed exists but has no episodes
            table.add_row(result.feed_name, "[dim]No episodes yet[/dim]", "-", "-")
        else:
            # Feed fetch failed
            error_msg = result.error[:40] + "..." if len(result.error or "") > 40 else result.error
            table.add_row(result.feed_name, f"[red]Error: {error_msg}[/red]", "-", "-")

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
            episodes.append({
                "feed": result.feed_name,
                "status": "success",
                "episode": {
                    "title": result.episode.title,
                    "date": result.episode.published.strftime("%Y-%m-%d"),
                    "duration": result.episode.duration_formatted if result.episode.duration_seconds else None,
                    "url": str(result.episode.url),
                },
            })
        elif result.success:
            episodes.append({
                "feed": result.feed_name,
                "status": "empty",
                "error": "No episodes yet",
            })
        else:
            episodes.append({
                "feed": result.feed_name,
                "status": "error",
                "error": result.error,
            })

    output = {
        "latest_episodes": episodes,
        "total_feeds": len(results),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
    }
    print(json.dumps(output, indent=2))
```

### test_cli_list.py additions

```python
# tests/integration/test_cli_list.py

class TestListLatest:
    """Tests for `inkwell list latest`."""

    def test_list_latest_no_feeds(self, tmp_path: Path, monkeypatch) -> None:
        """Should show helpful message when no feeds configured."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(app, ["list", "latest"])

        assert result.exit_code == 0
        assert "No feeds configured" in result.stdout

    def test_list_latest_json_no_feeds(self, tmp_path: Path, monkeypatch) -> None:
        """JSON output should return empty array when no feeds."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(app, ["list", "latest", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["latest_episodes"] == []
        assert data["total_feeds"] == 0

    def test_list_latest_help_shows_command(self) -> None:
        """inkwell list --help should show latest subcommand."""
        result = runner.invoke(app, ["list", "--help"])

        assert "latest" in result.stdout

    def test_list_latest_single_feed_success(self, tmp_path: Path, monkeypatch, mock_rss_feed) -> None:
        """Should display latest episode from a single feed."""
        # Setup: configure one feed and mock RSS response
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)
        # ... setup feed config and mock ...

        result = runner.invoke(app, ["list", "latest"])

        assert result.exit_code == 0
        assert "Latest Episodes" in result.stdout

    def test_list_latest_partial_failure(self, tmp_path: Path, monkeypatch) -> None:
        """Should show results from successful feeds even when some fail."""
        # Setup: configure multiple feeds, one fails
        # ... mock setup ...

        result = runner.invoke(app, ["list", "latest"])

        assert result.exit_code == 0  # Partial success = exit 0
        assert "succeeded" in result.stdout
        assert "failed" in result.stdout

    def test_list_latest_all_fail_exit_code(self, tmp_path: Path, monkeypatch) -> None:
        """Should exit 1 when all feeds fail."""
        # Setup: configure feeds that all fail
        # ... mock setup ...

        result = runner.invoke(app, ["list", "latest"])

        assert result.exit_code == 1

    def test_list_latest_empty_feed(self, tmp_path: Path, monkeypatch, mock_empty_feed) -> None:
        """Should show 'No episodes yet' for feeds with no episodes."""
        # Setup: feed returns successfully but has no entries
        # ... mock setup ...

        result = runner.invoke(app, ["list", "latest"])

        assert result.exit_code == 0
        assert "No episodes yet" in result.stdout

    def test_list_latest_json_success(self, tmp_path: Path, monkeypatch, mock_rss_feed) -> None:
        """JSON output should include episode metadata."""
        # ... setup ...

        result = runner.invoke(app, ["list", "latest", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["successful"] >= 1
        assert "episode" in data["latest_episodes"][0]
```

## References

### Internal References
- List command pattern: `src/inkwell/cli_list.py`
- RSSParser.get_latest_episode(): `src/inkwell/feeds/parser.py:116-134`
- Async pattern: `src/inkwell/cli.py:680-987`
- Progress display: `src/inkwell/utils/progress.py`

### External References
- [asyncio.gather documentation](https://docs.python.org/3/library/asyncio-task.html)
- [Rich Progress documentation](https://rich.readthedocs.io/en/stable/progress.html)
- [Typer subcommands](https://typer.tiangolo.com/tutorial/subcommands/)

### Related Issues
- PR #35: Enhanced list command with feeds/templates/episodes subcommands
