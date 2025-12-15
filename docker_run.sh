#!/bin/bash
set -eu pipefail

# Script to build and run the Docker container
# Usage: PORT=8502 ./docker_run.sh

IMAGE_NAME="seg-vrp"
CONTAINER_NAME="seg-vrp"
HOST_PORT="${PORT:-8501}"
CONTAINER_PORT="8501"

echo "🐳 Building Docker image..."
docker build -t "${IMAGE_NAME}" .
echo ""

echo "🔍 Checking for containers using host port ${HOST_PORT}..."
PORT_CONTAINERS=$(docker ps --filter "publish=${HOST_PORT}" -q)
if [ -n "${PORT_CONTAINERS}" ]; then
  echo "🛑 Stopping containers on port ${HOST_PORT}: ${PORT_CONTAINERS}"
  docker stop ${PORT_CONTAINERS} >/dev/null
  echo "🧹 Removing containers on port ${HOST_PORT}: ${PORT_CONTAINERS}"
  docker rm ${PORT_CONTAINERS} >/dev/null
fi
echo ""

echo "🧹 Removing existing container named ${CONTAINER_NAME} (if any)..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi
echo ""

echo "📁 Ensuring required directories and files exist..."

# Fix ownership first if directories exist but aren't writable (from previous root container)
for dir in .cache results; do
  if [ -d "$dir" ] && [ ! -w "$dir" ]; then
    echo "⚠️  Fixing $dir permissions (may require sudo)..."
    sudo chown -R "$(id -u):$(id -g)" "$dir" 2>/dev/null || {
      echo "❌ Error: $dir is not writable."
      echo "   Run: sudo chown -R \$(id -u):\$(id -g) $dir"
      exit 1
    }
  fi
done

# Now create all required directories
mkdir -p results .cache/route_geometry .streamlit

# Validate critical files for volume mounts
if [ ! -f "conf.yaml" ]; then
  echo "❌ Error: conf.yaml not found. Required for configuration."
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "❌ Error: .env not found. Copy from .env.example and configure."
  exit 1
fi

# Create default .streamlit/config.toml if missing
if [ ! -f ".streamlit/config.toml" ]; then
  echo "📝 Creating default .streamlit/config.toml..."
  cat > .streamlit/config.toml << 'TOMLEOF'
[theme]
primaryColor = "#366092"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"

[server]
headless = true
maxUploadSize = 200
enableXsrfProtection = false
enableCORS = true

[browser]
gatherUsageStats = false
TOMLEOF
fi

echo "🚀 Running Docker container on host port ${HOST_PORT}..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  --cpus="1" \
  --memory="2g" \
  --restart=unless-stopped \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  --env-file .env \
  -v "$(pwd)/results:/app/results" \
  -v "$(pwd)/.cache:/app/.cache" \
  -v "$(pwd)/conf.yaml:/app/conf.yaml" \
  -v "$(pwd)/.streamlit:/app/.streamlit:ro" \
  "${IMAGE_NAME}"

echo ""
echo "✅ Container started. Waiting for health check..."
sleep 5
docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
