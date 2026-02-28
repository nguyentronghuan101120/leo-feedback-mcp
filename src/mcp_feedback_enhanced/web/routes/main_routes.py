#!/usr/bin/env python3
"""
Main route handlers for the Web UI.
"""

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ... import __version__
from ...debug import web_debug_log as debug_log
from ..constants import get_message_code as get_msg_code


if TYPE_CHECKING:
    from ..main import WebUIManager


def setup_routes(manager: "WebUIManager"):
    """Configure routes."""

    @manager.app.get("/api/initial-data")
    async def get_initial_data():
        """Provide initial session data for Flutter UI"""
        current_session = manager.get_current_session()
        if not current_session:
            return JSONResponse({
                "has_session": False,
                "version": __version__,
            })
        return JSONResponse({
            "has_session": True,
            "version": __version__,
            "project_directory": current_session.project_directory,
            "summary": current_session.summary,
            "session_id": current_session.session_id,
        })

    @manager.app.get("/")
    async def index(request: Request):
        """Serve Flutter Web UI"""
        flutter_path = getattr(manager, "flutter_build_path", None)
        if flutter_path and (flutter_path / "index.html").exists():
            return FileResponse(str(flutter_path / "index.html"))

        return JSONResponse(
            status_code=503,
            content={"error": "Flutter Web UI not built. Run: cd frontend && flutter build web --release"},
        )

    @manager.app.get("/api/session-status")
    async def get_session_status(request: Request):
        """Get current session status."""
        current_session = manager.get_current_session()

        if not current_session:
            return JSONResponse(
                content={
                    "has_session": False,
                    "status": "no_session",
                    "messageCode": get_msg_code("no_active_session"),
                }
            )

        return JSONResponse(
            content={
                "has_session": True,
                "status": "active",
                "session_info": {
                    "project_directory": current_session.project_directory,
                    "summary": current_session.summary,
                    "feedback_completed": current_session.feedback_completed.is_set(),
                },
            }
        )

    @manager.app.get("/api/current-session")
    async def get_current_session(request: Request):
        """Get current session details."""
        current_session = manager.get_current_session()

        if not current_session:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "No active session",
                    "messageCode": get_msg_code("no_active_session"),
                },
            )

        return JSONResponse(
            content={
                "session_id": current_session.session_id,
                "project_directory": current_session.project_directory,
                "summary": current_session.summary,
                "feedback_completed": current_session.feedback_completed.is_set(),
                "command_logs": current_session.command_logs,
                "images_count": len(current_session.images),
            }
        )

    @manager.app.get("/api/all-sessions")
    async def get_all_sessions(request: Request):
        """Get real-time status of all sessions."""

        try:
            sessions_data = []

            for session_id, session in manager.sessions.items():
                session_info = {
                    "session_id": session.session_id,
                    "project_directory": session.project_directory,
                    "summary": session.summary,
                    "status": session.status.value,
                    "status_message": session.status_message,
                    "created_at": int(session.created_at * 1000),
                    "last_activity": int(session.last_activity * 1000),
                    "feedback_completed": session.feedback_completed.is_set(),
                    "has_websocket": session.websocket is not None,
                    "is_current": session == manager.current_session,
                    "user_messages": session.user_messages,
                }
                sessions_data.append(session_info)

            sessions_data.sort(key=lambda x: x["created_at"], reverse=True)

            debug_log(f"Returning real-time status for {len(sessions_data)} sessions")
            return JSONResponse(content={"sessions": sessions_data})

        except Exception as e:
            debug_log(f"Failed to get all sessions status: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": f"Failed to get sessions: {e!s}",
                    "messageCode": get_msg_code("get_sessions_failed"),
                },
            )

    @manager.app.post("/api/add-user-message")
    async def add_user_message(request: Request):
        """Add user message to current session."""

        try:
            data = await request.json()
            current_session = manager.get_current_session()

            if not current_session:
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": "No active session",
                        "messageCode": get_msg_code("no_active_session"),
                    },
                )

            current_session.add_user_message(data)

            debug_log(f"User message added to session {current_session.session_id}")
            return JSONResponse(
                content={
                    "status": "success",
                    "messageCode": get_msg_code("user_message_recorded"),
                }
            )

        except Exception as e:
            debug_log(f"Failed to add user message: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": f"Failed to add user message: {e!s}",
                    "messageCode": get_msg_code("add_user_message_failed"),
                },
            )

    @manager.app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, lang: str = "en"):
        """WebSocket endpoint."""
        session = manager.get_current_session()
        if not session:
            await websocket.close(code=4004, reason="No active session")
            return

        await websocket.accept()

        debug_log(f"WebSocket connection established, lang handled by frontend: {lang}")

        if session.websocket and session.websocket != websocket:
            debug_log("Session already has WebSocket, replacing with new connection")

        session.websocket = websocket
        debug_log(f"WebSocket connected: active session {session.session_id}")

        try:
            await websocket.send_json(
                {
                    "type": "connection_established",
                    "messageCode": get_msg_code("websocket_connected"),
                }
            )

            if getattr(manager, "_pending_session_update", False):
                debug_log("Pending session update detected, sending notification")
                await websocket.send_json(
                    {
                        "type": "session_updated",
                        "action": "new_session_created",
                        "messageCode": get_msg_code("new_session_created"),
                        "session_info": {
                            "project_directory": session.project_directory,
                            "summary": session.summary,
                            "session_id": session.session_id,
                        },
                    }
                )
                manager._pending_session_update = False
                debug_log("Session update notification sent to frontend")
            else:
                await websocket.send_json(
                    {"type": "status_update", "status_info": session.get_status_info()}
                )
                debug_log("Current session status sent to frontend")

        except Exception as e:
            debug_log(f"Failed to send connection confirmation: {e}")

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                current_session = manager.get_current_session()
                if current_session and current_session.websocket == websocket:
                    await handle_websocket_message(manager, current_session, message)
                else:
                    debug_log("Session switched or WebSocket mismatch, ignoring message")
                    break

        except WebSocketDisconnect:
            debug_log("WebSocket disconnected")
        except ConnectionResetError:
            debug_log("WebSocket connection reset")
        except Exception as e:
            debug_log(f"WebSocket error: {e}")
        finally:
            if session.websocket == websocket:
                session.websocket = None
                debug_log("Cleaned WebSocket from session")

    @manager.app.post("/api/save-settings")
    async def save_settings(request: Request):
        """Save settings to file."""

        try:
            data = await request.json()

            config_dir = Path.home() / ".config" / "leo-feedback-mcp"
            config_dir.mkdir(parents=True, exist_ok=True)
            settings_file = config_dir / "ui_settings.json"

            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            debug_log(f"Settings saved to: {settings_file}")

            return JSONResponse(
                content={
                    "status": "success",
                    "messageCode": get_msg_code("settings_saved"),
                }
            )

        except Exception as e:
            debug_log(f"Failed to save settings: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Save failed: {e!s}",
                    "messageCode": get_msg_code("save_failed"),
                },
            )

    @manager.app.get("/api/load-settings")
    async def load_settings(request: Request):
        """Load settings from file."""

        try:
            config_dir = Path.home() / ".config" / "leo-feedback-mcp"
            settings_file = config_dir / "ui_settings.json"

            if settings_file.exists():
                with open(settings_file, encoding="utf-8") as f:
                    settings = json.load(f)

                debug_log(f"Settings loaded from: {settings_file}")
                return JSONResponse(content=settings)
            debug_log("Settings file not found, returning empty")
            return JSONResponse(content={})

        except Exception as e:
            debug_log(f"Failed to load settings: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Load failed: {e!s}",
                    "messageCode": get_msg_code("load_failed"),
                },
            )

    @manager.app.post("/api/clear-settings")
    async def clear_settings(request: Request):
        """Clear settings file."""

        try:
            config_dir = Path.home() / ".config" / "leo-feedback-mcp"
            settings_file = config_dir / "ui_settings.json"

            if settings_file.exists():
                settings_file.unlink()
                debug_log(f"Settings file deleted: {settings_file}")
            else:
                debug_log("Settings file not found, nothing to delete")

            return JSONResponse(
                content={
                    "status": "success",
                    "messageCode": get_msg_code("settings_cleared"),
                }
            )

        except Exception as e:
            debug_log(f"Failed to clear settings: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Clear failed: {e!s}",
                    "messageCode": get_msg_code("clear_failed"),
                },
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

                debug_log(f"Session history loaded from: {history_file}")

                if isinstance(history_data, dict):
                    sessions = history_data.get("sessions", [])
                    last_cleanup = history_data.get("lastCleanup", 0)
                else:
                    sessions = history_data if isinstance(history_data, list) else []
                    last_cleanup = 0

                return JSONResponse(
                    content={"sessions": sessions, "lastCleanup": last_cleanup}
                )

            debug_log("Session history file not found, returning empty")
            return JSONResponse(content={"sessions": [], "lastCleanup": 0})

        except Exception as e:
            debug_log(f"Failed to load session history: {e}")
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

            debug_log(f"Session history saved to: {history_file}")
            session_count = len(history_data["sessions"])
            debug_log(f"Saved {session_count} session records")

            return JSONResponse(
                content={
                    "status": "success",
                    "messageCode": get_msg_code("session_history_saved"),
                    "params": {"count": session_count},
                }
            )

        except Exception as e:
            debug_log(f"Failed to save session history: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Save failed: {e!s}",
                    "messageCode": get_msg_code("save_failed"),
                },
            )

    @manager.app.get("/api/log-level")
    async def get_log_level(request: Request):
        """Get log level setting."""

        try:
            config_dir = Path.home() / ".config" / "leo-feedback-mcp"
            settings_file = config_dir / "ui_settings.json"

            if settings_file.exists():
                with open(settings_file, encoding="utf-8") as f:
                    settings_data = json.load(f)
                    log_level = settings_data.get("logLevel", "INFO")
                    debug_log(f"Log level loaded from settings: {log_level}")
                    return JSONResponse(content={"logLevel": log_level})
            else:
                default_log_level = "INFO"
                debug_log(f"Using default log level: {default_log_level}")
                return JSONResponse(content={"logLevel": default_log_level})

        except Exception as e:
            debug_log(f"Failed to get log level: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": f"Failed to get log level: {e!s}",
                    "messageCode": get_msg_code("get_log_level_failed"),
                },
            )

    @manager.app.post("/api/log-level")
    async def set_log_level(request: Request):
        """Set log level."""

        try:
            data = await request.json()
            log_level = data.get("logLevel")

            if not log_level or log_level not in ["DEBUG", "INFO", "WARN", "ERROR"]:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Invalid log level",
                        "messageCode": get_msg_code("invalid_log_level"),
                    },
                )

            config_dir = Path.home() / ".config" / "leo-feedback-mcp"
            config_dir.mkdir(parents=True, exist_ok=True)
            settings_file = config_dir / "ui_settings.json"

            settings_data = {}
            if settings_file.exists():
                with open(settings_file, encoding="utf-8") as f:
                    settings_data = json.load(f)

            settings_data["logLevel"] = log_level

            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(settings_data, f, ensure_ascii=False, indent=2)

            debug_log(f"Log level set to: {log_level}")

            return JSONResponse(
                content={
                    "status": "success",
                    "logLevel": log_level,
                    "messageCode": get_msg_code("log_level_updated"),
                }
            )

        except Exception as e:
            debug_log(f"Failed to set log level: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Set failed: {e!s}",
                    "messageCode": get_msg_code("set_failed"),
                },
            )

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
                debug_log(f"Failed to send status update: {e}")

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
                debug_log(f"Failed to send heartbeat response: {e}")

    elif message_type == "user_timeout":
        debug_log(f"User timeout notification received: {session.session_id}")
        await session._cleanup_resources_on_timeout()

    elif message_type == "pong":
        debug_log(f"Pong received, timestamp: {data.get('timestamp', 'N/A')}")

    elif message_type == "update_timeout_settings":
        settings = data.get("settings", {})
        debug_log(f"Timeout settings update received: {settings}")
        if settings.get("enabled"):
            session.update_timeout_settings(
                enabled=True, timeout_seconds=settings.get("seconds", 3600)
            )
        else:
            session.update_timeout_settings(enabled=False)

    else:
        debug_log(f"Unknown message type: {message_type}")


async def _delayed_server_stop(manager: "WebUIManager"):
    """Delayed server stop."""
    import asyncio

    await asyncio.sleep(5)
    from ..main import stop_web_ui

    stop_web_ui()
    debug_log("Web UI server stopped due to user timeout")
