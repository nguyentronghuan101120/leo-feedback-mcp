#!/usr/bin/env python3
"""Web UI utility functions."""

from .browser import get_browser_opener
from .network import find_free_port


__all__ = ["find_free_port", "get_browser_opener"]
