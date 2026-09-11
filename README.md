<p align="center">
  <img src="docs/assets/readme-header.svg" alt="Infinite Backlog MCP" width="70%">
</p>

<h1 align="center">Infinite Backlog MCP Server</h1>

Hybrid [Model Context Protocol](https://modelcontextprotocol.io/) server for [Infinite Backlog](https://infinitebacklog.net/), a free multi-platform video game collection tracker.

Infinite Backlog has no public write API, so this server drives a real Chromium session. After login it also uses read-only `GET /api/user_collections` to audit nested extras.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![MCP](https://img.shields.io/badge/protocol-MCP-555555.svg)

## Recommended login (user)

- Sign in once on Infinite Backlog in your usual browser (any browser is fine).
- Point the agent at that tab, or run headless if a session is already available.
- Leave the signed-in tab open so ratings, reviews, and collection writes reuse it.

**Agents:** prefer headless unless the user asks otherwise. For a private collection, use the tab the user pointed to, or `IB_COOKIES` / `set_cookies` only when a cookie JSON array is already in the environment. Never ask the user to harvest cookies from DevTools.

## Features

- **Deterministic [Playwright](https://github.com/microsoft/playwright) tools** for precise, low-cost reads and collection edits (no extra LLM cost).
- **Optional autonomous agent** (`run_browser_use_task`) powered by [browser-use](https://github.com/browser-use/browser-use) for multi-step or fragile goals.
- Related-content coverage for DLC, packs, add-ons, editions, remakes, bundles, and extras.
- Collection tools for ratings, reviews, extra platform copies, progress, acquisition info, and Play Records.
- User login in any browser (point the agent at the tab) or headless with an existing session.

<details>
<summary><h2>Tools</h2></summary>

### Deterministic (always available)


| Name                            | Description                                                                                                                               | Key inputs                                                                           |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `open_site`                     | Open `/`, `/games`, `/challenges`, or another IB path. Locked to `https://infinitebacklog.net`. `headless=false` opens a visible window for login; later calls reuse that session. | `path`, `wait_ms`, `headless`                                                        |
| `search_games`                  | Search the games catalog via `#game-search`. Live filter is `/games?q=`. `/games?search=` does not filter. Do not fill `#platforms-search`. | `query`, `wait_ms`                                                                   |
| `get_page_text`                 | Extract visible page text.                                                                                                                | `max_chars`                                                                          |
| `get_page_html`                 | Read HTML for a selector (default `body`).                                                                                                | `selector`, `max_chars`                                                              |
| `get_links`                     | List links on the current page.                                                                                                           | `max_links`                                                                          |
| `click`                         | Click by CSS selector or `text=...` on an IB page. Blocked for DELETE GAME, DELETE DRAFT, YES/NO, and UNLOCK CUSTOM TAGS.               | `selector`, `wait_ms`                                                                |
| `fill`                          | Fill an input. Refuses password and credential selectors.                                                                                 | `selector`, `value`                                                                  |
| `evaluate_js`                   | Debug-only page JavaScript. Disabled unless `IB_ALLOW_EVAL_JS=true`.                                                                      | `expression`                                                                         |
| `screenshot`                    | Save a PNG under the OS temp `infinitebacklog-mcp` directory (path is confined).                                                          | `path`, `full_page`                                                                  |
| `set_cookies`                   | Inject auth cookies as a JSON array. Only `infinitebacklog.net` domains are accepted.                                                     | `cookies_json`                                                                       |
| `current_url`                   | Return the current URL and title.                                                                                                         | none                                                                                 |
| `close_browser`                 | Close the shared Playwright browser.                                                                                                      | none                                                                                 |
| `list_related_content`          | Expand `ul.related-games-nav` tabs only (one tab is enough). Stay on `/games/{slug}`; do not click card labels such as EDITION.           | `game_slug`, `wait_ms`                                                               |
| `list_collection_content_menus` | Read Add DLC, owned DLC, `addon-*` boxes, and GAME EDITION text on an edit form (login required).                                         | `edit_path`, `wait_ms`                                                               |
| `add_game_content`              | Attach nested extras on the parent edit form. Searches DLC first, then every other menu before `not_found`.                               | `parent_slug`, `names`, `collection_id`                                              |
| `list_collection_game_options`  | Read copies, extra-platform control, progress, acquisition, ratings, reviews, and Play Records (no save).                                 | `slug`, `collection_id`                                                              |
| `set_game_rating`               | Set or clear 1-10 overall plus Visual / Gameplay / Story / Audio / Playability.                                                           | `slug`, `score`, sub-ratings, `clear`                                                |
| `add_game_review`               | Draft or publish at `/games/{slug}/add-review`. Publish needs 800+ characters.                                                            | `slug`, `body`, `publish`, `title`                                                   |
| `delete_game_review`            | Delete a **draft** review. Published reviews are out of scope unless named.                                                               | `slug`, `confirm`, `published`                                                       |
| `add_game_platform_copy`        | Add another GAME INFORMATION copy via `button.extra-platform`.                                                                            | `slug`, `platform`, `digital`, `submit`                                              |
| `set_game_progress`             | Set per-copy status, completion, 0-100 bar, and notes.                                                                                    | `slug`, `collection_id`, `status`, `completion`, `progress`, `notes`, `clear_fields` |
| `set_game_acquisition`          | Set or clear ACQUISITION INFO (type, source, date, amount, costs, notes, Digital Service).                                                | `slug`, `collection_id`, acquisition fields, `clear_fields`                          |
| `delete_game_copy`              | DELETE GAME for a saved copy.                                                                                                             | `collection_id` (required), `confirm=true` (required)                                |
| `list_play_records`             | Read Play Records categories on `/edit/stats`.                                                                                            | `slug`, `collection_id`                                                              |
| `set_play_record_category`      | Add a category (`keyValue` / `checkbox` / `progress` / `table`).                                                                          | `slug`, `name`, `type`, `layout`                                                     |
| `set_play_record`               | Add or update a row inside a category.                                                                                                    | `slug`, `category`, `action`, `name`, `value`                                        |
| `remove_play_record`            | Remove a row, or a whole category with `confirm=true`.                                                                                    | `slug`, `category`, `row_index`, `confirm`                                           |


If a title is missing from DLC, search PACK/ADDON, EDITIONS, extra-content checklists, and every other live related tab before reporting `not_found`. Skins are often packs, not DLC.

### Autonomous (requires `browser-use` and an LLM key)


| Name                   | Description                                                                                               | Key inputs                               |
| ---------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| `run_browser_use_task` | High-level goal on infinitebacklog.net only. The agent plans and executes with vision plus DOM. Best for multi-step or fragile flows. | `task`, `max_steps`, `model`, `headless` |


**When to use which**

- Simple read or a known selector -> deterministic tools.
- "Find all unfinished JRPGs and summarize playtime" -> `run_browser_use_task`.

</details>

## Requirements

- Python 3.11 or newer
- Playwright Chromium
- An MCP-compatible client (Cursor, Claude Desktop, VS Code, and others)
- An LLM API key only when using `run_browser_use_task`

## Installation

```bash
cd infinitebacklog-mcp
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -e .
python -m playwright install chromium
```

Optional autonomous agent:

```bash
pip install -e ".[agent]"
```

Copy `[.env.example](.env.example)` to `.env` and fill in keys as needed. Do not commit `.env`.

## Quick start

After install:

```bash
infinitebacklog-mcp
```

Or as a module:

```bash
python -m infinitebacklog_mcp.server
```

Development without installing the console script still works:

```bash
python server.py
```

The MCP server name is `infinitebacklog`. Logging goes to stderr only (required for stdio transport).

## MCP client configuration

Replace the working directory with the absolute path to this project. Treat API keys and `IB_COOKIES` as secrets.

**Installed command (Cursor / Claude Desktop style):**

```json
{
  "mcpServers": {
    "infinitebacklog": {
      "command": "infinitebacklog-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "IB_COOKIES": "[{\"name\":\"...\",\"value\":\"...\",\"domain\":\".infinitebacklog.net\",\"path\":\"/\"}]"
      }
    }
  }
}
```

**Module path (development):**

```json
{
  "mcpServers": {
    "infinitebacklog": {
      "command": "python",
      "args": ["-m", "infinitebacklog_mcp.server"],
      "cwd": "/absolute/path/to/infinitebacklog-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "IB_COOKIES": ""
      }
    }
  }
}
```

**Legacy file launch** (still supported):

```json
{
  "mcpServers": {
    "infinitebacklog": {
      "command": "python",
      "args": ["/absolute/path/to/infinitebacklog-mcp/server.py"],
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "IB_COOKIES": ""
      }
    }
  }
}
```

Public pages work without login. Private collection features use the signed-in tab in Recommended login (user), or `IB_COOKIES` / `set_cookies` when those values are already in the environment.

## Environment variables


| Variable              | Required                                   | Description                                                                             |
| --------------------- | ------------------------------------------ | --------------------------------------------------------------------------------------- |
| `OPENAI_API_KEY`      | For autonomous tool (one of the four keys) | OpenAI key for `run_browser_use_task`                                                   |
| `ANTHROPIC_API_KEY`   | Alternative                                | Anthropic key                                                                           |
| `GOOGLE_API_KEY`      | Alternative                                | Google key                                                                              |
| `BROWSER_USE_API_KEY` | Alternative                                | browser-use Cloud key                                                                   |
| `IB_COOKIES`          | Optional (agents only)                     | JSON array of cookies for a logged-in session. Do not ask a human to fill this by hand. |
| `IB_HEADLESS`         | Optional                                   | Default headless mode for tools that do not pass `headless` (`true` / `false`)          |
| `IB_VIEWPORT_WIDTH`   | Optional                                   | Playwright viewport width (default `1280`, clamped)                                     |
| `IB_VIEWPORT_HEIGHT`  | Optional                                   | Playwright viewport height (default `800`, clamped)                                     |
| `IB_ALLOW_EVAL_JS`    | Optional                                   | Enable the `evaluate_js` debug tool (`true` / `false`, default `false`)                 |
| `IB_CHROMIUM_NO_SANDBOX` | Optional                                | Pass `--no-sandbox` to Chromium (default `false`; containers only)                      |


## Collection model (live IB v1.13.6)

DLC and packs are **nested `additions` on the parent collection row**, not standalone collection games.

- `GET /api/user_collections?user_id=...&game_id=<DLC>` is empty even when that DLC is owned.
- `already_owned` is parent `additions[]` (and the edit form Owned DLC list).
- `/games/add/{dlc-slug}` SPA-redirects to `/games/{slug}`. There is no add form.
- Parent edit path: `/users/{user}/collection/{parent-slug}/edit?id={collection_id}`
- Pick extras from **Add DLC to your game**, tick **ADDONS/PACKS** labels only when unchecked, then click **UPDATE GAME** once.
- Never click **DELETE GAME**, fill Acquisition Info, or change edition / Digital-Physical / play status during `add_game_content`.
- Ratings and reviews are per IGDB game. Extra copies are extra `POST /user_collections` rows via `button.extra-platform`.
- Only `set_game_acquisition` writes Acquisition Info. Only `delete_game_copy` clicks DELETE GAME (`confirm=true`).

## Security and etiquette

- Unofficial project. Not affiliated with Infinite Backlog.
- Tool navigation, cookies, in-page API fetches, and `run_browser_use_task` are locked to `https://infinitebacklog.net`. Off-origin URLs are rejected.
- `evaluate_js` is off by default. Screenshots can only be written under the OS temp `infinitebacklog-mcp` directory. Chromium `--no-sandbox` is opt-in via `IB_CHROMIUM_NO_SANDBOX`.
- Generic `click` / `fill` cannot drive DELETE GAME, DELETE DRAFT, YES/NO confirms, UNLOCK CUSTOM TAGS, or password fields. Dedicated delete tools still require `confirm=true`.
- Be polite with request rate.
- SPA pages often need a short wait after navigation. About 281 characters with no `h1` is the Vue chrome. Wait for `h1`, `#game-search`, or more text. On an edit form, wait until **UPDATE GAME** is visible.
- Catalog search is `#game-search` (placeholder "Search for a game") with the Vue native value setter. `#platforms-search` is a sidebar filter. Live filter is `/games?q=`. `/games?search=` does not filter.
- Duplicate titles use IGDB-style slugs (Hades 1995 is `hades`, Hades 2020 is `hades--1`).
- `list_related_content` clicks only `ul.related-games-nav` tabs (href is often empty). A page-wide EDITION/DLC label is a card link to another game.
- Collection rows use `/users/{user}/collection/{slug}?id={collection_id}`. **WRITE A REVIEW** on the edit form goes to `/games/{slug}/add-review`. **DELETE DRAFT** confirm is **YES**.
- Nested extras are add-only in this pass. Do not auto-untick owned DLC.
- Do not click **UNLOCK CUSTOM TAGS**, Play Records **SETTINGS**, or edit `/settings` / profile widgets. Return `profile_scope`.
- `delete_game_review` only deletes a draft (`confirm=true`). Published reviews are `profile_scope` unless you name them.
- Prefer headed `open_site` so the user logs into Infinite Backlog in the MCP-controlled Chromium window. Cookie injection is an agent-only fallback. A logged-in Brave tab with CDP is a separate attach path and is not launched by this server.
- Concurrent tool calls share one browser and are serialized with a lock.

## Development

Project layout:

```text
infinitebacklog-mcp/
├── src/infinitebacklog_mcp/
│   ├── server.py          # MCPServer, instructions, main()
│   ├── browser.py         # Playwright lifecycle
│   ├── config.py          # constants and env
│   ├── security.py        # origin, cookie, path, and identifier allowlists
│   ├── matching.py        # name / kind matching
│   ├── tools/             # deterministic + agent tools
│   └── ...
├── tests/
├── docs/assets/           # README logos
└── server.py              # compatibility shim
```

Inspector:

```bash
npx @modelcontextprotocol/inspector python -m infinitebacklog_mcp.server
# after install:
npx @modelcontextprotocol/inspector infinitebacklog-mcp
```

Tests:

```bash
python -m unittest discover -s tests -v
```

## License

MIT. See [LICENSE](LICENSE).