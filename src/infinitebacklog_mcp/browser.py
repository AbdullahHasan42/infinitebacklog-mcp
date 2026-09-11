"""Shared Playwright browser lifecycle for deterministic tools."""
from __future__ import annotations

import atexit
import asyncio
import functools
import json
import os
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from .config import IB_ORIGIN, env_bool, logger, viewport
from .security import (
    SecurityError,
    chromium_launch_args,
    clamp_wait_ms,
    filter_ib_cookies,
    ib_url_from_path,
    is_ib_origin,
)

_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_page: Optional[Page] = None
_playwright = None
_headless_mode: Optional[bool] = None
_tool_lock = asyncio.Lock()


def locked_tool(fn):
    """Serialize tool bodies and convert SecurityError into a JSON error payload."""
    from .normalize import _dumps

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        async with _tool_lock:
            try:
                return await fn(*args, **kwargs)
            except SecurityError as exc:
                return _dumps({"error": exc.code, "hint": str(exc)})

    return wrapper


async def recover_off_origin(page: Page) -> None:
    """If the page left IB, try to return, then raise."""
    if is_ib_origin(page.url):
        return
    try:
        await page.go_back(wait_until="domcontentloaded")
    except Exception:
        pass
    if is_ib_origin(page.url):
        raise SecurityError(
            "off_origin",
            "Navigation left infinitebacklog.net; returned to the previous page.",
        )
    try:
        await page.goto(f"{IB_ORIGIN}/", wait_until="domcontentloaded", timeout=60000)
    except Exception:
        pass
    if is_ib_origin(page.url):
        raise SecurityError(
            "off_origin",
            "Navigation left infinitebacklog.net; returned to the home page.",
        )
    raise SecurityError("off_origin", "Navigation left infinitebacklog.net.")


async def require_ib_page(page: Page) -> None:
    if not is_ib_origin(page.url):
        raise SecurityError(
            "off_origin",
            "Current page is not infinitebacklog.net. Call open_site first.",
        )


async def _ensure_browser(headless: bool | None = None) -> Page:
    global _browser, _context, _page, _playwright, _headless_mode
    if headless is None:
        headless = env_bool("IB_HEADLESS", True)
    if _page is not None and not _page.is_closed():
        if headless is False and _headless_mode is True:
            await _close_browser()
        else:
            return _page
    if (
        _browser is not None
        and _headless_mode is not None
        and _headless_mode != headless
    ):
        await _close_browser()
    if _playwright is None:
        _playwright = await async_playwright().start()
    if _browser is None or not _browser.is_connected():
        _browser = await _playwright.chromium.launch(
            headless=headless,
            args=chromium_launch_args(),
        )
        _headless_mode = headless
        logger.info("Playwright Chromium started headless=%s", headless)
    if _context is None:
        _context = await _browser.new_context(
            viewport=viewport(),
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        cookies_json = os.environ.get("IB_COOKIES")
        if cookies_json:
            try:
                cookies = filter_ib_cookies(json.loads(cookies_json))
                await _context.add_cookies(cookies)
            except Exception:
                logger.info(
                    "IB_COOKIES was set but could not be parsed or was rejected; "
                    "continuing without cookies"
                )
    _page = await _context.new_page()
    return _page


async def _close_browser() -> None:
    global _browser, _context, _page, _playwright, _headless_mode
    had_session = _browser is not None or _playwright is not None
    if _page and not _page.is_closed():
        await _page.close()
    if _context:
        await _context.close()
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()
    _page = _context = _browser = _playwright = None
    _headless_mode = None
    if had_session:
        logger.info("Playwright browser closed")


async def _goto_ib(page: Page, path: str, wait_ms: int = 2000) -> None:
    wait_ms = clamp_wait_ms(wait_ms)
    url = ib_url_from_path(path)
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(wait_ms)
    try:
        await page.wait_for_selector("#app", timeout=min(max(wait_ms, 2000), 12000))
    except Exception:
        pass
    await _wait_spa_text(page, timeout_ms=min(max(wait_ms, 2000), 8000))
    await recover_off_origin(page)


async def _wait_spa_text(page: Page, min_chars: int = 400, timeout_ms: int = 8000) -> None:
    """Wait until the Vue app has real content. ~281 chars is the chrome shell without h1."""
    try:
        await page.wait_for_function(
            """(min) => {
              const t = (document.body && document.body.innerText || '').trim();
              if (t.length > min) return true;
              const h1 = document.querySelector('h1');
              if (h1 && (h1.innerText || '').trim()) return true;
              if (document.querySelector('#game-search')) return true;
              return false;
            }""",
            arg=int(min_chars),
            timeout=timeout_ms,
        )
    except Exception:
        pass


def _sync_close_browser() -> None:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_close_browser())
        else:
            loop.run_until_complete(_close_browser())
    except Exception:
        pass


atexit.register(_sync_close_browser)
