"""
Unified error handling: classification, user-friendly messages,
context logging, solution suggestions. Does not affect JSON RPC.
"""

import os
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
        ErrorType.NETWORK: {"en": "Network connection issue"},
        ErrorType.FILE_IO: {"en": "File read/write issue"},
        ErrorType.PROCESS: {"en": "Process execution issue"},
        ErrorType.TIMEOUT: {"en": "Operation timeout"},
        ErrorType.USER_CANCEL: {"en": "User cancelled the operation"},
        ErrorType.SYSTEM: {"en": "System issue"},
        ErrorType.PERMISSION: {"en": "Insufficient permissions"},
        ErrorType.VALIDATION: {"en": "Data validation failed"},
        ErrorType.DEPENDENCY: {"en": "Dependency issue"},
        ErrorType.CONFIGURATION: {"en": "Configuration issue"},
    }

    _ERROR_SOLUTIONS = {
        ErrorType.NETWORK: {
            "en": [
                "Check network connection",
                "Verify firewall settings",
                "Try restarting the application",
            ],
        },
        ErrorType.FILE_IO: {
            "en": [
                "Check if file exists",
                "Verify file permissions",
                "Check available disk space",
            ],
        },
        ErrorType.PROCESS: {
            "en": [
                "Check if process is running",
                "Verify system resources",
                "Try restarting related services",
            ],
        },
        ErrorType.TIMEOUT: {
            "en": [
                "Increase timeout settings",
                "Check network latency",
                "Retry the operation later",
            ],
        },
        ErrorType.PERMISSION: {
            "en": [
                "Run as administrator",
                "Check file/directory permissions",
                "Contact system administrator",
            ],
        },
    }

    @staticmethod
    def get_current_language() -> str:
        """Get current language."""
        try:
            from ..i18n import get_i18n_manager

            return get_i18n_manager().get_current_language()
        except Exception:
            return os.getenv("MCP_LANGUAGE", "en")

    @staticmethod
    def get_i18n_error_message(error_type: ErrorType) -> str:
        """Get error message from i18n or built-in mapping."""
        try:
            from ..i18n import get_i18n_manager

            i18n = get_i18n_manager()
            key = f"errors.types.{error_type.value}"
            message = i18n.t(key)
            if message == key:
                raise Exception("Translation not found")
            return message
        except Exception:
            language = ErrorHandler.get_current_language()
            error_messages = ErrorHandler._ERROR_MESSAGES.get(error_type, {})
            return error_messages.get(language, error_messages.get("en", "Unknown error"))

    @staticmethod
    def get_i18n_error_solutions(error_type: ErrorType) -> list[str]:
        """Get error solutions from i18n or built-in mapping."""
        try:
            from ..i18n import get_i18n_manager

            i18n = get_i18n_manager()
            key = f"errors.solutions.{error_type.value}"
            i18n_result = i18n.t(key)
            result: Any = i18n_result

            if isinstance(result, list) and len(result) > 0:
                return result

            raise Exception("Solutions not found or invalid format")
        except Exception:
            language = ErrorHandler.get_current_language()
            solutions_dict = ErrorHandler._ERROR_SOLUTIONS.get(error_type, {})
            return solutions_dict.get(language, solutions_dict.get("en", []))

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

        user_message = ErrorHandler.get_i18n_error_message(error_type)
        parts = [f"❌ {user_message}"]

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
        return ErrorHandler.get_i18n_error_solutions(error_type)

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

