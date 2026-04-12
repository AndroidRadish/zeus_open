#!/usr/bin/env bash
# ZeusOpen v2 — One-click start script for Linux / macOS
# Usage: ./start.sh [--port 8234] [--build]

set -euo pipefail

PORT="${PORT:-8234}"
BUILD=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --build)
      BUILD=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./start.sh [--port 8234] [--build]"
      exit 1
      ;;
  esac
done

echo "🚀 ZeusOpen v2 launcher"
echo "   Port: $PORT"

# Ensure Python >= 3.11
PY_VERSION=$(python3 --version 2>/dev/null | awk '{print $2}' | cut -d. -f1,2 || true)
if [[ -z "$PY_VERSION" ]]; then
  echo "❌ Python 3 is required but not found."
  exit 1
fi

echo "   Python: $(python3 --version)"

# Install dependencies if missing
if ! python3 -c "import fastapi, uvicorn, filelock" 2>/dev/null; then
  echo "📦 Installing dependencies..."
  pip3 install -r requirements.txt
fi

# Docker mode
if [[ "$BUILD" == true ]]; then
  echo "🐳 Building Docker image..."
  docker build -t zeus-open:v2 .
  echo "🐳 Starting container on port $PORT..."
  docker run --rm -p "$PORT:$PORT" -v "$(pwd):/app" zeus-open:v2 \
    python .zeus/v2/scripts/zeus_server.py --host 0.0.0.0 --port "$PORT"
  exit 0
fi

# Native mode
echo "▶ Starting ZeusOpen v2 backend (native)..."
python3 .zeus/v2/scripts/zeus_server.py --port "$PORT"
