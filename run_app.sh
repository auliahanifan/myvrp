#!/bin/bash
# Script to run the Streamlit application
# Usage: ./run_app.sh

echo "🚀 Starting Segarloka VRP Solver..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  WARNING: .env file not found!"
    echo "Please copy .env.example to .env and configure your API key"
    echo ""
    echo "cp .env.example .env"
    echo ""
    exit 1
fi

# Check for uv
UV_PATH=""
if command -v uv &> /dev/null; then
    UV_PATH="uv"
elif [ -f "$HOME/.local/bin/uv" ]; then
    UV_PATH="$HOME/.local/bin/uv"
else
    echo "❌ uv not found!"
    echo "Please install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✅ Using uv at: $UV_PATH"
echo ""

echo "📦 Checking dependencies..."
$UV_PATH pip list | grep streamlit > /dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Dependencies not installed. Installing..."
    $UV_PATH pip install -r requirements.txt
fi

echo ""
echo "✅ All checks passed!"
echo "🌐 Starting web application..."
echo ""

# Run streamlit with uv
$UV_PATH run streamlit run app.py
