FROM python:3.11-slim

# Prevent Python from writing pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# Install uv to /usr/local/bin (globally accessible)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL=/usr/local/bin sh

WORKDIR /app

# Copy dependency manifests first for better Docker layer caching
COPY pyproject.toml uv.lock requirements.txt ./

# Install runtime dependencies (no dev extras)
RUN uv sync --locked --no-dev

# Copy application source
COPY . .

# Ensure app files are readable by any user (for --user override)
RUN chmod -R a+rX /app

EXPOSE 8501

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit app via uv
ENTRYPOINT ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
