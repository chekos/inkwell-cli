"""Session management for interview mode.

Handles interview session lifecycle, state persistence, and resume capability.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from inkwell.utils.datetime import now_utc

from .models import (
    InterviewGuidelines,
    InterviewSession,
)


class SessionManager:
    """Manages interview session lifecycle and persistence.

    Handles creating, saving, loading, and resuming interview sessions.
    Provides atomic writes and timeout detection.

    Example:
        >>> manager = SessionManager(session_dir=Path("~/.inkwell/sessions"))
        >>> session = manager.create_session(
        ...     episode_url="https://example.com/ep1",
        ...     episode_title="Episode 1",
        ...     podcast_name="Test Podcast",
        ...     template_name="reflective"
        ... )
        >>> manager.save_session(session)
        >>> loaded = manager.load_session(session.session_id)
    """

    def __init__(self, session_dir: Path | None = None):
        """Initialize session manager.

        Args:
            session_dir: Directory for session files. If None, uses default.
        """
        self.session_dir = session_dir or self._get_default_session_dir()
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        episode_url: str,
        episode_title: str,
        podcast_name: str,
        template_name: str = "reflective",
        max_questions: int = 5,
        guidelines: InterviewGuidelines | None = None,
    ) -> InterviewSession:
        """Create a new interview session.

        Args:
            episode_url: URL of the episode
            episode_title: Title of the episode
            podcast_name: Name of the podcast
            template_name: Template to use (reflective, analytical, creative)
            max_questions: Maximum number of questions
            guidelines: Optional user guidelines

        Returns:
            New InterviewSession instance
        """
        session = InterviewSession(
            episode_url=episode_url,
            episode_title=episode_title,
            podcast_name=podcast_name,
            template_name=template_name,
            max_questions=max_questions,
            guidelines=guidelines,
        )

        # Save immediately
        self.save_session(session)

        return session

    def save_session(self, session: InterviewSession, update_timestamp: bool = True) -> Path:
        """Save session to disk.

        Uses atomic write (write to temp file, then rename) to prevent corruption.

        Args:
            session: Session to save
            update_timestamp: Whether to update the updated_at timestamp

        Returns:
            Path to saved session file
        """
        session_file = self._get_session_file(session.session_id)

        # Mark as updated (unless explicitly disabled)
        if update_timestamp:
            session.mark_updated()

        # Convert to dict for JSON serialization
        session_data = session.model_dump(mode="json")

        # Atomic write: write to temp file, then rename
        temp_file = session_file.with_suffix(".tmp")

        try:
            with temp_file.open("w") as f:
                json.dump(session_data, f, indent=2, default=str)

            # Atomic rename
            temp_file.replace(session_file)

            return session_file

        except Exception as e:
            # Clean up temp file on error
            if temp_file.exists():
                temp_file.unlink()
            raise RuntimeError(f"Failed to save session: {e}") from e

    def load_session(self, session_id: str) -> InterviewSession:
        """Load session from disk.

        Args:
            session_id: ID of session to load

        Returns:
            Loaded InterviewSession

        Raises:
            FileNotFoundError: If session file doesn't exist
            ValueError: If session data is invalid
        """
        session_file = self._get_session_file(session_id)

        if not session_file.exists():
            raise FileNotFoundError(f"Session {session_id} not found")

        try:
            with session_file.open("r") as f:
                session_data = json.load(f)

            # Parse with Pydantic
            session = InterviewSession.model_validate(session_data)

            return session

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid session data: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to load session: {e}") from e

    def list_sessions(
        self,
        episode_url: str | None = None,
        podcast_name: str | None = None,
        status: str | None = None,
    ) -> list[InterviewSession]:
        """List all sessions, optionally filtered.

        Args:
            episode_url: Filter by episode URL
            podcast_name: Filter by podcast name
            status: Filter by status (active, paused, completed, abandoned)

        Returns:
            List of sessions matching filters
        """
        sessions = []

        for session_file in self.session_dir.glob("session-*.json"):
            try:
                with session_file.open("r") as f:
                    session_data = json.load(f)

                # Apply filters
                if episode_url and session_data.get("episode_url") != episode_url:
                    continue

                if podcast_name and session_data.get("podcast_name") != podcast_name:
                    continue

                if status and session_data.get("status") != status:
                    continue

                # Parse session
                session = InterviewSession.model_validate(session_data)
                sessions.append(session)

            except (json.JSONDecodeError, ValueError):
                # Skip invalid sessions
                continue

        # Sort by most recent first
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        return sessions

    def find_resumable_session(self, episode_url: str) -> InterviewSession | None:
        """Find an active or paused session for an episode.

        Args:
            episode_url: Episode URL to search for

        Returns:
            Most recent active/paused session, or None if not found
        """
        # Look for active or paused sessions
        for status in ["active", "paused"]:
            sessions = self.list_sessions(episode_url=episode_url, status=status)
            if sessions:
                # Return most recent (already sorted)
                return sessions[0]

        return None

    def delete_session(self, session_id: str) -> bool:
        """Delete a session file.

        Args:
            session_id: ID of session to delete

        Returns:
            True if deleted, False if not found
        """
        session_file = self._get_session_file(session_id)

        if session_file.exists():
            session_file.unlink()
            return True

        return False

    def cleanup_old_sessions(self, days: int = 30) -> int:
        """Delete sessions older than specified days.

        Only deletes completed or abandoned sessions.

        Args:
            days: Delete sessions older than this many days

        Returns:
            Number of sessions deleted
        """
        cutoff_date = now_utc() - timedelta(days=days)
        deleted = 0

        for session_file in self.session_dir.glob("session-*.json"):
            try:
                with session_file.open("r") as f:
                    session_data = json.load(f)

                # Only delete completed/abandoned sessions
                status = session_data.get("status")
                if status not in ["completed", "abandoned"]:
                    continue

                # Check age
                updated_at_str = session_data.get("updated_at")
                if updated_at_str:
                    updated_at = datetime.fromisoformat(
                        updated_at_str.replace("Z", "+00:00")
                    )
                    if updated_at < cutoff_date:
                        session_file.unlink()
                        deleted += 1

            except (json.JSONDecodeError, ValueError, KeyError):
                # Skip invalid files
                continue

        return deleted

    def detect_timeout(
        self, session: InterviewSession, timeout_minutes: int = 60
    ) -> bool:
        """Check if session has timed out.

        Args:
            session: Session to check
            timeout_minutes: Timeout threshold in minutes

        Returns:
            True if session has timed out
        """
        if session.status not in ["active", "paused"]:
            return False

        timeout_delta = timedelta(minutes=timeout_minutes)
        time_since_update = now_utc() - session.updated_at

        return time_since_update > timeout_delta

    def auto_abandon_timed_out(self, timeout_minutes: int = 60) -> int:
        """Automatically abandon timed-out sessions.

        Args:
            timeout_minutes: Timeout threshold

        Returns:
            Number of sessions abandoned
        """
        abandoned = 0

        for session_file in self.session_dir.glob("session-*.json"):
            try:
                with session_file.open("r") as f:
                    session_data = json.load(f)

                session = InterviewSession.model_validate(session_data)

                if self.detect_timeout(session, timeout_minutes):
                    session.abandon()
                    self.save_session(session)
                    abandoned += 1

            except (json.JSONDecodeError, ValueError):
                continue

        return abandoned

    def _get_session_file(self, session_id: str) -> Path:
        """Get path to session file.

        Args:
            session_id: Session ID

        Returns:
            Path to session JSON file
        """
        return self.session_dir / f"session-{session_id}.json"

    def _get_default_session_dir(self) -> Path:
        """Get default session directory.

        Returns:
            Default path (XDG_DATA_HOME or ~/.local/share/inkwell/sessions)
        """
        import os

        xdg_data_home = os.getenv("XDG_DATA_HOME")
        if xdg_data_home:
            base_dir = Path(xdg_data_home)
        else:
            base_dir = Path.home() / ".local" / "share"

        return base_dir / "inkwell" / "sessions"

    def get_session_stats(self, session: InterviewSession) -> dict[str, Any]:
        """Get statistics about a session.

        Args:
            session: Session to analyze

        Returns:
            Dictionary of statistics
        """
        # Convert duration timedelta to minutes
        duration_minutes = session.duration.total_seconds() / 60.0

        return {
            "session_id": session.session_id,
            "status": session.status,
            "question_count": session.question_count,
            "substantive_responses": session.substantive_response_count,
            "average_response_length": session.average_response_length,
            "total_thinking_time": session.total_thinking_time,
            "duration_minutes": duration_minutes,
            "tokens_used": session.total_tokens_used,
            "cost_usd": session.total_cost_usd,
            "completion_rate": (
                session.question_count / session.max_questions
                if session.max_questions > 0
                else 0
            ),
        }
