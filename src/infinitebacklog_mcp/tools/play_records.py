"""MCP tools: play_records."""
from __future__ import annotations

import re

from ..browser import _ensure_browser, locked_tool
from ..config import PLAY_RECORD_TYPES
from ..js import (
    CLICK_EXACT_BUTTON_JS,
    FILL_CATEGORY_MODAL_JS,
    PLAY_RECORD_MUTATE_JS,
    SNAPSHOT_PLAY_RECORDS_JS,
)
from ..normalize import (
    _dumps,
    normalize_play_record_type,
    profile_scope,
    refuse_global_play_record_category,
)
from ..pages import _click_exact_button, _open_play_records, _resolve_game_context

async def list_play_records(slug: str, collection_id: str = "", wait_ms: int = 3000) -> str:
    """Read-only dump of Play Records categories and Add new category options. Does not save. Requires login. Play Records tab is hidden when status is No Status."""
    page = await _ensure_browser()
    ctx = await _resolve_game_context(page, slug, collection_id, wait_ms)
    if not ctx.get("game_id"):
        return _dumps({"error": "game_not_found", "slug": ctx.get("slug")})
    if not ctx.get("rows"):
        return _dumps({"error": "no_collection_row", "slug": ctx.get("slug")})
    cid = str((ctx.get("row") or {}).get("id") or collection_id or "")
    opened = await _open_play_records(page, ctx["username"], ctx["slug"], cid, wait_ms)
    if opened.get("error"):
        return _dumps(opened)
    snap = await page.evaluate(SNAPSHOT_PLAY_RECORDS_JS)
    return _dumps(
        {
            "slug": ctx["slug"],
            "collection_id": cid,
            "gameplay_stats_id": (ctx.get("row") or {}).get("gameplay_stats_id"),
            "records": snap,
            "category_options": {
                "types": list(PLAY_RECORD_TYPES),
                "layout_columns": [1, 2],
                "template": "FIND TEMPLATE uses this game Steam/PSN/Xbox lists",
            },
        }
    )

async def set_play_record_category(
    slug: str,
    name: str,
    type: str = "keyValue",
    layout: str = "1",
    template: str = "",
    category_id: str = "",
    confirm_new: bool = False,
    collection_id: str = "",
    wait_ms: int = 3000,
) -> str:
    """Add or edit a Play Records category on this game (not the user profile). Types: keyValue, checkbox, progress, table. If the UI would write a global category library, returns profile_scope unless confirm_new=true and you named that category in chat."""
    if not (name or "").strip() and not category_id:
        return _dumps({"error": "name_required"})
    type_id = normalize_play_record_type(type) if type else "keyValue"
    if type and type_id is None:
        return _dumps({"error": "unknown_type", "type": type, "allowed": PLAY_RECORD_TYPES})
    page = await _ensure_browser()
    ctx = await _resolve_game_context(page, slug, collection_id, wait_ms)
    if not ctx.get("rows"):
        return _dumps({"error": "no_collection_row", "slug": ctx.get("slug")})
    cid = str((ctx.get("row") or {}).get("id") or collection_id or "")
    opened = await _open_play_records(page, ctx["username"], ctx["slug"], cid, wait_ms)
    if opened.get("error"):
        return _dumps(opened)
    before = await page.evaluate(SNAPSHOT_PLAY_RECORDS_JS)
    existing_names = [c.get("name") for c in (before.get("categories") or [])]
    if not category_id and name in existing_names:
        return _dumps({"status": "already_exists", "name": name, "records": before})
    if "/settings" in page.url:
        return _dumps(profile_scope("settings_url", page.url))
    click = await _click_exact_button(page, "ADD CATEGORY")
    await page.wait_for_timeout(800)
    heading = await page.evaluate(
        """() => {
          const h = [...document.querySelectorAll('h1,h2,h3,h4')].find(e => /ADD NEW CATEGORY|EDIT CATEGORY/i.test(e.innerText || ''));
          return h ? (h.innerText || '').trim() : '';
        }"""
    )
    blocked = refuse_global_play_record_category(confirm_new, name, page.url, str(heading or ""))
    if blocked:
        await _click_exact_button(page, "CANCEL")
        return _dumps(blocked)
    if (template or "").strip():
        await _click_exact_button(page, "FIND TEMPLATE")
        await page.wait_for_timeout(800)
        return _dumps(
            {
                "slug": ctx["slug"],
                "status": "template_picker_opened",
                "hint": "FIND TEMPLATE lists this game's Steam/PSN/Xbox sets. Not submitted. Pass without template to add a blank category.",
                "confirm_new": confirm_new,
            }
        )
    fill = await page.evaluate(
        FILL_CATEGORY_MODAL_JS,
        {"name": name, "typeId": type_id, "columns": layout or "1", "submit": False},
    )
    submit = {"clicked": False}
    try:
        await page.locator("button").filter(has_text=re.compile(r"^ADD CATEGORY$")).last.click(timeout=8000)
        submit = {"clicked": True, "text": "ADD CATEGORY"}
    except Exception:
        submit = await page.evaluate(CLICK_EXACT_BUTTON_JS, {"exact": "ADD CATEGORY", "forbid": ""})
    await page.wait_for_timeout(2000)
    after = await page.evaluate(SNAPSHOT_PLAY_RECORDS_JS)
    return _dumps(
        {
            "slug": ctx["slug"],
            "collection_id": cid,
            "click": click,
            "fill": fill,
            "submit": submit,
            "before": before,
            "after": after,
            "confirm_new": confirm_new,
        }
    )


async def set_play_record(
    slug: str,
    category: str,
    action: str = "add",
    name: str = "",
    value: str = "",
    row_index: str = "",
    collection_id: str = "",
    wait_ms: int = 3000,
) -> str:
    """Add or update a Play Records row in a category on this game. action is add or update. keyValue uses name+value; checkbox uses name; progress uses name+value as progress_earned."""
    act = (action or "add").strip().lower()
    if act not in ("add", "update"):
        return _dumps({"error": "unknown_action", "action": action, "allowed": ["add", "update"]})
    page = await _ensure_browser()
    ctx = await _resolve_game_context(page, slug, collection_id, wait_ms)
    if not ctx.get("rows"):
        return _dumps({"error": "no_collection_row", "slug": ctx.get("slug")})
    cid = str((ctx.get("row") or {}).get("id") or collection_id or "")
    opened = await _open_play_records(page, ctx["username"], ctx["slug"], cid, wait_ms)
    if opened.get("error"):
        return _dumps(opened)
    row: dict[str, Any] = {}
    if name != "":
        row["name"] = name
    if value != "":
        row["value"] = value
        try:
            row["progress_earned"] = float(value)
        except ValueError:
            pass
    mutate = await page.evaluate(
        PLAY_RECORD_MUTATE_JS,
        {
            "action": "add_row" if act == "add" else "update_row",
            "categoryName": category,
            "categoryId": "",
            "rowIndex": row_index or "0",
            "row": row,
            "confirmDelete": False,
        },
    )
    await page.wait_for_timeout(800)
    after = await page.evaluate(SNAPSHOT_PLAY_RECORDS_JS)
    return _dumps({"slug": ctx["slug"], "mutate": mutate, "after": after})

async def remove_play_record(
    slug: str,
    category: str,
    row_index: str = "",
    confirm: bool = False,
    collection_id: str = "",
    wait_ms: int = 3000,
) -> str:
    """Remove a Play Records row, or an entire category if row_index is empty. confirm=true required for category delete. Never DELETE GAME."""
    if row_index == "" and not confirm:
        return _dumps(
            {
                "error": "confirm_required",
                "hint": "Pass confirm=true to delete a whole Play Records category.",
            }
        )
    page = await _ensure_browser()
    ctx = await _resolve_game_context(page, slug, collection_id, wait_ms)
    if not ctx.get("rows"):
        return _dumps({"error": "no_collection_row", "slug": ctx.get("slug")})
    cid = str((ctx.get("row") or {}).get("id") or collection_id or "")
    opened = await _open_play_records(page, ctx["username"], ctx["slug"], cid, wait_ms)
    if opened.get("error"):
        return _dumps(opened)
    if row_index == "":
        mutate = await page.evaluate(
            PLAY_RECORD_MUTATE_JS,
            {
                "action": "delete_category",
                "categoryName": category,
                "categoryId": "",
                "rowIndex": "",
                "row": None,
                "confirmDelete": True,
            },
        )
    else:
        mutate = await page.evaluate(
            PLAY_RECORD_MUTATE_JS,
            {
                "action": "remove_row",
                "categoryName": category,
                "categoryId": "",
                "rowIndex": row_index,
                "row": None,
                "confirmDelete": False,
            },
        )
    await page.wait_for_timeout(1500)
    after = await page.evaluate(SNAPSHOT_PLAY_RECORDS_JS)
    return _dumps({"slug": ctx["slug"], "mutate": mutate, "after": after})


def register(mcp) -> None:
    mcp.tool()(locked_tool(list_play_records))
    mcp.tool()(locked_tool(set_play_record_category))
    mcp.tool()(locked_tool(set_play_record))
    mcp.tool()(locked_tool(remove_play_record))
