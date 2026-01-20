FROM python:3.11-slim

# Labels
LABEL maintainer="Grab2RSS"
LABEL description="Prowlarr to RSS converter with multi-tracker support"
LABEL version="2.6.0"
LABEL org.opencontainers.image.source="https://github.com/kesurof/grabb2rss"
LABEL org.opencontainers.image.description="Prowlarr to RSS converter inspired by LinuxServer.io standards"
LABEL org.opencontainers.image.licenses="MIT"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gcc \
    python3-dev \
    su-exec \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy and set entrypoint permissions
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create necessary directories
RUN mkdir -p /app/data/torrents /config

# Environment variables (LinuxServer.io style)
ENV PUID=1000 \
    PGID=1000 \
    TZ=Etc/UTC

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use entrypoint for proper permission handling
ENTRYPOINT ["/entrypoint.sh"]
