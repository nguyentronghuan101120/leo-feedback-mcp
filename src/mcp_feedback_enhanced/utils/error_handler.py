"""
Unified error handling: classification, user-friendly messages,
context logging, solution suggestions. Does not affect JSON RPC.
"""

import time
import traceback
import sys
from enum import Enum
from typing import Any


class ErrorType(Enum):
    """Error type enum."""

    NETWORK = "network"
    FILE_IO = "file_io"
    PROCESS = "process"
    TIMEOUT = "timeout"
    USER_CANCEL = "user_cancel"
    SYSTEM = "system"
    PERMISSION = "permission"
    VALIDATION = "validation"
    DEPENDENCY = "dependency"
    CONFIGURATION = "config"


class ErrorSeverity(Enum):
    """Error severity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorHandler:
    """Unified error handler."""

    _ERROR_MESSAGES = {
        ErrorType.NETWORK: "Network connection issue",
        ErrorType.FILE_IO: "File read/write issue",
        ErrorType.PROCESS: "Process execution issue",
        ErrorType.TIMEOUT: "Operation timeout",
        ErrorType.USER_CANCEL: "User cancelled the operation",
        ErrorType.SYSTEM: "System issue",
        ErrorType.PERMISSION: "Insufficient permissions",
        ErrorType.VALIDATION: "Data validation failed",
        ErrorType.DEPENDENCY: "Dependency issue",
        ErrorType.CONFIGURATION: "Configuration issue",
    }

    _ERROR_SOLUTIONS = {
        ErrorType.NETWORK: [
            "Check network connection",
            "Verify firewall settings",
            "Try restarting the application",
        ],
        ErrorType.FILE_IO: [
            "Check if file exists",
            "Verify file permissions",
            "Check available disk space",
        ],
        ErrorType.PROCESS: [
            "Check if process is running",
            "Verify system resources",
            "Try restarting related services",
        ],
        ErrorType.TIMEOUT: [
            "Increase timeout settings",
            "Check network latency",
            "Retry the operation later",
        ],
        ErrorType.PERMISSION: [
            "Run as administrator",
            "Check file/directory permissions",
            "Contact system administrator",
        ],
    }

    @staticmethod
    def classify_error(error: Exception) -> ErrorType:
        """Classify error by exception type."""
        error_name = type(error).__name__
        error_message = str(error).lower()

        if "timeout" in error_name.lower() or "timeout" in error_message:
            return ErrorType.TIMEOUT

        if "permission" in error_name.lower():
            return ErrorType.PERMISSION
        if any(
            keyword in error_message
            for keyword in ["permission denied", "access denied", "forbidden"]
        ):
            return ErrorType.PERMISSION

        if any(
            keyword in error_name.lower()
            for keyword in ["connection", "network", "socket"]
        ):
            return ErrorType.NETWORK
        if any(
            keyword in error_message for keyword in ["connection", "network", "socket"]
        ):
            return ErrorType.NETWORK

        if any(
            keyword in error_name.lower() for keyword in ["file", "ioerror"]
        ):
            return ErrorType.FILE_IO
        if any(
            keyword in error_message
            for keyword in ["file", "directory", "no such file"]
        ):
            return ErrorType.FILE_IO

        if any(keyword in error_name.lower() for keyword in ["process", "subprocess"]):
            return ErrorType.PROCESS
        if any(
            keyword in error_message for keyword in ["process", "command", "executable"]
        ):
            return ErrorType.PROCESS

        if any(
            keyword in error_name.lower() for keyword in ["validation", "value", "type"]
        ):
            return ErrorType.VALIDATION

        if any(
            keyword in error_message for keyword in ["config", "setting", "environment"]
        ):
            return ErrorType.CONFIGURATION

        return ErrorType.SYSTEM

    @staticmethod
    def format_user_error(
        error: Exception,
        error_type: ErrorType | None = None,
        context: dict[str, Any] | None = None,
        include_technical: bool = False,
    ) -> str:
        """Format technical error as user-friendly message."""
        if error_type is None:
            error_type = ErrorHandler.classify_error(error)

        user_message = ErrorHandler._ERROR_MESSAGES.get(error_type, "Unknown error")
        parts = [user_message]

        if context:
            if context.get("operation"):
                parts.append(f"Operation: {context['operation']}")
            if context.get("file_path"):
                parts.append(f"File: {context['file_path']}")

        if include_technical:
            parts.append(f"Technical details: {type(error).__name__}: {error!s}")

        return "\n".join(parts)

    @staticmethod
    def get_error_solutions(error_type: ErrorType) -> list[str]:
        """Get error solution suggestions."""
        return ErrorHandler._ERROR_SOLUTIONS.get(error_type, [])

    @staticmethod
    def log_error_with_context(
        error: Exception,
        context: dict[str, Any] | None = None,
        error_type: ErrorType | None = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    ) -> str:
        """Log error with context (does not affect JSON RPC)."""
        error_id = f"ERR_{int(time.time())}_{id(error) % 10000}"

        if error_type is None:
            error_type = ErrorHandler.classify_error(error)

        try:
            print(f"[ERROR] [{error_id}]: {error_type.value} - {error!s}", file=sys.stderr, flush=True)
            if context:
                print(f"[ERROR] context [{error_id}]: {context}", file=sys.stderr, flush=True)
            if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                print(f"[ERROR] stack [{error_id}]:\n{traceback.format_exc()}", file=sys.stderr, flush=True)
        except Exception:
            pass

        return error_id
