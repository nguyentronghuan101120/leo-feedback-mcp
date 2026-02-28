#!/usr/bin/env python3
"""Feedback result data model for Web UI and backend."""

from typing import TypedDict


class FeedbackResult(TypedDict):
    """Feedback result type."""

    command_logs: str
    interactive_feedback: str
    images: list[dict]
