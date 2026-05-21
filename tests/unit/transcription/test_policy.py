"""Tests for transcription attempt policy."""

from inkwell.transcription.policy import TranscriptionAttemptKind, TranscriptionAttemptPolicy


def _kinds(policy_result):
    return [attempt.kind for attempt in policy_result]


def test_policy_orders_default_youtube_url_attempts() -> None:
    policy = TranscriptionAttemptPolicy()

    attempts = policy.plan(
        use_cache=True,
        skip_youtube=False,
        is_youtube_url=True,
        is_local_media=False,
    )

    assert _kinds(attempts) == [
        TranscriptionAttemptKind.CACHE,
        TranscriptionAttemptKind.YOUTUBE_TRANSCRIPT,
        TranscriptionAttemptKind.GEMINI_YOUTUBE_URL,
        TranscriptionAttemptKind.GEMINI_AUDIO,
    ]
    assert [attempt.record_as for attempt in attempts] == [
        "cache",
        "youtube",
        "gemini",
        "gemini",
    ]


def test_policy_skips_cache_and_youtube_when_requested() -> None:
    policy = TranscriptionAttemptPolicy()

    attempts = policy.plan(
        use_cache=False,
        skip_youtube=True,
        is_youtube_url=True,
        is_local_media=False,
    )

    assert _kinds(attempts) == [
        TranscriptionAttemptKind.GEMINI_YOUTUBE_URL,
        TranscriptionAttemptKind.GEMINI_AUDIO,
    ]


def test_policy_uses_audio_fallback_for_non_youtube_urls() -> None:
    policy = TranscriptionAttemptPolicy()

    attempts = policy.plan(
        use_cache=True,
        skip_youtube=False,
        is_youtube_url=False,
        is_local_media=False,
    )

    assert _kinds(attempts) == [
        TranscriptionAttemptKind.CACHE,
        TranscriptionAttemptKind.YOUTUBE_TRANSCRIPT,
        TranscriptionAttemptKind.GEMINI_AUDIO,
    ]


def test_policy_local_media_goes_directly_to_gemini() -> None:
    policy = TranscriptionAttemptPolicy()

    attempts = policy.plan(
        use_cache=True,
        skip_youtube=False,
        is_youtube_url=False,
        is_local_media=True,
    )

    assert _kinds(attempts) == [TranscriptionAttemptKind.GEMINI_LOCAL_MEDIA]
    assert attempts[0].provider == "gemini"
