#!/usr/bin/env python3
"""
MCP Feedback Enhanced Web UI: FastAPI + WebSocket.
Features: text input, image upload, command execution, i18n, responsive design.
"""

from .main import WebUIManager, get_web_ui_manager, launch_web_feedback_ui, stop_web_ui


__all__ = [
    "WebUIManager",
    "get_web_ui_manager",
    "launch_web_feedback_ui",
    "stop_web_ui",
]
