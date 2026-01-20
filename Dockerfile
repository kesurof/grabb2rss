# ============================================
# Stage 1: Builder - Compile Python packages
# ============================================
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment for isolation
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install wheel for faster builds
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy and install requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ============================================
# Stage 2: Runtime - Minimal production image
# ============================================
FROM python:3.11-slim

# Labels
LABEL maintainer="Grab2RSS"
LABEL description="Prowlarr to RSS converter with multi-tracker support"
LABEL version="2.6.0"
LABEL org.opencontainers.image.source="https://github.com/kesurof/grabb2rss"
LABEL org.opencontainers.image.description="Prowlarr to RSS converter inspired by LinuxServer.io standards"
LABEL org.opencontainers.image.licenses="MIT"

# Install only runtime dependencies (no gcc/build tools)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gosu \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Copy Python virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set PATH to use venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code (do this late to maximize cache)
COPY . .

# Copy and set entrypoint permissions
RUN chmod +x /entrypoint.sh

# Create necessary directories
RUN mkdir -p /app/data/torrents /config

# Environment variables (LinuxServer.io style)
ENV PUID=1000 \
    PGID=1000 \
    TZ=Etc/UTC \
    PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use entrypoint for proper permission handling
ENTRYPOINT ["/entrypoint.sh"]
