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

echo "🚀 Running Docker container on host port ${HOST_PORT}..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  --env-file .env \
  "${IMAGE_NAME}"
