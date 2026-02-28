#!/usr/bin/env bash
set -euo pipefail

CURRENT_VERSION=$(grep 'current_version' .bumpversion.cfg | head -1 | cut -d'=' -f2 | tr -d ' ')

echo "=== Build Leo Feedback MCP ==="
echo ""
echo "Current version: $CURRENT_VERSION"
echo ""

read -rp "Enter new version (leave empty to keep $CURRENT_VERSION): " NEW_VERSION

if [[ -n "$NEW_VERSION" ]]; then
  echo ""
  echo "-> Bumping version to $NEW_VERSION..."
  uv run bump2version --allow-dirty --new-version "$NEW_VERSION" patch
  echo "   Updated: pyproject.toml, __init__.py, .bumpversion.cfg"
  CURRENT_VERSION="$NEW_VERSION"
fi

echo ""
echo "-> Building Flutter Web UI..."
cd frontend && flutter build web --release
cd ..

echo ""
echo "-> Building Python package..."
uv build

echo ""
echo "Build complete! Version: $CURRENT_VERSION"
echo "Output: dist/"
