#!/bin/bash
# Script to build and run the Docker container
# Usage: ./run_docker.sh

echo "🐳 Building Docker image..."
echo ""

# Build Docker image
docker build -t seg-vrp .
echo ""

# Run Docker container
echo "🚀 Running Docker container..."
echo ""

# Run Docker container with environment variables
docker run -p 8501:8501 --env-file .env seg-vrp