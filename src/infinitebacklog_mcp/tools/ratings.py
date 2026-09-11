"""MCP tools: ratings."""
from __future__ import annotations

from typing import Any

from ..browser import _ensure_browser, locked_tool
from ..js import RESTORE_COLLECTION_STATUS_JS, SET_STAR_RATING_JS, SNAPSHOT_RATINGS_JS
from ..normalize import _dumps, parse_score, rating_label, score_to_star_event
from ..pages import _ensure_rating_card, _fetch_ib_api, _resolve_game_context

async def set_game_rating(
    slug: str,
    score: str = "",
    gameplay: str = "",
    sound: str = "",
    story: str = "",
    visual: str = "",
    playability: str = "",
    clear: bool = False,
    wait_ms: int = 3000,
) -> str:
    """Set or clear IB ratings on the collection game page (per IGDB game, not per copy). Scores are 1-10. Empty sub-fields stay unchanged. clear=true removes the rating. Requires login."""
    page = await _ensure_browser()
    ctx = await _resolve_game_context(page, slug, "", wait_ms)
    if not ctx.get("game_id"):
        return _dumps({"error": "game_not_found", "slug": ctx.get("slug")})

    current = await _fetch_ib_api(page, f"/ratings?user_id={ctx['user_id']}&game_id={ctx['game_id']}")
    existing = current.get("data") if isinstance(current.get("data"), dict) else None
    if existing and existing.get("errorResponseId"):
        existing = None

    if clear and not (existing and existing.get("id") and existing.get("score")):
        return _dumps(
            {
                "slug": ctx["slug"],
                "game_id": ctx["game_id"],
                "clear": True,
                "status": "already_empty",
                "before": existing,
            }
        )

    try:
        parsed = {
            "score": parse_score(score),
            "gameplay": parse_score(gameplay),
            "sound": parse_score(sound),
            "story": parse_score(story),
            "visual": parse_score(visual),
            "accessibility": parse_score(playability),
        }
    except ValueError as e:
        return _dumps({"error": "invalid_score", "detail": str(e)})

    if not clear and all(v is None for v in parsed.values()):
        return _dumps({"error": "no_scores", "hint": "Pass score and/or sub-ratings as 1-10, or clear=true."})
    if not clear and parsed["score"] is None and not (existing and existing.get("score")):
        return _dumps(
            {
                "error": "overall_required",
                "hint": "IB persists sub-ratings only after an overall score exists. Pass score (1-10) first.",
            }
        )

    mounted = await _ensure_rating_card(page, ctx, wait_ms)
    if mounted.get("error"):
        return _dumps(mounted)

    widgets_before = await page.evaluate(SNAPSHOT_RATINGS_JS)
    actions: list[dict[str, Any]] = []
    restore_status = mounted.get("previous_status") if mounted.get("revealed") else None

    try:
        if clear:
            result = await page.evaluate(
                SET_STAR_RATING_JS,
                {"label": "Overall Rating", "starId": 5, "position": 100, "clear": True},
            )
            actions.append(result)
            await page.wait_for_timeout(800)
            after = await _fetch_ib_api(page, f"/ratings?user_id={ctx['user_id']}&game_id={ctx['game_id']}")
            return _dumps(
                {
                    "slug": ctx["slug"],
                    "game_id": ctx["game_id"],
                    "clear": True,
                    "before": existing,
                    "widgets_before": widgets_before,
                    "actions": actions,
                    "surface": mounted.get("surface"),
                    "revealed": mounted.get("revealed"),
                    "after": after.get("data") if after.get("ok") else after,
                }
            )

        for key, label in (
            ("score", "Overall Rating"),
            ("visual", "Visual"),
            ("gameplay", "Gameplay"),
            ("story", "Story"),
            ("sound", "Audio"),
            ("accessibility", "Playability"),
        ):
            val = parsed.get(key)
            if val is None:
                continue
            event = score_to_star_event(val)
            result = await page.evaluate(
                SET_STAR_RATING_JS,
                {"label": label, "starId": event["id"], "position": event["position"], "clear": False},
            )
            result["requested_score"] = val
            result["label_text"] = rating_label(val)
            actions.append(result)
            await page.wait_for_timeout(500)

        await page.wait_for_timeout(800)
        after = await _fetch_ib_api(page, f"/ratings?user_id={ctx['user_id']}&game_id={ctx['game_id']}")
        widgets_after = await page.evaluate(SNAPSHOT_RATINGS_JS)
        return _dumps(
            {
                "slug": ctx["slug"],
                "game_id": ctx["game_id"],
                "before": existing,
                "actions": actions,
                "surface": mounted.get("surface"),
                "revealed": mounted.get("revealed"),
                "after": after.get("data") if after.get("ok") else after,
                "widgets_after": widgets_after,
            }
        )
    finally:
        if restore_status:
            await page.evaluate(RESTORE_COLLECTION_STATUS_JS, {"status": restore_status})


def register(mcp) -> None:
    mcp.tool()(locked_tool(set_game_rating))
