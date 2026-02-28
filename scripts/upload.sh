#!/usr/bin/env bash
set -euo pipefail

CURRENT_VERSION=$(grep 'current_version' .bumpversion.cfg | head -1 | cut -d'=' -f2 | tr -d ' ')

echo "=== Upload Leo Feedback MCP to PyPI ==="
echo ""
echo "Current version: $CURRENT_VERSION"
echo ""

WHL="dist/leo_feedback_mcp-${CURRENT_VERSION}-py3-none-any.whl"
TAR="dist/leo_feedback_mcp-${CURRENT_VERSION}.tar.gz"

if [[ ! -f "$WHL" || ! -f "$TAR" ]]; then
  echo "Build files for v${CURRENT_VERSION} not found in dist/"
  echo "Run 'make build' first."
  exit 1
fi

echo "Files to upload:"
echo "  - $WHL"
echo "  - $TAR"
echo ""

read -rsp "Enter PyPI API token: " TOKEN
echo ""

if [[ -z "$TOKEN" ]]; then
  echo "Token is required."
  exit 1
fi

echo ""
echo "-> Uploading to PyPI..."
uv run twine upload --username __token__ --password "$TOKEN" "$WHL" "$TAR"

echo ""
echo "Upload complete!"
echo "View at: https://pypi.org/project/leo-feedback-mcp/${CURRENT_VERSION}/"
