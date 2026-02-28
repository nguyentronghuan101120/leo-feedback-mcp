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

from .error_handler import ErrorHandler, ErrorType


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

    def _setup_memory_monitoring(self):
        """Setup memory monitoring integration."""
        try:
            from .memory_monitor import get_memory_monitor

            self.memory_monitor = get_memory_monitor()
            self.memory_monitor.add_cleanup_callback(self._memory_triggered_cleanup)
            self.memory_monitor.start_monitoring()

        except Exception as e:
            ErrorHandler.log_error_with_context(
                e, context={"operation": "setup_memory_monitoring"}, error_type=ErrorType.SYSTEM
            )

    def _memory_triggered_cleanup(self, force: bool = False):
        """Cleanup triggered by memory monitoring."""
        try:
            self.cleanup_temp_files()
            self.cleanup_temp_dirs()
            self.cleanup_file_handles()

            if force:
                self.cleanup_processes(force=True)

            self.stats["cleanup_runs"] += 1
            self.stats["last_cleanup"] = time.time()

        except Exception as e:
            ErrorHandler.log_error_with_context(
                e,
                context={"operation": "memory_triggered_cleanup", "force": force},
                error_type=ErrorType.SYSTEM,
            )

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

            return temp_path

        except Exception as e:
            ErrorHandler.log_error_with_context(
                e,
                context={
                    "operation": "create_temp_file",
                    "suffix": suffix,
                    "prefix": prefix,
                },
                error_type=ErrorType.FILE_IO,
            )
            raise

    def create_temp_dir(
        self, suffix: str = "", prefix: str = "mcp_", dir: str | None = None
    ) -> str:
        """Create and track temp directory."""
        try:
            temp_dir = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)

            self.temp_dirs.add(temp_dir)
            self.stats["temp_dirs_created"] += 1

            return temp_dir

        except Exception as e:
            ErrorHandler.log_error_with_context(
                e,
                context={
                    "operation": "create_temp_dir",
                    "suffix": suffix,
                    "prefix": prefix,
                },
                error_type=ErrorType.FILE_IO,
            )
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

            return pid

        except Exception as e:
            ErrorHandler.log_error_with_context(
                e,
                context={"operation": "register_process", "description": description},
                error_type=ErrorType.PROCESS,
            )
            raise

    def unregister_process(self, pid: int) -> bool:
        """Unregister process."""
        try:
            if pid in self.processes:
                del self.processes[pid]
                return True
            return False

        except Exception as e:
            ErrorHandler.log_error_with_context(
                e,
                context={"operation": "unregister_process", "pid": pid},
                error_type=ErrorType.PROCESS,
            )
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

            except Exception as e:
                ErrorHandler.log_error_with_context(
                    e,
                    context={"operation": "cleanup_temp_files", "file_path": file_path},
                    error_type=ErrorType.FILE_IO,
                )
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

            except Exception as e:
                ErrorHandler.log_error_with_context(
                    e,
                    context={"operation": "cleanup_temp_dirs", "dir_path": dir_path},
                    error_type=ErrorType.FILE_IO,
                )
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
                            process_obj.kill()
                        else:
                            process_obj.terminate()

                        try:
                            process_obj.wait(timeout=5)
                            cleaned_count += 1
                        except subprocess.TimeoutExpired:
                            if not force:
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
                        processes_to_remove.append(pid)
                    except Exception:
                        processes_to_remove.append(pid)

            except Exception as e:
                ErrorHandler.log_error_with_context(
                    e,
                    context={"operation": "cleanup_processes", "pid": pid},
                    error_type=ErrorType.PROCESS,
                )
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

                handles_to_remove.add(handle_ref)

            except Exception as e:
                ErrorHandler.log_error_with_context(
                    e,
                    context={"operation": "cleanup_file_handles"},
                    error_type=ErrorType.FILE_IO,
                )
                handles_to_remove.add(handle_ref)

        self.file_handles -= handles_to_remove

        return cleaned_count

    def cleanup_all(self, force: bool = False) -> dict[str, int]:
        """Cleanup all resources; force enables aggressive cleanup."""
        results = {"temp_files": 0, "temp_dirs": 0, "processes": 0, "file_handles": 0}

        try:
            results["file_handles"] = self.cleanup_file_handles()
            results["processes"] = self.cleanup_processes(force=force)
            results["temp_files"] = self.cleanup_temp_files(max_age=0)
            results["temp_dirs"] = self.cleanup_temp_dirs()

            self.stats["cleanup_runs"] += 1
            self.stats["last_cleanup"] = time.time()

        except Exception as e:
            ErrorHandler.log_error_with_context(
                e, context={"operation": "cleanup_all"}, error_type=ErrorType.SYSTEM
            )

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
                    ErrorHandler.log_error_with_context(
                        e,
                        context={"operation": "auto_cleanup"},
                        error_type=ErrorType.SYSTEM,
                    )

        self._cleanup_thread = threading.Thread(
            target=cleanup_worker, name="ResourceManager-AutoCleanup", daemon=True
        )
        self._cleanup_thread.start()

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
                        self.unregister_process(pid)

            except Exception:
                pass

    def stop_auto_cleanup(self) -> None:
        """Stop auto cleanup."""
        if self._cleanup_thread:
            self._stop_cleanup.set()
            self._cleanup_thread.join(timeout=5)
            self._cleanup_thread = None

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
        except Exception:
            pass

        return current_stats

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
