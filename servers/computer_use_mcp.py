#!/usr/bin/env python3
"""
MCP Server: Gemini Computer Use Tool Client (Playwright-based)
Provides tools for:
  - initialize_browser(url: str, width: int=1440, height: int=900)
  - execute_action(action_name: str, args: Dict[str, Any])
  - capture_state(action_name: str, result_ok: bool=True, error_msg: str="")
  - close_browser()

Notes:
- Requires Playwright and its dependencies (chromium).
- Uses FastMCP over stdio. Logs to stderr only.
"""

import os, sys, time, logging
from pathlib import Path  # needed by capture_state
from typing import Optional, Dict, Any, Tuple, List
from io import BytesIO

# ----- Logging to stderr only -----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("ComputerUseMCP")

# ---------- FastMCP ----------
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP  # type: ignore

# ---------- Playwright Dependencies ----------
try:
    from playwright.sync_api import (
        sync_playwright, Playwright, Browser, BrowserContext, Page, TimeoutError
    )
    from PIL import Image
except ImportError as e:
    log.error("Missing dependency: %s (pip install playwright pillow)", e)
    log.error("Also run: playwright install chromium")
    raise

# Global state for Playwright instance
_STATE: Dict[str, Any] = {
    "playwright": None,     # Playwright handle
    "browser": None,        # Browser handle
    "context": None,        # Context handle
    "page": None,           # Page handle
    "screen_width": 1440,
    "screen_height": 900,
}

# Supported UI Actions (matching the predefined functions from the Computer Use model)
_SUPPORTED_ACTIONS = [
    "open_web_browser", "click_at", "type_text_at",
    "scroll_to_percent", "enter_text_at", "select_option_at",
    "drag_and_drop", "press_key", "execute_javascript",
]

# --- Helper Functions ---

def denormalize_x(x: int, screen_width: int) -> int:
    """Convert normalized x coordinate (0..1000) to actual pixel coordinate."""
    return int(int(x) / 1000 * screen_width)

def denormalize_y(y: int, screen_height: int) -> int:
    """Convert normalized y coordinate (0..1000) to actual pixel coordinate."""
    return int(int(y) / 1000 * screen_height)

def get_page() -> Optional[Page]:
    """Retrieves the current Playwright page, or None if not initialized."""
    return _STATE["page"]

def _await_render(page: Page) -> None:
    """Wait for page load and a brief moment for rendering."""
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except TimeoutError:
        log.warning("Page load wait timed out.")
    time.sleep(1)  # small buffer for visual stability

# --- Core Action Handlers ---

def _execute_open_web_browser(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handles open_web_browser. Navigates the current page."""
    page = get_page()
    if page is None:
        raise RuntimeError("Browser not initialized.")
    url = args.get("url", "about:blank")
    log.info("Navigating to: %s", url)
    page.goto(url, timeout=15000)
    return {"status": f"Navigated to {page.url}"}

def _execute_click_at(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handles click_at."""
    page = get_page()
    if page is None:
        raise RuntimeError("Browser not initialized.")
    if "x" not in args or "y" not in args:
        raise ValueError("click_at requires numeric 'x' and 'y' in 0..1000")

    x = denormalize_x(args["x"], _STATE["screen_width"])
    y = denormalize_y(args["y"], _STATE["screen_height"])

    log.info("Clicking at: (%d, %d)", x, y)
    page.mouse.click(x, y)
    return {"status": f"Clicked at ({x}, {y})"}

def _execute_type_text_at(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handles type_text_at."""
    page = get_page()
    if page is None:
        raise RuntimeError("Browser not initialized.")

    for k in ("x", "y", "text"):
        if k not in args:
            raise ValueError("type_text_at requires 'x','y','text'")

    x = denormalize_x(args["x"], _STATE["screen_width"])
    y = denormalize_y(args["y"], _STATE["screen_height"])
    text = str(args["text"])
    press_enter = bool(args.get("press_enter", False))

    log.info("Typing at (%d, %d): %r (enter=%s)", x, y, text, press_enter)

    # Click to focus
    page.mouse.click(x, y)
    # Clear then type
    page.keyboard.press("Meta+A" if sys.platform == "darwin" else "Control+A")
    page.keyboard.press("Delete")
    page.keyboard.type(text)
    if press_enter:
        page.keyboard.press("Enter")

    return {"status": f"Typed text at ({x}, {y}), enter: {press_enter}"}

# ---------- MCP server ----------
mcp = FastMCP("ComputerUse MCP")

@mcp.tool()
def initialize_browser(url: str, width: int = 1440, height: int = 900) -> Dict[str, Any]:
    """
    Initializes the Playwright browser, context, and page.
    Args:
        url (str): The initial URL to navigate to.
        width (int): Screen width (recommended 1440).
        height (int): Screen height (recommended 900).
    """
    _STATE["screen_width"] = int(width)
    _STATE["screen_height"] = int(height)

    if get_page():
        log.warning("Browser already initialized. Closing and re-initializing.")
        close_browser()

    try:
        # 1) Start Playwright
        _STATE["playwright"] = sync_playwright().start()

        # 2) Launch browser — headless by default to avoid hidden dialogs
        headful_env = os.getenv("CU_HEADFUL", "")
        headless = not (headful_env.strip().lower() in ("1", "true", "yes"))
        launch_args: Dict[str, Any] = {}
        if os.getenv("CU_NO_SANDBOX", "").strip().lower() in ("1", "true", "yes"):
            launch_args["args"] = ["--no-sandbox"]

        _STATE["browser"] = _STATE["playwright"].chromium.launch(
            headless=headless, **launch_args
        )

        # 3) Create context and page with specified dimensions
        _STATE["context"] = _STATE["browser"].new_context(
            viewport={"width": _STATE["screen_width"], "height": _STATE["screen_height"]},
            device_scale_factor=1,  # consistent coordinate behavior
        )
        _STATE["page"] = _STATE["context"].new_page()

        # 4) Navigate to initial page
        _STATE["page"].goto(url, timeout=15000)
        _await_render(_STATE["page"])

        log.info("Browser initialized to %s at %dx%d", url, width, height)
        return {
            "ok": True,
            "url": _STATE["page"].url,
            "width": _STATE["screen_width"],
            "height": _STATE["screen_height"],
        }
    except Exception as e:
        log.error("Initialization failed: %s", e)
        close_browser()
        return {"ok": False, "error": f"Browser initialization failed: {e}"}

@mcp.tool()
def execute_action(action_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes a single Computer Use action from the model's FunctionCall.
    Args:
        action_name (str): The name of the function (e.g., 'click_at').
        args (Dict): Arguments for the function call (e.g., {'x': 500, 'y': 500}).
    """
    page = get_page()
    if page is None:
        return {"ok": False, "error": "Browser not initialized. Use /cu:init first."}

    log.info("Executing action: %s with args: %s", action_name, args)

    try:
        result: Dict[str, Any] = {"status": "Action completed successfully."}

        if action_name == "open_web_browser":
            result.update(_execute_open_web_browser(args))
        elif action_name == "click_at":
            result.update(_execute_click_at(args))
        elif action_name == "type_text_at":
            result.update(_execute_type_text_at(args))
        elif action_name in _SUPPORTED_ACTIONS:
            # Placeholder for unsupported but known actions
            result = {
                "status": (
                    f"Warning: Action '{action_name}' is supported by the model "
                    f"but not implemented in this MCP. Skipping."
                ),
                "unimplemented": True,
            }
        else:
            result = {
                "status": f"Error: Unknown or unsupported action: {action_name}",
                "error": True,
            }

        _await_render(page)
        return {"ok": True, "action_name": action_name, "result": result}

    except Exception as e:
        log.error("Error executing %s: %s", action_name, e)
        return {"ok": False, "action_name": action_name, "error": str(e), "result": {}}

@mcp.tool()
def capture_state(action_name: str, result_ok: bool = True, error_msg: str = "") -> Dict[str, Any]:
    """
    Captures the current screen state (screenshot) and URL after an action.
    Returns:
        A dict including the URL and the path to the saved screenshot file.
    """
    page = get_page()
    if page is None:
        return {"ok": False, "error": "Browser not initialized. Cannot capture state."}

    try:
        screenshot_bytes = page.screenshot(type="png")

        temp_dir = Path("/tmp/gemini_computer_use")
        temp_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{int(time.time() * 1000)}_{action_name}.png"
        fpath = temp_dir / fname

        with open(fpath, "wb") as f:
            f.write(screenshot_bytes)

        current_url = page.url

        response_data: Dict[str, Any] = {"url": current_url}
        if not result_ok:
            response_data["error"] = error_msg

        return {
            "ok": True,
            "path": str(fpath),
            "mime_type": "image/png",
            "url": current_url,
            "response_data": response_data,
        }

    except Exception as e:
        log.error("Error capturing state: %s", e)
        return {"ok": False, "error": f"State capture failed: {e}"}

@mcp.tool()
def close_browser() -> Dict[str, Any]:
    """Closes the Playwright browser and releases resources."""
    try:
        if _STATE["browser"]:
            _STATE["browser"].close()
        if _STATE["playwright"]:
            _STATE["playwright"].stop()
        log.info("Browser closed successfully.")
        return {"ok": True}
    except Exception as e:
        log.error("Error closing browser: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        _STATE.update({
            "playwright": None, "browser": None, "context": None, "page": None,
            "screen_width": 1440, "screen_height": 900,
        })

if __name__ == "__main__":
    try:
        # TEMPORARY selftest block (uncomment to use):
        # if os.getenv("CU_SELFTEST") == "1":
        #     print("Running selftest…", file=sys.stderr)
        #     print(initialize_browser("https://example.com", 1440, 900), file=sys.stderr)
        #     print(execute_action("open_web_browser", {"url": "https://duckduckgo.com"}), file=sys.stderr)
        #     print(execute_action("type_text_at", {"x":220, "y":110, "text":"playwright", "press_enter":True}), file=sys.stderr)
        #     print(capture_state("selftest", True, ""), file=sys.stderr)
        #     print(close_browser(), file=sys.stderr)
        #     sys.exit(0)

        log.info("✅ ComputerUse MCP ready on stdio. PID=%s", os.getpid())
        mcp.run()
    except Exception as e:
        log.exception("MCP server crashed: %s", e)
        sys.exit(1)
