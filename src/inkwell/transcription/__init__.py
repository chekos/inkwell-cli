"""Transcription module for podcast audio-to-text conversion.

This module provides multi-tier transcription capabilities:
- Tier 1: YouTube transcript extraction (free, fast)
- Tier 2: Gemini AI transcription (fallback, costs money)

Key components:
- models: Data models for transcripts and segments
- youtube: YouTube transcript extraction
- audio: Audio download with yt-dlp
- gemini: Gemini API transcription
- cache: Transcript caching layer
- manager: High-level orchestration
"""

from inkwell.transcription.cache import CacheError, TranscriptCache
from inkwell.transcription.gemini import (
    CostEstimate,
    GeminiTranscriber,
    GeminiTranscriberWithSegments,
)
from inkwell.transcription.manager import TranscriptionManager
from inkwell.transcription.models import (
    Transcript,
    TranscriptionResult,
    TranscriptSegment,
)
from inkwell.transcription.youtube import YouTubeTranscriber

__all__ = [
    "CacheError",
    "CostEstimate",
    "GeminiTranscriber",
    "GeminiTranscriberWithSegments",
    "Transcript",
    "TranscriptCache",
    "TranscriptionManager",
    "TranscriptSegment",
    "TranscriptionResult",
    "YouTubeTranscriber",
]
