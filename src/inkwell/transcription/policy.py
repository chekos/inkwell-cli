"""Transcription attempt policy.

The policy keeps fallback order explicit without adding new providers. It is
small on purpose: future provider plugins can add capability-aware attempts
without spreading ordering logic through TranscriptionManager.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TranscriptionAttemptKind(str, Enum):
    """Supported transcription attempt kinds."""

    CACHE = "cache"
    YOUTUBE_TRANSCRIPT = "youtube_transcript"
    GEMINI_YOUTUBE_URL = "gemini_youtube_url"
    GEMINI_AUDIO = "gemini_audio"
    GEMINI_LOCAL_MEDIA = "gemini_local_media"


@dataclass(frozen=True)
class TranscriptionAttempt:
    """One ordered transcription attempt."""

    kind: TranscriptionAttemptKind
    provider: str
    record_as: str


class TranscriptionAttemptPolicy:
    """Produce ordered transcription attempts for the current provider set."""

    def plan(
        self,
        *,
        use_cache: bool,
        skip_youtube: bool,
        is_youtube_url: bool,
        is_local_media: bool,
    ) -> list[TranscriptionAttempt]:
        """Return ordered attempts for a transcription request."""
        if is_local_media:
            return [
                TranscriptionAttempt(
                    kind=TranscriptionAttemptKind.GEMINI_LOCAL_MEDIA,
                    provider="gemini",
                    record_as="gemini",
                )
            ]

        attempts: list[TranscriptionAttempt] = []
        if use_cache:
            attempts.append(
                TranscriptionAttempt(
                    kind=TranscriptionAttemptKind.CACHE,
                    provider="cache",
                    record_as="cache",
                )
            )

        if not skip_youtube:
            attempts.append(
                TranscriptionAttempt(
                    kind=TranscriptionAttemptKind.YOUTUBE_TRANSCRIPT,
                    provider="youtube",
                    record_as="youtube",
                )
            )

        if is_youtube_url:
            attempts.append(
                TranscriptionAttempt(
                    kind=TranscriptionAttemptKind.GEMINI_YOUTUBE_URL,
                    provider="gemini",
                    record_as="gemini",
                )
            )

        attempts.append(
            TranscriptionAttempt(
                kind=TranscriptionAttemptKind.GEMINI_AUDIO,
                provider="gemini",
                record_as="gemini",
            )
        )
        return attempts
