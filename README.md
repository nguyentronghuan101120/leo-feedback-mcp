# Leo Feedback MCP

A customized MCP (Model Context Protocol) server for interactive feedback collection during AI-assisted development. Forked from [mcp-feedback-enhanced](https://github.com/Minidoracat/mcp-feedback-enhanced).

## Features

- Web UI for interactive feedback between AI and user
- Image upload support (PNG, JPG, GIF, BMP, WebP)
- Markdown rendering in summaries
- Command execution from the feedback interface
- Multi-language support (English, Chinese)
- Smart browser detection (WSL, SSH, local)
- Session management with auto-cleanup

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Installation

### 1. Clone the repository

```bash
git clone <your-repo-url> ~/Desktop/leo-feedback-mcp
cd ~/Desktop/leo-feedback-mcp
```

### 2. Install dependencies

```bash
uv sync
```

This will automatically create a virtual environment with Python 3.11 and install all dependencies.

### 3. Verify installation

```bash
uv run mcp-feedback-enhanced version
```

## Setup MCP in Cursor

### Project-level configuration

Create or edit `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "mcp-feedback-enhanced": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/sotatek/Desktop/leo-feedback-mcp", "mcp-feedback-enhanced"],
      "timeout": 600,
      "autoApprove": ["interactive_feedback"]
    }
  }
}
```

### Global configuration

Edit `~/.cursor/mcp.json` to apply across all projects:

```json
{
  "mcpServers": {
    "mcp-feedback-enhanced": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/sotatek/Desktop/leo-feedback-mcp", "mcp-feedback-enhanced"],
      "timeout": 600,
      "autoApprove": ["interactive_feedback"]
    }
  }
}
```

After editing, restart Cursor or reload MCP servers (Cursor Settings > MCP > Reload).

## Usage

Once configured, the AI assistant will automatically call `interactive_feedback` to collect your feedback during conversations. A Web UI will open in your browser where you can:

1. Review the AI's work summary
2. Provide text feedback
3. Upload images as feedback
4. Execute commands to verify results

## Testing

### Test Web UI manually

```bash
uv run mcp-feedback-enhanced test --web
```

This starts the Web UI server and opens a browser for testing.

### Run unit tests

```bash
uv run pytest
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_DEBUG` | Enable debug logging | `false` |
| `MCP_WEB_HOST` | Web UI host | `127.0.0.1` |
| `MCP_WEB_PORT` | Web UI port | `8765` |
| `MCP_LANGUAGE` | UI language | Auto-detect |

## Development

```bash
# Install dev dependencies
make install-dev

# Run linting
make lint

# Format code
make format

# Run all checks
make check

# Build package
make build
```

## Credits

- Original author: Fabio Ferreira
- Enhanced by: [Minidoracat](https://github.com/Minidoracat/mcp-feedback-enhanced)
