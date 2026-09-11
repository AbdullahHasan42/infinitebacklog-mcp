"""MCP tools: interaction."""
from __future__ import annotations

import json

from ..browser import _ensure_browser, _goto_ib, _wait_spa_text, locked_tool, recover_off_origin, require_ib_page
from ..config import GAME_SEARCH_SELECTORS, catalog_search_path, is_filter_search_box
from ..js import FILL_GAME_SEARCH_JS
from ..normalize import _dumps
from ..security import (
    SecurityError,
    clamp_wait_ms,
    credential_fill_blocked,
    destructive_click_blocked,
    eval_js_allowed,
)


async def search_games(query: str, wait_ms: int = 2500) -> str:
    """Search the Infinite Backlog games catalog and return page text.

    Fill #game-search via the Vue native value setter. Live filter is /games?q=.
    /games?search= does not filter. Never type into #platforms-search.
    """
    page = await _ensure_browser()
    q = (query or "").strip()
    wait_ms = clamp_wait_ms(wait_ms, default=2500)
    await _goto_ib(page, catalog_search_path(q), wait_ms)
    try:
        await page.wait_for_selector("#game-search", timeout=min(max(wait_ms, 2000), 12000))
    except Exception:
        pass

    filled = False
    for sel in GAME_SEARCH_SELECTORS:
        try:
            el = page.locator(sel).first
            if await el.count() == 0:
                continue
            el_id = (await el.get_attribute("id")) or ""
            placeholder = (await el.get_attribute("placeholder")) or ""
            if is_filter_search_box(el_id, placeholder):
                continue
            native = await page.evaluate(FILL_GAME_SEARCH_JS, q)
            filled = bool(native and native.get("ok") and (native.get("value") or "").strip() == q)
            if not filled:
                await el.fill(q)
                await el.press("Enter")
                filled = True
            break
        except Exception:
            continue

    if filled:
        try:
            await page.wait_for_function(
                """(wanted) => {
                  const el = document.querySelector('#game-search');
                  if (el && (el.value || '').trim() !== wanted) return false;
                  const params = new URLSearchParams(location.search);
                  const t = document.body.innerText || '';
                  return params.get('q') === wanted || /Order by:\\s*Relevance/i.test(t);
                }""",
                arg=q,
                timeout=min(max(wait_ms, 2500), 10000),
            )
        except Exception:
            await page.wait_for_timeout(wait_ms)
    else:
        await _wait_spa_text(page, timeout_ms=min(max(wait_ms, 2000), 8000))

    await recover_off_origin(page)
    text = " ".join((await page.inner_text("body")).split())
    if not filled:
        hint = " Catalog search box #game-search was not filled; results may be unfiltered."
        text = (text + hint) if text else hint.strip()
    return text[:10000] if len(text) > 10000 else text


async def click(selector: str, wait_ms: int = 1500) -> str:
    """Click by CSS selector or text=... Blocked for destructive IB actions owned by dedicated tools."""
    blocked = destructive_click_blocked(selector)
    if blocked:
        return _dumps({"error": "destructive_click_blocked", "hint": blocked})
    page = await _ensure_browser()
    await require_ib_page(page)
    wait_ms = clamp_wait_ms(wait_ms, default=1500)
    try:
        if selector.startswith("text="):
            loc = page.get_by_text(selector[5:], exact=False).first
        else:
            loc = page.locator(selector).first
        await loc.click(timeout=10000)
        await page.wait_for_timeout(wait_ms)
        await recover_off_origin(page)
        return f"Clicked: {selector}\nCurrent URL: {page.url}"
    except SecurityError:
        raise
    except Exception as e:
        return f"Click failed: {e}"


async def fill(selector: str, value: str) -> str:
    """Fill an input field. Refuses password and credential selectors."""
    blocked = credential_fill_blocked(selector)
    if blocked:
        return _dumps({"error": "credential_fill_blocked", "hint": blocked})
    page = await _ensure_browser()
    await require_ib_page(page)
    try:
        await page.locator(selector).first.fill(value)
        await recover_off_origin(page)
        return f"Filled {selector}"
    except SecurityError:
        raise
    except Exception as e:
        return f"Fill failed: {e}"


async def evaluate_js(expression: str) -> str:
    """Run JavaScript in the page and return JSON result. Disabled unless IB_ALLOW_EVAL_JS=true."""
    if not eval_js_allowed():
        return _dumps(
            {
                "error": "eval_js_disabled",
                "hint": "evaluate_js is a debug escape hatch. Set IB_ALLOW_EVAL_JS=true to enable it.",
            }
        )
    page = await _ensure_browser()
    await require_ib_page(page)
    try:
        result = await page.evaluate(expression)
        await recover_off_origin(page)
        return json.dumps(result, ensure_ascii=False, indent=2)[:12000]
    except SecurityError:
        raise
    except Exception as e:
        return f"JS error: {e}"


def register(mcp) -> None:
    mcp.tool()(locked_tool(search_games))
    mcp.tool()(locked_tool(click))
    mcp.tool()(locked_tool(fill))
    mcp.tool()(locked_tool(evaluate_js))
