#!/bin/bash
set -euo pipefail

IMAGE_NAME="seg-vrp"
PORT="8501"

echo "🐳 Building Docker image..."
docker build -t "${IMAGE_NAME}" .
echo ""

echo "🚀 Running Docker container..."

# Prefer .env, fall back to .env.example if present
ENV_FILE_ARGS=()
if [ -f .env ]; then
  ENV_FILE_ARGS+=(--env-file .env)
elif [ -f .env.example ]; then
  ENV_FILE_ARGS+=(--env-file .env.example)
fi

docker run -p "${PORT}:${PORT}" "${ENV_FILE_ARGS[@]}" "${IMAGE_NAME}"
