#!/bin/sh
set -eu

IMAGE_NAME="seg-vrp"
PORT="8501"

echo "🐳 Building Docker image..."
docker build -t "${IMAGE_NAME}" .
echo ""

echo "🚀 Running Docker container..."

# Prefer .env, fall back to .env.example if present
if [ -f .env ]; then
  ENV_FILE_ARG="--env-file .env"
elif [ -f .env.example ]; then
  ENV_FILE_ARG="--env-file .env.example"
else
  ENV_FILE_ARG=""
fi

if [ -n "${ENV_FILE_ARG}" ]; then
  docker run -p "${PORT}:${PORT}" ${ENV_FILE_ARG} "${IMAGE_NAME}"
else
  docker run -p "${PORT}:${PORT}" "${IMAGE_NAME}"
fi
