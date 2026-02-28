"""Enhanced port management: smart port lookup, process detection, conflict resolution."""

import socket
import time
from typing import Any

import psutil


class PortManager:
    """Enhanced port management."""

    @staticmethod
    def find_process_using_port(port: int) -> dict[str, Any] | None:
        """Find process using the given port."""
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                    try:
                        process = psutil.Process(conn.pid)
                        return {
                            "pid": conn.pid,
                            "name": process.name(),
                            "cmdline": " ".join(process.cmdline()),
                            "create_time": process.create_time(),
                            "status": process.status(),
                        }
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
        except Exception:
            pass

        return None

    @staticmethod
    def kill_process_on_port(port: int, force: bool = False) -> bool:
        """Kill process using the given port."""
        process_info = PortManager.find_process_using_port(port)
        if not process_info:
            return True

        try:
            pid = process_info["pid"]
            process = psutil.Process(pid)

            if force:
                process.kill()
            else:
                process.terminate()

            try:
                process.wait(timeout=5)
                return True
            except psutil.TimeoutExpired:
                if not force:
                    process.kill()
                    process.wait(timeout=3)
                    return True
                return False

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception:
            return False

    @staticmethod
    def is_port_available(host: str, port: int) -> bool:
        """Check if port is available."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((host, port))
                return True
        except OSError:
            try:
                import psutil

                for conn in psutil.net_connections(kind="inet"):
                    if (
                        conn.laddr.port == port
                        and conn.laddr.ip in [host, "0.0.0.0", "::"]
                        and conn.status == psutil.CONN_LISTEN
                    ):
                        return False
                return True
            except Exception:
                return False

    @staticmethod
    def find_free_port_enhanced(
        preferred_port: int = 8765,
        auto_cleanup: bool = True,
        host: str = "127.0.0.1",
        max_attempts: int = 100,
    ) -> int:
        """Find available port with optional auto-cleanup of occupying process."""
        if PortManager.is_port_available(host, preferred_port):
            return preferred_port

        if auto_cleanup:
            process_info = PortManager.find_process_using_port(preferred_port)

            if process_info:
                if PortManager._should_cleanup_process(process_info):
                    if PortManager.kill_process_on_port(preferred_port):
                        time.sleep(1)
                        if PortManager.is_port_available(host, preferred_port):
                            return preferred_port

        for i in range(max_attempts):
            port = preferred_port + i + 1
            if PortManager.is_port_available(host, port):
                return port

        for i in range(1, min(preferred_port - 1024, max_attempts)):
            port = preferred_port - i
            if port < 1024:
                break
            if PortManager.is_port_available(host, port):
                return port

        raise RuntimeError(
            f"No available port in {preferred_port}±{max_attempts}. "
            "Check for excessive port usage or specify another port."
        )

    @staticmethod
    def _should_cleanup_process(process_info: dict[str, Any]) -> bool:
        """Determine if process should be cleaned up."""
        cmdline = process_info.get("cmdline", "").lower()
        process_name = process_info.get("name", "").lower()

        if any(
            keyword in cmdline
            for keyword in ["leo-feedback-mcp", "mcp-feedback-enhanced", "mcp_feedback_enhanced"]
        ):
            return True

        if "python" in process_name and any(
            keyword in cmdline for keyword in ["uvicorn", "fastapi"]
        ):
            return True

        return False

