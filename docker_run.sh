#!/bin/bash
set -euo pipefail

# Script to build and run the Docker container
# Usage: PORT=8502 ./docker_run.sh

IMAGE_NAME="seg-vrp"
CONTAINER_NAME="seg-vrp"
HOST_PORT="${PORT:-8501}"
CONTAINER_PORT="8501"

echo "🐳 Building Docker image..."
docker build -t "${IMAGE_NAME}" .
echo ""

echo "🧹 Removing existing container (if any)..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi
echo ""

echo "🚀 Running Docker container on host port ${HOST_PORT}..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  --env-file .env \
  "${IMAGE_NAME}"
