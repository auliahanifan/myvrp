FROM python:3.11-slim

# Prevent Python from writing pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# Install uv and minimal OS dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_CONFIRM=1 sh -s -- --bin-dir /usr/local/bin

WORKDIR /app

# Copy dependency manifests first for better Docker layer caching
COPY pyproject.toml uv.lock requirements.txt ./

# Install runtime dependencies (no dev extras)
RUN uv sync --locked --no-dev

# Copy application source
COPY . .

EXPOSE 8501

# Run Streamlit app via uv
ENTRYPOINT ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
