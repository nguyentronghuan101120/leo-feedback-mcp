#!/usr/bin/env python3
"""
Main route handlers for the Web UI.
"""

import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ... import __version__
from ..constants import get_message_code as get_msg_code


if TYPE_CHECKING:
    from ..main import WebUIManager


def setup_routes(manager: "WebUIManager"):
    """Configure routes with per-session isolation."""

    @manager.app.get("/api/session/{session_id}/initial-data")
    async def get_initial_data(session_id: str):
        """Provide initial session data for Flutter UI (session-scoped)."""
        session = manager.get_session(session_id)
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
        """Serve Flutter Web UI (root)."""
        flutter_path = getattr(manager, "flutter_build_path", None)
        if flutter_path and (flutter_path / "index.html").exists():
            return FileResponse(str(flutter_path / "index.html"))

        return JSONResponse(
            status_code=503,
            content={"error": "Flutter Web UI not built. Run: cd frontend && flutter build web --release"},
        )

    @manager.app.get("/session/{session_id}")
    async def session_index(session_id: str):
        """Serve Flutter Web UI for a specific session."""
        session = manager.get_session(session_id)
        if not session:
            return JSONResponse(
                status_code=404,
                content={"error": f"Session {session_id} not found"},
            )

        flutter_path = getattr(manager, "flutter_build_path", None)
        if flutter_path and (flutter_path / "index.html").exists():
            return FileResponse(str(flutter_path / "index.html"))

        return JSONResponse(
            status_code=503,
            content={"error": "Flutter Web UI not built. Run: cd frontend && flutter build web --release"},
        )

    @manager.app.get("/api/sessions/active")
    async def get_active_sessions():
        """Get list of sessions currently waiting for feedback."""
        try:
            active = []
            for session in manager.sessions.values():
                if session.is_active() and not session.is_terminal():
                    active.append({
                        "session_id": session.session_id,
                        "project_directory": session.project_directory,
                        "summary": session.summary,
                        "status": session.status.value,
                        "created_at": int(session.created_at * 1000),
                    })
            active.sort(key=lambda x: x["created_at"], reverse=True)
            return JSONResponse(content={"sessions": active})
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to get active sessions: {e!s}"},
            )

    @manager.app.get("/api/load-session-history")
    async def load_session_history(request: Request):
        """Load session history from file."""

        try:
            config_dir = Path.home() / ".config" / "leo-feedback-mcp"
            history_file = config_dir / "session_history.json"

            if history_file.exists():
                with open(history_file, encoding="utf-8") as f:
                    history_data = json.load(f)

                if isinstance(history_data, dict):
                    sessions = history_data.get("sessions", [])
                    last_cleanup = history_data.get("lastCleanup", 0)
                else:
                    sessions = history_data if isinstance(history_data, list) else []
                    last_cleanup = 0

                return JSONResponse(
                    content={"sessions": sessions, "lastCleanup": last_cleanup}
                )

            return JSONResponse(content={"sessions": [], "lastCleanup": 0})

        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Load failed: {e!s}",
                    "messageCode": get_msg_code("load_failed"),
                },
            )

    @manager.app.post("/api/save-session-history")
    async def save_session_history(request: Request):
        """Save session history to file."""

        try:
            data = await request.json()

            config_dir = Path.home() / ".config" / "leo-feedback-mcp"
            config_dir.mkdir(parents=True, exist_ok=True)
            history_file = config_dir / "session_history.json"

            history_data = {
                "version": "1.0",
                "sessions": data.get("sessions", []),
                "lastCleanup": data.get("lastCleanup", 0),
                "savedAt": int(time.time() * 1000),
            }

            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)

            session_count = len(history_data["sessions"])

            return JSONResponse(
                content={
                    "status": "success",
                    "messageCode": get_msg_code("session_history_saved"),
                    "params": {"count": session_count},
                }
            )

        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Save failed: {e!s}",
                    "messageCode": get_msg_code("save_failed"),
                },
            )

    @manager.app.websocket("/ws/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str):
        """WebSocket endpoint scoped to a specific session."""
        session = manager.get_session(session_id)
        if not session:
            await websocket.close(code=4004, reason="Session not found")
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
                await handle_websocket_message(manager, session, message)

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
