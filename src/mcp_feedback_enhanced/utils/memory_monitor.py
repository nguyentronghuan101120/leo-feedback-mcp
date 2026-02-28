#!/usr/bin/env python3
"""Memory monitoring integrated with resource manager."""

import gc
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psutil

from .error_handler import ErrorHandler, ErrorType


@dataclass
class MemorySnapshot:
    """Memory snapshot data."""

    timestamp: datetime
    system_total: int
    system_available: int
    system_used: int
    system_percent: float
    process_rss: int
    process_vms: int
    process_percent: float
    gc_objects: int


@dataclass
class MemoryAlert:
    """Memory alert data."""

    level: str  # warning, critical, emergency
    message: str
    timestamp: datetime
    memory_percent: float
    recommended_action: str


@dataclass
class MemoryStats:
    """Memory stats."""

    monitoring_duration: float
    snapshots_count: int
    average_system_usage: float
    peak_system_usage: float
    average_process_usage: float
    peak_process_usage: float
    alerts_count: int
    cleanup_triggers: int
    memory_trend: str


class MemoryMonitor:
    """Memory monitor."""

    def __init__(
        self,
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.9,
        emergency_threshold: float = 0.95,
        monitoring_interval: int = 30,
        max_snapshots: int = 1000,
    ):
        """Initialize memory monitor."""
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.emergency_threshold = emergency_threshold
        self.monitoring_interval = monitoring_interval
        self.max_snapshots = max_snapshots

        self.is_monitoring = False
        self.monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self.snapshots: deque = deque(maxlen=max_snapshots)
        self.alerts: list[MemoryAlert] = []
        self.max_alerts = 100

        self.cleanup_callbacks: list[Callable] = []
        self.alert_callbacks: list[Callable[[MemoryAlert], None]] = []

        self.start_time: datetime | None = None
        self.cleanup_triggers_count = 0

        self.process = psutil.Process()

    def start_monitoring(self) -> bool:
        """Start memory monitoring."""
        if self.is_monitoring:
            return True

        try:
            self.is_monitoring = True
            self.start_time = datetime.now()
            self._stop_event.clear()

            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop, name="MemoryMonitor", daemon=True
            )
            self.monitor_thread.start()

            return True

        except Exception as e:
            self.is_monitoring = False
            ErrorHandler.log_error_with_context(
                e, context={"operation": "start_memory_monitoring"}, error_type=ErrorType.SYSTEM
            )
            return False

    def _monitoring_loop(self):
        """Memory monitoring main loop."""
        while not self._stop_event.is_set():
            try:
                snapshot = self._collect_memory_snapshot()
                self.snapshots.append(snapshot)

                self._check_memory_usage(snapshot)

                if self._stop_event.wait(self.monitoring_interval):
                    break

            except Exception as e:
                ErrorHandler.log_error_with_context(
                    e,
                    context={"operation": "memory_monitoring_loop"},
                    error_type=ErrorType.SYSTEM,
                )

                if self._stop_event.wait(5):
                    break

    def _collect_memory_snapshot(self) -> MemorySnapshot:
        """Collect memory snapshot."""
        try:
            system_memory = psutil.virtual_memory()

            process_memory = self.process.memory_info()
            process_percent = self.process.memory_percent()

            gc_objects = len(gc.get_objects())

            return MemorySnapshot(
                timestamp=datetime.now(),
                system_total=system_memory.total,
                system_available=system_memory.available,
                system_used=system_memory.used,
                system_percent=system_memory.percent,
                process_rss=process_memory.rss,
                process_vms=process_memory.vms,
                process_percent=process_percent,
                gc_objects=gc_objects,
            )

        except Exception as e:
            ErrorHandler.log_error_with_context(
                e, context={"operation": "collect_memory_snapshot"}, error_type=ErrorType.SYSTEM
            )
            raise

    def _check_memory_usage(self, snapshot: MemorySnapshot):
        """Check memory usage and trigger actions."""
        usage_percent = snapshot.system_percent / 100.0

        if usage_percent >= self.emergency_threshold:
            alert = MemoryAlert(
                level="emergency",
                message=f"Memory usage at emergency level: {snapshot.system_percent:.1f}%",
                timestamp=snapshot.timestamp,
                memory_percent=snapshot.system_percent,
                recommended_action="Run forced cleanup and garbage collection",
            )
            self._handle_alert(alert)
            self._trigger_emergency_cleanup()

        elif usage_percent >= self.critical_threshold:
            alert = MemoryAlert(
                level="critical",
                message=f"Memory usage at critical level: {snapshot.system_percent:.1f}%",
                timestamp=snapshot.timestamp,
                memory_percent=snapshot.system_percent,
                recommended_action="Run resource cleanup and garbage collection",
            )
            self._handle_alert(alert)
            self._trigger_cleanup()

        elif usage_percent >= self.warning_threshold:
            alert = MemoryAlert(
                level="warning",
                message=f"Memory usage high: {snapshot.system_percent:.1f}%",
                timestamp=snapshot.timestamp,
                memory_percent=snapshot.system_percent,
                recommended_action="Consider light cleanup",
            )
            self._handle_alert(alert)

    def _handle_alert(self, alert: MemoryAlert):
        """Handle memory alert."""
        self.alerts.append(alert)

        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts :]

        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception:
                pass

    def _trigger_cleanup(self):
        """Trigger cleanup."""
        self.cleanup_triggers_count += 1

        gc.collect()

        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception:
                pass

    def _trigger_emergency_cleanup(self):
        """Trigger emergency cleanup."""
        for _ in range(3):
            gc.collect()

        for callback in self.cleanup_callbacks:
            try:
                import inspect

                sig = inspect.signature(callback)
                if "force" in sig.parameters:
                    callback(force=True)
                else:
                    callback()
            except Exception:
                pass

    def add_cleanup_callback(self, callback: Callable):
        """Add cleanup callback."""
        if callback not in self.cleanup_callbacks:
            self.cleanup_callbacks.append(callback)

    def add_alert_callback(self, callback: Callable[[MemoryAlert], None]):
        """Add alert callback."""
        if callback not in self.alert_callbacks:
            self.alert_callbacks.append(callback)

    def get_current_memory_info(self) -> dict[str, Any]:
        """Get current memory info."""
        try:
            snapshot = self._collect_memory_snapshot()
            return {
                "timestamp": snapshot.timestamp.isoformat(),
                "system": {
                    "total_gb": round(snapshot.system_total / (1024**3), 2),
                    "available_gb": round(snapshot.system_available / (1024**3), 2),
                    "used_gb": round(snapshot.system_used / (1024**3), 2),
                    "usage_percent": round(snapshot.system_percent, 1),
                },
                "process": {
                    "rss_mb": round(snapshot.process_rss / (1024**2), 2),
                    "vms_mb": round(snapshot.process_vms / (1024**2), 2),
                    "usage_percent": round(snapshot.process_percent, 1),
                },
                "gc_objects": snapshot.gc_objects,
                "status": self._get_memory_status(snapshot.system_percent / 100.0),
            }
        except Exception as e:
            ErrorHandler.log_error_with_context(
                e,
                context={"operation": "get_current_memory_info"},
                error_type=ErrorType.SYSTEM,
            )
            return {}

    def get_memory_stats(self) -> MemoryStats:
        """Get memory stats."""
        if not self.snapshots:
            return MemoryStats(
                monitoring_duration=0.0,
                snapshots_count=0,
                average_system_usage=0.0,
                peak_system_usage=0.0,
                average_process_usage=0.0,
                peak_process_usage=0.0,
                alerts_count=0,
                cleanup_triggers=0,
                memory_trend="unknown",
            )

        system_usages = [s.system_percent for s in self.snapshots]
        process_usages = [s.process_percent for s in self.snapshots]

        duration = 0.0
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()

        return MemoryStats(
            monitoring_duration=duration,
            snapshots_count=len(self.snapshots),
            average_system_usage=sum(system_usages) / len(system_usages),
            peak_system_usage=max(system_usages),
            average_process_usage=sum(process_usages) / len(process_usages),
            peak_process_usage=max(process_usages),
            alerts_count=len(self.alerts),
            cleanup_triggers=self.cleanup_triggers_count,
            memory_trend=self._analyze_memory_trend(),
        )

    def get_recent_alerts(self, limit: int = 10) -> list[MemoryAlert]:
        """Get recent alerts."""
        return self.alerts[-limit:] if self.alerts else []

    def _get_memory_status(self, usage_percent: float) -> str:
        """Get memory status string."""
        if usage_percent >= self.emergency_threshold:
            return "emergency"
        if usage_percent >= self.critical_threshold:
            return "critical"
        if usage_percent >= self.warning_threshold:
            return "warning"
        return "normal"

    def _analyze_memory_trend(self) -> str:
        """Analyze memory usage trend."""
        if len(self.snapshots) < 10:
            return "insufficient_data"

        recent_snapshots = list(self.snapshots)[-10:]
        usages = [s.system_percent for s in recent_snapshots]

        first_half = usages[:5]
        second_half = usages[5:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        diff = avg_second - avg_first

        if abs(diff) < 2.0:
            return "stable"
        if diff > 0:
            return "increasing"
        return "decreasing"

_memory_monitor: MemoryMonitor | None = None
_monitor_lock = threading.Lock()


def get_memory_monitor() -> MemoryMonitor:
    """Get global memory monitor instance."""
    global _memory_monitor
    if _memory_monitor is None:
        with _monitor_lock:
            if _memory_monitor is None:
                _memory_monitor = MemoryMonitor()
    return _memory_monitor
