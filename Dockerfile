# Inkwell CLI - Docker Image
# Enables containerized podcast processing with LLM-powered note generation

FROM python:3.11-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official GitHub release with checksum verification
# To update: https://github.com/astral-sh/uv/releases
# 1. Update UV_VERSION to latest release
# 2. Download checksum: curl -fsSL https://github.com/astral-sh/uv/releases/download/VERSION/uv-x86_64-unknown-linux-gnu.tar.gz.sha256
ARG UV_VERSION=0.9.9
ARG UV_SHA256="9ec303873e00deed44d1b2b52b85ab7aa55d849588d7242298748390eaea07ef"

RUN curl -LsSf \
    "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
    -o /tmp/uv.tar.gz && \
    echo "${UV_SHA256}  /tmp/uv.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/uv.tar.gz -C /usr/local/bin && \
    rm /tmp/uv.tar.gz && \
    chmod +x /usr/local/bin/uv

# Verify installation
RUN uv --version

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY templates/ templates/
COPY README.md LICENSE ./

# Install dependencies (frozen for reproducibility)
RUN uv sync --frozen --no-dev

# Runtime stage - minimal image
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 inkwell && \
    mkdir -p /home/inkwell/.config/inkwell \
             /home/inkwell/.cache/inkwell \
             /home/inkwell/.local/state/inkwell \
             /app/output && \
    chown -R inkwell:inkwell /home/inkwell /app

WORKDIR /app

# Copy uv and installed packages from builder
COPY --from=builder /usr/local/bin/uv /usr/local/bin/
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/templates /app/templates
COPY --from=builder /app/pyproject.toml /app/
COPY --from=builder /app/README.md /app/LICENSE /app/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    INKWELL_CONFIG_DIR="/home/inkwell/.config/inkwell" \
    INKWELL_CACHE_DIR="/home/inkwell/.cache/inkwell" \
    INKWELL_LOG_DIR="/home/inkwell/.local/state/inkwell"

# Switch to non-root user
USER inkwell

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD inkwell --version || exit 1

# Default command (show help)
ENTRYPOINT ["inkwell"]
CMD ["--help"]

# Usage examples:
#
# Build image:
#   docker build -t inkwell-cli .
#
# Run with API keys from environment:
#   docker run -e GOOGLE_API_KEY -e ANTHROPIC_API_KEY \
#              -v ./output:/app/output \
#              inkwell-cli process <url>
#
# Run with persistent config:
#   docker run -v ~/.config/inkwell:/home/inkwell/.config/inkwell \
#              -v ./output:/app/output \
#              -e GOOGLE_API_KEY -e ANTHROPIC_API_KEY \
#              inkwell-cli process <url>
#
# Interactive mode:
#   docker run -it \
#              -v ~/.config/inkwell:/home/inkwell/.config/inkwell \
#              -v ./output:/app/output \
#              -e GOOGLE_API_KEY -e ANTHROPIC_API_KEY \
#              inkwell-cli process <url> --interview
#
# Using docker compose (see docker-compose.yml for full config):
#   docker-compose run inkwell process <url>
