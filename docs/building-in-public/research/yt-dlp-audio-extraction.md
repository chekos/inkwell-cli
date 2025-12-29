# Research: yt-dlp Audio Extraction Best Practices

**Date**: 2025-11-07
**Author**: Claude (Phase 2 Research)
**Status**: Complete

## Overview

Research on using yt-dlp for downloading podcast audio from various sources, optimizing for transcription quality and Gemini API compatibility.

---

## yt-dlp Overview

**yt-dlp** is a feature-rich command-line audio/video downloader forked from youtube-dl, with better performance and more features.

### Key Features
- ✅ **Universal** - Supports 1000+ websites
- ✅ **Audio extraction** - Built-in audio-only mode
- ✅ **Format conversion** - Integrated FFmpeg support
- ✅ **Authentication** - HTTP basic auth, cookies, bearer tokens
- ✅ **Resumable** - Can resume interrupted downloads
- ✅ **Metadata** - Extracts episode info, duration, etc.

---

## Audio Format Optimization

### Formats Tested (Conceptual Analysis)

| Format | Codec | Bitrate | File Size (1hr) | Gemini Compatible | Quality | Recommendation |
|--------|-------|---------|-----------------|-------------------|---------|----------------|
| M4A | AAC | 128kbps | ~58MB | ✅ Yes | Excellent | **Recommended** |
| MP3 | MP3 | 128kbps | ~58MB | ✅ Yes | Good | Alternative |
| OPUS | Opus | 64kbps | ~29MB | ⚠️ Maybe | Excellent | Future consideration |
| WAV | PCM | 1411kbps | ~605MB | ✅ Yes | Perfect | Too large |

### Decision: M4A at 128kbps AAC

**Rationale**:
1. **Quality vs Size**: 128kbps AAC provides excellent speech intelligibility
2. **Gemini Compatibility**: M4A/AAC explicitly supported by Gemini
3. **Ecosystem**: Native Apple format, widely compatible
4. **Efficiency**: AAC more efficient than MP3 at same bitrate

**Trade-offs**:
- Slightly larger than OPUS (64kbps would halve size)
- Not as universally compatible as MP3
- But: Speech-optimized, good balance point

---

## yt-dlp Configuration

### Optimal Settings for Podcast Audio

```python
ydl_opts = {
    # Audio extraction
    "format": "bestaudio/best",  # Prefer audio-only streams
    "extract_audio": True,

    # Post-processing with FFmpeg
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "m4a",
        "preferredquality": "128",  # 128kbps AAC
    }],

    # Output
    "outtmpl": "%(id)s.%(ext)s",  # Filename template

    # Quality/Performance
    "quiet": False,
    "no_warnings": False,
    "retries": 3,
    "fragment_retries": 3,

    # Metadata
    "writeinfojson": False,  # Don't need JSON metadata
    "writethumbnail": False,  # Don't need artwork
}
```

### Authentication Support

yt-dlp handles various auth methods:

```python
# HTTP Basic Auth
ydl_opts["username"] = "user@example.com"
ydl_opts["password"] = "secret"

# Bearer Token
ydl_opts["http_headers"] = {
    "Authorization": f"Bearer {token}"
}

# Custom Headers
ydl_opts["http_headers"] = {
    "Cookie": "session=abc123",
    "User-Agent": "Mozilla/5.0...",
}
```

---

## Performance Characteristics

### Download Speed
- **Depends on**: Source bandwidth, network speed
- **Typical**: 5-10 MB/s for podcasts
- **Time estimate**:
  - 30-minute episode (~25MB): 5-30 seconds
  - 60-minute episode (~50MB): 10-60 seconds
  - 120-minute episode (~100MB): 20-120 seconds

### FFmpeg Conversion
- **Negligible** for audio-only (< 5 seconds for 1-hour episode)
- **CPU-bound** but very fast
- **Memory**: Low overhead (< 100MB)

---

## Error Scenarios & Handling

### Common Errors

#### 1. Unsupported URL
```
ERROR: Unsupported URL: http://example.com/podcast.mp3
```
**Cause**: URL not recognized by yt-dlp extractors
**Solution**: May be a direct audio file, try direct HTTP download

#### 2. Geo-restricted Content
```
ERROR: This video is not available in your country
```
**Cause**: Geographic restrictions
**Solution**: Inform user, potentially offer proxy option (future)

#### 3. Authentication Required
```
ERROR: This video is only available for registered users
```
**Cause**: Private content needing auth
**Solution**: Prompt for credentials if not configured

#### 4. File Too Large
```
Filesize: 500MB (max: 200MB)
```
**Cause**: Very long episode
**Solution**: Warn user, allow override, or split (future feature)

---

## Integration with Phase 1

### Using Stored Credentials

From Phase 1, we have encrypted credentials stored per feed. Integration:

```python
from inkwell.config.manager import ConfigManager

config_manager = ConfigManager()
feed_config = config_manager.get_feed("my-podcast")

# Build yt-dlp options with decrypted auth
if feed_config.auth.type == "basic":
    ydl_opts["username"] = feed_config.auth.username  # Auto-decrypted
    ydl_opts["password"] = feed_config.auth.password

elif feed_config.auth.type == "bearer":
    ydl_opts["http_headers"] = {
        "Authorization": f"Bearer {feed_config.auth.token}"
    }
```

---

## File Management

### Temporary Storage Strategy

**Location**: `~/.cache/inkwell/audio/` (XDG cache directory)

**Lifecycle**:
1. Download audio to cache
2. Transcribe with Gemini
3. Delete audio file immediately after
4. Keep only transcripts (in separate cache)

**Why Not Keep Audio**:
- Large files (50-100MB each)
- Not needed after transcription
- Privacy: users may not want audio stored
- Transcripts are much smaller (< 1MB typically)

### Cleanup Strategy

```python
# After successful transcription
audio_path.unlink()  # Delete immediately

# Periodic cleanup (startup, or scheduled)
cache_dir = get_cache_dir() / "audio"
for audio_file in cache_dir.glob("*.m4a"):
    # Delete files older than 24 hours
    if (time.time() - audio_file.stat().st_mtime) > 86400:
        audio_file.unlink()
```

---

## File Size Validation

### Limits

**Maximum file size**: 500MB (Gemini limit is higher, but protect users)

**Rationale**:
- Typical 60-min podcast at 128kbps: ~58MB
- 500MB = ~9 hours of audio
- Catches errors (wrong URL, video instead of audio)
- Reasonable limit for free tier

**Validation**:
```python
file_size_mb = audio_path.stat().st_size / (1024 * 1024)
if file_size_mb > 500:
    audio_path.unlink()  # Delete oversized file
    raise AudioDownloadError(
        f"Audio file too large: {file_size_mb:.1f}MB "
        f"(max: 500MB). This may be a video file instead of audio."
    )
```

---

## Progress Indicators

### Rich Progress Bar Integration

```python
from rich.progress import Progress, DownloadColumn, TransferSpeedColumn

with Progress(
    TextColumn("[bold blue]{task.description}"),
    BarColumn(),
    DownloadColumn(),
    TransferSpeedColumn(),
    TimeRemainingColumn(),
) as progress:
    task = progress.add_task("Downloading audio...", total=100)

    # yt-dlp progress hook
    def progress_hook(d):
        if d['status'] == 'downloading':
            progress.update(task, completed=d.get('downloaded_bytes', 0))

    ydl_opts['progress_hooks'] = [progress_hook]
```

---

## Dependencies

### System Requirements

**Required**: FFmpeg
- Install: `sudo apt install ffmpeg` (Linux) or `brew install ffmpeg` (macOS)
- Version: Any recent version (4.0+)
- Used for: Audio extraction and format conversion

**Python Dependencies**:
```toml
dependencies = [
    "yt-dlp>=2024.0.0",
]
```

### FFmpeg Check

```python
import subprocess

def check_ffmpeg_installed() -> bool:
    """Check if FFmpeg is available."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
```

---

## Best Practices

### 1. Use Deterministic Filenames
Generate from URL hash to enable resume/dedup:
```python
import hashlib
url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
filename = f"audio_{url_hash}.m4a"
```

### 2. Always Set Timeout
Prevent hanging downloads:
```python
ydl_opts["socket_timeout"] = 30  # seconds
```

### 3. Handle Partial Downloads
yt-dlp creates `.part` files during download:
```python
# Clean up failed downloads
for part_file in cache_dir.glob("*.part"):
    if part_file.stat().st_mtime < time.time() - 3600:  # 1 hour old
        part_file.unlink()
```

### 4. Validate Audio Duration
Ensure downloaded file matches expected duration:
```python
def get_audio_duration(path: Path) -> float:
    """Get audio duration using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
         str(path)],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())
```

---

## Security Considerations

### 1. Validate URLs
Never blindly download from user-provided URLs:
```python
from urllib.parse import urlparse

def is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ["http", "https"]
```

### 2. Sanitize Filenames
yt-dlp handles this, but validate:
```python
def sanitize_filename(filename: str) -> str:
    # Remove dangerous characters
    return re.sub(r'[^\w\-_.]', '_', filename)
```

### 3. Resource Limits
Set download size limits to prevent abuse:
```python
ydl_opts["max_filesize"] = 500 * 1024 * 1024  # 500MB
```

---

## Testing Strategy

### Unit Tests
- Mock yt-dlp calls with `unittest.mock`
- Test filename generation
- Test auth header construction
- Test error handling

### Integration Tests
- Download sample public podcast
- Verify file format and size
- Validate audio duration
- Test cleanup mechanism

### Manual Tests
- Private podcast with auth
- Various podcast sources (YouTube, Substack, etc.)
- Large files (>100MB)
- Network interruption handling

---

## Known Limitations

1. **Site Support**: While yt-dlp supports 1000+ sites, some may fail
2. **DRM Content**: Cannot download DRM-protected audio
3. **JavaScript Required**: Some sites need browser emulation (not implemented)
4. **Rate Limiting**: Some sources may rate-limit or block
5. **Format Changes**: Websites change formats, yt-dlp needs updates

---

## Recommendations

### For Phase 2 (v0.2)
1. ✅ Use M4A format at 128kbps AAC
2. ✅ Integrate with Phase 1 authentication
3. ✅ Implement file size validation
4. ✅ Add progress indicators
5. ✅ Immediate cleanup after transcription

### For Future Versions
- **v0.3+**: Resume interrupted downloads
- **v0.4+**: Parallel downloads for batch processing
- **v0.5+**: Audio quality validation
- **v0.6+**: Bandwidth throttling option

---

## References

- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [AAC Audio Codec](https://en.wikipedia.org/wiki/Advanced_Audio_Coding)
- [Phase 2 Implementation Plan](../devlog/2025-11-07-phase-2-detailed-plan.md)

---

## Conclusion

yt-dlp is the ideal tool for downloading podcast audio:
- **Universal** compatibility with sources
- **Efficient** audio extraction with FFmpeg
- **Authenticated** access for private feeds
- **Reliable** with good error handling

The M4A/AAC format at 128kbps provides the best balance of quality, compatibility, and file size for our transcription pipeline.

**Decision**: Proceed with yt-dlp + M4A/128kbps AAC as designed. ✅
