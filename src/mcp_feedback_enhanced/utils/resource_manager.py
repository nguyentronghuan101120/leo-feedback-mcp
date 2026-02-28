"""Unified resource manager: temp files/dirs, process tracking, auto cleanup, monitoring."""

import atexit
import os
import shutil
import subprocess
import tempfile
import threading
import time
import weakref
from typing import Any

from ..debug import debug_log
from .error_handler import ErrorHandler, ErrorType


class ResourceType:
    """Resource type constants."""

    TEMP_FILE = "temp_file"
    TEMP_DIR = "temp_dir"
    PROCESS = "process"
    FILE_HANDLE = "file_handle"


class ResourceManager:
    """Unified resource lifecycle management."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize resource manager."""
        if hasattr(self, "_initialized"):
            return

        self._initialized = True

        self.temp_files: set[str] = set()
        self.temp_dirs: set[str] = set()
        self.processes: dict[int, dict[str, Any]] = {}
        self.file_handles: set[Any] = set()

        self.stats: dict[str, int | float] = {
            "temp_files_created": 0,
            "temp_dirs_created": 0,
            "processes_registered": 0,
            "cleanup_runs": 0,
            "last_cleanup": 0.0,
        }

        self.auto_cleanup_enabled = True
        self.cleanup_interval = 300
        self.temp_file_max_age = 3600

        self._cleanup_thread: threading.Thread | None = None
        self._stop_cleanup = threading.Event()

        atexit.register(self.cleanup_all)
        self._start_auto_cleanup()
        self._setup_memory_monitoring()

        debug_log("ResourceManager initialized")

    def _setup_memory_monitoring(self):
        """Setup memory monitoring integration."""
        try:
            from .memory_monitor import get_memory_monitor

            self.memory_monitor = get_memory_monitor()
            self.memory_monitor.add_cleanup_callback(self._memory_triggered_cleanup)

            if self.memory_monitor.start_monitoring():
                debug_log("Memory monitoring integrated with ResourceManager")
            else:
                debug_log("Memory monitoring failed to start")

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e, context={"operation": "setup_memory_monitoring"}, error_type=ErrorType.SYSTEM
            )
            debug_log(f"Failed to setup memory monitoring [error_id: {error_id}]: {e}")

    def _memory_triggered_cleanup(self, force: bool = False):
        """Cleanup triggered by memory monitoring."""
        debug_log(f"Memory-triggered cleanup (force={force})")

        try:
            cleaned_files = self.cleanup_temp_files()
            cleaned_dirs = self.cleanup_temp_dirs()
            cleaned_handles = self.cleanup_file_handles()

            cleaned_processes = 0
            if force:
                cleaned_processes = self.cleanup_processes(force=True)

            debug_log(
                f"Memory cleanup done: files={cleaned_files}, dirs={cleaned_dirs}, "
                f"handles={cleaned_handles}, processes={cleaned_processes}"
            )

            self.stats["cleanup_runs"] += 1
            self.stats["last_cleanup"] = time.time()

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e,
                context={"operation": "memory_triggered_cleanup", "force": force},
                error_type=ErrorType.SYSTEM,
            )
            debug_log(f"Memory-triggered cleanup failed [error_id: {error_id}]: {e}")

    def create_temp_file(
        self,
        suffix: str = "",
        prefix: str = "mcp_",
        dir: str | None = None,
        text: bool = True,
    ) -> str:
        """Create and track temp file."""
        try:
            fd, temp_path = tempfile.mkstemp(
                suffix=suffix, prefix=prefix, dir=dir, text=text
            )
            os.close(fd)

            self.temp_files.add(temp_path)
            self.stats["temp_files_created"] += 1

            debug_log(f"Created temp file: {temp_path}")
            return temp_path

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e,
                context={
                    "operation": "create_temp_file",
                    "suffix": suffix,
                    "prefix": prefix,
                },
                error_type=ErrorType.FILE_IO,
            )
            debug_log(f"Failed to create temp file [error_id: {error_id}]: {e}")
            raise

    def create_temp_dir(
        self, suffix: str = "", prefix: str = "mcp_", dir: str | None = None
    ) -> str:
        """Create and track temp directory."""
        try:
            temp_dir = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)

            self.temp_dirs.add(temp_dir)
            self.stats["temp_dirs_created"] += 1

            debug_log(f"Created temp dir: {temp_dir}")
            return temp_dir

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e,
                context={
                    "operation": "create_temp_dir",
                    "suffix": suffix,
                    "prefix": prefix,
                },
                error_type=ErrorType.FILE_IO,
            )
            debug_log(f"Failed to create temp dir [error_id: {error_id}]: {e}")
            raise

    def register_process(
        self,
        process: subprocess.Popen | int,
        description: str = "",
        auto_cleanup: bool = True,
    ) -> int:
        """Register process for tracking."""
        try:
            if isinstance(process, subprocess.Popen):
                pid = process.pid
                process_obj = process
            else:
                pid = process
                process_obj = None

            self.processes[pid] = {
                "process": process_obj,
                "description": description,
                "auto_cleanup": auto_cleanup,
                "registered_at": time.time(),
                "last_check": time.time(),
            }

            self.stats["processes_registered"] += 1

            debug_log(f"Process registered: PID {pid} - {description}")
            return pid

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e,
                context={"operation": "register_process", "description": description},
                error_type=ErrorType.PROCESS,
            )
            debug_log(f"Failed to register process [error_id: {error_id}]: {e}")
            raise

    def register_file_handle(self, file_handle: Any) -> None:
        """Register file handle for tracking."""
        try:
            self.file_handles.add(weakref.ref(file_handle))
            debug_log(f"File handle registered: {type(file_handle).__name__}")

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e, context={"operation": "register_file_handle"}, error_type=ErrorType.FILE_IO
            )
            debug_log(f"Failed to register file handle [error_id: {error_id}]: {e}")

    def unregister_temp_file(self, file_path: str) -> bool:
        """Unregister temp file."""
        try:
            if file_path in self.temp_files:
                self.temp_files.remove(file_path)
                debug_log(f"Temp file unregistered: {file_path}")
                return True
            return False

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e,
                context={"operation": "unregister_temp_file", "file_path": file_path},
                error_type=ErrorType.FILE_IO,
            )
            debug_log(f"Failed to unregister file [error_id: {error_id}]: {e}")
            return False

    def unregister_process(self, pid: int) -> bool:
        """Unregister process."""
        try:
            if pid in self.processes:
                del self.processes[pid]
                debug_log(f"Process unregistered: PID {pid}")
                return True
            return False

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e,
                context={"operation": "unregister_process", "pid": pid},
                error_type=ErrorType.PROCESS,
            )
            debug_log(f"Failed to unregister process [error_id: {error_id}]: {e}")
            return False

    def cleanup_temp_files(self, max_age: int | None = None) -> int:
        """Cleanup temp files; max_age in seconds, None uses default."""
        if max_age is None:
            max_age = self.temp_file_max_age

        cleaned_count = 0
        current_time = time.time()
        files_to_remove = set()

        for file_path in self.temp_files.copy():
            try:
                if not os.path.exists(file_path):
                    files_to_remove.add(file_path)
                    continue

                file_age = current_time - os.path.getmtime(file_path)
                if file_age > max_age:
                    os.remove(file_path)
                    files_to_remove.add(file_path)
                    cleaned_count += 1
                    debug_log(f"Cleaned expired temp file: {file_path}")

            except Exception as e:
                error_id = ErrorHandler.log_error_with_context(
                    e,
                    context={"operation": "cleanup_temp_files", "file_path": file_path},
                    error_type=ErrorType.FILE_IO,
                )
                debug_log(f"Failed to cleanup temp file [error_id: {error_id}]: {e}")
                files_to_remove.add(file_path)

        self.temp_files -= files_to_remove

        return cleaned_count

    def cleanup_temp_dirs(self) -> int:
        """Cleanup temp directories."""
        cleaned_count = 0
        dirs_to_remove = set()

        for dir_path in self.temp_dirs.copy():
            try:
                if not os.path.exists(dir_path):
                    dirs_to_remove.add(dir_path)
                    continue

                shutil.rmtree(dir_path)
                dirs_to_remove.add(dir_path)
                cleaned_count += 1
                debug_log(f"Cleaned temp dir: {dir_path}")

            except Exception as e:
                error_id = ErrorHandler.log_error_with_context(
                    e,
                    context={"operation": "cleanup_temp_dirs", "dir_path": dir_path},
                    error_type=ErrorType.FILE_IO,
                )
                debug_log(f"Failed to cleanup temp dir [error_id: {error_id}]: {e}")
                dirs_to_remove.add(dir_path)

        self.temp_dirs -= dirs_to_remove

        return cleaned_count

    def cleanup_processes(self, force: bool = False) -> int:
        """Cleanup processes; force kills if True."""
        cleaned_count = 0
        processes_to_remove = []

        for pid, process_info in self.processes.copy().items():
            try:
                process_obj = process_info.get("process")
                auto_cleanup = process_info.get("auto_cleanup", True)

                if not auto_cleanup:
                    continue

                if process_obj and hasattr(process_obj, "poll"):
                    if process_obj.poll() is None:
                        if force:
                            debug_log(f"Force killing process: PID {pid}")
                            process_obj.kill()
                        else:
                            debug_log(f"Terminating process: PID {pid}")
                            process_obj.terminate()

                        try:
                            process_obj.wait(timeout=5)
                            cleaned_count += 1
                        except subprocess.TimeoutExpired:
                            if not force:
                                debug_log(f"Process {pid} graceful terminate timeout, force killing")
                                process_obj.kill()
                                process_obj.wait(timeout=3)
                                cleaned_count += 1

                    processes_to_remove.append(pid)
                else:
                    try:
                        import psutil

                        if psutil.pid_exists(pid):
                            proc = psutil.Process(pid)
                            if force:
                                proc.kill()
                            else:
                                proc.terminate()
                            proc.wait(timeout=5)
                            cleaned_count += 1
                        processes_to_remove.append(pid)
                    except ImportError:
                        debug_log("psutil not available, skipping process check")
                        processes_to_remove.append(pid)
                    except Exception as e:
                        debug_log(f"Failed to cleanup process {pid}: {e}")
                        processes_to_remove.append(pid)

            except Exception as e:
                error_id = ErrorHandler.log_error_with_context(
                    e,
                    context={"operation": "cleanup_processes", "pid": pid},
                    error_type=ErrorType.PROCESS,
                )
                debug_log(f"Failed to cleanup process [error_id: {error_id}]: {e}")
                processes_to_remove.append(pid)

        for pid in processes_to_remove:
            self.processes.pop(pid, None)

        return cleaned_count

    def cleanup_file_handles(self) -> int:
        """Cleanup file handles."""
        cleaned_count = 0
        handles_to_remove = set()

        for handle_ref in self.file_handles.copy():
            try:
                handle = handle_ref()
                if handle is None:
                    handles_to_remove.add(handle_ref)
                    continue

                if hasattr(handle, "close") and not handle.closed:
                    handle.close()
                    cleaned_count += 1
                    debug_log(f"Closed file handle: {type(handle).__name__}")

                handles_to_remove.add(handle_ref)

            except Exception as e:
                error_id = ErrorHandler.log_error_with_context(
                    e,
                    context={"operation": "cleanup_file_handles"},
                    error_type=ErrorType.FILE_IO,
                )
                debug_log(f"Failed to cleanup file handle [error_id: {error_id}]: {e}")
                handles_to_remove.add(handle_ref)

        self.file_handles -= handles_to_remove

        return cleaned_count

    def cleanup_all(self, force: bool = False) -> dict[str, int]:
        """Cleanup all resources; force enables aggressive cleanup."""
        debug_log("Starting full resource cleanup...")

        results = {"temp_files": 0, "temp_dirs": 0, "processes": 0, "file_handles": 0}

        try:
            results["file_handles"] = self.cleanup_file_handles()
            results["processes"] = self.cleanup_processes(force=force)
            results["temp_files"] = self.cleanup_temp_files(max_age=0)
            results["temp_dirs"] = self.cleanup_temp_dirs()

            self.stats["cleanup_runs"] += 1
            self.stats["last_cleanup"] = time.time()

            total_cleaned = sum(results.values())
            debug_log(f"Resource cleanup done: {total_cleaned} resources: {results}")

        except Exception as e:
            error_id = ErrorHandler.log_error_with_context(
                e, context={"operation": "cleanup_all"}, error_type=ErrorType.SYSTEM
            )
            debug_log(f"Full resource cleanup failed [error_id: {error_id}]: {e}")

        return results

    def _start_auto_cleanup(self) -> None:
        """Start auto cleanup thread."""
        if not self.auto_cleanup_enabled or self._cleanup_thread:
            return

        def cleanup_worker():
            while not self._stop_cleanup.wait(self.cleanup_interval):
                try:
                    self.cleanup_temp_files()
                    self._check_process_health()

                except Exception as e:
                    error_id = ErrorHandler.log_error_with_context(
                        e,
                        context={"operation": "auto_cleanup"},
                        error_type=ErrorType.SYSTEM,
                    )
                    debug_log(f"Auto cleanup failed [error_id: {error_id}]: {e}")

        self._cleanup_thread = threading.Thread(
            target=cleanup_worker, name="ResourceManager-AutoCleanup", daemon=True
        )
        self._cleanup_thread.start()
        debug_log("Auto cleanup thread started")

    def _check_process_health(self) -> None:
        """Check process health."""
        current_time = time.time()

        for pid, process_info in self.processes.items():
            try:
                process_obj = process_info.get("process")
                last_check = process_info.get("last_check", current_time)

                if current_time - last_check < 60:
                    continue

                process_info["last_check"] = current_time

                if process_obj and hasattr(process_obj, "poll"):
                    if process_obj.poll() is not None:
                        debug_log(f"Process {pid} ended, unregistering")
                        self.unregister_process(pid)

            except Exception as e:
                debug_log(f"Failed to check process {pid} health: {e}")

    def stop_auto_cleanup(self) -> None:
        """Stop auto cleanup."""
        if self._cleanup_thread:
            self._stop_cleanup.set()
            self._cleanup_thread.join(timeout=5)
            self._cleanup_thread = None
            debug_log("Auto cleanup thread stopped")

    def get_resource_stats(self) -> dict[str, Any]:
        """Get resource stats."""
        current_stats = self.stats.copy()
        current_stats.update(
            {
                "current_temp_files": len(self.temp_files),
                "current_temp_dirs": len(self.temp_dirs),
                "current_processes": len(self.processes),
                "current_file_handles": len(self.file_handles),
                "auto_cleanup_enabled": self.auto_cleanup_enabled,
                "cleanup_interval": self.cleanup_interval,
                "temp_file_max_age": self.temp_file_max_age,
            }
        )

        try:
            if hasattr(self, "memory_monitor") and self.memory_monitor:
                memory_info = self.memory_monitor.get_current_memory_info()
                memory_stats = self.memory_monitor.get_memory_stats()

                current_stats.update(
                    {
                        "memory_monitoring_enabled": self.memory_monitor.is_monitoring,
                        "current_memory_usage": memory_info.get("system", {}).get(
                            "usage_percent", 0
                        ),
                        "memory_status": memory_info.get("status", "unknown"),
                        "memory_cleanup_triggers": memory_stats.cleanup_triggers,
                        "memory_alerts_count": memory_stats.alerts_count,
                    }
                )
        except Exception as e:
            debug_log(f"Failed to get memory stats: {e}")

        return current_stats

    def get_detailed_info(self) -> dict[str, Any]:
        """Get detailed resource info."""
        return {
            "temp_files": list(self.temp_files),
            "temp_dirs": list(self.temp_dirs),
            "processes": {
                pid: {
                    "description": info.get("description", ""),
                    "auto_cleanup": info.get("auto_cleanup", True),
                    "registered_at": info.get("registered_at", 0),
                    "last_check": info.get("last_check", 0),
                }
                for pid, info in self.processes.items()
            },
            "file_handles_count": len(self.file_handles),
            "stats": self.get_resource_stats(),
        }

    def configure(
        self,
        auto_cleanup_enabled: bool | None = None,
        cleanup_interval: int | None = None,
        temp_file_max_age: int | None = None,
    ) -> None:
        """Configure resource manager."""
        if auto_cleanup_enabled is not None:
            old_enabled = self.auto_cleanup_enabled
            self.auto_cleanup_enabled = auto_cleanup_enabled

            if old_enabled and not auto_cleanup_enabled:
                self.stop_auto_cleanup()
            elif (not old_enabled and auto_cleanup_enabled) or (auto_cleanup_enabled and self._cleanup_thread is None):
                self._start_auto_cleanup()

        if cleanup_interval is not None:
            self.cleanup_interval = max(60, cleanup_interval)

        if temp_file_max_age is not None:
            self.temp_file_max_age = max(300, temp_file_max_age)

        debug_log(
            f"ResourceManager config updated: auto_cleanup={self.auto_cleanup_enabled}, "
            f"interval={self.cleanup_interval}, max_age={self.temp_file_max_age}"
        )


_resource_manager = None


def get_resource_manager() -> ResourceManager:
    """Get global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


def create_temp_file(suffix: str = "", prefix: str = "mcp_", **kwargs) -> str:
    """Convenience: create temp file."""
    return get_resource_manager().create_temp_file(
        suffix=suffix, prefix=prefix, **kwargs
    )


def create_temp_dir(suffix: str = "", prefix: str = "mcp_", **kwargs) -> str:
    """Convenience: create temp dir."""
    return get_resource_manager().create_temp_dir(
        suffix=suffix, prefix=prefix, **kwargs
    )


def register_process(
    process: subprocess.Popen | int, description: str = "", **kwargs
) -> int:
    """Convenience: register process."""
    return get_resource_manager().register_process(
        process, description=description, **kwargs
    )


def cleanup_all_resources(force: bool = False) -> dict[str, int]:
    """Convenience: cleanup all resources."""
    return get_resource_manager().cleanup_all(force=force)
