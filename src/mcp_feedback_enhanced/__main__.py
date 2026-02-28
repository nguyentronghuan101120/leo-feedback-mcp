#!/usr/bin/env python3
"""
MCP Interactive Feedback Enhanced - main entry point.
Usage: python -m mcp_feedback_enhanced [server|test|version]
"""

import argparse
import asyncio
import os
import sys
import warnings


# Suppress asyncio ResourceWarning on Windows
if sys.platform == "win32":
    warnings.filterwarnings(
        "ignore", category=ResourceWarning, message=".*unclosed transport.*"
    )
    warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*")

    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        pass


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MCP Feedback Enhanced - interactive feedback MCP server"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser("server", help="Start MCP server (default)")

    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument(
        "--web", action="store_true", help="Test Web UI (runs continuously)"
    )
    test_parser.add_argument(
        "--timeout", type=int, default=60, help="Test timeout (seconds)"
    )

    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "test":
        run_tests(args)
    elif args.command == "version":
        show_version()
    elif args.command == "server" or args.command is None:
        run_server()
    else:
        parser.print_help()
        sys.exit(1)


def run_server():
    """Start MCP server."""
    from .server import main as server_main

    return server_main()


def run_tests(args):
    """Run tests."""
    os.environ["MCP_DEBUG"] = "true"

    if sys.platform == "win32":
        import warnings

        os.environ["PYTHONWARNINGS"] = (
            "ignore::ResourceWarning,ignore::DeprecationWarning"
        )
        warnings.filterwarnings("ignore", category=ResourceWarning)
        warnings.filterwarnings("ignore", message=".*unclosed transport.*")
        warnings.filterwarnings("ignore", message=".*I/O operation on closed pipe.*")
        warnings.filterwarnings("ignore", message=".*unclosed.*")
        warnings.filterwarnings("ignore", module="asyncio.*")

    if args.web:
        print("🧪 Running Web UI test...")
        success = test_web_ui_simple()
        if not success:
            sys.exit(1)
    else:
        print("❌ Test options simplified")
        print("💡 Available: --web (test Web UI)")
        print("💡 For full tests: uv run pytest")
        sys.exit(1)


def test_web_ui_simple():
    """Simple Web UI test."""
    try:
        import tempfile
        import time
        import webbrowser

        from .web.main import WebUIManager

        os.environ["MCP_TEST_MODE"] = "true"
        os.environ["MCP_WEB_HOST"] = "127.0.0.1"
        os.environ["MCP_WEB_PORT"] = "9765"

        print("🔧 Creating Web UI manager...")
        manager = WebUIManager()

        if manager.port != 9765:
            print(f"💡 Port 9765 in use, switched to {manager.port}")

        print("🔧 Creating test session...")
        with tempfile.TemporaryDirectory() as temp_dir:
            markdown_test_content = """# Web UI Test - Markdown Rendering

## Test Goal
Verify **combinedSummaryContent** Markdown display

### Syntax Support

#### Text Formatting
- **Bold** with double asterisks
- *Italic* with single asterisks
- ~~Strikethrough~~ with double tildes
- `Inline code` with backticks

#### Code Blocks
```javascript
// JavaScript example
function renderMarkdown(content) {
    return marked.parse(content);
}
```

```python
# Python example
def process_feedback(data):
    return {"status": "success", "data": data}
```

#### Lists
**Unordered:**
- Item 1
- Item 2
  - Nested 1
  - Nested 2

**Ordered:**
1. Init Markdown renderer
2. Load marked.js and DOMPurify
3. Render content

#### Links
- [MCP Feedback Enhanced](https://github.com/example/mcp-feedback-enhanced)
- [Marked.js Docs](https://marked.js.org/)

> **Note:** All HTML output is sanitized with DOMPurify.

#### Table
| Feature | Status |
|---------|--------|
| Headers | H1-H6 supported |
| Code | Syntax highlighting |
| Lists | Ordered/unordered |

### Security
- XSS protection via DOMPurify
- URL validation"""

            created_session_id = manager.create_session(temp_dir, markdown_test_content)

            if created_session_id:
                print("✅ Session created")

                print("🚀 Starting Web server...")
                manager.start_server()
                time.sleep(5)

                if (
                    manager.server_thread is not None
                    and manager.server_thread.is_alive()
                ):
                    print("✅ Web server started")
                    url = f"http://{manager.host}:{manager.port}"
                    print(f"🌐 Server at: {url}")

                    if manager.port != 9765:
                        print(
                            f"📌 Port 9765 in use, using {manager.port}"
                        )

                    print("🌐 Opening browser...")
                    try:
                        webbrowser.open(url)
                        print("✅ Browser opened")
                    except Exception as e:
                        print(f"⚠️  Cannot open browser: {e}")
                        print(f"💡 Open manually: {url}")

                    print("📝 Web UI test complete, running...")
                    print("💡 Press Ctrl+C to stop")

                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        print("\n🛑 Stopping server...")
                        return True
                else:
                    print("❌ Web server failed to start")
                    return False
            else:
                print("❌ Session creation failed")
                return False

    except Exception as e:
        print(f"❌ Web UI test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        os.environ.pop("MCP_TEST_MODE", None)
        os.environ.pop("MCP_WEB_HOST", None)
        os.environ.pop("MCP_WEB_PORT", None)


def show_version():
    """Show version."""
    from . import __author__, __version__

    print(f"Leo Feedback MCP v{__version__}")
    print(f"Author: {__author__}")


if __name__ == "__main__":
    main()
