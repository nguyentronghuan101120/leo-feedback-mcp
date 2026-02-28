"""Enhanced port management: smart port lookup, process detection, conflict resolution."""

import socket
import time
from typing import Any

import psutil

from ...debug import debug_log


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
        except Exception as e:
            debug_log(f"Error finding process for port {port}: {e}")

        return None

    @staticmethod
    def kill_process_on_port(port: int, force: bool = False) -> bool:
        """Kill process using the given port."""
        process_info = PortManager.find_process_using_port(port)
        if not process_info:
            debug_log(f"Port {port} not in use")
            return True

        try:
            pid = process_info["pid"]
            process = psutil.Process(pid)
            process_name = process_info["name"]

            debug_log(f"Process {process_name} (PID: {pid}) using port {port}")

            if "mcp-feedback-enhanced" in process_info["cmdline"].lower():
                debug_log("MCP Feedback Enhanced process detected, attempting graceful terminate")

            if force:
                debug_log(f"Force killing process {process_name} (PID: {pid})")
                process.kill()
            else:
                debug_log(f"Terminating process {process_name} (PID: {pid})")
                process.terminate()

            try:
                process.wait(timeout=5)
                debug_log(f"Process {process_name} (PID: {pid}) terminated")
                return True
            except psutil.TimeoutExpired:
                if not force:
                    debug_log(f"Graceful terminate timeout, force killing {process_name} (PID: {pid})")
                    process.kill()
                    process.wait(timeout=3)
                    return True
                debug_log(f"Failed to force kill process {process_name} (PID: {pid})")
                return False

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            debug_log(f"Cannot terminate process (PID: {process_info['pid']}): {e}")
            return False
        except Exception as e:
            debug_log(f"Error killing process on port {port}: {e}")
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
            debug_log(f"Preferred port {preferred_port} available")
            return preferred_port

        if auto_cleanup:
            debug_log(f"Preferred port {preferred_port} in use, attempting cleanup")
            process_info = PortManager.find_process_using_port(preferred_port)

            if process_info:
                debug_log(
                    f"Port {preferred_port} used by {process_info['name']} (PID: {process_info['pid']})"
                )

                if PortManager._should_cleanup_process(process_info):
                    if PortManager.kill_process_on_port(preferred_port):
                        time.sleep(1)
                        if PortManager.is_port_available(host, preferred_port):
                            debug_log(f"Port {preferred_port} cleared and available")
                            return preferred_port

        debug_log(f"Preferred port {preferred_port} unavailable, searching for alternate")

        for i in range(max_attempts):
            port = preferred_port + i + 1
            if PortManager.is_port_available(host, port):
                debug_log(f"Found available port: {port}")
                return port

        for i in range(1, min(preferred_port - 1024, max_attempts)):
            port = preferred_port - i
            if port < 1024:
                break
            if PortManager.is_port_available(host, port):
                debug_log(f"Found available port: {port}")
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
            for keyword in ["mcp-feedback-enhanced", "mcp_feedback_enhanced"]
        ):
            return True

        if "python" in process_name and any(
            keyword in cmdline for keyword in ["uvicorn", "fastapi"]
        ):
            return True

        debug_log(
            f"Process {process_info['name']} (PID: {process_info['pid']}) is not MCP-related, skipping auto cleanup"
        )
        return False

    @staticmethod
    def get_port_status(port: int, host: str = "127.0.0.1") -> dict[str, Any]:
        """Get port status info."""
        status = {
            "port": port,
            "host": host,
            "available": False,
            "process": None,
            "error": None,
        }

        try:
            status["available"] = PortManager.is_port_available(host, port)

            if not status["available"]:
                status["process"] = PortManager.find_process_using_port(port)

        except Exception as e:
            status["error"] = str(e)
            debug_log(f"Error getting port {port} status: {e}")

        return status

    @staticmethod
    def list_listening_ports(
        start_port: int = 8000, end_port: int = 9000
    ) -> list[dict[str, Any]]:
        """List listening ports in the given range."""
        listening_ports = []

        try:
            for conn in psutil.net_connections(kind="inet"):
                if (
                    conn.status == psutil.CONN_LISTEN
                    and start_port <= conn.laddr.port <= end_port
                ):
                    try:
                        process = psutil.Process(conn.pid)
                        port_info = {
                            "port": conn.laddr.port,
                            "host": conn.laddr.ip,
                            "pid": conn.pid,
                            "process_name": process.name(),
                            "cmdline": " ".join(process.cmdline()),
                        }
                        listening_ports.append(port_info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

        except Exception as e:
            debug_log(f"Error listing listening ports: {e}")

        return listening_ports
