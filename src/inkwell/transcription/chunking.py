"""Audio chunking for long transcriptions.

Splits long audio files into overlapping chunks for transcription,
then merges the results back together.
"""

import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Chunking configuration
CHUNK_DURATION_SECONDS = 600  # 10 minutes per chunk
OVERLAP_SECONDS = 30  # 30-second overlap between chunks
MIN_DURATION_FOR_CHUNKING = 900  # Only chunk files > 15 minutes


def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using ffprobe.

    Args:
        audio_path: Path to audio file

    Returns:
        Duration in seconds

    Raises:
        RuntimeError: If ffprobe fails
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except FileNotFoundError as e:
        raise RuntimeError("ffprobe not found - install ffmpeg") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr}") from e
    except ValueError as e:
        raise RuntimeError(f"Could not parse duration: {e}") from e


def split_audio_into_chunks(
    audio_path: Path,
    chunk_duration: int = CHUNK_DURATION_SECONDS,
    overlap: int = OVERLAP_SECONDS,
    output_dir: Path | None = None,
) -> list[Path]:
    """Split audio file into overlapping chunks using ffmpeg.

    Args:
        audio_path: Path to source audio file
        chunk_duration: Duration of each chunk in seconds (default: 600 = 10 min)
        overlap: Overlap between chunks in seconds (default: 30)
        output_dir: Directory for chunk files (default: temp directory)

    Returns:
        List of paths to chunk files in order

    Example:
        For a 25-minute audio with 10-min chunks and 30s overlap:
        - Chunk 0: 0:00 - 10:00
        - Chunk 1: 9:30 - 19:30
        - Chunk 2: 19:00 - 25:00
    """
    duration = get_audio_duration(audio_path)

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="inkwell_chunks_"))
    output_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[Path] = []
    start = 0.0
    chunk_idx = 0
    step = chunk_duration - overlap  # Move forward by chunk_duration minus overlap

    while start < duration:
        # Calculate end time (don't exceed total duration)
        end = min(start + chunk_duration, duration)
        actual_duration = end - start

        # Generate chunk filename
        chunk_path = output_dir / f"chunk_{chunk_idx:03d}{audio_path.suffix}"

        logger.info(
            f"Creating chunk {chunk_idx}: {start:.1f}s - {end:.1f}s "
            f"(duration: {actual_duration:.1f}s)"
        )

        # Use ffmpeg to extract chunk
        # -ss before -i for fast seeking, -t for duration
        subprocess.run(
            [
                "ffmpeg",
                "-y",  # Overwrite output
                "-ss",
                str(start),  # Start time
                "-i",
                str(audio_path),  # Input file
                "-t",
                str(actual_duration),  # Duration
                "-c",
                "copy",  # Copy codec (fast, no re-encoding)
                "-avoid_negative_ts",
                "make_zero",  # Fix timestamp issues
                str(chunk_path),
            ],
            capture_output=True,
            check=True,
        )

        chunks.append(chunk_path)

        # Move to next chunk start position
        start += step
        chunk_idx += 1

        # Safety check: if we're very close to the end, stop
        if duration - start < overlap:
            break

    logger.info(f"Split audio into {len(chunks)} chunks")
    return chunks


def needs_chunking(audio_path: Path, threshold: int = MIN_DURATION_FOR_CHUNKING) -> bool:
    """Check if audio file needs to be chunked.

    Args:
        audio_path: Path to audio file
        threshold: Duration threshold in seconds (default: 900 = 15 min)

    Returns:
        True if audio is longer than threshold
    """
    try:
        duration = get_audio_duration(audio_path)
        needs_it = duration > threshold
        logger.debug(
            f"Audio duration: {duration:.1f}s ({duration/60:.1f} min), "
            f"threshold: {threshold}s, needs_chunking: {needs_it}"
        )
        return needs_it
    except RuntimeError as e:
        # Log the failure - this can cause transcripts to be truncated!
        logger.warning(
            f"Failed to determine audio duration for {audio_path}: {e}. "
            f"Skipping chunking - transcript may be incomplete for long audio."
        )
        return False


def cleanup_chunks(chunk_paths: list[Path]) -> None:
    """Remove temporary chunk files.

    Args:
        chunk_paths: List of chunk file paths to remove
    """
    for chunk_path in chunk_paths:
        try:
            if chunk_path.exists():
                chunk_path.unlink()
                logger.debug(f"Removed chunk: {chunk_path}")
        except OSError as e:
            logger.warning(f"Failed to remove chunk {chunk_path}: {e}")

    # Try to remove the parent directory if empty
    if chunk_paths:
        parent = chunk_paths[0].parent
        try:
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                logger.debug(f"Removed chunk directory: {parent}")
        except OSError:
            pass  # Directory not empty or other issue
