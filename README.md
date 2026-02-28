# Leo Feedback MCP

A customized MCP (Model Context Protocol) server for interactive feedback collection during AI-assisted development. Built with a **Flutter Web** frontend and **Python/FastAPI** backend.


## Features

- **Flutter Web UI** with dark theme for interactive feedback
- **AI Work Summary** panel with Markdown rendering
- **Image support** - upload, drag & drop from IDE, paste (PNG, JPG, GIF, BMP, WebP)
- **Auto-submit countdown** with configurable prompts
- **Audio & browser notifications** when AI requests feedback
- **Session history** - persists across browser reloads via backend storage
- **Drag & drop** files from IDE (Cursor) into the feedback panel
- **Keyboard shortcuts** - Ctrl+Enter / Cmd+Enter for quick submit
- Smart browser detection (WSL, SSH, local)
- Session management with auto-cleanup

## Architecture

```
┌─────────────────────────────────────────────┐
│  Cursor / AI Client                         │
│  (calls interactive_feedback MCP tool)      │
└──────────────┬──────────────────────────────┘
               │ MCP Protocol (stdio)
┌──────────────▼──────────────────────────────┐
│  Python Backend                             │
│  ├── FastMCP server (MCP tool definitions)  │
│  ├── FastAPI (HTTP routes + WebSocket)      │
│  └── Session management & image processing  │
└──────────────┬──────────────────────────────┘
               │ HTTP + WebSocket
┌──────────────▼──────────────────────────────┐
│  Flutter Web Frontend                       │
│  ├── Workspace (AI Summary + Feedback)      │
│  ├── Sessions (chat history)                │
│  ├── Settings (auto-submit, timeout)        │
│  └── About                                  │
└─────────────────────────────────────────────┘
```

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Flutter](https://flutter.dev/docs/get-started/install) 3.x+ (for frontend development/building)

## Installation

### Option A: Install from PyPI (recommended for users)

```bash
pip install leo-feedback-mcp
```

Or with `uv`:

```bash
uv pip install leo-feedback-mcp
```

MCP configuration (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "leo-feedback-mcp": {
      "command": "uvx",
      "args": ["leo-feedback-mcp"],
      "timeout": 600,
      "autoApprove": ["interactive_feedback"]
    }
  }
}
```

### Option B: Install from source (for development)

```bash
git clone <your-repo-url> ~/Desktop/leo-feedback-mcp
cd ~/Desktop/leo-feedback-mcp
make init
make build
```

MCP configuration (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "leo-feedback-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "<path-to-leo-feedback-mcp>", "leo-feedback-mcp"],
      "timeout": 600,
      "autoApprove": ["interactive_feedback"]
    }
  }
}
```

Replace `<path-to-leo-feedback-mcp>` with the actual path to the cloned repository.

### Apply configuration

You can place the MCP config in:
- **Project-level**: `.cursor/mcp.json` in your project root
- **Global**: `~/.cursor/mcp.json` to apply across all projects

After editing, restart Cursor or reload MCP servers (Cursor Settings > MCP > Reload).

## Usage

Once configured, the AI assistant will automatically call `interactive_feedback` to collect your feedback during conversations. A Web UI will open in your browser where you can:

1. **Review** the AI's work summary (Markdown rendered)
2. **Provide** text feedback with keyboard shortcuts
3. **Attach images** via upload button, drag & drop, or paste
4. **View session history** of previous AI interactions
5. **Configure** auto-submit prompts and timeout settings

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_DEBUG` | Enable debug logging | `false` |
| `MCP_WEB_HOST` | Web UI host | `127.0.0.1` |
| `MCP_WEB_PORT` | Web UI port | `8765` |

## Credits

- Author: Leo Nguyen
