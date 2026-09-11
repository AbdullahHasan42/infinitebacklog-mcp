"""MCP tools: auth."""
from __future__ import annotations

import json

from .. import browser as browser_mod
from ..browser import _ensure_browser, locked_tool
from ..normalize import _dumps
from ..security import SecurityError, filter_ib_cookies


async def set_cookies(cookies_json: str) -> str:
    """
    Inject cookies for authenticated sessions.
    JSON array: [{"name":"...","value":"...","domain":".infinitebacklog.net","path":"/"}, ...]
    Only infinitebacklog.net cookies are accepted.
    """
    try:
        cookies = filter_ib_cookies(json.loads(cookies_json))
    except SecurityError as exc:
        return _dumps({"error": exc.code, "hint": str(exc)})
    except Exception:
        return _dumps({"error": "invalid_cookies", "hint": "Cookies must be a JSON array of objects."})
    await _ensure_browser()
    try:
        await browser_mod._context.add_cookies(cookies)
        return f"Added {len(cookies)} cookie(s)."
    except Exception:
        return _dumps({"error": "cookie_inject_failed", "hint": "Playwright rejected the cookie payload."})


def register(mcp) -> None:
    mcp.tool()(locked_tool(set_cookies))
