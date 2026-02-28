#!/usr/bin/env bash
set -euo pipefail

echo "=== Initializing Leo Feedback MCP ==="
echo ""

# Python dependencies
echo "-> Installing Python dependencies..."
uv sync --dev
echo ""

# Flutter dependencies
echo "-> Installing Flutter dependencies..."
cd frontend && flutter pub get
cd ..
echo ""

echo "Project is ready!"
echo "  - Python (backend):  uv run leo-feedback-mcp"
echo "  - Flutter (frontend): cd frontend && flutter run -d chrome"
