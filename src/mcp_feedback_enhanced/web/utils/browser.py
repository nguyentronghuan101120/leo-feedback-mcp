#!/usr/bin/env python3
"""Browser utilities including WSL-specific handling."""

import os
import subprocess
import webbrowser
from collections.abc import Callable

from ...debug import server_debug_log as debug_log


def is_wsl_environment() -> bool:
    """Detect if running in WSL environment."""
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version") as f:
                version_info = f.read().lower()
                if "microsoft" in version_info or "wsl" in version_info:
                    return True

        wsl_env_vars = ["WSL_DISTRO_NAME", "WSL_INTEROP", "WSLENV"]
        for env_var in wsl_env_vars:
            if os.getenv(env_var):
                return True

        wsl_paths = ["/mnt/c", "/mnt/d", "/proc/sys/fs/binfmt_misc/WSLInterop"]
        for path in wsl_paths:
            if os.path.exists(path):
                return True

    except Exception:
        pass

    return False


def open_browser_in_wsl(url: str) -> None:
    """Open Windows browser from WSL environment."""
    try:
        cmd = ["cmd.exe", "/c", "start", url]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, check=False
        )

        if result.returncode == 0:
            debug_log(f"Browser launched via cmd.exe: {url}")
            return
        debug_log(
            f"cmd.exe launch failed, returncode: {result.returncode}, error: {result.stderr}"
        )

    except Exception as e:
        debug_log(f"Failed to launch browser via cmd.exe: {e}")

    try:
        cmd = ["powershell.exe", "-c", f'Start-Process "{url}"']
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, check=False
        )

        if result.returncode == 0:
            debug_log(f"Browser launched via powershell.exe: {url}")
            return
        debug_log(
            f"powershell.exe launch failed, returncode: {result.returncode}, error: {result.stderr}"
        )

    except Exception as e:
        debug_log(f"Failed to launch browser via powershell.exe: {e}")

    try:
        cmd = ["wslview", url]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, check=False
        )

        if result.returncode == 0:
            debug_log(f"Browser launched via wslview: {url}")
            return
        debug_log(
            f"wslview launch failed, returncode: {result.returncode}, error: {result.stderr}"
        )

    except Exception as e:
        debug_log(f"Failed to launch browser via wslview: {e}")

    raise Exception("Cannot launch Windows browser from WSL")


def smart_browser_open(url: str) -> None:
    """Open browser using best method for current environment."""
    if is_wsl_environment():
        debug_log("WSL detected, using WSL-specific browser launch")
        open_browser_in_wsl(url)
    else:
        debug_log("Using standard browser launch")
        webbrowser.open(url)


def get_browser_opener() -> Callable[[str], None]:
    """Return the browser opener function."""
    return smart_browser_open
