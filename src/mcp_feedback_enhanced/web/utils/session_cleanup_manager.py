#!/usr/bin/env python3
"""Session cleanup manager: policy, stats, monitoring; integrated with memory monitoring."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from ...debug import web_debug_log as debug_log
from ...utils.error_handler import ErrorHandler, ErrorType
from ..models.feedback_session import CleanupReason, SessionStatus


@dataclass
class CleanupPolicy:
    """Cleanup policy config."""

    max_idle_time: int = 1800
    max_session_age: int = 7200
    max_sessions: int = 10
    cleanup_interval: int = 300
    memory_pressure_threshold: float = 0.8
    enable_auto_cleanup: bool = True
    preserve_active_session: bool = True


@dataclass
class CleanupStats:
    """Cleanup stats."""

    total_cleanups: int = 0
    expired_cleanups: int = 0
    memory_pressure_cleanups: int = 0
    manual_cleanups: int = 0
    auto_cleanups: int = 0
    total_sessions_cleaned: int = 0
    total_cleanup_time: float = 0.0
    average_cleanup_time: float = 0.0
    last_cleanup_time: datetime | None = None
    cleanup_efficiency: float = 0.0


class CleanupTrigger(Enum):
    """Cleanup trigger type."""

    AUTO = "auto"
    MEMORY_PRESSURE = "memory_pressure"
    MANUAL = "manual"
    EXPIRED = "expired"
    CAPACITY = "capacity"


class SessionCleanupManager:
    """Session cleanup manager."""

    def __init__(self, web_ui_manager, policy: CleanupPolicy | None = None):
        """Initialize session cleanup manager."""
        self.web_ui_manager = web_ui_manager
        self.policy = policy or CleanupPolicy()
        self.stats = CleanupStats()

        self.is_running = False
        self.cleanup_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self.cleanup_callbacks: list[Callable] = []
        self.stats_callbacks: list[Callable] = []

        self.cleanup_history: list[dict[str, Any]] = []
        self.max_history = 100

        debug_log("SessionCleanupManager initialized")

    def start_auto_cleanup(self) -> bool:
        """Start auto cleanup."""
        if not self.policy.enable_auto_cleanup:
            debug_log("Auto cleanup disabled")
            return False

        if self.is_running:
            debug_log("Auto cleanup already running")
            return True

        try:
            self.is_running = True
            self._stop_event.clear()

            self.cleanup_thread = threading.Thread(
                target=self._auto_cleanup_loop,
                name="SessionCleanupManager",
                daemon=True,
            )
            self.cleanup_thread.start()

            debug_log(f"Auto cleanup started, interval {self.policy.cleanup_interval}s")
            return True

        except Exception as e:
            self.is_running = False
            error_id = ErrorHandler.log_error_with_context(
                e, context={"operation": "start_auto_cleanup"}, error_type=ErrorType.SYSTEM
            )
            debug_log(f"Failed to start auto cleanup [error_id: {error_id}]: {e}")
            return False

    def stop_auto_cleanup(self) -> bool:
        """Stop auto cleanup."""
        if not self.is_running:
            debug_log("Auto cleanup not running")
            return True

        try:
            self.is_running = False
            self._stop_event.set()

            if self.cleanup_thread and self.cleanup_thread.is_alive():
                self.cleanup_thread.join(timeout=5)

            debug_log("Auto cleanup stopped")
            return True

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e, context={"operation": "stop_auto_cleanup"}, error_type=ErrorType.SYSTEM
            )
            debug_log(f"Failed to stop auto cleanup [error_id: {error_id}]: {e}")
            return False

    def _auto_cleanup_loop(self):
        """Auto cleanup main loop."""
        debug_log("Auto cleanup loop started")

        while not self._stop_event.is_set():
            try:
                self._perform_auto_cleanup()

                if self._stop_event.wait(self.policy.cleanup_interval):
                    break

            except Exception as e:
                error_id = ErrorHandler.log_error_with_context(
                    e,
                    context={"operation": "auto_cleanup_loop"},
                    error_type=ErrorType.SYSTEM,
                )
                debug_log(f"Auto cleanup loop error [error_id: {error_id}]: {e}")

                if self._stop_event.wait(30):
                    break

        debug_log("Auto cleanup loop ended")

    def _perform_auto_cleanup(self):
        """Perform auto cleanup."""
        cleanup_start_time = time.time()
        cleaned_sessions = 0

        try:
            if len(self.web_ui_manager.sessions) > self.policy.max_sessions:
                cleaned = self._cleanup_by_capacity()
                cleaned_sessions += cleaned
                debug_log(f"Capacity limit cleanup: {cleaned} sessions")

            cleaned = self._cleanup_expired_sessions()
            cleaned_sessions += cleaned

            cleaned = self._cleanup_idle_sessions()
            cleaned_sessions += cleaned

            cleanup_duration = time.time() - cleanup_start_time
            self._update_cleanup_stats(
                CleanupTrigger.AUTO, cleaned_sessions, cleanup_duration
            )

            if cleaned_sessions > 0:
                debug_log(
                    f"Auto cleanup done: {cleaned_sessions} sessions, {cleanup_duration:.2f}s"
                )

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e, context={"operation": "perform_auto_cleanup"}, error_type=ErrorType.SYSTEM
            )
            debug_log(f"Failed to perform auto cleanup [error_id: {error_id}]: {e}")

    def trigger_cleanup(self, trigger: CleanupTrigger, force: bool = False) -> int:
        """Trigger cleanup operation."""
        cleanup_start_time = time.time()
        cleaned_sessions = 0

        try:
            debug_log(f"Trigger cleanup: {trigger.value}, force={force}")

            if trigger == CleanupTrigger.MEMORY_PRESSURE:
                cleaned_sessions = (
                    self.web_ui_manager.cleanup_sessions_by_memory_pressure(force)
                )
            elif trigger == CleanupTrigger.EXPIRED:
                cleaned_sessions = self.web_ui_manager.cleanup_expired_sessions()
            elif trigger == CleanupTrigger.CAPACITY:
                cleaned_sessions = self._cleanup_by_capacity()
            elif trigger == CleanupTrigger.MANUAL:
                cleaned_sessions += self.web_ui_manager.cleanup_expired_sessions()
                if force:
                    cleaned_sessions += (
                        self.web_ui_manager.cleanup_sessions_by_memory_pressure(force)
                    )
            else:
                self._perform_auto_cleanup()
                return 0

            cleanup_duration = time.time() - cleanup_start_time
            self._update_cleanup_stats(trigger, cleaned_sessions, cleanup_duration)

            debug_log(
                f"Cleanup done: {cleaned_sessions} sessions, {cleanup_duration:.2f}s"
            )
            return cleaned_sessions

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e,
                context={
                    "operation": "trigger_cleanup",
                    "trigger": trigger.value,
                    "force": force,
                },
                error_type=ErrorType.SYSTEM,
            )
            debug_log(f"Trigger cleanup failed [error_id: {error_id}]: {e}")
            return 0

    def _cleanup_by_capacity(self) -> int:
        """Cleanup sessions by capacity limit."""
        sessions = self.web_ui_manager.sessions
        if len(sessions) <= self.policy.max_sessions:
            return 0

        excess_count = len(sessions) - self.policy.max_sessions

        session_priorities = []
        for session_id, session in sessions.items():
            if (
                self.policy.preserve_active_session
                and self.web_ui_manager.current_session
                and session.session_id == self.web_ui_manager.current_session.session_id
            ):
                continue

            priority_score = 0

            if session.status in [
                SessionStatus.COMPLETED,
                SessionStatus.ERROR,
                SessionStatus.TIMEOUT,
            ]:
                priority_score += 100
            elif session.status == SessionStatus.FEEDBACK_SUBMITTED:
                priority_score += 50

            age = session.get_age()
            priority_score += age / 60
            idle_time = session.get_idle_time()
            priority_score += idle_time / 30

            session_priorities.append((session_id, session, priority_score))

        session_priorities.sort(key=lambda x: x[2], reverse=True)
        cleaned_count = 0

        for i in range(min(excess_count, len(session_priorities))):
            session_id, session, _ = session_priorities[i]
            try:
                session._cleanup_sync_enhanced(CleanupReason.MANUAL)
                del self.web_ui_manager.sessions[session_id]
                cleaned_count += 1
            except Exception as e:
                debug_log(f"Capacity cleanup failed for session {session_id}: {e}")


        return cleaned_count

    def _cleanup_expired_sessions(self) -> int:
        """Cleanup expired sessions."""
        expired_sessions = []

        for session_id, session in self.web_ui_manager.sessions.items():
            if session.is_expired() or session.get_age() > self.policy.max_session_age:
                expired_sessions.append(session_id)

        cleaned_count = 0
        for session_id in expired_sessions:
            try:
                session = self.web_ui_manager.sessions.get(session_id)
                if session:
                    session._cleanup_sync_enhanced(CleanupReason.EXPIRED)
                    del self.web_ui_manager.sessions[session_id]
                    cleaned_count += 1

                    if (
                        self.web_ui_manager.current_session
                        and self.web_ui_manager.current_session.session_id == session_id
                    ):
                        self.web_ui_manager.current_session = None

            except Exception as e:
                debug_log(f"Failed to cleanup expired session {session_id}: {e}")

        return cleaned_count

    def _cleanup_idle_sessions(self) -> int:
        """Cleanup idle sessions."""
        idle_sessions = []

        for session_id, session in self.web_ui_manager.sessions.items():
            if (
                self.policy.preserve_active_session
                and self.web_ui_manager.current_session
                and session.session_id == self.web_ui_manager.current_session.session_id
            ):
                continue

            if session.get_idle_time() > self.policy.max_idle_time:
                idle_sessions.append(session_id)

        cleaned_count = 0
        for session_id in idle_sessions:
            try:
                session = self.web_ui_manager.sessions.get(session_id)
                if session:
                    session._cleanup_sync_enhanced(CleanupReason.EXPIRED)
                    del self.web_ui_manager.sessions[session_id]
                    cleaned_count += 1

            except Exception as e:
                debug_log(f"Failed to cleanup idle session {session_id}: {e}")

        return cleaned_count

    def _update_cleanup_stats(
        self, trigger: CleanupTrigger, cleaned_count: int, duration: float
    ):
        """Update cleanup stats."""
        self.stats.total_cleanups += 1
        self.stats.total_sessions_cleaned += cleaned_count
        self.stats.total_cleanup_time += duration
        self.stats.last_cleanup_time = datetime.now()

        if self.stats.total_cleanups > 0:
            self.stats.average_cleanup_time = (
                self.stats.total_cleanup_time / self.stats.total_cleanups
            )

        total_sessions = len(self.web_ui_manager.sessions) + cleaned_count
        if total_sessions > 0:
            self.stats.cleanup_efficiency = cleaned_count / total_sessions

        if trigger == CleanupTrigger.AUTO:
            self.stats.auto_cleanups += 1
        elif trigger == CleanupTrigger.MEMORY_PRESSURE:
            self.stats.memory_pressure_cleanups += 1
        elif trigger == CleanupTrigger.EXPIRED:
            self.stats.expired_cleanups += 1
        elif trigger == CleanupTrigger.MANUAL:
            self.stats.manual_cleanups += 1

        cleanup_record = {
            "timestamp": datetime.now().isoformat(),
            "trigger": trigger.value,
            "cleaned_count": cleaned_count,
            "duration": duration,
            "total_sessions_before": total_sessions,
            "total_sessions_after": len(self.web_ui_manager.sessions),
        }

        self.cleanup_history.append(cleanup_record)

        if len(self.cleanup_history) > self.max_history:
            self.cleanup_history = self.cleanup_history[-self.max_history :]

        for callback in self.stats_callbacks:
            try:
                callback(self.stats, cleanup_record)
            except Exception as e:
                debug_log(f"Stats callback failed: {e}")

    def get_cleanup_statistics(self) -> dict[str, Any]:
        """Get cleanup statistics."""
        stats_dict = {
            "total_cleanups": self.stats.total_cleanups,
            "expired_cleanups": self.stats.expired_cleanups,
            "memory_pressure_cleanups": self.stats.memory_pressure_cleanups,
            "manual_cleanups": self.stats.manual_cleanups,
            "auto_cleanups": self.stats.auto_cleanups,
            "total_sessions_cleaned": self.stats.total_sessions_cleaned,
            "total_cleanup_time": round(self.stats.total_cleanup_time, 2),
            "average_cleanup_time": round(self.stats.average_cleanup_time, 2),
            "cleanup_efficiency": round(self.stats.cleanup_efficiency, 3),
            "last_cleanup_time": self.stats.last_cleanup_time.isoformat()
            if self.stats.last_cleanup_time
            else None,
            "is_auto_cleanup_running": self.is_running,
            "current_sessions": len(self.web_ui_manager.sessions),
            "policy": {
                "max_idle_time": self.policy.max_idle_time,
                "max_session_age": self.policy.max_session_age,
                "max_sessions": self.policy.max_sessions,
                "cleanup_interval": self.policy.cleanup_interval,
                "enable_auto_cleanup": self.policy.enable_auto_cleanup,
                "preserve_active_session": self.policy.preserve_active_session,
            },
        }

        return stats_dict

    def get_cleanup_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get cleanup history."""
        return self.cleanup_history[-limit:] if self.cleanup_history else []

    def add_cleanup_callback(self, callback: Callable):
        """Add cleanup callback."""
        if callback not in self.cleanup_callbacks:
            self.cleanup_callbacks.append(callback)
            debug_log("Cleanup callback added")

    def add_stats_callback(self, callback: Callable):
        """Add stats callback."""
        if callback not in self.stats_callbacks:
            self.stats_callbacks.append(callback)
            debug_log("Stats callback added")

    def update_policy(self, **kwargs):
        """Update cleanup policy."""
        for key, value in kwargs.items():
            if hasattr(self.policy, key):
                setattr(self.policy, key, value)
                debug_log(f"Cleanup policy updated: {key} = {value}")
            else:
                debug_log(f"Unknown policy parameter: {key}")

    def reset_stats(self):
        """Reset stats."""
        self.stats = CleanupStats()
        self.cleanup_history.clear()
        debug_log("Cleanup stats reset")

    def force_cleanup_all(self, exclude_current: bool = True) -> int:
        """Force cleanup all sessions."""
        sessions_to_clean = []

        for session_id, session in self.web_ui_manager.sessions.items():
            if (
                exclude_current
                and self.web_ui_manager.current_session
                and session.session_id == self.web_ui_manager.current_session.session_id
            ):
                continue
            sessions_to_clean.append(session_id)

        cleaned_count = 0
        for session_id in sessions_to_clean:
            try:
                session = self.web_ui_manager.sessions.get(session_id)
                if session:
                    session._cleanup_sync_enhanced(CleanupReason.MANUAL)
                    del self.web_ui_manager.sessions[session_id]
                    cleaned_count += 1
            except Exception as e:
                debug_log(f"Force cleanup failed for session {session_id}: {e}")

        self._update_cleanup_stats(CleanupTrigger.MANUAL, cleaned_count, 0.0)

        debug_log(f"Force cleanup done: {cleaned_count} sessions")
        return cleaned_count
