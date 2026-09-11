"""Infinite Backlog Hybrid MCP Server entry point."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .config import logger
from .tools import register_all

mcp = MCPServer(
    name="infinitebacklog",
    version="1.0.1",
    instructions=(
        "Hybrid browser automation for Infinite Backlog (https://infinitebacklog.net/). "
        "Use the fast deterministic tools (open_site, click, fill, get_page_text, search_games) "
        "for precise, cheap operations. "
        "search_games must fill #game-search (placeholder Search for a game) with the Vue "
        "native value setter. Do not fill #platforms-search or other filter boxes. "
        "The live catalog filter is /games?q=; /games?search= does not filter. "
        "The SPA shell is about 281 characters with no h1; wait for h1, #game-search, or more text. "
        "Duplicate titles use IGDB-style slugs (Hades 1995 is hades, Hades 2020 is hades--1). "
        "list_related_content clicks only ul.related-games-nav tabs (href is often empty) "
        "and must stay on /games/{slug}; card labels such as EDITION are links to other games. "
        "Collection rows use /users/{user}/collection/{slug}?id={collection_id}. "
        "WRITE A REVIEW on the edit form goes to /games/{slug}/add-review. "
        "DELETE DRAFT confirm is YES on the DELETE REVIEW dialog. "
        "To list or add DLC, expansions, packs, add-ons, extra content, or other related items, "
        "use list_related_content, list_collection_content_menus, and add_game_content. "
        "Always search every related-content tab and every extras dropdown on the collection "
        "edit form before reporting not_found. A skin or pack often lives under PACK/ADDON, "
        "not DLC. An edition extra lives under EDITIONS; never switch the parent edition. "
        "DLC and packs attach as nested additions on the parent collection row. Use the "
        "parent edit form: the Add DLC to your game dropdown, then addon-* checkboxes "
        "(click the label, and only if unchecked), then one UPDATE GAME. "
        "Do not use /games/add/{slug} for DLC or packs; the SPA redirects to the extra's "
        "game page and there is no add form. already_owned is parent additions[], not a "
        "standalone user_collections row for the DLC game_id. "
        "Never change parent platform, Digital/Physical, play status, or Acquisition Info "
        "unless the caller used set_game_progress, add_game_platform_copy, or "
        "set_game_acquisition for those fields. "
        "Ratings and reviews are per IGDB game, not per platform copy. Extra platform copies "
        "are extra user_collections rows via button.extra-platform, not nested additions. "
        "IB hides .collection-rating while Unplayed or No Status; set_game_rating locally "
        "sets Playing on the edit form (no UPDATE GAME) then restores status. "
        "Progress (status, completion, bar, notes) is per copy on the collection edit form. "
        "Acquisition Info is per copy via set_game_acquisition (Acquisition, Source, Date, "
        "Amount, Additional Costs, Notes, Digital Service). "
        "Play Records live at /collection/{slug}/edit/stats (li.stats-link). Categories are "
        "per-game (keyValue, checkbox, progress, table), not a profile library. "
        "Use list_collection_game_options, set_game_rating, add_game_review, "
        "delete_game_review, add_game_platform_copy, set_game_progress, set_game_acquisition, "
        "delete_game_copy, list_play_records, set_play_record_category, set_play_record, "
        "and remove_play_record for those flows. "
        "If a control would write the user profile, settings, widgets, UNLOCK CUSTOM TAGS, "
        "or a global tag/category library, return profile_scope and stop. "
        "Use run_browser_use_task only for complex goals that need an autonomous agent "
        "(requires browser-use + an LLM API key). The agent stays on infinitebacklog.net. "
        "open_site, cookies, and screenshots are origin/path locked. evaluate_js is off "
        "unless IB_ALLOW_EVAL_JS=true. Generic click/fill cannot DELETE GAME, DELETE DRAFT, "
        "YES/NO confirm dialogs, or UNLOCK CUSTOM TAGS. "
        "Public pages work without login. For private collection features, the preferred "
        "path is headed open_site(..., headless=false) so the human can log into Infinite "
        "Backlog in the MCP-controlled Chromium window, then later calls reuse that tab. "
        "Do not ask the user to copy, export, or paste session cookies. IB_COOKIES and "
        "set_cookies are agent-only when a cookie JSON array is already in the environment. "
        "Only delete_game_copy clicks DELETE GAME, and only with confirm=true. "
        "Never fill Acquisition Info except via set_game_acquisition."
    ),
)

register_all(mcp)


def main() -> None:
    logger.info("Starting Infinite Backlog MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
