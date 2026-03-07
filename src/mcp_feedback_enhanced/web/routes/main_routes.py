#!/usr/bin/env python3
"""
Main route handlers for the Web UI.
"""

import json
import sys
import time
from typing import TYPE_CHECKING

from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ... import __version__
from ..constants import get_message_code as get_msg_code


if TYPE_CHECKING:
    from ..main import WebUIManager


def setup_routes(manager: "WebUIManager"):
    """Configure routes for single-session model."""

    @manager.app.get("/api/initial-data")
    async def get_initial_data():
        """Provide initial session data for Flutter UI."""
        session = manager.session
        if not session:
            return JSONResponse({
                "has_session": False,
                "version": __version__,
            })
        return JSONResponse({
            "has_session": True,
            "version": __version__,
            "project_directory": session.project_directory,
            "summary": session.summary,
            "session_id": session.session_id,
        })

    @manager.app.get("/")
    async def index(request: Request):
        """Serve Flutter Web UI."""
        flutter_path = getattr(manager, "flutter_build_path", None)
        if flutter_path and (flutter_path / "index.html").exists():
            return FileResponse(str(flutter_path / "index.html"))

        return JSONResponse(
            status_code=503,
            content={"error": "Flutter Web UI not built. Run: cd frontend && flutter build web --release"},
        )

    @manager.app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for the single session."""
        session = manager.session
        if not session:
            await websocket.close(code=4004, reason="No active session")
            return

        await websocket.accept()
        session.websocket = websocket

        try:
            await websocket.send_json(
                {
                    "type": "connection_established",
                    "messageCode": get_msg_code("websocket_connected"),
                }
            )

            await websocket.send_json(
                {"type": "status_update", "status_info": session.get_status_info()}
            )

        except Exception as e:
            print(str(e), file=sys.stderr)

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                current_session = manager.session
                if current_session is None:
                    break
                await handle_websocket_message(manager, current_session, message)

        except WebSocketDisconnect:
            pass
        except ConnectionResetError:
            pass
        except Exception as e:
            print(str(e), file=sys.stderr)
        finally:
            if session.websocket == websocket:
                session.websocket = None

    # Mount Flutter static files LAST so API routes take priority
    flutter_path = getattr(manager, "flutter_build_path", None)
    if flutter_path and flutter_path.exists():
        manager.app.mount(
            "/", StaticFiles(directory=str(flutter_path)), name="flutter_ui"
        )


async def handle_websocket_message(manager: "WebUIManager", session, data: dict):
    """Handle WebSocket messages."""
    message_type = data.get("type")

    if message_type == "submit_feedback":
        feedback = data.get("feedback", "")
        images = data.get("images", [])
        settings = data.get("settings", {})
        await session.submit_feedback(feedback, images, settings)

    elif message_type == "run_command":
        command = data.get("command", "")
        if command.strip():
            await session.run_command(command)

    elif message_type == "get_status":
        if session.websocket:
            try:
                await session.websocket.send_json(
                    {"type": "status_update", "status_info": session.get_status_info()}
                )
            except Exception as e:
                print(str(e), file=sys.stderr)

    elif message_type == "heartbeat":
        session.last_heartbeat = time.time()
        session.last_activity = time.time()

        if session.websocket:
            try:
                await session.websocket.send_json(
                    {
                        "type": "heartbeat_response",
                        "timestamp": data.get("timestamp", 0),
                    }
                )
            except Exception as e:
                print(str(e), file=sys.stderr)

    elif message_type == "user_timeout":
        await session._cleanup_resources_on_timeout()

    elif message_type == "pong":
        pass

    elif message_type == "update_timeout_settings":
        settings = data.get("settings", {})
        if settings.get("enabled"):
            session.update_timeout_settings(
                enabled=True, timeout_seconds=settings.get("seconds", 3600)
            )
        else:
            session.update_timeout_settings(enabled=False)

    else:
        pass
