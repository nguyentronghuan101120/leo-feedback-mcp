#!/usr/bin/env python3
"""
Web feedback session model.

Manages data and logic for web feedback sessions.

Note: subprocess calls use shlex.split() and shell=False to prevent injection.
"""

import asyncio
import base64
import shlex
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import WebSocket

from ...debug import web_debug_log as debug_log
from ...utils.error_handler import ErrorHandler, ErrorType
from ...utils.resource_manager import get_resource_manager, register_process
from ..constants import get_message_code


class SessionStatus(Enum):
    """Session status enum (one-way transitions)."""

    WAITING = "waiting"
    ACTIVE = "active"
    FEEDBACK_SUBMITTED = "feedback_submitted"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"
    EXPIRED = "expired"


class CleanupReason(Enum):
    """Cleanup reason enum."""

    TIMEOUT = "timeout"
    EXPIRED = "expired"
    MEMORY_PRESSURE = "memory_pressure"
    MANUAL = "manual"
    ERROR = "error"
    SHUTDOWN = "shutdown"


MAX_IMAGE_SIZE = 1 * 1024 * 1024  # 1MB limit
SUPPORTED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/bmp",
    "image/webp",
}
TEMP_DIR = Path.home() / ".cache" / "interactive-feedback-mcp-web"

def _safe_parse_command(command: str) -> list[str]:
    """
    Parse command string safely to avoid shell injection.

    Args:
        command: Command string.

    Returns:
        Parsed command argument list.

    Raises:
        ValueError: If command contains unsafe characters.
    """
    try:
        parsed = shlex.split(command)

        dangerous_patterns = [
            ";",
            "&&",
            "||",
            "|",
            ">",
            "<",
            "`",
            "$(",
            "rm -rf",
            "del /f",
            "format",
            "fdisk",
        ]

        command_lower = command.lower()
        for pattern in dangerous_patterns:
            if pattern in command_lower:
                raise ValueError(f"Command contains unsafe pattern: {pattern}")

        if not parsed:
            raise ValueError("Empty command")

        return parsed

    except Exception as e:
        debug_log(f"Command parse failed: {e}")
        raise ValueError(f"Cannot safely parse command: {e}") from e


class WebFeedbackSession:
    """Web feedback session manager."""

    def __init__(
        self,
        session_id: str,
        project_directory: str,
        summary: str,
        auto_cleanup_delay: int = 3600,
        max_idle_time: int = 1800,
    ):
        self.session_id = session_id
        self.project_directory = project_directory
        self.summary = summary
        self.websocket: WebSocket | None = None
        self.feedback_result: str | None = None
        self.images: list[dict] = []
        self.settings: dict[str, Any] = {}
        self.feedback_completed = threading.Event()
        self.process: subprocess.Popen | None = None
        self.command_logs: list[str] = []
        self.user_messages: list[dict] = []
        self._cleanup_done = False

        self.status = SessionStatus.WAITING
        self.status_message = "Waiting for user feedback"
        self.created_at = time.time()
        self.last_activity = self.created_at
        self.last_heartbeat = None

        self.auto_cleanup_delay = auto_cleanup_delay
        self.max_idle_time = max_idle_time
        self.cleanup_timer: threading.Timer | None = None
        self.cleanup_callbacks: list[Callable[..., None]] = []
        self.cleanup_stats: dict[str, Any] = {
            "cleanup_count": 0,
            "last_cleanup_time": None,
            "cleanup_reason": None,
            "cleanup_duration": 0.0,
            "memory_freed": 0,
            "resources_cleaned": 0,
        }

        self.active_tabs: dict[str, Any] = {}

        self.user_timeout_enabled = False
        self.user_timeout_seconds = 3600
        self.user_timeout_timer: threading.Timer | None = None

        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        self.resource_manager = get_resource_manager()

        self._schedule_auto_cleanup()

        debug_log(
            f"Session {self.session_id} initialized, auto_cleanup_delay={auto_cleanup_delay}s, max_idle={max_idle_time}s"
        )

    def get_message_code(self, key: str) -> str:
        """Get message code for frontend i18n."""
        return get_message_code(key)

    def next_step(self, message: str | None = None) -> bool:
        """Transition to next status (one-way, no rollback)."""
        old_status = self.status

        next_status_map = {
            SessionStatus.WAITING: SessionStatus.ACTIVE,
            SessionStatus.ACTIVE: SessionStatus.FEEDBACK_SUBMITTED,
            SessionStatus.FEEDBACK_SUBMITTED: SessionStatus.COMPLETED,
            SessionStatus.COMPLETED: None,
            SessionStatus.ERROR: None,
            SessionStatus.TIMEOUT: None,
            SessionStatus.EXPIRED: None,
        }

        next_status = next_status_map.get(self.status)

        if next_status is None:
            debug_log(
                f"Session {self.session_id} already in terminal state {self.status.value}, cannot advance"
            )
            return False

        self.status = next_status
        if message:
            self.status_message = message
        else:
            default_messages = {
                SessionStatus.ACTIVE: "Session started",
                SessionStatus.FEEDBACK_SUBMITTED: "User submitted feedback",
                SessionStatus.COMPLETED: "Session completed",
            }
            self.status_message = default_messages.get(next_status, "Status updated")

        self.last_activity = time.time()

        if next_status == SessionStatus.FEEDBACK_SUBMITTED:
            self._schedule_auto_cleanup()

        debug_log(
            f"Session {self.session_id} status: {old_status.value} -> {next_status.value} - {self.status_message}"
        )
        return True

    def set_error(self, message: str = "Session error") -> bool:
        """Set error state (can enter from any state)."""
        old_status = self.status
        self.status = SessionStatus.ERROR
        self.status_message = message
        self.last_activity = time.time()

        debug_log(
            f"Session {self.session_id} set to error: {old_status.value} -> {self.status.value} - {message}"
        )
        return True

    def set_expired(self, message: str = "Session expired") -> bool:
        """Set expired state (can enter from any state)."""
        old_status = self.status
        self.status = SessionStatus.EXPIRED
        self.status_message = message
        self.last_activity = time.time()

        debug_log(
            f"Session {self.session_id} set to expired: {old_status.value} -> {self.status.value} - {message}"
        )
        return True

    def can_proceed(self) -> bool:
        """Check if session can advance to next step."""
        return self.status in [SessionStatus.WAITING, SessionStatus.FEEDBACK_SUBMITTED]

    def is_terminal(self) -> bool:
        """Check if session is in terminal state."""
        return self.status in [
            SessionStatus.COMPLETED,
            SessionStatus.ERROR,
            SessionStatus.TIMEOUT,
            SessionStatus.EXPIRED,
        ]

    def get_status_info(self) -> dict[str, Any]:
        """Get session status info."""
        return {
            "status": self.status.value,
            "message": self.status_message,
            "feedback_completed": self.feedback_completed.is_set(),
            "has_websocket": self.websocket is not None,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "project_directory": self.project_directory,
            "summary": self.summary,
            "session_id": self.session_id,
        }

    def is_active(self) -> bool:
        """Check if session is active."""
        return self.status in [
            SessionStatus.WAITING,
            SessionStatus.ACTIVE,
            SessionStatus.FEEDBACK_SUBMITTED,
        ]

    def is_expired(self) -> bool:
        """Check if session has expired."""
        current_time = time.time()

        idle_time = current_time - self.last_activity
        if idle_time > self.max_idle_time:
            debug_log(
                f"Session {self.session_id} idle too long: {idle_time:.1f}s > {self.max_idle_time}s"
            )
            return True

        if self.status == SessionStatus.EXPIRED:
            return True

        if self.status in [SessionStatus.ERROR, SessionStatus.TIMEOUT]:
            error_time = current_time - self.last_activity
            if error_time > 300:
                debug_log(
                    f"Session {self.session_id} in error state too long: {error_time:.1f}s"
                )
                return True

        return False

    def get_age(self) -> float:
        """Get session age in seconds."""
        current_time = time.time()
        return current_time - self.created_at

    def get_idle_time(self) -> float:
        """Get session idle time in seconds."""
        current_time = time.time()
        return current_time - self.last_activity

    def _schedule_auto_cleanup(self):
        """Schedule auto cleanup timer."""
        if self.cleanup_timer:
            self.cleanup_timer.cancel()

        def auto_cleanup():
            try:
                if not self._cleanup_done and self.is_expired():
                    debug_log(f"Session {self.session_id} auto cleanup (expired)")
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(
                            self._cleanup_resources_enhanced(CleanupReason.EXPIRED)
                        )
                    except RuntimeError:
                        self._cleanup_sync_enhanced(CleanupReason.EXPIRED)
                else:
                    self._schedule_auto_cleanup()
            except Exception as e:
                error_id = ErrorHandler.log_error_with_context(
                    e,
                    context={"session_id": self.session_id, "operation": "auto_cleanup"},
                    error_type=ErrorType.SYSTEM,
                )
                debug_log(f"Auto cleanup failed [error_id: {error_id}]: {e}")

        self.cleanup_timer = threading.Timer(self.auto_cleanup_delay, auto_cleanup)
        self.cleanup_timer.daemon = True
        self.cleanup_timer.start()
        debug_log(
            f"Session {self.session_id} auto cleanup timer set, triggers in {self.auto_cleanup_delay}s"
        )

    def extend_cleanup_timer(self, additional_time: int | None = None):
        """Extend cleanup timer."""
        if additional_time is None:
            additional_time = self.auto_cleanup_delay

        if self.cleanup_timer:
            self.cleanup_timer.cancel()

        self.cleanup_timer = threading.Timer(additional_time, lambda: None)
        self.cleanup_timer.daemon = True
        self.cleanup_timer.start()

        debug_log(f"Session {self.session_id} cleanup timer extended by {additional_time}s")

    def add_cleanup_callback(self, callback: Callable[..., None]):
        """Add cleanup callback."""
        if callback not in self.cleanup_callbacks:
            self.cleanup_callbacks.append(callback)
            debug_log(f"Session {self.session_id} added cleanup callback")

    def remove_cleanup_callback(self, callback: Callable[..., None]):
        """Remove cleanup callback."""
        if callback in self.cleanup_callbacks:
            self.cleanup_callbacks.remove(callback)
            debug_log(f"Session {self.session_id} removed cleanup callback")

    def get_cleanup_stats(self) -> dict[str, Any]:
        """Get cleanup stats."""
        stats = self.cleanup_stats.copy()
        stats.update(
            {
                "session_id": self.session_id,
                "age": self.get_age(),
                "idle_time": self.get_idle_time(),
                "is_expired": self.is_expired(),
                "is_active": self.is_active(),
                "status": self.status.value,
                "has_websocket": self.websocket is not None,
                "has_process": self.process is not None,
                "command_logs_count": len(self.command_logs),
                "images_count": len(self.images),
            }
        )
        return stats

    def update_timeout_settings(self, enabled: bool, timeout_seconds: int = 3600):
        """Update user-configured session timeout."""
        debug_log(f"Update session timeout: enabled={enabled}, seconds={timeout_seconds}")

        if self.user_timeout_timer:
            self.user_timeout_timer.cancel()
            self.user_timeout_timer = None

        self.user_timeout_enabled = enabled
        self.user_timeout_seconds = timeout_seconds

        if enabled and self.status == SessionStatus.WAITING:

            def timeout_handler():
                debug_log(f"User timeout reached: {self.session_id}")
                self.status = SessionStatus.TIMEOUT
                self.status_message = "User-configured session timeout"
                self.feedback_completed.set()

            self.user_timeout_timer = threading.Timer(timeout_seconds, timeout_handler)
            self.user_timeout_timer.start()
            debug_log(f"Started user timeout timer: {timeout_seconds}s")

    async def wait_for_feedback(self, timeout: int = 600) -> dict[str, Any]:
        """
        Wait for user feedback (including images), with timeout and auto cleanup.

        Args:
            timeout: Timeout in seconds.

        Returns:
            Feedback result dict.
        """
        try:
            if timeout <= 30:
                actual_timeout = max(timeout - 1, 5)
            else:
                actual_timeout = timeout - 5
            debug_log(
                f"Session {self.session_id} waiting for feedback, timeout={actual_timeout}s (original={timeout}s)"
            )

            loop = asyncio.get_event_loop()

            def wait_in_thread():
                return self.feedback_completed.wait(actual_timeout)

            completed = await loop.run_in_executor(None, wait_in_thread)

            if completed:
                if self.status == SessionStatus.TIMEOUT and self.user_timeout_enabled:
                    debug_log(f"Session {self.session_id} ended due to user timeout")
                    await self._cleanup_resources_on_timeout()
                    raise TimeoutError("Session closed due to user-configured timeout")

                debug_log(f"Session {self.session_id} received user feedback")
                return {
                    "logs": "\n".join(self.command_logs),
                    "interactive_feedback": self.feedback_result or "",
                    "images": self.images,
                    "settings": self.settings,
                }
            debug_log(
                f"Session {self.session_id} timed out after {actual_timeout}s, cleaning up..."
            )
            await self._cleanup_resources_on_timeout()
            raise TimeoutError(
                f"Wait for feedback timed out ({actual_timeout}s), interface auto-closed"
            )

        except Exception as e:
            debug_log(f"Session {self.session_id} exception: {e}")
            await self._cleanup_resources_on_timeout()
            raise

    async def submit_feedback(
        self,
        feedback: str,
        images: list[dict[str, Any]],
        settings: dict[str, Any] | None = None,
    ):
        """Submit feedback and images."""
        self.feedback_result = feedback
        self.settings = settings or {}
        self.images = self._process_images(images)

        self.next_step("Feedback submitted, waiting for next MCP call")

        self.feedback_completed.set()

        if self.websocket:
            try:
                await self.websocket.send_json(
                    {
                        "type": "notification",
                        "code": self.get_message_code("FEEDBACK_SUBMITTED"),
                        "severity": "success",
                        "status": self.status.value,
                    }
                )

            except Exception as e:
                debug_log(f"Send feedback confirmation failed: {e}")

    def add_user_message(self, message_data: dict[str, Any]) -> None:
        """Add user message record."""
        import time

        user_message = {
            "timestamp": int(time.time() * 1000),
            "content": message_data.get("content", ""),
            "images": message_data.get("images", []),
            "submission_method": message_data.get("submission_method", "manual"),
            "type": "feedback",
        }

        self.user_messages.append(user_message)
        debug_log(
            f"Session {self.session_id} added user message, total: {len(self.user_messages)}"
        )

    def _process_images(self, images: list[dict]) -> list[dict]:
        """Process image data into unified format."""
        processed_images = []

        size_limit = self.settings.get("image_size_limit", MAX_IMAGE_SIZE)

        for img in images:
            try:
                if not all(key in img for key in ["name", "data", "size"]):
                    continue

                if size_limit > 0 and img["size"] > size_limit:
                    debug_log(
                        f"Image {img['name']} exceeds size limit ({size_limit} bytes), skipped"
                    )
                    continue

                if isinstance(img["data"], str):
                    try:
                        image_bytes = base64.b64decode(img["data"])
                    except Exception as e:
                        debug_log(f"Image {img['name']} base64 decode failed: {e}")
                        continue
                else:
                    image_bytes = img["data"]

                if len(image_bytes) == 0:
                    debug_log(f"Image {img['name']} empty data, skipped")
                    continue

                processed_images.append(
                    {
                        "name": img["name"],
                        "data": image_bytes,
                        "size": len(image_bytes),
                    }
                )

                debug_log(
                    f"Image {img['name']} processed, size: {len(image_bytes)} bytes"
                )

            except Exception as e:
                debug_log(f"Image processing error: {e}")
                continue

        return processed_images

    def add_log(self, log_entry: str):
        """Add command log entry."""
        self.command_logs.append(log_entry)

    async def run_command(self, command: str):
        """Execute command and send output via WebSocket (safe version)."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None

        try:
            debug_log(f"Execute command: {command}")

            try:
                parsed_command = _safe_parse_command(command)
            except ValueError as e:
                error_msg = f"Command safety check failed: {e}"
                debug_log(error_msg)
                if self.websocket:
                    await self.websocket.send_json(
                        {"type": "command_error", "error": error_msg}
                    )
                return

            self.process = subprocess.Popen(
                parsed_command,
                shell=False,
                cwd=self.project_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            register_process(
                self.process,
                description=f"WebFeedbackSession-{self.session_id}-command",
                auto_cleanup=True,
            )

            async def read_output():
                loop = asyncio.get_event_loop()
                try:
                    def read_line():
                        if self.process and self.process.stdout:
                            return self.process.stdout.readline()
                        return ""

                    while True:
                        line = await loop.run_in_executor(None, read_line)
                        if not line:
                            break

                        self.add_log(line.rstrip())
                        if self.websocket:
                            try:
                                await self.websocket.send_json(
                                    {"type": "command_output", "output": line}
                                )
                            except Exception as e:
                                debug_log(f"WebSocket send failed: {e}")
                                break

                except Exception as e:
                    debug_log(f"Read command output error: {e}")
                finally:
                    if self.process:
                        exit_code = self.process.wait()

                        self.resource_manager.unregister_process(self.process.pid)

                        if self.websocket:
                            try:
                                await self.websocket.send_json(
                                    {"type": "command_complete", "exit_code": exit_code}
                                )
                            except Exception as e:
                                debug_log(f"Send completion signal failed: {e}")

            asyncio.create_task(read_output())

        except Exception as e:
            debug_log(f"Execute command error: {e}")
            if self.websocket:
                try:
                    await self.websocket.send_json(
                        {"type": "command_error", "error": str(e)}
                    )
                except:
                    pass

    async def _cleanup_resources_on_timeout(self):
        """Clean up all resources on timeout (backward compatible)."""
        await self._cleanup_resources_enhanced(CleanupReason.TIMEOUT)

    async def _cleanup_resources_enhanced(self, reason: CleanupReason):
        """Enhanced resource cleanup."""
        if self._cleanup_done:
            return

        cleanup_start_time = time.time()
        self._cleanup_done = True

        debug_log(f"Cleaning up session {self.session_id} resources, reason: {reason.value}")
        self.cleanup_stats["cleanup_count"] += 1
        self.cleanup_stats["cleanup_reason"] = reason.value
        self.cleanup_stats["last_cleanup_time"] = datetime.now().isoformat()

        resources_cleaned = 0
        memory_before = 0

        try:
            try:
                import psutil

                process = psutil.Process()
                memory_before = process.memory_info().rss
            except:
                pass

            if self.cleanup_timer:
                self.cleanup_timer.cancel()
                self.cleanup_timer = None
                resources_cleaned += 1

            if self.user_timeout_timer:
                self.user_timeout_timer.cancel()
                self.user_timeout_timer = None
                resources_cleaned += 1

            if self.websocket:
                try:
                    code_key_map = {
                        CleanupReason.TIMEOUT: "TIMEOUT_CLEANUP",
                        CleanupReason.EXPIRED: "EXPIRED_CLEANUP",
                        CleanupReason.MEMORY_PRESSURE: "MEMORY_PRESSURE_CLEANUP",
                        CleanupReason.MANUAL: "MANUAL_CLEANUP",
                        CleanupReason.ERROR: "ERROR_CLEANUP",
                        CleanupReason.SHUTDOWN: "SHUTDOWN_CLEANUP",
                    }

                    code_key = code_key_map.get(reason, "SESSION_CLEANUP")

                    await self.websocket.send_json(
                        {
                            "type": "notification",
                            "code": self.get_message_code(code_key),
                            "severity": "warning",
                            "reason": reason.value,
                        }
                    )
                    await asyncio.sleep(0.1)

                    await self._safe_close_websocket()
                    debug_log(f"Session {self.session_id} WebSocket closed")
                    resources_cleaned += 1
                except Exception as e:
                    debug_log(f"Error closing WebSocket: {e}")
                finally:
                    self.websocket = None

            if self.process:
                try:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=3)
                        debug_log(f"Session {self.session_id} command process terminated")
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        debug_log(f"Session {self.session_id} command process force killed")
                    resources_cleaned += 1
                except Exception as e:
                    debug_log(f"Error terminating command process: {e}")
                finally:
                    self.process = None

            self.feedback_completed.set()

            logs_count = len(self.command_logs)
            images_count = len(self.images)

            self.command_logs.clear()
            self.images.clear()
            self.settings.clear()

            if logs_count > 0 or images_count > 0:
                resources_cleaned += logs_count + images_count
                debug_log(f"Cleaned {logs_count} logs and {images_count} images")

            if reason == CleanupReason.EXPIRED:
                self.status = SessionStatus.EXPIRED
            elif reason == CleanupReason.TIMEOUT:
                self.status = SessionStatus.TIMEOUT
            elif reason == CleanupReason.ERROR:
                self.status = SessionStatus.ERROR
            else:
                self.status = SessionStatus.COMPLETED

            for callback in self.cleanup_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self, reason)
                    else:
                        callback(self, reason)
                except Exception as e:
                    debug_log(f"Cleanup callback failed: {e}")

            cleanup_duration = time.time() - cleanup_start_time
            memory_after = 0
            try:
                import psutil

                process = psutil.Process()
                memory_after = process.memory_info().rss
            except:
                pass

            memory_freed = max(0, memory_before - memory_after)

            self.cleanup_stats.update(
                {
                    "cleanup_duration": cleanup_duration,
                    "memory_freed": memory_freed,
                    "resources_cleaned": resources_cleaned,
                }
            )

            debug_log(
                f"Session {self.session_id} cleanup done, duration={cleanup_duration:.2f}s, "
                f"resources={resources_cleaned}, memory_freed={memory_freed} bytes"
            )

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e,
                context={
                    "session_id": self.session_id,
                    "cleanup_reason": reason.value,
                    "operation": "enhanced_resource_cleanup",
                },
                error_type=ErrorType.SYSTEM,
            )
            debug_log(
                f"Error cleaning up session {self.session_id} [error_id: {error_id}]: {e}"
            )

            self.cleanup_stats["cleanup_duration"] = time.time() - cleanup_start_time

    def _cleanup_sync(self):
        """Sync cleanup (preserve WebSocket for backward compatibility)."""
        self._cleanup_sync_enhanced(CleanupReason.MANUAL, preserve_websocket=True)

    def _cleanup_sync_enhanced(
        self, reason: CleanupReason, preserve_websocket: bool = False
    ):
        """Enhanced sync resource cleanup."""
        if self._cleanup_done and not preserve_websocket:
            return

        cleanup_start_time = time.time()
        debug_log(
            f"Sync cleanup session {self.session_id}, reason={reason.value}, preserve_websocket={preserve_websocket}"
        )

        self.cleanup_stats["cleanup_count"] += 1
        self.cleanup_stats["cleanup_reason"] = reason.value
        self.cleanup_stats["last_cleanup_time"] = datetime.now().isoformat()

        resources_cleaned = 0
        memory_before = 0

        try:
            try:
                import psutil

                process = psutil.Process()
                memory_before = process.memory_info().rss
            except:
                pass

            if self.cleanup_timer:
                self.cleanup_timer.cancel()
                self.cleanup_timer = None
                resources_cleaned += 1

            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                    debug_log(f"Session {self.session_id} command process terminated")
                    resources_cleaned += 1
                except:
                    try:
                        self.process.kill()
                        debug_log(f"Session {self.session_id} command process force killed")
                        resources_cleaned += 1
                    except:
                        pass
                self.process = None

            logs_count = len(self.command_logs)
            images_count = len(self.images)

            self.command_logs.clear()
            if not preserve_websocket:
                self.images.clear()
                self.settings.clear()
                resources_cleaned += images_count

            resources_cleaned += logs_count

            if not preserve_websocket:
                self.feedback_completed.set()

            if not preserve_websocket:
                if reason == CleanupReason.EXPIRED:
                    self.status = SessionStatus.EXPIRED
                elif reason == CleanupReason.TIMEOUT:
                    self.status = SessionStatus.TIMEOUT
                elif reason == CleanupReason.ERROR:
                    self.status = SessionStatus.ERROR
                else:
                    self.status = SessionStatus.COMPLETED

                self._cleanup_done = True

            for callback in self.cleanup_callbacks:
                try:
                    if not asyncio.iscoroutinefunction(callback):
                        callback(self, reason)
                except Exception as e:
                    debug_log(f"Sync cleanup callback failed: {e}")

            cleanup_duration = time.time() - cleanup_start_time
            memory_after = 0
            try:
                import psutil

                process = psutil.Process()
                memory_after = process.memory_info().rss
            except:
                pass

            memory_freed = max(0, memory_before - memory_after)

            self.cleanup_stats.update(
                {
                    "cleanup_duration": cleanup_duration,
                    "memory_freed": memory_freed,
                    "resources_cleaned": resources_cleaned,
                }
            )

            debug_log(
                f"Session {self.session_id} sync cleanup done, duration={cleanup_duration:.2f}s, "
                f"resources={resources_cleaned}, memory_freed={memory_freed} bytes"
            )

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e,
                context={
                    "session_id": self.session_id,
                    "cleanup_reason": reason.value,
                    "preserve_websocket": preserve_websocket,
                    "operation": "sync_resource_cleanup",
                },
                error_type=ErrorType.SYSTEM,
            )
            debug_log(
                f"Error in sync cleanup session {self.session_id} [error_id: {error_id}]: {e}"
            )

            self.cleanup_stats["cleanup_duration"] = time.time() - cleanup_start_time

    def cleanup(self):
        """Sync cleanup (backward compatible)."""
        self._cleanup_sync_enhanced(CleanupReason.MANUAL)

    async def _safe_close_websocket(self):
        """Safely close WebSocket, avoid event loop conflicts."""
        if not self.websocket:
            return

        try:
            if (
                hasattr(self.websocket, "client_state")
                and self.websocket.client_state.DISCONNECTED
            ):
                debug_log("WebSocket already disconnected, skip close")
                return

            await asyncio.wait_for(
                self.websocket.close(code=1000, reason="Session cleanup"), timeout=2.0
            )
            debug_log(f"Session {self.session_id} WebSocket closed")

        except TimeoutError:
            debug_log(f"Session {self.session_id} WebSocket close timeout")
        except RuntimeError as e:
            if "attached to a different loop" in str(e):
                debug_log(
                    f"Session {self.session_id} WebSocket event loop conflict, ignoring: {e}"
                )
            else:
                debug_log(f"Session {self.session_id} WebSocket runtime error: {e}")
        except Exception as e:
            debug_log(f"Session {self.session_id} unknown WebSocket close error: {e}")
