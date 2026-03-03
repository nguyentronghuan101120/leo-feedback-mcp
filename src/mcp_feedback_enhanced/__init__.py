#!/usr/bin/env python3
"""
Leo Feedback MCP
================

Interactive MCP feedback server with Flutter Web UI
for AI-assisted development.

Features:
- Flutter Web UI with dark theme
- Image upload and drag & drop support
- Session history management
- Auto-submit with configurable prompts
- Audio & browser notifications
"""

__version__ = "1.1.1"
__author__ = "Leo Nguyen"

from .server import main as run_server
from .web import WebUIManager, get_web_ui_manager, launch_web_feedback_ui, stop_web_ui

__all__ = [
    "WebUIManager",
    "__author__",
    "__version__",
    "get_web_ui_manager",
    "launch_web_feedback_ui",
    "run_server",
    "stop_web_ui",
]


def main():
    """Main entry point for uvx."""
    from .__main__ import main as cli_main

    return cli_main()
