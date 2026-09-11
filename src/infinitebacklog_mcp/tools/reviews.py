"""MCP tools: reviews."""
from __future__ import annotations

from ..browser import _ensure_browser, _goto_ib, locked_tool
from ..config import REVIEW_MIN_PUBLISH_CHARS
from ..js import CALL_REVIEW_SAVE_JS, CLICK_EXACT_BUTTON_JS, CLICK_NAMED_BUTTON_JS, FILL_REVIEW_FORM_JS
from ..normalize import _dumps, _reviews_list, profile_scope
from ..pages import _fetch_ib_api, _resolve_game_context, _wait_review_form
from ..security import sanitize_path_segment

async def add_game_review(
    slug: str,
    body: str,
    spoilers: bool = False,
    publish: bool = True,
    title: str = "",
    mature: bool = False,
    language: str = "",
    platform: str = "",
    feed: bool = False,
    wait_ms: int = 3000,
) -> str:
    """Add or update a review at /games/{slug}/add-review. Body required. Publish needs 800+ characters; use publish=false for Save draft. If a review already exists, opens the existing editor. Never clicks DELETE. Requires login."""
    if not (body or "").strip():
        return _dumps({"error": "empty_body"})
    if publish and len(body.strip()) < REVIEW_MIN_PUBLISH_CHARS:
        return _dumps(
            {
                "error": "too_short_to_publish",
                "length": len(body.strip()),
                "min": REVIEW_MIN_PUBLISH_CHARS,
                "hint": "Pass publish=false to save a draft, or write at least 800 characters.",
            }
        )

    page = await _ensure_browser()
    ctx = await _resolve_game_context(page, slug, "", wait_ms)
    if not ctx.get("game_id"):
        return _dumps({"error": "game_not_found", "slug": ctx.get("slug")})

    published = await _fetch_ib_api(
        page,
        f"/reviews?user_id={ctx['user_id']}&game_id={ctx['game_id']}&published=true",
    )
    drafts = await _fetch_ib_api(
        page,
        f"/reviews?user_id={ctx['user_id']}&game_id={ctx['game_id']}&published=false",
    )
    existing = _reviews_list(published.get("data")) + _reviews_list(drafts.get("data") if drafts.get("ok") else None)
    review_path = f"/games/{ctx['slug']}/add-review"
    if existing:
        slug_or_id = existing[0].get("slug") or ctx["slug"]
        review_path = f"/users/{ctx['username']}/reviews/{sanitize_path_segment(str(slug_or_id), name='review slug')}"

    await _goto_ib(page, review_path, wait_ms)
    if not await _wait_review_form(page, wait_ms):
        await _goto_ib(page, f"/games/{ctx['slug']}/add-review", wait_ms)
        if not await _wait_review_form(page, wait_ms):
            return _dumps({"error": "review_form_not_ready", "url": page.url})

    fill = await page.evaluate(
        FILL_REVIEW_FORM_JS,
        {
            "body": body,
            "title": title,
            "spoilers": spoilers,
            "mature": mature,
            "feed": feed,
            "language": language,
            "platform": platform,
            "completion": None,
        },
    )
    click = await page.evaluate(CALL_REVIEW_SAVE_JS, {"publish": publish})
    if not click.get("clicked"):
        names = ["PUBLISH"] if publish else ["SAVE DRAFT"]
        click = await page.evaluate(CLICK_NAMED_BUTTON_JS, {"names": names, "forbid": "DELETE"})
    await page.wait_for_timeout(2000)
    after = await _fetch_ib_api(
        page,
        f"/reviews?user_id={ctx['user_id']}&game_id={ctx['game_id']}&published={'true' if publish else 'false'}",
    )
    return _dumps(
        {
            "slug": ctx["slug"],
            "game_id": ctx["game_id"],
            "url": page.url,
            "existing_before": existing,
            "fill": fill,
            "click": click,
            "publish": publish,
            "after": after.get("data") if after.get("ok") else after,
        }
    )

async def delete_game_review(
    slug: str,
    confirm: bool = False,
    published: bool = False,
    wait_ms: int = 3000,
) -> str:
    """Delete a review. Drafts only unless published=true AND you named that review. confirm=true required. Never DELETE GAME."""
    if not confirm:
        return _dumps({"error": "confirm_required", "hint": "Pass confirm=true to delete a draft review."})
    if published:
        return _dumps(
            profile_scope(
                "published_review",
                "Pass published=true only after naming the published review in chat. Default is draft-only.",
            )
        )
    page = await _ensure_browser()
    ctx = await _resolve_game_context(page, slug, "", wait_ms)
    if not ctx.get("game_id"):
        return _dumps({"error": "game_not_found", "slug": ctx.get("slug")})
    await _goto_ib(page, f"/users/{ctx['username']}/reviews/{ctx['slug']}", wait_ms)
    body = " ".join((await page.inner_text("body")).split())[:800]
    if "DELETE DRAFT" not in body and "This review is a draft" not in body:
        return _dumps(
            {
                "error": "not_a_draft",
                "url": page.url,
                "hint": "No DELETE DRAFT on this page. Will not delete a published review unless you name it.",
            }
        )
    click = await page.evaluate(CLICK_EXACT_BUTTON_JS, {"exact": "DELETE DRAFT", "forbid": "DELETE GAME"})
    await page.wait_for_timeout(800)
    confirm_click = await page.evaluate(
        CLICK_NAMED_BUTTON_JS,
        {"names": ["YES", "CONFIRM", "DELETE", "DELETE DRAFT"], "forbid": "GAME"},
    )
    await page.wait_for_timeout(2000)
    return _dumps({"slug": ctx["slug"], "click": click, "confirm": confirm_click, "url": page.url})


def register(mcp) -> None:
    mcp.tool()(locked_tool(add_game_review))
    mcp.tool()(locked_tool(delete_game_review))
