#!/usr/bin/env python3
"""Network utilities (port detection, etc.)."""

import socket


def find_free_port(
    start_port: int = 8765, max_attempts: int = 100, preferred_port: int = 8765
) -> int:
    """Find available port, preferring the specified port."""
    if is_port_available("127.0.0.1", preferred_port):
        return preferred_port

    for i in range(max_attempts):
        port = start_port + i
        if port == preferred_port:
            continue
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue

    raise RuntimeError(
        f"No available port in range {start_port}-{start_port + max_attempts - 1}"
    )


def is_port_available(host: str, port: int) -> bool:
    """Check if port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
            return True
    except OSError:
        return False
