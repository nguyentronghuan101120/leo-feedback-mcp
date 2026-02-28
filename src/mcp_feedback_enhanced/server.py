#!/usr/bin/env python3
"""
Leo Feedback MCP - Server Module

MCP tool definitions for interactive feedback collection.
Supports Web UI, image processing, environment detection.

MCP Tools:
- interactive_feedback: Collect user feedback via Web UI
- get_system_info: Get system environment info
"""

import base64
import io
import json
import os
import sys
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.utilities.types import Image as MCPImage
from mcp.types import TextContent
from pydantic import Field

from .utils.error_handler import ErrorHandler, ErrorType
from .utils.resource_manager import create_temp_file
from .web.utils.browser import is_wsl_environment


def init_encoding():
    """Initialize encoding for proper Unicode handling."""
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

            stdin_buffer = getattr(sys.stdin, "buffer", None)
            if stdin_buffer is None and hasattr(sys.stdin, "detach"):
                stdin_buffer = sys.stdin.detach()

            stdout_buffer = getattr(sys.stdout, "buffer", None)
            if stdout_buffer is None and hasattr(sys.stdout, "detach"):
                stdout_buffer = sys.stdout.detach()

            sys.stdin = io.TextIOWrapper(
                stdin_buffer, encoding="utf-8", errors="replace", newline=None
            )
            sys.stdout = io.TextIOWrapper(
                stdout_buffer,
                encoding="utf-8",
                errors="replace",
                newline="",
                write_through=True,
            )
        else:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stdin, "reconfigure"):
                sys.stdin.reconfigure(encoding="utf-8", errors="replace")

        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

        return True
    except Exception:
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stdin, "reconfigure"):
                sys.stdin.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except:
            pass
        return False


_encoding_initialized = init_encoding()

SERVER_NAME = "Leo Feedback MCP"
SSH_ENV_VARS = ["SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"]
REMOTE_ENV_VARS = ["REMOTE_CONTAINERS", "CODESPACES"]


from . import __version__


fastmcp_settings = {}
env_log_level = os.getenv("FASTMCP_LOG_LEVEL", "").upper()
if env_log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
    fastmcp_settings["log_level"] = env_log_level
else:
    fastmcp_settings["log_level"] = "INFO"

mcp: Any = FastMCP(SERVER_NAME)


def is_remote_environment() -> bool:
    """Detect if running in a remote environment (SSH, Codespaces, etc.)."""
    if is_wsl_environment():
        return False

    for env_var in SSH_ENV_VARS:
        if os.getenv(env_var):
            return True

    for env_var in REMOTE_ENV_VARS:
        if os.getenv(env_var):
            return True

    if os.path.exists("/.dockerenv"):
        return True

    if sys.platform == "win32":
        session_name = os.getenv("SESSIONNAME", "")
        if session_name and "RDP" in session_name:
            return True

    if (
        sys.platform.startswith("linux")
        and not os.getenv("DISPLAY")
        and not is_wsl_environment()
    ):
        return True

    return False


def save_feedback_to_file(feedback_data: dict, file_path: str | None = None) -> str:
    """Save feedback data to a JSON file."""
    if file_path is None:
        file_path = create_temp_file(suffix=".json", prefix="feedback_")

    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    json_data = feedback_data.copy()

    if "images" in json_data and isinstance(json_data["images"], list):
        processed_images = []
        for img in json_data["images"]:
            if isinstance(img, dict) and "data" in img:
                processed_img = img.copy()
                if isinstance(img["data"], bytes):
                    processed_img["data"] = base64.b64encode(img["data"]).decode(
                        "utf-8"
                    )
                    processed_img["data_type"] = "base64"
                processed_images.append(processed_img)
            else:
                processed_images.append(img)
        json_data["images"] = processed_images

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    return file_path


def create_feedback_text(feedback_data: dict) -> str:
    """Build formatted feedback text for AI consumption."""
    text_parts = []

    if feedback_data.get("interactive_feedback"):
        text_parts.append(f"=== User Feedback ===\n{feedback_data['interactive_feedback']}")

    if feedback_data.get("command_logs"):
        text_parts.append(f"=== Command Logs ===\n{feedback_data['command_logs']}")

    if feedback_data.get("images"):
        images = feedback_data["images"]
        text_parts.append(f"=== Image Attachments ===\nUser provided {len(images)} image(s):")

        for i, img in enumerate(images, 1):
            size = img.get("size", 0)
            name = img.get("name", "unknown")

            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_kb = size / 1024
                size_str = f"{size_kb:.1f} KB"
            else:
                size_mb = size / (1024 * 1024)
                size_str = f"{size_mb:.1f} MB"

            img_info = f"  {i}. {name} ({size_str})"

            if img.get("data"):
                try:
                    if isinstance(img["data"], bytes):
                        img_base64 = base64.b64encode(img["data"]).decode("utf-8")
                    elif isinstance(img["data"], str):
                        img_base64 = img["data"]
                    else:
                        img_base64 = None

                    if img_base64:
                        preview = (
                            img_base64[:50] + "..."
                            if len(img_base64) > 50
                            else img_base64
                        )
                        img_info += f"\n     Base64 preview: {preview}"
                        img_info += f"\n     Full Base64 length: {len(img_base64)} chars"

                        include_full_base64 = feedback_data.get("settings", {}).get(
                            "enable_base64_detail", False
                        )

                        if include_full_base64:
                            file_name = img.get("name", "image.png")
                            if file_name.lower().endswith((".jpg", ".jpeg")):
                                mime_type = "image/jpeg"
                            elif file_name.lower().endswith(".gif"):
                                mime_type = "image/gif"
                            elif file_name.lower().endswith(".webp"):
                                mime_type = "image/webp"
                            else:
                                mime_type = "image/png"

                            img_info += f"\n     Full Base64: data:{mime_type};base64,{img_base64}"

                except Exception:
                    pass

            text_parts.append(img_info)

        text_parts.append(
            "\nNote: If the AI cannot display images, the image data is included in the Base64 information above."
        )

    return "\n\n".join(text_parts) if text_parts else "No feedback provided."


def process_images(images_data: list[dict]) -> list[MCPImage]:
    """Convert image data to MCP Image objects."""
    mcp_images = []

    for i, img in enumerate(images_data, 1):
        try:
            if not img.get("data"):
                continue

            if isinstance(img["data"], bytes):
                image_bytes = img["data"]
            elif isinstance(img["data"], str):
                image_bytes = base64.b64decode(img["data"])
            else:
                continue

            if len(image_bytes) == 0:
                continue

            file_name = img.get("name", "image.png")
            if file_name.lower().endswith((".jpg", ".jpeg")):
                image_format = "jpeg"
            elif file_name.lower().endswith(".gif"):
                image_format = "gif"
            elif file_name.lower().endswith(".webp"):
                image_format = "webp"
            else:
                image_format = "png"

            mcp_image = MCPImage(data=image_bytes, format=image_format)
            mcp_images.append(mcp_image)

        except Exception as e:
            ErrorHandler.log_error_with_context(
                e,
                context={"operation": "image_processing", "image_index": i},
                error_type=ErrorType.FILE_IO,
            )

    return mcp_images


@mcp.tool()
async def interactive_feedback(
    project_directory: Annotated[str, Field(description="Project directory path")] = ".",
    summary: Annotated[
        str, Field(description="Summary of AI work completed")
    ] = "I have completed the requested task.",
    timeout: Annotated[int, Field(description="Timeout in seconds for user feedback")] = 600,
):
    """Interactive feedback collection tool for LLM agents.

    USAGE RULES:
    1. During any process, task, or conversation, whether asking, replying, or completing phased tasks, you must call this tool to ask for feedback.
    2. Unless receiving termination instructions, all steps must repeatedly call this tool.
    3. Whenever user feedback is received, if the feedback content is not empty, you must call this tool again and adjust behavior based on the feedback content.
    4. Only when the user explicitly indicates "end" or "no more interaction needed" can you stop calling this tool, and the process is considered complete.
    5. You should summarize what have done, and provide project directory through args to let user know what you have done to provide feedback for next step.

    Args:
        project_directory: Project directory path for context
        summary: Summary of AI work completed for user review
        timeout: Timeout in seconds for waiting user feedback (default: 600 seconds)

    Returns:
        list: List containing TextContent and MCPImage objects representing user feedback
    """
    try:
        if not os.path.exists(project_directory):
            project_directory = os.getcwd()
        project_directory = os.path.abspath(project_directory)

        result = await launch_web_feedback_ui(project_directory, summary, timeout)

        if not result:
            return [TextContent(type="text", text="Feedback cancelled by user.")]

        save_feedback_to_file(result)

        feedback_items = []

        if (
            result.get("interactive_feedback")
            or result.get("command_logs")
            or result.get("images")
        ):
            feedback_text = create_feedback_text(result)
            feedback_items.append(TextContent(type="text", text=feedback_text))

        if result.get("images"):
            mcp_images = process_images(result["images"])
            feedback_items.extend(mcp_images)

        if not feedback_items:
            feedback_items.append(
                TextContent(type="text", text="No feedback provided.")
            )

        return feedback_items

    except Exception as e:
        ErrorHandler.log_error_with_context(
            e,
            context={"operation": "feedback_collection", "project_dir": project_directory},
            error_type=ErrorType.SYSTEM,
        )

        user_error_msg = ErrorHandler.format_user_error(e, include_technical=False)

        return [TextContent(type="text", text=user_error_msg)]


async def launch_web_feedback_ui(project_dir: str, summary: str, timeout: int) -> dict:
    """Launch Web UI for feedback collection with custom timeout."""
    try:
        from .web import launch_web_feedback_ui as web_launch

        return await web_launch(project_dir, summary, timeout)
    except ImportError as e:
        ErrorHandler.log_error_with_context(
            e,
            context={"operation": "web_ui_import", "module": "web"},
            error_type=ErrorType.DEPENDENCY,
        )
        user_error_msg = ErrorHandler.format_user_error(
            e, ErrorType.DEPENDENCY, include_technical=False
        )

        return {
            "command_logs": "",
            "interactive_feedback": user_error_msg,
            "images": [],
        }


@mcp.tool()
def get_system_info() -> str:
    """Get system environment information as JSON."""
    is_remote = is_remote_environment()
    is_wsl = is_wsl_environment()

    system_info = {
        "platform": sys.platform,
        "python_version": sys.version.split()[0],
        "wsl_environment": is_wsl,
        "remote_environment": is_remote,
        "interface_type": "Web UI",
        "environment_variables": {
            "SSH_CONNECTION": os.getenv("SSH_CONNECTION"),
            "SSH_CLIENT": os.getenv("SSH_CLIENT"),
            "DISPLAY": os.getenv("DISPLAY"),
            "VSCODE_INJECTION": os.getenv("VSCODE_INJECTION"),
            "SESSIONNAME": os.getenv("SESSIONNAME"),
            "WSL_DISTRO_NAME": os.getenv("WSL_DISTRO_NAME"),
            "WSL_INTEROP": os.getenv("WSL_INTEROP"),
            "WSLENV": os.getenv("WSLENV"),
        },
    }

    return json.dumps(system_info, ensure_ascii=False, indent=2)


def main():
    """Main entry point for package execution. Collects user feedback via Web UI."""
    try:
        mcp.run()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
