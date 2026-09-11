"""MCP tools: content."""
from __future__ import annotations

import json

from ..browser import _ensure_browser, _wait_spa_text, locked_tool, require_ib_page
from ..security import clamp_max_chars, clamp_max_links, resolve_screenshot_path


async def get_page_text(max_chars: int = 8000) -> str:
    """Extract visible text from the current page."""
    page = await _ensure_browser()
    await require_ib_page(page)
    await _wait_spa_text(page)
    limit = clamp_max_chars(max_chars, default=8000)
    text = " ".join((await page.inner_text("body")).split())
    if len(text) > limit:
        text = text[:limit] + "\n...[truncated]"
    return text


async def get_page_html(selector: str = "body", max_chars: int = 15000) -> str:
    """Get HTML of an element (default body)."""
    page = await _ensure_browser()
    await require_ib_page(page)
    try:
        html = await page.inner_html(selector or "body")
    except Exception as e:
        return f"Error: {e}"
    limit = clamp_max_chars(max_chars, default=15000)
    if len(html) > limit:
        html = html[:limit] + "\n...[truncated]"
    return html


async def get_links(max_links: int = 50) -> str:
    """Extract links (text + href) from the current page."""
    page = await _ensure_browser()
    await require_ib_page(page)
    limit = clamp_max_links(max_links)
    links = await page.evaluate(
        """(max) => {
            return Array.from(document.querySelectorAll('a[href]'))
                .slice(0, max)
                .map(a => ({
                    text: (a.innerText || a.textContent || '').trim().slice(0, 120),
                    href: a.href
                }))
                .filter(x => x.href);
        }""",
        limit,
    )
    return json.dumps(links, ensure_ascii=False, indent=2)


async def screenshot(path: str = "screenshot.png", full_page: bool = False) -> str:
    """Take a screenshot of the current page. Saved under the OS temp infinitebacklog-mcp directory."""
    dest = resolve_screenshot_path(path)
    page = await _ensure_browser()
    try:
        await page.wait_for_selector("#app, h1, .app-wrapper", timeout=4000)
    except Exception:
        pass
    dest.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(dest), full_page=full_page)
    return f"Screenshot saved to {dest}"


def register(mcp) -> None:
    mcp.tool()(locked_tool(get_page_text))
    mcp.tool()(locked_tool(get_page_html))
    mcp.tool()(locked_tool(get_links))
    mcp.tool()(locked_tool(screenshot))
