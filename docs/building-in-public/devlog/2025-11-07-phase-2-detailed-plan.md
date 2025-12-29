# Phase 2 Detailed Implementation Plan - Transcription Layer

**Date**: 2025-11-07
**Status**: Planning
**Phase**: 2 of 5
**Related**: [PRD_v0.md](../PRD_v0.md), [Phase 1 Complete](../PHASE_1_COMPLETE.md)

## Overview

Phase 2 adds the transcription layer to Inkwell, enabling the tool to convert podcast audio into text. This is the critical bridge between Phase 1 (feed management) and Phase 3 (LLM extraction). We implement a multi-strategy approach: YouTube transcript API (primary), Gemini transcription (fallback), with intelligent caching to minimize costs and latency.

**Key Principle**: After each unit of work, we pause to document lessons learned, experiments, research, and architectural decisions. Documentation is not an afterthought—it's an integral part of our development process that ensures accessibility and maintainability.

---

## Phase 2 Scope (from PRD)

**Core Requirements:**
- YouTube transcript extraction via `youtube-transcript-api`
- Audio download using `yt-dlp`
- Gemini Flash transcription integration (fallback)
- Transcript caching and retrieval

**Professional Grade Additions:**
- Comprehensive error handling for network/API failures
- Cost tracking and optimization for Gemini API calls
- Progress indicators for long-running operations
- Transcript quality validation
- Support for multiple audio formats
- Retry logic with exponential backoff
- Integration testing with real podcast episodes

---

## Architecture Overview

### Transcription Flow

```
Episode URL
    │
    ├─► Is YouTube URL?
    │     │
    │     ├─► Yes → YouTubeTranscriber
    │     │           │
    │     │           ├─► youtube_transcript_api.list_transcripts()
    │     │           │     │
    │     │           │     ├─► Success → Return transcript
    │     │           │     └─► Fail → Fall to Gemini
    │     │           │
    │     │           └─► [Cache transcript]
    │     │
    │     └─► No → Skip to audio download
    │
    ├─► AudioDownloader (yt-dlp)
    │     │
    │     ├─► Download audio to temp location
    │     ├─► Convert to optimal format (if needed)
    │     ├─► Validate file integrity
    │     └─► Return audio file path
    │
    ├─► GeminiTranscriber
    │     │
    │     ├─► Upload audio file
    │     ├─► Request transcription (gemini-2.0-flash-exp)
    │     ├─► Stream/poll for results
    │     ├─► Track API costs
    │     └─► Return transcript
    │
    ├─► TranscriptCache
    │     │
    │     ├─► Generate cache key (episode URL + hash)
    │     ├─► Check if cached transcript exists
    │     ├─► Save new transcripts
    │     └─► Handle cache invalidation
    │
    └─► Return Transcript object
```

### Module Structure

```
src/inkwell/
├── transcription/
│   ├── __init__.py
│   ├── models.py          # Transcript, TranscriptSegment data models
│   ├── youtube.py         # YouTube transcript extraction
│   ├── audio.py           # Audio download with yt-dlp
│   ├── gemini.py          # Gemini API transcription
│   ├── cache.py           # Transcript caching layer
│   ├── manager.py         # High-level transcription orchestrator
│   └── validators.py      # Transcript quality validation
└── api/
    ├── __init__.py
    ├── gemini_client.py   # Gemini API client wrapper
    └── rate_limiter.py    # API rate limiting
```

---

## Detailed Implementation Plan

### Unit 1: Research & Architecture Decision Making

**Duration**: 1-2 hours
**Goal**: Make informed decisions about libraries, APIs, and architecture

#### Tasks:
1. **Research YouTube Transcript API**
   - Test `youtube-transcript-api` library with sample podcasts
   - Understand limitations (language support, availability)
   - Document error scenarios (transcript unavailable, private videos)
   - Test with different URL formats (youtube.com, youtu.be, embedded)

2. **Research yt-dlp**
   - Test audio extraction from various podcast sources
   - Identify optimal audio format for Gemini (codec, bitrate)
   - Document command-line flags needed
   - Test authentication handling for private feeds
   - Benchmark download speeds and file sizes

3. **Research Gemini Transcription API**
   - Review Google AI Python SDK documentation
   - Understand pricing model (cost per minute)
   - Test transcription quality with sample audio
   - Document API rate limits and quotas
   - Identify optimal audio preprocessing (format, length limits)

4. **Cache Strategy Research**
   - Decide cache key generation (URL hash vs episode ID)
   - Determine cache location (XDG cache directory)
   - Research cache invalidation strategies
   - Decide cache format (JSON, SQLite, plain text)

#### Documentation Tasks:

**Create Research Document**: `docs/research/transcription-apis-comparison.md`
- Comparative analysis of YouTube vs Gemini transcription
- Pros/cons of each approach
- Cost analysis (Gemini pricing)
- Quality comparison with sample transcripts
- Recommendations for fallback strategy

**Create Research Document**: `docs/research/yt-dlp-audio-extraction.md`
- Best practices for audio extraction
- Optimal formats for transcription
- Performance benchmarks
- Authentication handling
- Error scenarios and mitigation

**Create ADR**: `docs/adr/009-transcription-strategy.md`
- **Decision**: Multi-tier transcription (YouTube → Gemini)
- **Alternatives**: Gemini-only, Whisper local, third-party services
- **Rationale**: Cost optimization (YouTube free), quality (Gemini Flash good enough), privacy (no third-party)
- **Consequences**: Need to handle YouTube unavailability gracefully

**Create ADR**: `docs/adr/010-transcript-caching.md`
- **Decision**: File-based JSON cache in XDG cache directory
- **Alternatives**: SQLite, in-memory, no caching
- **Rationale**: Simplicity, inspectability, XDG compliance
- **Consequences**: Need cache cleanup strategy

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-2-day-1-research.md`
- Document research findings
- Summarize key decisions
- Note any surprises or gotchas discovered
- Link to research docs and ADRs
- Outline next steps

#### Experiments to Run:

**Create Experiment Log**: `docs/experiments/2025-11-07-youtube-transcript-availability.md`
- Test 20-30 popular podcast episodes on YouTube
- Record availability rate of transcripts
- Document quality of auto-generated vs manual transcripts
- Identify patterns (which podcasts have transcripts)
- Results inform our fallback strategy

**Create Experiment Log**: `docs/experiments/2025-11-07-gemini-transcription-quality.md`
- Transcribe 5 sample podcast segments (varying lengths: 5min, 15min, 30min, 1hr)
- Compare against YouTube transcripts (ground truth)
- Measure accuracy, cost, latency
- Document edge cases (music, multiple speakers, accents)
- Results inform our confidence in Gemini as fallback

**Create Experiment Log**: `docs/experiments/2025-11-07-audio-format-optimization.md`
- Test different audio formats (MP3, M4A, WAV, OPUS)
- Compare file sizes and Gemini transcription quality
- Measure download times with yt-dlp
- Identify optimal format/bitrate trade-off
- Results inform our audio download settings

#### Success Criteria:
- Clear understanding of each transcription method's strengths/weaknesses
- All ADRs created with rationale
- Research documents comprehensive
- Experiment results documented
- Ready to proceed with implementation

---

### Unit 2: Data Models & Core Abstractions

**Duration**: 2-3 hours
**Goal**: Define type-safe models and interfaces for transcription system

#### Tasks:

1. **Create Transcript Models** (`transcription/models.py`)
```python
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Literal, Optional
from pathlib import Path

class TranscriptSegment(BaseModel):
    """Single segment of transcript with timing"""
    text: str
    start: float  # Seconds from beginning
    duration: float  # Duration in seconds

    @property
    def end(self) -> float:
        return self.start + self.duration

    def __str__(self) -> str:
        """Format as [MM:SS] text"""
        minutes, seconds = divmod(int(self.start), 60)
        return f"[{minutes:02d}:{seconds:02d}] {self.text}"

class Transcript(BaseModel):
    """Complete transcript for an episode"""
    segments: list[TranscriptSegment]
    source: Literal["youtube", "gemini", "cached"]
    language: str = "en"
    episode_url: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Metadata
    duration_seconds: Optional[float] = None
    word_count: Optional[int] = None
    cost_usd: Optional[float] = None  # For Gemini transcriptions

    @property
    def full_text(self) -> str:
        """Concatenate all segments into single text"""
        return " ".join(seg.text for seg in self.segments)

    @property
    def total_duration(self) -> timedelta:
        """Total duration of transcript"""
        if self.duration_seconds:
            return timedelta(seconds=self.duration_seconds)
        if self.segments:
            return timedelta(seconds=self.segments[-1].end)
        return timedelta(0)

    def get_segment_at_time(self, time_seconds: float) -> Optional[TranscriptSegment]:
        """Get segment containing specific timestamp"""
        for segment in self.segments:
            if segment.start <= time_seconds < segment.end:
                return segment
        return None

class TranscriptionResult(BaseModel):
    """Result of transcription operation"""
    success: bool
    transcript: Optional[Transcript] = None
    error: Optional[str] = None
    attempts: list[str] = Field(default_factory=list)  # Track what was tried

    # Stats
    duration_seconds: float = 0.0
    cost_usd: float = 0.0
    from_cache: bool = False
```

2. **Create Abstract Base Classes** (`transcription/base.py`)
```python
from abc import ABC, abstractmethod
from typing import Optional

class Transcriber(ABC):
    """Abstract base class for transcription implementations"""

    @abstractmethod
    async def can_transcribe(self, url: str) -> bool:
        """Check if this transcriber can handle the given URL"""
        pass

    @abstractmethod
    async def transcribe(self, url: str, audio_path: Optional[Path] = None) -> Transcript:
        """Transcribe audio from URL or file path"""
        pass

    @abstractmethod
    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate cost in USD for transcribing given duration"""
        pass
```

3. **Write Comprehensive Tests** (`tests/unit/test_transcript_models.py`)
   - Test segment timing calculations
   - Test full_text concatenation
   - Test segment lookup by timestamp
   - Test serialization/deserialization
   - Test edge cases (empty segments, overlapping times)

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-2-day-2-data-models.md`
- Document model design decisions
- Explain why we chose certain field types
- Note any challenges in modeling transcript data
- Document test coverage achieved
- Link to relevant code

**Update**: `CLAUDE.md` (if needed)
- Add any new conventions for the transcription module

#### Success Criteria:
- All models defined with comprehensive type hints
- Models validated with Pydantic
- 100% test coverage for model logic
- Clear documentation of model usage
- Devlog captures design decisions

---

### Unit 3: YouTube Transcript Extraction

**Duration**: 3-4 hours
**Goal**: Implement YouTube transcript extraction with robust error handling

#### Tasks:

1. **Implement YouTubeTranscriber** (`transcription/youtube.py`)
```python
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
import re
from urllib.parse import urlparse, parse_qs

class YouTubeTranscriber(Transcriber):
    """Extract transcripts from YouTube videos"""

    def __init__(self, preferred_languages: list[str] = None):
        self.preferred_languages = preferred_languages or ["en"]

    async def can_transcribe(self, url: str) -> bool:
        """Check if URL is a YouTube video"""
        return self._is_youtube_url(url)

    def _is_youtube_url(self, url: str) -> bool:
        """Detect YouTube URLs (youtube.com, youtu.be)"""
        patterns = [
            r"youtube\.com/watch",
            r"youtu\.be/",
            r"youtube\.com/embed/",
        ]
        return any(re.search(pattern, url) for pattern in patterns)

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats"""
        # youtube.com/watch?v=VIDEO_ID
        parsed = urlparse(url)
        if "youtube.com" in parsed.netloc:
            query = parse_qs(parsed.query)
            if "v" in query:
                return query["v"][0]

        # youtu.be/VIDEO_ID
        if "youtu.be" in parsed.netloc:
            return parsed.path.strip("/")

        return None

    async def transcribe(self, url: str, audio_path: Optional[Path] = None) -> Transcript:
        """Fetch transcript from YouTube"""
        video_id = self._extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")

        try:
            # Fetch transcript list
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try to find preferred language
            transcript = None
            for lang in self.preferred_languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    break
                except NoTranscriptFound:
                    continue

            # Fallback to first available
            if not transcript:
                transcript = transcript_list.find_generated_transcript(self.preferred_languages)

            # Fetch transcript data
            transcript_data = transcript.fetch()

            # Convert to our model
            segments = [
                TranscriptSegment(
                    text=entry["text"],
                    start=entry["start"],
                    duration=entry["duration"],
                )
                for entry in transcript_data
            ]

            return Transcript(
                segments=segments,
                source="youtube",
                language=transcript.language_code,
                episode_url=url,
            )

        except TranscriptsDisabled:
            raise TranscriptionError(f"Transcripts disabled for video: {video_id}")
        except NoTranscriptFound:
            raise TranscriptionError(f"No transcript found for video: {video_id}")
        except VideoUnavailable:
            raise TranscriptionError(f"Video unavailable: {video_id}")

    def estimate_cost(self, duration_seconds: float) -> float:
        """YouTube transcripts are free"""
        return 0.0
```

2. **Error Handling**
   - Custom exceptions for each YouTube error type
   - Graceful degradation when transcript unavailable
   - Logging of failed attempts with context

3. **Write Comprehensive Tests** (`tests/unit/test_youtube_transcriber.py`)
   - Test URL detection (various formats)
   - Test video ID extraction
   - Mock successful transcript retrieval
   - Mock various error scenarios
   - Test language preference handling

4. **Integration Testing** (`tests/integration/test_youtube_real.py`)
   - Test with real public podcast on YouTube (pytest marker for slow tests)
   - Verify transcript quality
   - Document any issues found

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-2-day-3-youtube-transcriber.md`
- Document implementation approach
- Note challenges with URL parsing
- Document error scenarios discovered
- Show example transcript output
- Note test coverage achieved

**Create Lessons Learned**: `docs/lessons/2025-11-07-youtube-transcript-api-quirks.md`
- Document any surprising behavior
- Note edge cases discovered
- Best practices for YouTube URL handling
- Common errors and how to handle them

**Update Progress**: Document any experiments run during implementation

#### Success Criteria:
- YouTube transcriber fully functional
- Handles all common YouTube URL formats
- Graceful error handling for unavailable transcripts
- 95%+ test coverage
- Integration test passes with real podcast
- Comprehensive documentation of lessons learned

---

### Unit 4: Audio Download with yt-dlp

**Duration**: 3-4 hours
**Goal**: Robust audio extraction from podcast episodes

#### Tasks:

1. **Implement AudioDownloader** (`transcription/audio.py`)
```python
import yt_dlp
from pathlib import Path
import hashlib
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class AudioDownloader:
    """Download and process audio from podcast episodes"""

    def __init__(
        self,
        download_dir: Optional[Path] = None,
        format_preference: str = "m4a/bestaudio",
        max_file_size_mb: int = 500,
    ):
        self.download_dir = download_dir or self._get_temp_dir()
        self.format_preference = format_preference
        self.max_file_size_mb = max_file_size_mb

    def _get_temp_dir(self) -> Path:
        """Get temporary directory for audio files"""
        from inkwell.utils.paths import get_cache_dir
        temp_dir = get_cache_dir() / "audio"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

    def _generate_filename(self, url: str) -> str:
        """Generate deterministic filename from URL"""
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        return f"audio_{url_hash}.%(ext)s"

    async def download(
        self,
        url: str,
        auth: Optional[dict] = None,
    ) -> Path:
        """Download audio from URL"""

        output_template = str(self.download_dir / self._generate_filename(url))

        ydl_opts = {
            "format": self.format_preference,
            "outtmpl": output_template,
            "quiet": False,
            "no_warnings": False,
            "extract_audio": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "128",
            }],
        }

        # Add authentication if provided
        if auth:
            if auth.get("type") == "basic":
                ydl_opts["username"] = auth.get("username")
                ydl_opts["password"] = auth.get("password")
            elif auth.get("type") == "bearer":
                ydl_opts["http_headers"] = {
                    "Authorization": f"Bearer {auth.get('token')}"
                }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"Downloading audio from {url}")
                info = ydl.extract_info(url, download=True)

                # Get actual downloaded file path
                filename = ydl.prepare_filename(info)
                audio_path = Path(filename).with_suffix(".m4a")

                if not audio_path.exists():
                    raise AudioDownloadError(f"Downloaded file not found: {audio_path}")

                # Validate file size
                file_size_mb = audio_path.stat().st_size / (1024 * 1024)
                if file_size_mb > self.max_file_size_mb:
                    audio_path.unlink()  # Delete oversized file
                    raise AudioDownloadError(
                        f"Audio file too large: {file_size_mb:.1f}MB (max: {self.max_file_size_mb}MB)"
                    )

                logger.info(f"Downloaded audio: {audio_path} ({file_size_mb:.1f}MB)")
                return audio_path

        except yt_dlp.utils.DownloadError as e:
            raise AudioDownloadError(f"Failed to download audio: {e}")

    def cleanup(self, audio_path: Path) -> None:
        """Delete downloaded audio file"""
        if audio_path.exists():
            audio_path.unlink()
            logger.debug(f"Cleaned up audio file: {audio_path}")
```

2. **Progress Tracking**
   - Integrate with rich progress bars
   - Show download speed and ETA
   - Handle interrupted downloads

3. **Authentication Handling**
   - Support for basic auth and bearer tokens (from Phase 1)
   - Test with private podcast feeds

4. **Write Comprehensive Tests** (`tests/unit/test_audio_downloader.py`)
   - Mock yt_dlp calls
   - Test filename generation
   - Test file size validation
   - Test authentication integration
   - Test cleanup

5. **Integration Testing** (`tests/integration/test_audio_download_real.py`)
   - Test with real public podcast episode
   - Verify file format and integrity
   - Document download times

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-2-day-4-audio-download.md`
- Document yt-dlp integration challenges
- Explain format and codec choices
- Note authentication handling
- Document file size limits and rationale
- Show example downloads

**Create ADR**: `docs/adr/011-audio-format-selection.md`
- **Decision**: M4A format at 128kbps
- **Alternatives**: MP3, WAV, OPUS
- **Rationale**: Balance of quality, file size, Gemini compatibility
- **Consequences**: Need ffmpeg installed on system

**Create Lessons Learned**: `docs/lessons/2025-11-07-yt-dlp-integration.md`
- Document yt-dlp configuration gotchas
- Note ffmpeg requirements
- Best practices for error handling
- Performance optimization tips

#### Success Criteria:
- Can download audio from various podcast sources
- Handles authentication correctly
- File size limits enforced
- Progress tracking works
- Cleanup mechanism reliable
- 90%+ test coverage
- Integration test passes

---

### Unit 5: Gemini Transcription API Integration

**Duration**: 4-5 hours
**Goal**: Implement Gemini-based transcription with cost tracking

#### Tasks:

1. **Implement Gemini Client** (`api/gemini_client.py`)
```python
import google.generativeai as genai
from pathlib import Path
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class GeminiClient:
    """Wrapper for Google Gemini API"""

    # Gemini pricing (as of 2025)
    COST_PER_MINUTE = 0.01  # $0.01 per minute of audio

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name)

    async def transcribe_audio(
        self,
        audio_path: Path,
        language: str = "en",
    ) -> dict:
        """Transcribe audio file using Gemini"""

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Uploading audio to Gemini: {audio_path}")

        # Upload file
        audio_file = genai.upload_file(path=str(audio_path))

        # Wait for processing
        logger.info("Waiting for Gemini to process audio...")
        while audio_file.state.name == "PROCESSING":
            await asyncio.sleep(1)
            audio_file = genai.get_file(audio_file.name)

        if audio_file.state.name == "FAILED":
            raise GeminiError(f"Audio processing failed: {audio_file.state}")

        # Generate transcript
        prompt = f"""
        Transcribe the following audio file.

        Requirements:
        - Return only the transcript text
        - Do not add commentary or explanations
        - Preserve speaker changes if detectable
        - Include timestamps approximately every 30 seconds
        - Language: {language}

        Format timestamps as [MM:SS] at the start of each paragraph.
        """

        logger.info("Requesting transcription from Gemini...")
        response = self.model.generate_content([audio_file, prompt])

        # Clean up uploaded file
        genai.delete_file(audio_file.name)

        return {
            "text": response.text,
            "model": self.model_name,
        }

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate transcription cost"""
        minutes = duration_seconds / 60
        return minutes * self.COST_PER_MINUTE
```

2. **Implement GeminiTranscriber** (`transcription/gemini.py`)
```python
class GeminiTranscriber(Transcriber):
    """Transcribe audio using Gemini API"""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
        self.client = GeminiClient(api_key, model_name)

    async def can_transcribe(self, url: str) -> bool:
        """Gemini can transcribe any audio file"""
        return True  # Universal fallback

    async def transcribe(self, url: str, audio_path: Optional[Path] = None) -> Transcript:
        """Transcribe audio file"""

        if not audio_path or not audio_path.exists():
            raise ValueError("Gemini transcriber requires audio file path")

        # Get audio duration for cost estimation
        duration_seconds = self._get_audio_duration(audio_path)
        estimated_cost = self.estimate_cost(duration_seconds)

        logger.info(f"Transcribing {audio_path} (estimated cost: ${estimated_cost:.2f})")

        result = await self.client.transcribe_audio(audio_path)

        # Parse timestamps from Gemini output
        segments = self._parse_timestamps(result["text"])

        return Transcript(
            segments=segments,
            source="gemini",
            episode_url=url,
            duration_seconds=duration_seconds,
            cost_usd=estimated_cost,
        )

    def _parse_timestamps(self, text: str) -> list[TranscriptSegment]:
        """Parse [MM:SS] timestamps from Gemini output"""
        import re

        segments = []
        pattern = r'\[(\d+):(\d+)\]\s*(.+?)(?=\[\d+:\d+\]|$)'

        matches = re.finditer(pattern, text, re.DOTALL)

        for match in matches:
            minutes, seconds, segment_text = match.groups()
            start_seconds = int(minutes) * 60 + int(seconds)

            # Estimate duration until next segment (will be corrected by next segment)
            duration = 30.0  # Default 30 seconds

            segments.append(TranscriptSegment(
                text=segment_text.strip(),
                start=float(start_seconds),
                duration=duration,
            ))

        # Correct durations
        for i in range(len(segments) - 1):
            segments[i].duration = segments[i + 1].start - segments[i].start

        return segments

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds using ffprobe"""
        import subprocess

        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
             str(audio_path)],
            capture_output=True,
            text=True,
        )

        return float(result.stdout.strip())

    def estimate_cost(self, duration_seconds: float) -> float:
        return self.client.estimate_cost(duration_seconds)
```

3. **Cost Tracking**
   - Log all Gemini API calls with costs
   - Cumulative cost tracking per session
   - Warning when costs exceed threshold

4. **Write Comprehensive Tests** (`tests/unit/test_gemini_transcriber.py`)
   - Mock Gemini API calls
   - Test timestamp parsing
   - Test duration calculation
   - Test cost estimation
   - Test error handling

5. **Integration Testing** (`tests/integration/test_gemini_real.py`)
   - Test with real audio sample (short clip to minimize cost)
   - Verify transcript quality
   - Document actual vs estimated costs

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-2-day-5-gemini-transcriber.md`
- Document Gemini API integration
- Explain prompt engineering for transcription
- Show cost estimation formula
- Document timestamp parsing logic
- Note quality observations

**Create Research Document**: `docs/research/gemini-prompt-optimization.md`
- Document prompt iterations
- Show quality improvements from prompt changes
- Best practices for transcription prompts

**Create Lessons Learned**: `docs/lessons/2025-11-07-gemini-api-integration.md`
- Document API quirks
- Cost optimization strategies
- Error handling patterns
- Best practices for file uploads

**Create ADR**: `docs/adr/012-gemini-cost-management.md`
- **Decision**: Require user confirmation for high-cost transcriptions
- **Threshold**: Warn if estimated cost > $1.00
- **Rationale**: Prevent unexpected API bills
- **Consequences**: Extra prompt for long episodes

#### Success Criteria:
- Gemini transcriber functional
- Accurate cost estimation
- Quality transcripts produced
- Timestamp parsing works
- 90%+ test coverage
- Integration test validates quality
- Cost tracking implemented

---

### Unit 6: Transcript Caching System

**Duration**: 2-3 hours
**Goal**: Implement intelligent caching to avoid redundant API calls

#### Tasks:

1. **Implement TranscriptCache** (`transcription/cache.py`)
```python
import hashlib
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class TranscriptCache:
    """Cache transcripts to avoid redundant transcription"""

    def __init__(self, cache_dir: Optional[Path] = None, ttl_days: int = 30):
        self.cache_dir = cache_dir or self._get_cache_dir()
        self.ttl_days = ttl_days
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_dir(self) -> Path:
        from inkwell.utils.paths import get_cache_dir
        return get_cache_dir() / "transcripts"

    def _generate_cache_key(self, episode_url: str) -> str:
        """Generate cache key from episode URL"""
        return hashlib.sha256(episode_url.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get path to cached transcript file"""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, episode_url: str) -> Optional[Transcript]:
        """Retrieve cached transcript if available and fresh"""
        cache_key = self._generate_cache_key(episode_url)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            logger.debug(f"Cache miss for {episode_url}")
            return None

        try:
            data = json.loads(cache_path.read_text())
            transcript = Transcript(**data)

            # Check if cache is still valid
            age = datetime.utcnow() - transcript.created_at
            if age > timedelta(days=self.ttl_days):
                logger.info(f"Cache expired for {episode_url} (age: {age.days} days)")
                cache_path.unlink()
                return None

            logger.info(f"Cache hit for {episode_url} (source: {transcript.source})")
            return transcript

        except Exception as e:
            logger.warning(f"Failed to load cached transcript: {e}")
            cache_path.unlink()  # Delete corrupted cache
            return None

    def set(self, episode_url: str, transcript: Transcript) -> None:
        """Cache transcript"""
        cache_key = self._generate_cache_key(episode_url)
        cache_path = self._get_cache_path(cache_key)

        try:
            cache_path.write_text(transcript.model_dump_json(indent=2))
            logger.info(f"Cached transcript for {episode_url}")
        except Exception as e:
            logger.error(f"Failed to cache transcript: {e}")

    def invalidate(self, episode_url: str) -> bool:
        """Remove cached transcript"""
        cache_key = self._generate_cache_key(episode_url)
        cache_path = self._get_cache_path(cache_key)

        if cache_path.exists():
            cache_path.unlink()
            logger.info(f"Invalidated cache for {episode_url}")
            return True
        return False

    def clear_expired(self) -> int:
        """Remove all expired cached transcripts"""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(cache_file.read_text())
                created_at = datetime.fromisoformat(data["created_at"])
                age = datetime.utcnow() - created_at

                if age > timedelta(days=self.ttl_days):
                    cache_file.unlink()
                    count += 1
            except Exception:
                # Delete corrupted cache files
                cache_file.unlink()
                count += 1

        logger.info(f"Cleared {count} expired cached transcripts")
        return count
```

2. **Cache Management CLI Commands**
   - `inkwell cache list` - Show cached transcripts
   - `inkwell cache clear` - Clear all cache
   - `inkwell cache stats` - Show cache statistics

3. **Write Comprehensive Tests** (`tests/unit/test_transcript_cache.py`)
   - Test cache hit/miss
   - Test TTL expiration
   - Test cache invalidation
   - Test corrupted cache handling
   - Test cache cleanup

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-2-day-6-caching.md`
- Document cache design
- Explain TTL strategy
- Show cache performance gains
- Document cache management commands

**Create Lessons Learned**: `docs/lessons/2025-11-07-cache-invalidation.md`
- Document cache invalidation strategies
- Best practices for cache key generation
- Handling corrupted cache files

#### Success Criteria:
- Cache working correctly
- TTL enforcement works
- Cache CLI commands functional
- 95%+ test coverage
- Documentation complete

---

### Unit 7: Transcription Manager (Orchestrator)

**Duration**: 3-4 hours
**Goal**: High-level orchestration of the multi-tier transcription strategy

#### Tasks:

1. **Implement TranscriptionManager** (`transcription/manager.py`)
```python
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class TranscriptionManager:
    """Orchestrate multi-tier transcription strategy"""

    def __init__(
        self,
        gemini_api_key: str,
        cache_enabled: bool = True,
        cache_ttl_days: int = 30,
    ):
        self.youtube_transcriber = YouTubeTranscriber()
        self.gemini_transcriber = GeminiTranscriber(gemini_api_key)
        self.audio_downloader = AudioDownloader()

        self.cache = TranscriptCache(ttl_days=cache_ttl_days) if cache_enabled else None

    async def transcribe(
        self,
        episode_url: str,
        auth: Optional[dict] = None,
        force_refresh: bool = False,
    ) -> TranscriptionResult:
        """Transcribe episode using multi-tier strategy"""

        attempts = []

        # Check cache first
        if self.cache and not force_refresh:
            cached = self.cache.get(episode_url)
            if cached:
                logger.info(f"Using cached transcript (source: {cached.source})")
                return TranscriptionResult(
                    success=True,
                    transcript=cached,
                    attempts=["cache"],
                    from_cache=True,
                )

        # Strategy 1: Try YouTube transcript (free, fast)
        if await self.youtube_transcriber.can_transcribe(episode_url):
            try:
                logger.info("Attempting YouTube transcript extraction...")
                transcript = await self.youtube_transcriber.transcribe(episode_url)
                attempts.append("youtube")

                # Cache success
                if self.cache:
                    self.cache.set(episode_url, transcript)

                return TranscriptionResult(
                    success=True,
                    transcript=transcript,
                    attempts=attempts,
                )

            except TranscriptionError as e:
                logger.warning(f"YouTube transcription failed: {e}")
                attempts.append("youtube_failed")

        # Strategy 2: Download audio and use Gemini (costs money, slower)
        try:
            logger.info("Falling back to audio download + Gemini transcription...")

            # Download audio
            audio_path = await self.audio_downloader.download(episode_url, auth)
            attempts.append("audio_download")

            # Estimate cost
            duration = self.gemini_transcriber._get_audio_duration(audio_path)
            cost = self.gemini_transcriber.estimate_cost(duration)

            logger.warning(f"Gemini transcription will cost approximately ${cost:.2f}")

            # Transcribe with Gemini
            transcript = await self.gemini_transcriber.transcribe(episode_url, audio_path)
            attempts.append("gemini")

            # Cleanup audio file
            self.audio_downloader.cleanup(audio_path)

            # Cache success
            if self.cache:
                self.cache.set(episode_url, transcript)

            return TranscriptionResult(
                success=True,
                transcript=transcript,
                attempts=attempts,
                duration_seconds=duration,
                cost_usd=cost,
            )

        except Exception as e:
            logger.error(f"Gemini transcription failed: {e}")
            attempts.append("gemini_failed")

            # Cleanup on failure
            if audio_path and audio_path.exists():
                self.audio_downloader.cleanup(audio_path)

            return TranscriptionResult(
                success=False,
                error=str(e),
                attempts=attempts,
            )
```

2. **Add User Confirmation for Costly Operations**
```python
def confirm_transcription_cost(cost: float, duration: float) -> bool:
    """Prompt user to confirm expensive transcription"""
    if cost < 1.0:
        return True  # Auto-approve small costs

    from rich.console import Console
    console = Console()

    console.print(f"\n[yellow]⚠️  Transcription Cost Warning[/yellow]")
    console.print(f"Duration: {duration / 60:.1f} minutes")
    console.print(f"Estimated cost: ${cost:.2f}")
    console.print()

    response = Prompt.ask(
        "Continue with Gemini transcription?",
        choices=["y", "n"],
        default="n",
    )

    return response == "y"
```

3. **Write Comprehensive Tests** (`tests/unit/test_transcription_manager.py`)
   - Test strategy fallback logic
   - Test cache integration
   - Test cost confirmation flow
   - Test error handling at each tier
   - Mock all external dependencies

4. **Integration Testing** (`tests/integration/test_full_transcription.py`)
   - End-to-end test with real podcast
   - Test both YouTube and Gemini paths
   - Verify caching works
   - Document performance

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-2-day-7-orchestration.md`
- Document orchestration logic
- Explain fallback strategy
- Show decision flow diagram
- Document cost confirmation UX
- Note integration test results

**Create Lessons Learned**: `docs/lessons/2025-11-07-transcription-orchestration.md`
- Document multi-tier strategy lessons
- Best practices for fallback logic
- Error handling patterns
- User experience considerations

#### Success Criteria:
- Orchestration logic working
- All fallback scenarios handled
- Cost confirmation working
- Cache integration seamless
- 95%+ test coverage
- Integration test passes
- Documentation complete

---

### Unit 8: CLI Integration & User Experience

**Duration**: 2-3 hours
**Goal**: Expose transcription functionality through CLI with great UX

#### Tasks:

1. **Add Transcription Command** (`cli.py`)
```python
@app.command()
def transcribe(
    url: str = typer.Argument(..., help="Episode URL or feed name"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path for transcript"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip cache, force re-transcription"),
    format: str = typer.Option("text", "--format", help="Output format (text, json, srt)"),
) -> None:
    """Transcribe a podcast episode"""

    from rich.progress import Progress, SpinnerColumn, TextColumn
    from inkwell.transcription.manager import TranscriptionManager
    from inkwell.config.manager import ConfigManager

    config_manager = ConfigManager()
    config = config_manager.load_config()

    # Get Gemini API key
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        console.print("[red]Error: GEMINI_API_KEY not set[/red]")
        console.print("Set it with: export GEMINI_API_KEY=your-key")
        raise typer.Exit(1)

    manager = TranscriptionManager(gemini_api_key)

    # Show progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Transcribing...", total=None)

        result = asyncio.run(manager.transcribe(url, force_refresh=force))

    if result.success:
        console.print(f"\n[green]✓[/green] Transcription complete!")
        console.print(f"Source: {result.transcript.source}")
        console.print(f"Duration: {result.transcript.total_duration}")
        console.print(f"Segments: {len(result.transcript.segments)}")

        if result.cost_usd > 0:
            console.print(f"Cost: ${result.cost_usd:.2f}")

        # Save output
        if output:
            if format == "json":
                output.write_text(result.transcript.model_dump_json(indent=2))
            elif format == "srt":
                output.write_text(_format_as_srt(result.transcript))
            else:  # text
                output.write_text(result.transcript.full_text)

            console.print(f"\nSaved to: {output}")
        else:
            # Print to stdout
            console.print("\n" + "=" * 80)
            console.print(result.transcript.full_text)
    else:
        console.print(f"[red]✗[/red] Transcription failed: {result.error}")
        console.print(f"Attempts: {', '.join(result.attempts)}")
        raise typer.Exit(1)
```

2. **Add Output Formatters**
   - Plain text format
   - JSON format (full Transcript model)
   - SRT subtitle format
   - Markdown format with timestamps

3. **Add Progress Indicators**
   - Spinner for YouTube API calls
   - Progress bar for audio downloads
   - Status updates during Gemini transcription

4. **Write CLI Tests** (`tests/integration/test_cli_transcribe.py`)
   - Test transcribe command with various options
   - Test output formats
   - Test error scenarios
   - Verify progress indicators

#### Documentation Tasks:

**Create Devlog Entry**: `docs/devlog/2025-11-07-phase-2-day-8-cli-integration.md`
- Document CLI design decisions
- Show usage examples
- Document output formats
- Note UX improvements

**Update USER_GUIDE.md**
- Add transcription command documentation
- Show examples with different options
- Document output formats
- Add troubleshooting section

#### Success Criteria:
- CLI command fully functional
- All output formats working
- Progress indicators smooth
- Error messages helpful
- Integration tests pass
- User guide updated

---

### Unit 9: Testing, Polish & Documentation

**Duration**: 3-4 hours
**Goal**: Comprehensive testing, edge case handling, and documentation completion

#### Tasks:

1. **Comprehensive Test Suite Review**
   - Ensure 90%+ test coverage across all modules
   - Add missing edge case tests
   - Fix any flaky tests
   - Add performance benchmarks

2. **Error Handling Review**
   - Audit all error paths
   - Ensure helpful error messages
   - Add retry logic where appropriate
   - Test network failure scenarios

3. **Performance Optimization**
   - Profile slow operations
   - Add caching where beneficial
   - Optimize file I/O
   - Document performance characteristics

4. **Documentation Polish**
   - Review all docstrings
   - Update README with transcription examples
   - Create architecture diagram
   - Document API usage examples

5. **Manual End-to-End Testing**
   - Test with 5-10 different podcast episodes
   - Test various failure scenarios
   - Verify cache behavior
   - Document any issues found

#### Documentation Tasks:

**Create Final Phase 2 Summary**: `docs/PHASE_2_COMPLETE.md`
- Overview of what was built
- Statistics (code lines, tests, coverage)
- Key achievements
- Known limitations
- What's next (Phase 3)

**Create Comprehensive Lessons Document**: `docs/lessons/2025-11-07-phase-2-complete.md`
- Aggregate all lessons from Phase 2
- Top insights and takeaways
- Patterns to repeat
- Patterns to avoid
- Recommendations for Phase 3

**Update CLAUDE.md**
- Add transcription module conventions
- Document testing patterns
- Update architecture overview

**Create Architecture Diagram**: `docs/architecture/phase-2-transcription.md`
- Visual diagram of transcription flow
- Component interactions
- Data flow diagrams
- Decision trees

#### Success Criteria:
- 90%+ test coverage
- All tests passing
- No critical bugs
- Documentation complete
- Manual testing validated
- Ready for Phase 3

---

## Quality Gates

### Phase 2 is Complete When:

**Functionality:**
- [ ] YouTube transcript extraction working
- [ ] Audio download with yt-dlp working
- [ ] Gemini transcription working
- [ ] Multi-tier fallback strategy working
- [ ] Caching system working
- [ ] CLI commands functional
- [ ] Multiple output formats supported

**Code Quality:**
- [ ] 90%+ test coverage
- [ ] All tests passing
- [ ] No mypy errors
- [ ] No ruff warnings
- [ ] Pre-commit hooks passing

**User Experience:**
- [ ] Progress indicators smooth
- [ ] Clear error messages
- [ ] Cost warnings for expensive operations
- [ ] Help text comprehensive
- [ ] Works with real podcasts

**Documentation:**
- [ ] All ADRs created
- [ ] All devlogs written
- [ ] Lessons learned documented
- [ ] Research docs complete
- [ ] Experiments documented
- [ ] User guide updated
- [ ] Architecture diagrams created
- [ ] PHASE_2_COMPLETE.md written

**Performance:**
- [ ] YouTube transcription < 10 seconds
- [ ] Audio download appropriate for file size
- [ ] Gemini transcription performance documented
- [ ] Cache provides measurable speedup

---

## Architecture Decision Records to Create

1. **ADR-009: Transcription Strategy** (Multi-tier: YouTube → Gemini)
2. **ADR-010: Transcript Caching** (File-based JSON cache)
3. **ADR-011: Audio Format Selection** (M4A at 128kbps)
4. **ADR-012: Gemini Cost Management** (User confirmation for high costs)
5. **ADR-013: Timestamp Preservation** (Why we keep timestamps in transcripts)

---

## Research Documents to Create

1. **Transcription APIs Comparison** (YouTube vs Gemini vs alternatives)
2. **yt-dlp Audio Extraction** (Best practices and benchmarks)
3. **Gemini Prompt Optimization** (Prompt engineering for transcription)
4. **Cache Invalidation Strategies** (TTL vs manual invalidation)

---

## Experiments to Document

1. **YouTube Transcript Availability** (Availability rate across podcasts)
2. **Gemini Transcription Quality** (Accuracy vs cost vs latency)
3. **Audio Format Optimization** (Quality vs file size trade-offs)
4. **Cache Performance Impact** (Speed improvement from caching)

---

## Lessons Learned Documents to Create

1. **YouTube Transcript API Quirks** (Edge cases and gotchas)
2. **yt-dlp Integration** (Configuration and error handling)
3. **Gemini API Integration** (Best practices and cost optimization)
4. **Cache Invalidation** (Strategies and trade-offs)
5. **Transcription Orchestration** (Multi-tier fallback logic)
6. **Phase 2 Complete** (Aggregate lessons from entire phase)

---

## Devlog Entries to Create

1. **Phase 2 Day 1: Research** (Initial research and planning)
2. **Phase 2 Day 2: Data Models** (Transcript models and abstractions)
3. **Phase 2 Day 3: YouTube Transcriber** (YouTube integration)
4. **Phase 2 Day 4: Audio Download** (yt-dlp integration)
5. **Phase 2 Day 5: Gemini Transcriber** (Gemini API integration)
6. **Phase 2 Day 6: Caching** (Cache implementation)
7. **Phase 2 Day 7: Orchestration** (TranscriptionManager)
8. **Phase 2 Day 8: CLI Integration** (User-facing commands)
9. **Phase 2 Day 9: Testing & Polish** (Final testing and documentation)

---

## Success Metrics

**Code Metrics:**
- Production code: ~1,500-2,000 lines
- Test code: ~2,000-2,500 lines
- Documentation: ~3,000-4,000 lines
- Test coverage: 90%+

**Functional Metrics:**
- YouTube transcription success rate: 70%+
- Gemini transcription success rate: 95%+
- Cache hit rate (repeat episodes): 100%
- Average transcription time: < 2 minutes per hour of audio

**Documentation Metrics:**
- 5+ ADRs created
- 9+ devlog entries
- 6+ lessons learned documents
- 4+ research documents
- 4+ experiment logs

---

## Timeline Estimate

**Total Duration**: 8-10 days

- Unit 1 (Research): 0.5 days
- Unit 2 (Data Models): 0.5 days
- Unit 3 (YouTube): 1 day
- Unit 4 (Audio Download): 1 day
- Unit 5 (Gemini): 1.5 days
- Unit 6 (Caching): 0.5 days
- Unit 7 (Orchestration): 1 day
- Unit 8 (CLI): 0.5 days
- Unit 9 (Testing & Docs): 1 day
- Buffer: 1.5 days

---

## Dependencies & Prerequisites

**System Requirements:**
- ffmpeg (for audio processing)
- Python 3.10+
- Internet connection for API calls

**API Keys:**
- Google AI (Gemini) API key - Required
- YouTube Data API (optional, for quota management)

**Python Dependencies (to add to pyproject.toml):**
```toml
dependencies = [
    # ... existing ...
    "youtube-transcript-api>=0.6.0",
    "yt-dlp>=2024.0.0",
    "google-generativeai>=0.3.0",
]
```

---

## Risk Mitigation

**Risk**: YouTube transcript availability lower than expected
**Mitigation**: Gemini fallback handles this gracefully

**Risk**: Gemini API costs higher than expected
**Mitigation**: Cost confirmation prompt, caching, user warnings

**Risk**: Audio download failures with private feeds
**Mitigation**: Robust auth handling from Phase 1, detailed error messages

**Risk**: Transcript quality issues
**Mitigation**: Manual review of sample outputs, prompt optimization

**Risk**: Network failures during long operations
**Mitigation**: Retry logic, progress persistence, graceful degradation

---

## What Comes After Phase 2

**Phase 3: LLM Extraction Pipeline**
- Template-based content extraction
- Quote extraction
- Key concept identification
- Summary generation
- Category-specific templates

**Phase 4: Interview Mode**
- Claude Agent SDK integration
- Interactive Q&A
- Personal notes generation

**Phase 5: Obsidian Integration**
- Frontmatter generation
- Wikilink creation
- Tag generation

---

## Notes for Implementation

1. **Documentation is Not Optional**: After each unit, stop and document. This is not "extra work"—it's core work that makes the project accessible and maintainable.

2. **Test as You Go**: Write tests during implementation, not after. Tests document behavior and catch bugs immediately.

3. **Cost Awareness**: Gemini API calls cost money. Always show cost estimates to users before proceeding.

4. **User Experience First**: Progress indicators, helpful errors, and clear messaging are not polish—they're core functionality.

5. **Cache Aggressively**: Transcription is expensive (time and money). Caching is critical for good UX.

6. **Fail Gracefully**: Network issues, API failures, and missing transcripts are normal. Handle them with helpful messages.

7. **Manual Testing Matters**: Automated tests verify correctness, but manual testing with real podcasts verifies UX and reveals edge cases.

---

## Getting Started

Once this plan is approved, we'll proceed with:

1. **Unit 1**: Research phase (library testing, API exploration, experiments)
2. **Documentation**: Create initial ADRs and research documents
3. **Unit 2**: Implement data models with comprehensive tests
4. **Continue**: Follow the unit-by-unit plan with documentation at each step

The detailed plan ensures we build Phase 2 with the same quality and rigor as Phase 1, with even stronger emphasis on documentation accessibility.

---

**Ready to begin Phase 2 implementation! 🚀**
