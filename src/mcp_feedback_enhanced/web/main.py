#!/usr/bin/env python3
"""FastAPI-based Web UI manager for feedback collection, image upload, and command execution."""

import asyncio
import concurrent.futures
import os
import sys
import threading
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware

from ..utils.error_handler import ErrorHandler, ErrorType
from ..utils.memory_monitor import get_memory_monitor
from .models import CleanupReason, SessionStatus, WebFeedbackSession
from .routes import setup_routes
from .utils import get_browser_opener
from .utils.compression_config import get_compression_manager
from .utils.port_manager import PortManager


class WebUIManager:
    """Web UI manager with single-session model.

    Each server instance holds exactly one session. When a new MCP call
    arrives while the current session is blocking (wait_for_feedback),
    an overflow server is created on a different port.
    """

    def __init__(self, host: str = "127.0.0.1", port: int | None = None):
        env_host = os.getenv("MCP_WEB_HOST")
        if env_host:
            self.host = env_host
        else:
            self.host = host

        preferred_port = 33333

        env_port = os.getenv("MCP_WEB_PORT")
        if env_port:
            try:
                custom_port = int(env_port)
                if custom_port == 0:
                    preferred_port = 0
                elif 1024 <= custom_port <= 65535:
                    preferred_port = custom_port
            except ValueError:
                pass

        auto_cleanup = os.environ.get("MCP_TEST_MODE", "").lower() != "true"

        if port is not None:
            self.port = port
            if not PortManager.is_port_available(self.host, self.port):
                if os.environ.get("MCP_TEST_MODE", "").lower() == "true":
                    self.port = PortManager.find_free_port_enhanced(
                        preferred_port=self.port, auto_cleanup=False, host=self.host
                    )
        elif preferred_port == 0:
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.host, 0))
                self.port = s.getsockname()[1]
        else:
            self.port = PortManager.find_free_port_enhanced(
                preferred_port=preferred_port, auto_cleanup=auto_cleanup, host=self.host
            )
        self.app = FastAPI(title="Leo Feedback MCP")

        self._setup_compression_middleware()
        self._setup_memory_monitoring()

        self.session: WebFeedbackSession | None = None

        self.server_thread: threading.Thread | None = None
        self.server_process = None
        self._uvicorn_server: uvicorn.Server | None = None

        self._initialization_complete = False
        self._initialization_lock = threading.Lock()

        self._init_basic_components()

    def _init_basic_components(self):
        """Sync initialization of basic components."""
        self._setup_static_files()
        setup_routes(self)

    async def _init_async_components(self):
        """Async initialization (parallel execution)."""
        with self._initialization_lock:
            if self._initialization_complete:
                return

        tasks = []
        tasks.append(self._preload_i18n_async())

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    pass

        with self._initialization_lock:
            self._initialization_complete = True

    async def _preload_i18n_async(self):
        """Async preload of i18n resources (handled by frontend)."""

        def preload_i18n():
            try:
                return True
            except Exception as e:
                return False

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, preload_i18n)

    def _setup_compression_middleware(self):
        """Setup compression and cache middleware."""
        compression_manager = get_compression_manager()
        config = compression_manager.config

        self.app.add_middleware(GZipMiddleware, minimum_size=config.minimum_size)

        @self.app.middleware("http")
        async def compression_and_cache_middleware(request: Request, call_next):
            response = await call_next(request)

            if not config.should_exclude_path(request.url.path):
                cache_headers = config.get_cache_headers(request.url.path)
                for key, value in cache_headers.items():
                    response.headers[key] = value

            try:
                content_length = int(response.headers.get("content-length", 0))
                content_encoding = response.headers.get("content-encoding", "")
                was_compressed = "gzip" in content_encoding

                if content_length > 0:
                    original_size = (
                        content_length
                        if not was_compressed
                        else int(content_length / 0.7)
                    )
                    compression_manager.update_stats(
                        original_size, content_length, was_compressed
                    )
            except (ValueError, TypeError):
                pass

            return response

    def _setup_memory_monitoring(self):
        """Setup memory monitoring."""
        try:
            self.memory_monitor = get_memory_monitor()

            def web_memory_alert(alert):
                if alert.level in ("critical", "emergency"):
                    if self.session and not self.is_blocking():
                        self.cleanup_session(CleanupReason.MEMORY_PRESSURE)

            self.memory_monitor.add_alert_callback(web_memory_alert)

            if not self.memory_monitor.is_monitoring:
                self.memory_monitor.start_monitoring()

        except Exception as e:
            ErrorHandler.log_error_with_context(
                e,
                context={"operation": "setup_web_ui_memory_monitoring"},
                error_type=ErrorType.SYSTEM,
            )

    def _setup_static_files(self):
        """Setup static file serving (Flutter Web only)."""
        self.flutter_build_path: Path | None = None

        dev_path = Path(__file__).parent.parent.parent.parent / "frontend" / "build" / "web"
        pkg_path = Path(__file__).parent.parent / "flutter_web"

        if dev_path.exists():
            self.flutter_build_path = dev_path
        elif pkg_path.exists():
            self.flutter_build_path = pkg_path
        else:
            self.flutter_build_path = None

    def create_session(self, project_directory: str, summary: str) -> None:
        """Create (or reset) the single session for this server."""
        session_id = str(uuid.uuid4())
        self.session = WebFeedbackSession(session_id, project_directory, summary)

    def is_blocking(self) -> bool:
        """Check if the current session is blocking on wait_for_feedback."""
        if self.session is None:
            return False
        return self.session._is_waiting

    def start_server(self):
        """Start Web server (supports parallel init)."""

        def run_server_with_retry():
            max_retries = 5
            retry_count = 0
            original_port = self.port

            while retry_count < max_retries:
                try:
                    if not PortManager.is_port_available(self.host, self.port):
                        process_info = PortManager.find_process_using_port(self.port)

                        try:
                            new_port = PortManager.find_free_port_enhanced(
                                preferred_port=self.port,
                                auto_cleanup=False,
                                host=self.host,
                            )
                            self.port = new_port
                        except RuntimeError as port_error:
                            ErrorHandler.log_error_with_context(
                                port_error,
                                context={
                                    "operation": "port_lookup",
                                    "original_port": original_port,
                                    "current_port": self.port,
                                },
                                error_type=ErrorType.NETWORK,
                            )
                            raise RuntimeError(
                                f"No available port, original {original_port} in use"
                            ) from port_error

                    config = uvicorn.Config(
                        app=self.app,
                        host=self.host,
                        port=self.port,
                        log_level="warning",
                        access_log=False,
                    )

                    server_instance = uvicorn.Server(config)
                    self._uvicorn_server = server_instance

                    async def serve_with_async_init(server=server_instance):
                        server_task = asyncio.create_task(server.serve())
                        init_task = asyncio.create_task(self._init_async_components())
                        await asyncio.gather(
                            server_task, init_task, return_exceptions=True
                        )

                    asyncio.run(serve_with_async_init())

                    break

                except OSError as e:
                    if e.errno in {10048, 98}:
                        retry_count += 1
                        if retry_count < max_retries:
                            self.port = self.port + 1
                        else:
                            break
                    else:
                        ErrorHandler.log_error_with_context(
                            e,
                            context={
                                "operation": "server_startup",
                                "host": self.host,
                                "port": self.port,
                            },
                            error_type=ErrorType.NETWORK,
                        )
                        break
                except Exception as e:
                    ErrorHandler.log_error_with_context(
                        e,
                        context={
                            "operation": "server_run",
                            "host": self.host,
                            "port": self.port,
                        },
                        error_type=ErrorType.SYSTEM,
                    )
                    break

        self.server_thread = threading.Thread(target=run_server_with_retry, daemon=True)
        self.server_thread.start()

        time.sleep(2)

    def open_browser(self, url: str):
        """Open browser."""
        try:
            browser_opener = get_browser_opener()
            browser_opener(url)
        except Exception as e:
            print(str(e), file=sys.stderr)

    def get_server_url(self) -> str:
        """Get server URL."""
        return f"http://{self.host}:{self.port}"

    def cleanup_session(self, reason: CleanupReason = CleanupReason.MANUAL) -> None:
        """Clean up the current session."""
        if self.session is None:
            return
        try:
            self.session._cleanup_sync_enhanced(reason)
        except Exception as e:
            ErrorHandler.log_error_with_context(
                e,
                context={"operation": "cleanup_session", "reason": reason.value},
                error_type=ErrorType.SYSTEM,
            )
        self.session = None

    def stop(self):
        """Stop Web UI service and release the port."""
        self.cleanup_session(CleanupReason.SHUTDOWN)

        if self._uvicorn_server is not None:
            self._uvicorn_server.should_exit = True
            self._uvicorn_server = None

        if self.server_thread is not None and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
            self.server_thread = None


_primary_manager: WebUIManager | None = None
_overflow_managers: list[WebUIManager] = []
_MAX_OVERFLOW = 3


def _get_or_create_primary() -> WebUIManager:
    """Get (or create) the primary server."""
    global _primary_manager
    if _primary_manager is None:
        _primary_manager = WebUIManager()
    return _primary_manager


def _find_available_manager() -> WebUIManager:
    """Find a server that is NOT blocking, or create an overflow.

    Priority: primary first, then existing overflow servers.
    If all are blocking, create a new overflow server (up to _MAX_OVERFLOW).
    """
    primary = _get_or_create_primary()

    if not primary.is_blocking():
        return primary

    for mgr in _overflow_managers:
        if not mgr.is_blocking():
            return mgr

    if len(_overflow_managers) < _MAX_OVERFLOW:
        overflow = WebUIManager()
        _overflow_managers.append(overflow)
        return overflow

    return primary


def _cleanup_idle_overflows() -> None:
    """Shutdown overflow servers that are idle (not blocking, no active session)."""
    global _overflow_managers
    still_active = []
    for mgr in _overflow_managers:
        if mgr.is_blocking():
            still_active.append(mgr)
        else:
            mgr.stop()
    _overflow_managers = still_active


async def launch_web_feedback_ui(
    project_directory: str,
    summary: str,
    timeout: int = 600,
) -> dict:
    """Launch Web feedback UI and wait for user feedback.

    Single-session model:
    - If the server's session is idle (not blocking), reuse it.
    - If blocking (concurrent chat), create overflow on a new port.

    Args:
        project_directory: Project directory path.
        summary: AI work summary.
        timeout: Timeout in seconds.

    Returns:
        dict: Feedback result with logs, interactive_feedback, images.
    """
    manager = _find_available_manager()

    if manager.server_thread is None or not manager.server_thread.is_alive():
        manager.start_server()

    session = manager.session

    if session is not None and not manager.is_blocking():
        session.summary = summary
        session.project_directory = project_directory
        session.feedback_result = None
        session.images = []
        session.settings = {}
        session.feedback_completed.clear()
        session.status = SessionStatus.WAITING
        session.status_message = "Waiting for user feedback"
        session.last_activity = time.time()
        session._cleanup_done = False

        if session.websocket:
            try:
                await session.websocket.send_json({
                    "type": "session_updated",
                    "action": "session_reused",
                    "session_info": {
                        "session_id": session.session_id,
                        "project_directory": session.project_directory,
                        "summary": session.summary,
                        "status": session.status.value,
                    },
                })
            except Exception:
                pass
        else:
            manager.open_browser(manager.get_server_url())
    else:
        manager.create_session(project_directory, summary)
        session = manager.session

        if not session:
            raise RuntimeError("Failed to create feedback session")

        manager.open_browser(manager.get_server_url())

    try:
        result = await session.wait_for_feedback(timeout)
        return result
    except TimeoutError:
        raise
    except Exception:
        raise


def stop_web_ui():
    """Stop all servers (primary + overflows)."""
    global _primary_manager, _overflow_managers
    if _primary_manager:
        _primary_manager.stop()
        _primary_manager = None
    for mgr in _overflow_managers:
        mgr.stop()
    _overflow_managers = []


if __name__ == "__main__":

    async def main():
        try:
            project_dir = os.getcwd()
            summary = """# Markdown Feature Test

## Task Summary

Implemented Markdown syntax display for **mcp-feedback-enhanced** project.

### Completed

1. **Headings** - H1 to H6
2. **Text formatting**
   - **Bold** with double asterisk
   - *Italic* with single asterisk
   - `Inline code` with backticks
3. **Code blocks**
4. **Lists**
   - Unordered items
   - Ordered items

### Implementation

```javascript
const renderedContent = this.renderMarkdownSafely(summary);
element.innerHTML = renderedContent;
```

### Links

- [marked.js docs](https://marked.js.org/)
- [DOMPurify](https://github.com/cure53/DOMPurify)

> XSS protection via DOMPurify HTML sanitization.

---

**Status**: OK"""

            result = await launch_web_feedback_ui(project_dir, summary)

            print("Received feedback result:")
            print(f"Command logs: {result.get('logs', '')}")
            print(f"User feedback: {result.get('interactive_feedback', '')}")
            print(f"Images count: {len(result.get('images', []))}")

        except KeyboardInterrupt:
            print("\nUser cancelled")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            stop_web_ui()

    asyncio.run(main())
