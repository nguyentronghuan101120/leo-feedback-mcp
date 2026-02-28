#!/usr/bin/env python3
"""FastAPI-based Web UI manager for feedback collection, image upload, and command execution."""

import asyncio
import concurrent.futures
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware

from ..debug import web_debug_log as debug_log
from ..utils.error_handler import ErrorHandler, ErrorType
from ..utils.memory_monitor import get_memory_monitor
from .models import CleanupReason, SessionStatus, WebFeedbackSession
from .routes import setup_routes
from .utils import get_browser_opener
from .utils.compression_config import get_compression_manager
from .utils.port_manager import PortManager


class WebUIManager:
    """Web UI manager with single active session mode."""

    def __init__(self, host: str = "127.0.0.1", port: int | None = None):
        env_host = os.getenv("MCP_WEB_HOST")
        if env_host:
            self.host = env_host
            debug_log(f"Using host from env: {self.host}")
        else:
            self.host = host
            debug_log(f"MCP_WEB_HOST not set, using default host {self.host}")

        preferred_port = 8765

        env_port = os.getenv("MCP_WEB_PORT")
        if env_port:
            try:
                custom_port = int(env_port)
                if custom_port == 0:
                    preferred_port = 0
                    debug_log("Using auto port allocation (0) from env")
                elif 1024 <= custom_port <= 65535:
                    preferred_port = custom_port
                    debug_log(f"Using port from env: {preferred_port}")
                else:
                    debug_log(
                        f"MCP_WEB_PORT invalid ({custom_port}), must be 1024-65535 or 0, using 8765"
                    )
            except ValueError:
                debug_log(f"MCP_WEB_PORT invalid format ({env_port}), must be numeric, using 8765")
        else:
            debug_log(f"MCP_WEB_PORT not set, using default port {preferred_port}")

        auto_cleanup = os.environ.get("MCP_TEST_MODE", "").lower() != "true"

        if port is not None:
            self.port = port
            if not PortManager.is_port_available(self.host, self.port):
                debug_log(f"Warning: port {self.port} may be in use")
                if os.environ.get("MCP_TEST_MODE", "").lower() == "true":
                    debug_log("Test mode: searching for alternative port")
                    original_port = self.port
                    self.port = PortManager.find_free_port_enhanced(
                        preferred_port=self.port, auto_cleanup=False, host=self.host
                    )
                    if self.port != original_port:
                        debug_log(f"Switched to available port: {original_port} -> {self.port}")
        elif preferred_port == 0:
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.host, 0))
                self.port = s.getsockname()[1]
            debug_log(f"System-assigned port: {self.port}")
        else:
            self.port = PortManager.find_free_port_enhanced(
                preferred_port=preferred_port, auto_cleanup=auto_cleanup, host=self.host
            )
        self.app = FastAPI(title="Leo Feedback MCP")

        self._setup_compression_middleware()
        self._setup_memory_monitoring()

        self.current_session: WebFeedbackSession | None = None
        self.sessions: dict[str, WebFeedbackSession] = {}

        self.global_active_tabs: dict[str, dict] = {}
        self._pending_session_update = False

        self.cleanup_stats: dict[str, Any] = {
            "total_cleanups": 0,
            "expired_cleanups": 0,
            "memory_pressure_cleanups": 0,
            "manual_cleanups": 0,
            "last_cleanup_time": None,
            "total_cleanup_duration": 0.0,
            "sessions_cleaned": 0,
        }

        self.server_thread: threading.Thread | None = None
        self.server_process = None

        self._initialization_complete = False
        self._initialization_lock = threading.Lock()

        self._init_basic_components()

        debug_log(f"WebUIManager initialized, starting at {self.host}:{self.port}")
        debug_log("Feedback mode: web")

    def _init_basic_components(self):
        """Sync initialization of basic components."""
        self._setup_static_files()
        setup_routes(self)

    async def _init_async_components(self):
        """Async initialization (parallel execution)."""
        with self._initialization_lock:
            if self._initialization_complete:
                return

        debug_log("Starting parallel component initialization...")
        start_time = time.time()

        tasks = []
        tasks.append(self._preload_i18n_async())

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    debug_log(f"Parallel init task {i} failed: {result}")

        with self._initialization_lock:
            self._initialization_complete = True

        elapsed = time.time() - start_time
        debug_log(f"Parallel init complete in {elapsed:.2f}s")

    async def _preload_i18n_async(self):
        """Async preload of i18n resources (handled by frontend)."""

        def preload_i18n():
            try:
                debug_log("i18n preload complete (frontend)")
                return True
            except Exception as e:
                debug_log(f"i18n preload failed: {e}")
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

        debug_log("Compression and cache middleware configured")

    def _setup_memory_monitoring(self):
        """Setup memory monitoring."""
        try:
            self.memory_monitor = get_memory_monitor()

            def web_memory_alert(alert):
                debug_log(f"Web UI memory alert [{alert.level}]: {alert.message}")
                if alert.level == "critical":
                    cleaned = self.cleanup_expired_sessions()
                    debug_log(f"Memory critical: cleaned {cleaned} expired sessions")
                elif alert.level == "emergency":
                    cleaned = self.cleanup_sessions_by_memory_pressure(force=True)
                    debug_log(f"Memory emergency: force cleaned {cleaned} sessions")

            self.memory_monitor.add_alert_callback(web_memory_alert)

            def session_cleanup_callback(force: bool = False):
                try:
                    if force:
                        cleaned = self.cleanup_sessions_by_memory_pressure(force=True)
                        debug_log(f"Memory monitor force cleaned {cleaned} sessions")
                    else:
                        cleaned = self.cleanup_expired_sessions()
                        debug_log(f"Memory monitor cleaned {cleaned} expired sessions")
                except Exception as e:
                    error_id = ErrorHandler.log_error_with_context(
                        e,
                        context={"operation": "memory_monitor_session_cleanup", "force": force},
                        error_type=ErrorType.SYSTEM,
                    )
                    debug_log(f"Memory monitor session cleanup failed [error_id: {error_id}]: {e}")

            self.memory_monitor.add_cleanup_callback(session_cleanup_callback)

            if not self.memory_monitor.is_monitoring:
                self.memory_monitor.start_monitoring()

            debug_log("Web UI memory monitoring configured with session cleanup callback")

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e,
                context={"operation": "setup_web_ui_memory_monitoring"},
                error_type=ErrorType.SYSTEM,
            )
            debug_log(f"Setup Web UI memory monitoring failed [error_id: {error_id}]: {e}")

    def _setup_static_files(self):
        """Setup static file serving (Flutter Web only)."""
        self.flutter_build_path: Path | None = None

        dev_path = Path(__file__).parent.parent.parent.parent / "frontend" / "build" / "web"
        pkg_path = Path(__file__).parent.parent / "flutter_web"

        if dev_path.exists():
            self.flutter_build_path = dev_path
            debug_log(f"Flutter Web build found (dev): {dev_path}")
        elif pkg_path.exists():
            self.flutter_build_path = pkg_path
            debug_log(f"Flutter Web build found (package): {pkg_path}")
        else:
            self.flutter_build_path = None
            debug_log(f"Flutter Web build not found. Searched: {dev_path}, {pkg_path}")

    def create_session(self, project_directory: str, summary: str) -> str:
        """Create new feedback session; single active session mode, preserves tab state."""
        old_session = self.current_session
        old_websocket = None
        if old_session and old_session.websocket:
            old_websocket = old_session.websocket
            debug_log("Saved old session WebSocket for update notification")

        session_id = str(uuid.uuid4())
        session = WebFeedbackSession(session_id, project_directory, summary)

        if old_session:
            debug_log(
                f"Processing old session {old_session.session_id} state transition, status: {old_session.status.value}"
            )

            if hasattr(old_session, "active_tabs"):
                self._merge_tabs_to_global(old_session.active_tabs)

            if old_session.status == SessionStatus.FEEDBACK_SUBMITTED:
                debug_log(
                    f"Old session {old_session.session_id} next_step: submitted -> completed"
                )
                success = old_session.next_step("Feedback processed, session completed")
                if success:
                    debug_log(f"Old session {old_session.session_id} moved to completed")
                else:
                    debug_log(f"Old session {old_session.session_id} failed next_step")
            else:
                debug_log(
                    f"Old session {old_session.session_id} status {old_session.status.value}, no transition"
                )

            if old_session.session_id in self.sessions:
                debug_log(f"Old session {old_session.session_id} still in sessions dict")
            else:
                debug_log(f"Old session {old_session.session_id} not in dict, re-adding")
                self.sessions[old_session.session_id] = old_session

            old_session._cleanup_sync()

        session.active_tabs = self.global_active_tabs.copy()

        self.current_session = session
        self.sessions[session_id] = session

        debug_log(f"Created new active session: {session_id}")
        debug_log(f"Inherited {len(session.active_tabs)} active tabs")

        if old_websocket:
            session.websocket = old_websocket
            debug_log("Transferred old WebSocket connection to new session")
        else:
            self._pending_session_update = True
            debug_log("No old WebSocket, set pending session update")

        return session_id

    def get_session(self, session_id: str) -> WebFeedbackSession | None:
        """Get feedback session (backward compatible)."""
        return self.sessions.get(session_id)

    def get_current_session(self) -> WebFeedbackSession | None:
        """Get current active session."""
        return self.current_session

    def remove_session(self, session_id: str):
        """Remove feedback session."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.cleanup()
            del self.sessions[session_id]

            if self.current_session and self.current_session.session_id == session_id:
                self.current_session = None
                debug_log("Cleared current active session")

            debug_log(f"Removed feedback session: {session_id}")

    def clear_current_session(self):
        """Clear current active session."""
        if self.current_session:
            session_id = self.current_session.session_id
            self.current_session.cleanup()
            self.current_session = None

            if session_id in self.sessions:
                del self.sessions[session_id]

            debug_log("Cleared current active session")

    def _merge_tabs_to_global(self, session_tabs: dict):
        """Merge session tab state into global state."""
        current_time = time.time()
        expired_threshold = 60

        self.global_active_tabs = {
            tab_id: tab_info
            for tab_id, tab_info in self.global_active_tabs.items()
            if current_time - tab_info.get("last_seen", 0) <= expired_threshold
        }

        for tab_id, tab_info in session_tabs.items():
            if current_time - tab_info.get("last_seen", 0) <= expired_threshold:
                self.global_active_tabs[tab_id] = tab_info

        debug_log(f"Merged tab state, global active tabs: {len(self.global_active_tabs)}")

    def get_global_active_tabs_count(self) -> int:
        """Get count of global active tabs."""
        current_time = time.time()
        expired_threshold = 60

        valid_tabs = {
            tab_id: tab_info
            for tab_id, tab_info in self.global_active_tabs.items()
            if current_time - tab_info.get("last_seen", 0) <= expired_threshold
        }

        self.global_active_tabs = valid_tabs
        return len(valid_tabs)

    async def broadcast_to_active_tabs(self, message: dict):
        """Broadcast message to all active tabs."""
        if not self.current_session or not self.current_session.websocket:
            debug_log("No active WebSocket connection, cannot broadcast")
            return

        try:
            await self.current_session.websocket.send_json(message)
            debug_log(f"Broadcast to active tabs: {message.get('type', 'unknown')}")
        except Exception as e:
            debug_log(f"Broadcast failed: {e}")

    def start_server(self):
        """Start Web server (supports parallel init)."""

        def run_server_with_retry():
            max_retries = 5
            retry_count = 0
            original_port = self.port

            while retry_count < max_retries:
                try:
                    if not PortManager.is_port_available(self.host, self.port):
                        debug_log(f"Port {self.port} in use, searching for alternative")

                        process_info = PortManager.find_process_using_port(self.port)
                        if process_info:
                            debug_log(
                                f"Port {self.port} used by {process_info['name']} "
                                f"(PID: {process_info['pid']})"
                            )

                        try:
                            new_port = PortManager.find_free_port_enhanced(
                                preferred_port=self.port,
                                auto_cleanup=False,
                                host=self.host,
                            )
                            debug_log(f"Switched port: {self.port} -> {new_port}")
                            self.port = new_port
                        except RuntimeError as port_error:
                            error_id = ErrorHandler.log_error_with_context(
                                port_error,
                                context={
                                    "operation": "port_lookup",
                                    "original_port": original_port,
                                    "current_port": self.port,
                                },
                                error_type=ErrorType.NETWORK,
                            )
                            debug_log(
                                f"No available port [error_id: {error_id}]: {port_error}"
                            )
                            raise RuntimeError(
                                f"No available port, original {original_port} in use"
                            ) from port_error

                    debug_log(
                        f"Starting server at {self.host}:{self.port} (attempt {retry_count + 1}/{max_retries})"
                    )

                    config = uvicorn.Config(
                        app=self.app,
                        host=self.host,
                        port=self.port,
                        log_level="warning",
                        access_log=False,
                    )

                    server_instance = uvicorn.Server(config)

                    async def serve_with_async_init(server=server_instance):
                        server_task = asyncio.create_task(server.serve())
                        init_task = asyncio.create_task(self._init_async_components())
                        await asyncio.gather(
                            server_task, init_task, return_exceptions=True
                        )

                    asyncio.run(serve_with_async_init())

                    if self.port != original_port:
                        debug_log(
                            f"Server started on alternate port {self.port} (original {original_port} in use)"
                        )

                    break

                except OSError as e:
                    if e.errno in {10048, 98}:
                        retry_count += 1
                        if retry_count < max_retries:
                            debug_log(
                                f"Port {self.port} startup failed (OSError), trying next"
                            )
                            self.port = self.port + 1
                        else:
                            debug_log("Max retries reached, server startup failed")
                            break
                    else:
                        error_id = ErrorHandler.log_error_with_context(
                            e,
                            context={
                                "operation": "server_startup",
                                "host": self.host,
                                "port": self.port,
                            },
                            error_type=ErrorType.NETWORK,
                        )
                        debug_log(f"Server startup error [error_id: {error_id}]: {e}")
                        break
                except Exception as e:
                    error_id = ErrorHandler.log_error_with_context(
                        e,
                        context={
                            "operation": "server_run",
                            "host": self.host,
                            "port": self.port,
                        },
                        error_type=ErrorType.SYSTEM,
                    )
                    debug_log(f"Server run error [error_id: {error_id}]: {e}")
                    break

        self.server_thread = threading.Thread(target=run_server_with_retry, daemon=True)
        self.server_thread.start()

        time.sleep(2)

    def open_browser(self, url: str):
        """Open browser."""
        try:
            browser_opener = get_browser_opener()
            browser_opener(url)
            debug_log(f"Opened browser: {url}")
        except Exception as e:
            debug_log(f"Failed to open browser: {e}")

    async def smart_open_browser(self, url: str) -> bool:
        """Open browser; reuse existing tab if active.

        Returns:
            bool: True if active tabs detected, False if new window opened.
        """
        try:
            has_active_tabs = await self._check_active_tabs()

            if has_active_tabs:
                debug_log("Active tabs detected, sending refresh")
                debug_log(f"Sending refresh to existing tabs: {url}")

                refresh_success = await self.notify_existing_tab_to_refresh()

                debug_log(f"Refresh result: {refresh_success}")
                debug_log("Active tabs detected, not opening new window")
                return True

            debug_log("No active tabs, opening new browser window")
            self.open_browser(url)
            return False

        except Exception as e:
            debug_log(f"Smart open failed, fallback to regular open: {e}")
            self.open_browser(url)
            return False

    async def _safe_close_websocket(self, websocket):
        """Safely close WebSocket (only after connection transferred)."""
        if not websocket:
            return

        try:
            if (
                hasattr(websocket, "client_state")
                and websocket.client_state.DISCONNECTED
            ):
                debug_log("WebSocket disconnected, skip close")
                return

            debug_log("WebSocket transferred to new session, skip close")

        except Exception as e:
            debug_log(f"Error checking WebSocket state: {e}")

    async def notify_existing_tab_to_refresh(self) -> bool:
        """Notify existing tabs to refresh for new session.

        Returns:
            bool: True if sent successfully.
        """
        try:
            if not self.current_session or not self.current_session.websocket:
                debug_log("No active WebSocket, cannot send refresh")
                return False

            refresh_message = {
                "type": "session_updated",
                "action": "new_session_created",
                "messageCode": "session.created",
                "session_info": {
                    "session_id": self.current_session.session_id,
                    "project_directory": self.current_session.project_directory,
                    "summary": self.current_session.summary,
                    "status": self.current_session.status.value,
                },
            }

            await self.current_session.websocket.send_json(refresh_message)
            debug_log(f"Refresh sent to existing tabs: {self.current_session.session_id}")

            await asyncio.sleep(0.2)
            debug_log("Refresh notification sent")
            return True

        except Exception as e:
            debug_log(f"Send refresh failed: {e}")
            return False

    async def _check_active_tabs(self) -> bool:
        """Check for active tabs (layered detection)."""
        try:
            if not self.current_session or not self.current_session.websocket:
                debug_log("Quick check: no session or WebSocket")
                return False

            last_heartbeat = getattr(self.current_session, "last_heartbeat", None)
            if last_heartbeat:
                heartbeat_age = time.time() - last_heartbeat
                if heartbeat_age > 10:
                    debug_log(f"Quick check: heartbeat timeout ({heartbeat_age:.1f}s)")
                else:
                    debug_log(f"Quick check: heartbeat ok ({heartbeat_age:.1f}s ago)")
                    return True

            try:
                websocket = self.current_session.websocket

                if hasattr(websocket, "client_state"):
                    try:
                        import starlette.websockets  # type: ignore[import-not-found]

                        if hasattr(starlette.websockets, "WebSocketState"):
                            WebSocketState = starlette.websockets.WebSocketState
                            if websocket.client_state != WebSocketState.CONNECTED:
                                debug_log(
                                    f"Check: WebSocket not CONNECTED, state={websocket.client_state}"
                                )
                                self.current_session.websocket = None
                                return False
                    except ImportError:
                        debug_log("WebSocketState import failed, using fallback")

                await websocket.send_json({"type": "ping", "timestamp": time.time()})
                debug_log("Check: ping sent, connection active")
                return True

            except Exception as e:
                debug_log(f"Check: connection test failed - {e}")
                if self.current_session:
                    self.current_session.websocket = None
                return False

        except Exception as e:
            debug_log(f"Error checking active connection: {e}")
            return False

    def get_server_url(self) -> str:
        """Get server URL."""
        return f"http://{self.host}:{self.port}"

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        cleanup_start_time = time.time()
        expired_sessions = []

        for session_id, session in self.sessions.items():
            if session.is_expired():
                expired_sessions.append(session_id)

        cleaned_count = 0
        for session_id in expired_sessions:
            try:
                if session_id in self.sessions:
                    session = self.sessions[session_id]
                    session._cleanup_sync_enhanced(CleanupReason.EXPIRED)
                    del self.sessions[session_id]
                    cleaned_count += 1

                    if (
                        self.current_session
                        and self.current_session.session_id == session_id
                    ):
                        self.current_session = None
                        debug_log("Cleared expired current session")

            except Exception as e:
                error_id = ErrorHandler.log_error_with_context(
                    e,
                    context={"session_id": session_id, "operation": "cleanup_expired_sessions"},
                    error_type=ErrorType.SYSTEM,
                )
                debug_log(f"Cleanup expired session {session_id} failed [error_id: {error_id}]: {e}")

        cleanup_duration = time.time() - cleanup_start_time
        self.cleanup_stats.update(
            {
                "total_cleanups": self.cleanup_stats["total_cleanups"] + 1,
                "expired_cleanups": self.cleanup_stats["expired_cleanups"] + 1,
                "last_cleanup_time": datetime.now().isoformat(),
                "total_cleanup_duration": self.cleanup_stats["total_cleanup_duration"]
                + cleanup_duration,
                "sessions_cleaned": self.cleanup_stats["sessions_cleaned"]
                + cleaned_count,
            }
        )

        if cleaned_count > 0:
            debug_log(
                f"Cleaned {cleaned_count} expired sessions in {cleanup_duration:.2f}s"
            )

        return cleaned_count

    def cleanup_sessions_by_memory_pressure(self, force: bool = False) -> int:
        """Clean sessions under memory pressure."""
        cleanup_start_time = time.time()
        sessions_to_clean = []

        for session_id, session in self.sessions.items():
            if (
                not force
                and self.current_session
                and session.session_id == self.current_session.session_id
            ):
                continue

            if session.status in [
                SessionStatus.COMPLETED,
                SessionStatus.ERROR,
                SessionStatus.TIMEOUT,
            ]:
                sessions_to_clean.append((session_id, session, 1))
            elif session.status == SessionStatus.FEEDBACK_SUBMITTED:
                if session.get_idle_time() > 300:
                    sessions_to_clean.append((session_id, session, 2))
            elif session.get_idle_time() > 600:
                sessions_to_clean.append((session_id, session, 3))

        sessions_to_clean.sort(key=lambda x: x[2])

        max_cleanup = min(
            len(sessions_to_clean), 5 if not force else len(sessions_to_clean)
        )
        cleaned_count = 0

        for i in range(max_cleanup):
            session_id, session, _ = sessions_to_clean[i]
            try:
                session._cleanup_sync_enhanced(CleanupReason.MEMORY_PRESSURE)
                del self.sessions[session_id]
                cleaned_count += 1

                if (
                    self.current_session
                    and self.current_session.session_id == session_id
                ):
                    self.current_session = None
                    debug_log("Cleared current session under memory pressure")

            except Exception as e:
                error_id = ErrorHandler.log_error_with_context(
                    e,
                    context={"session_id": session_id, "operation": "memory_pressure_cleanup"},
                    error_type=ErrorType.SYSTEM,
                )
                debug_log(
                    f"Memory pressure cleanup {session_id} failed [error_id: {error_id}]: {e}"
                )

        cleanup_duration = time.time() - cleanup_start_time
        self.cleanup_stats.update(
            {
                "total_cleanups": self.cleanup_stats["total_cleanups"] + 1,
                "memory_pressure_cleanups": self.cleanup_stats[
                    "memory_pressure_cleanups"
                ]
                + 1,
                "last_cleanup_time": datetime.now().isoformat(),
                "total_cleanup_duration": self.cleanup_stats["total_cleanup_duration"]
                + cleanup_duration,
                "sessions_cleaned": self.cleanup_stats["sessions_cleaned"]
                + cleaned_count,
            }
        )

        if cleaned_count > 0:
            debug_log(
                f"Memory pressure: cleaned {cleaned_count} sessions in {cleanup_duration:.2f}s"
            )

        return cleaned_count

    def get_session_cleanup_stats(self) -> dict:
        """Get session cleanup statistics."""
        stats = self.cleanup_stats.copy()
        stats.update(
            {
                "active_sessions": len(self.sessions),
                "current_session_id": self.current_session.session_id
                if self.current_session
                else None,
                "expired_sessions": sum(
                    1 for s in self.sessions.values() if s.is_expired()
                ),
                "idle_sessions": sum(
                    1 for s in self.sessions.values() if s.get_idle_time() > 300
                ),
                "memory_usage_mb": 0,
            }
        )

        try:
            import psutil

            process = psutil.Process()
            stats["memory_usage_mb"] = round(
                process.memory_info().rss / (1024 * 1024), 2
            )
        except:
            pass

        return stats

    def _scan_expired_sessions(self) -> list[str]:
        """Scan and return expired session IDs."""
        expired_sessions = []
        for session_id, session in self.sessions.items():
            if session.is_expired():
                expired_sessions.append(session_id)
        return expired_sessions

    def stop(self):
        """Stop Web UI service."""
        cleanup_start_time = time.time()
        session_count = len(self.sessions)

        for session in list(self.sessions.values()):
            try:
                session._cleanup_sync_enhanced(CleanupReason.SHUTDOWN)
            except Exception as e:
                debug_log(f"Session cleanup failed during stop: {e}")

        self.sessions.clear()
        self.current_session = None

        cleanup_duration = time.time() - cleanup_start_time
        self.cleanup_stats.update(
            {
                "total_cleanups": self.cleanup_stats["total_cleanups"] + 1,
                "manual_cleanups": self.cleanup_stats["manual_cleanups"] + 1,
                "last_cleanup_time": datetime.now().isoformat(),
                "total_cleanup_duration": self.cleanup_stats["total_cleanup_duration"]
                + cleanup_duration,
                "sessions_cleaned": self.cleanup_stats["sessions_cleaned"]
                + session_count,
            }
        )

        debug_log(
            f"Stopped service: cleaned {session_count} sessions in {cleanup_duration:.2f}s"
        )

        if self.server_thread is not None and self.server_thread.is_alive():
            debug_log("Stopping Web UI service")


_web_ui_manager: WebUIManager | None = None


def get_web_ui_manager() -> WebUIManager:
    """Get Web UI manager instance."""
    global _web_ui_manager
    if _web_ui_manager is None:
        _web_ui_manager = WebUIManager()
    return _web_ui_manager


async def launch_web_feedback_ui(
    project_directory: str, summary: str, timeout: int = 600
) -> dict:
    """Launch Web feedback UI and wait for user feedback.

    Args:
        project_directory: Project directory path.
        summary: AI work summary.
        timeout: Timeout in seconds.

    Returns:
        dict: Feedback result with logs, interactive_feedback, images.
    """
    manager = get_web_ui_manager()

    manager.create_session(project_directory, summary)
    session = manager.get_current_session()

    if not session:
        raise RuntimeError("Failed to create feedback session")

    if manager.server_thread is None or not manager.server_thread.is_alive():
        manager.start_server()

    feedback_url = manager.get_server_url()
    has_active_tabs = await manager.smart_open_browser(feedback_url)

    debug_log(f"[DEBUG] Server URL: {feedback_url}")

    if has_active_tabs:
        debug_log("Active tabs detected, session update notification sent")

    try:
        result = await session.wait_for_feedback(timeout)
        debug_log("Received user feedback")
        return result
    except TimeoutError:
        debug_log("Session timeout")
        raise
    except Exception as e:
        debug_log(f"Session error: {e}")
        raise
    finally:
        debug_log("Session kept active for next MCP call")


def stop_web_ui():
    """Stop Web UI service."""
    global _web_ui_manager
    if _web_ui_manager:
        _web_ui_manager.stop()
        _web_ui_manager = None
        debug_log("Web UI service stopped")


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

            from ..debug import debug_log

            debug_log("Starting Web UI test...")
            debug_log(f"Project dir: {project_dir}")
            debug_log("Waiting for user feedback...")

            result = await launch_web_feedback_ui(project_dir, summary)

            debug_log("Received feedback result:")
            debug_log(f"Command logs: {result.get('logs', '')}")
            debug_log(f"Interactive feedback: {result.get('interactive_feedback', '')}")
            debug_log(f"Images count: {len(result.get('images', []))}")

        except KeyboardInterrupt:
            debug_log("\nUser cancelled")
        except Exception as e:
            debug_log(f"Error: {e}")
        finally:
            stop_web_ui()

    asyncio.run(main())
