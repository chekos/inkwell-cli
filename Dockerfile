# syntax=docker/dockerfile:1.7
#
# Inkwell demo (OBRA-74) container image.
#
# Builds the FastAPI service that serves the public try-it surface. The
# image bundles ffmpeg (yt-dlp + transcription dependency), the inkwell
# package itself (CLI + demo modules), and the uvicorn entrypoint. It
# does NOT carry GCP credentials — those mount in at runtime from
# Secret Manager via Cloud Run env vars.
#
# Layer ordering favors cache hits: system packages first, then the
# resolved dependency lock, then the source. A change to source code
# rebuilds only the last two layers.

# ---- builder: resolve and install Python deps with uv ----
FROM python:3.12-slim AS builder

# uv is the project's package manager (see ADR-008). Install the
# released wheel via pip — pinning the major version keeps reproducible
# builds without coupling to the ecosystem-wide GitHub release URL.
RUN pip install --no-cache-dir uv==0.5.11

WORKDIR /app

# Pre-copy the lock + project metadata so we cache the dependency
# install separately from the source tree.
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Install the project + production dependencies into a venv at /app/.venv.
# --no-dev skips test/lint deps that don't ship in production; --frozen
# refuses to drift from uv.lock so Cloud Run can't accidentally pull a
# different version than CI tested.
RUN uv sync --frozen --no-dev


# ---- runtime: thin layer with ffmpeg + the venv ----
FROM python:3.12-slim AS runtime

# ffmpeg is required by yt-dlp for audio extraction. tini gives us PID-1
# behavior so Cloud Run's SIGTERM cleanly shuts down uvicorn instead of
# hanging on an in-flight job.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the resolved venv from the builder stage. We don't need uv at
# runtime — the venv has everything pinned.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Add the venv to PATH so `uvicorn` resolves without an explicit prefix.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    # Cloud Run sends traffic to whatever port `$PORT` points at.
    # Default to 8080 for local `docker run` parity.
    PORT=8080

# Cloud Run respects HEALTHCHECK; we expose the FastAPI /healthz route.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0) if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8080\")}/healthz', timeout=3).status == 200 else sys.exit(1)" || exit 1

EXPOSE 8080

# tini → uvicorn → create_app() factory. Concurrency=1 so the
# class-attribute model pin in service.py stays single-threaded per
# instance; Cloud Run scales by adding more instances, not threads.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "uvicorn inkwell.demo.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
