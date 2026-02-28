#!/usr/bin/env python3
"""
Debug log module: output to stderr when MCP_DEBUG is enabled.
Env: MCP_DEBUG=true/1/yes/on to enable.
"""

import os
import sys
from typing import Any


def debug_log(message: Any, prefix: str = "DEBUG") -> None:
    """Write debug message to stderr when MCP_DEBUG is enabled."""
    if os.getenv("MCP_DEBUG", "").lower() not in ("true", "1", "yes", "on"):
        return

    try:
        if not isinstance(message, str):
            message = str(message)

        try:
            print(f"[{prefix}] {message}", file=sys.stderr, flush=True)
        except UnicodeEncodeError:
            safe_message = message.encode("ascii", errors="replace").decode("ascii")
            print(f"[{prefix}] {safe_message}", file=sys.stderr, flush=True)
    except Exception:
        pass


def i18n_debug_log(message: Any) -> None:
    """i18n module debug log."""
    debug_log(message, "I18N")


def server_debug_log(message: Any) -> None:
    """Server module debug log."""
    debug_log(message, "SERVER")


def web_debug_log(message: Any) -> None:
    """Web UI module debug log."""
    debug_log(message, "WEB")


def is_debug_enabled() -> bool:
    """Check if debug mode is enabled."""
    return os.getenv("MCP_DEBUG", "").lower() in ("true", "1", "yes", "on")


def set_debug_mode(enabled: bool) -> None:
    """Set debug mode (for tests)."""
    os.environ["MCP_DEBUG"] = "true" if enabled else "false"
