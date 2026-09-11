"""MCP tools: navigation."""
from __future__ import annotations

from .. import browser as browser_mod
from ..browser import _close_browser, _ensure_browser, _goto_ib, locked_tool
from ..security import ib_url_from_path


async def open_site(path: str = "/", wait_ms: int = 2000, headless: bool = True) -> str:
    """Navigate to a page on infinitebacklog.net. Pass headless=false for a visible window so you can log in."""
    ib_url_from_path(path)
    page = await _ensure_browser(headless=headless)
    await _goto_ib(page, path, wait_ms)
    title = await page.title()
    return f"Opened {page.url}\nTitle: {title}\nheadless={browser_mod._headless_mode}"


async def current_url() -> str:
    """Return current URL and title."""
    page = await _ensure_browser()
    return f"URL: {page.url}\nTitle: {await page.title()}"


async def close_browser() -> str:
    """Close the shared Playwright browser used by deterministic tools."""
    await _close_browser()
    return "Browser closed."


def register(mcp) -> None:
    mcp.tool()(locked_tool(open_site))
    mcp.tool()(locked_tool(current_url))
    mcp.tool()(locked_tool(close_browser))
