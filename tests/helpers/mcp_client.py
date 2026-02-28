#!/usr/bin/env python3
"""
Simplified MCP client simulator.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

from .test_utils import PerformanceTimer


class SimpleMCPClient:
    """Simplified MCP client simulator."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.server_process: subprocess.Popen | None = None
        self.stdin: Any = None
        self.stdout: Any = None
        self.stderr: Any = None
        self.initialized = False

    async def start_server(self) -> bool:
        """Start MCP server."""
        try:
            cmd = ["uv", "run", "python", "-m", "mcp_feedback_enhanced"]

            self.server_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
                cwd=Path.cwd(),
                encoding="utf-8",
                errors="replace",
            )

            self.stdin = self.server_process.stdin
            self.stdout = self.server_process.stdout
            self.stderr = self.server_process.stderr

            await asyncio.sleep(2)

            if self.server_process.poll() is not None:
                return False

            return True

        except Exception as e:
            print(f"Failed to start MCP server: {e}")
            return False

    async def initialize(self) -> bool:
        """Initialize MCP connection."""
        if not self.server_process or self.server_process.poll() is not None:
            return False

        try:
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }

            await self._send_request(init_request)
            response = await self._read_response()

            if response and "result" in response:
                self.initialized = True
                return True

        except Exception as e:
            print(f"MCP initialization failed: {e}")

        return False

    async def call_interactive_feedback(
        self, project_directory: str, summary: str, timeout: int = 30
    ) -> dict[str, Any]:
        """Call interactive_feedback tool."""
        if not self.initialized:
            return {"error": "MCP client not initialized"}

        try:
            request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "interactive_feedback",
                    "arguments": {
                        "project_directory": project_directory,
                        "summary": summary,
                        "timeout": timeout,
                    },
                },
            }

            with PerformanceTimer() as timer:
                await self._send_request(request)
                response = await self._read_response(timeout=timeout + 5)

            if response and "result" in response:
                result = response["result"]
                result["performance"] = {"duration": timer.duration}
                return dict(result)
            return {"error": "Invalid response format", "response": response}

        except TimeoutError:
            return {"error": "Call timeout"}
        except Exception as e:
            return {"error": f"Call failed: {e!s}"}

    async def _send_request(self, request: dict[str, Any]):
        """Send request."""
        if not self.stdin:
            raise RuntimeError("stdin not available")

        request_str = json.dumps(request) + "\n"
        self.stdin.write(request_str)
        self.stdin.flush()

    async def _read_response(self, timeout: int = 30) -> dict[str, Any] | None:
        """Read response."""
        if not self.stdout:
            raise RuntimeError("stdout not available")

        try:
            response_line = await asyncio.wait_for(
                asyncio.to_thread(self.stdout.readline), timeout=timeout
            )

            if response_line:
                response_data = json.loads(response_line.strip())
                return (
                    dict(response_data)
                    if isinstance(response_data, dict)
                    else response_data
                )
            return None

        except TimeoutError:
            raise
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}, raw data: {response_line}")
            return None

    async def cleanup(self):
        """Clean up resources."""
        if self.server_process:
            try:
                self.server_process.terminate()

                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(self.server_process.wait), timeout=5
                    )
                except TimeoutError:
                    self.server_process.kill()
                    await asyncio.to_thread(self.server_process.wait)

            except Exception as e:
                print(f"Failed to cleanup MCP server: {e}")
            finally:
                self.server_process = None
                self.stdin = None
                self.stdout = None
                self.stderr = None
                self.initialized = False


class MCPWorkflowTester:
    """MCP workflow tester."""

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.client = SimpleMCPClient(timeout)

    async def test_basic_workflow(
        self, project_dir: str, summary: str
    ) -> dict[str, Any]:
        """Test basic workflow."""
        result: dict[str, Any] = {
            "success": False,
            "steps": {},
            "errors": [],
            "performance": {},
        }

        with PerformanceTimer() as timer:
            try:
                if await self.client.start_server():
                    result["steps"]["server_started"] = True
                else:
                    result["errors"].append("Server start failed")
                    return result

                if await self.client.initialize():
                    result["steps"]["initialized"] = True
                else:
                    result["errors"].append("Initialization failed")
                    return result

                feedback_result = await self.client.call_interactive_feedback(
                    project_dir, summary, timeout=10
                )

                if "error" not in feedback_result:
                    result["steps"]["interactive_feedback_called"] = True
                    result["feedback_result"] = feedback_result
                    result["success"] = True
                else:
                    result["errors"].append(
                        f"interactive_feedback call failed: {feedback_result['error']}"
                    )

            except Exception as e:
                result["errors"].append(f"Test exception: {e!s}")
            finally:
                await self.client.cleanup()
                result["performance"]["total_duration"] = timer.duration

        return result
