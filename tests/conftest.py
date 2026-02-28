#!/usr/bin/env python3
"""
Test configuration and shared fixtures.
"""

import asyncio
import os
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from mcp_feedback_enhanced.i18n import get_i18n_manager
from mcp_feedback_enhanced.web.main import WebUIManager


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop fixture."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create temp directory fixture."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_project_dir(temp_dir: Path) -> Path:
    """Create test project directory."""
    project_dir = temp_dir / "test_project"
    project_dir.mkdir()

    (project_dir / "README.md").write_text("# Test Project")
    (project_dir / "main.py").write_text("print('Hello World')")

    return project_dir


@pytest.fixture
def web_ui_manager() -> Generator[WebUIManager, None, None]:
    """Create WebUIManager fixture."""
    import os

    original_test_mode = os.environ.get("MCP_TEST_MODE")
    original_web_host = os.environ.get("MCP_WEB_HOST")
    original_web_port = os.environ.get("MCP_WEB_PORT")

    os.environ["MCP_TEST_MODE"] = "true"
    os.environ["MCP_WEB_HOST"] = "127.0.0.1"
    os.environ["MCP_WEB_PORT"] = "0"

    try:
        manager = WebUIManager()
        yield manager
    finally:
        if original_test_mode is not None:
            os.environ["MCP_TEST_MODE"] = original_test_mode
        else:
            os.environ.pop("MCP_TEST_MODE", None)

        if original_web_host is not None:
            os.environ["MCP_WEB_HOST"] = original_web_host
        else:
            os.environ.pop("MCP_WEB_HOST", None)

        if original_web_port is not None:
            os.environ["MCP_WEB_PORT"] = original_web_port
        else:
            os.environ.pop("MCP_WEB_PORT", None)

        if manager.server_thread and manager.server_thread.is_alive():
            pass


@pytest.fixture
def i18n_manager():
    """Create I18N manager fixture."""
    return get_i18n_manager()


@pytest.fixture
def test_config() -> dict[str, Any]:
    """Test config fixture."""
    return {
        "timeout": 30,
        "debug": True,
        "web_port": 8765,
        "test_summary": "Test summary - automated test",
        "test_feedback": "Test feedback content",
    }


@pytest.fixture(autouse=True)
def setup_test_env():
    """Auto setup test environment."""
    original_debug = os.environ.get("MCP_DEBUG")
    os.environ["MCP_DEBUG"] = "true"

    yield

    if original_debug is not None:
        os.environ["MCP_DEBUG"] = original_debug
    else:
        os.environ.pop("MCP_DEBUG", None)
