"""Pure name/kind matching helpers for related content and extras."""
from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urlparse

def _kind_from_label(label: str) -> str:
    t = (label or "").upper()
    if "EDITION" in t:
        return "edition"
    if "REMAKE" in t:
        return "remake"
    if "BUNDLE" in t:
        return "bundle"
    if "PACK" in t or "ADDON" in t or "ADD-ON" in t or "ADDITIONAL" in t:
        return "pack_addon"
    if "DLC" in t or "EXPANSION" in t:
        return "dlc"
    if "MOD" in t:
        return "other"
    return "other"


def _slug_from_href(href: str) -> str:
    path = urlparse(href).path if "://" in href else href
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "games":
        return parts[1]
    return parts[-1] if parts else href


def _normalize_name(name: str, parent_title: str = "") -> str:
    s = (name or "").lower().replace("\u2019", "'")
    s = s.replace("reticle", "reticule")
    s = re.sub(r"\s+", " ", s).strip()
    prefixes = [
        "tomb raider:",
        "tomb raider -",
        "tomb raider ",
    ]
    if parent_title:
        pt = parent_title.lower().strip()
        prefixes.extend([pt + ":", pt + " -", pt + " "])
    for prefix in prefixes:
        if s.startswith(prefix):
            s = s[len(prefix) :].strip()
            break
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b(skin|pack|dlc|addon|add on|bonus content|bonus|content)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _names_match(query: str, candidate: str, parent_title: str = "") -> bool:
    q = _normalize_name(query, parent_title)
    c = _normalize_name(candidate, parent_title)
    if not q or not c:
        return False
    if q == c:
        return True
    if q in c or c in q:
        return True
    qt = set(q.split())
    ct = set(c.split())
    if not qt or not ct:
        return False
    shorter, longer = (qt, ct) if len(qt) <= len(ct) else (ct, qt)
    return shorter <= longer


def _parse_names(names: str) -> list[str]:
    raw = (names or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    if "\n" in raw:
        return [ln.strip().strip(",").strip() for ln in raw.splitlines() if ln.strip()]
    return [raw]


def _flatten_related(related: dict[str, Any]) -> list[dict[str, Any]]:
    flat = []
    for section in related.get("sections") or []:
        for item in section.get("items") or []:
            row = dict(item)
            row["section"] = section.get("label")
            row["section_kind"] = section.get("kind")
            if not row.get("kind"):
                row["kind"] = section.get("kind") or "other"
            flat.append(row)
    return flat



def _match_item(
    name: str,
    related_flat: list[dict[str, Any]],
    menus: dict[str, Any] | None,
    parent_title: str,
    prefer_kind: str | None,
) -> dict[str, Any] | None:
    pools: list[tuple[str, dict[str, Any]]] = []
    for item in related_flat:
        pools.append(("related", item))
    if menus:
        for sel in menus.get("selects") or []:
            for opt in sel.get("options") or []:
                pools.append(
                    (
                        "menu_select",
                        {
                            "title": opt.get("text"),
                            "kind": sel.get("kind") or _kind_from_label(sel.get("label") or ""),
                            "section": sel.get("label"),
                            "value": opt.get("value"),
                            "game_id": opt.get("game_id"),
                            "selected": opt.get("selected"),
                            "slug": None,
                        },
                    )
                )
        for box in menus.get("checkboxes") or []:
            pools.append(
                (
                    "menu_checkbox",
                    {
                        "title": box.get("label"),
                        "kind": box.get("kind") or "pack_addon",
                        "section": "checkbox",
                        "id": box.get("id"),
                        "game_id": box.get("game_id"),
                        "checked": box.get("checked"),
                        "slug": None,
                    },
                )
            )

    def search(kind_filter: str | None) -> dict[str, Any] | None:
        for source, item in pools:
            title = item.get("title") or item.get("slug") or ""
            if re.search(r"^add dlc to your game$", title, re.I):
                continue
            if source == "menu_select" and not item.get("value") and not item.get("slug"):
                continue
            if kind_filter:
                item_kind = item.get("kind") or item.get("section_kind")
                if item_kind != kind_filter:
                    continue
            slug = item.get("slug") or ""
            if _names_match(name, title, parent_title) or (slug and _names_match(name, slug.replace("-", " "), parent_title)):
                hit = dict(item)
                hit["_source"] = source
                return hit
        return None

    if prefer_kind:
        found = search(prefer_kind)
        if found:
            found["_matched_in"] = prefer_kind
            return found
    found = search(None)
    if found:
        found["_matched_in"] = found.get("kind") or "all"
        return found
    return None


def _game_id_from_hit(hit: dict[str, Any] | None) -> Optional[int]:
    if not hit:
        return None
    raw = hit.get("game_id")
    if raw is None:
        raw = hit.get("value")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    box_id = str(hit.get("id") or "")
    m = re.match(r"addon-(\d+)$", box_id, re.I)
    if m:
        return int(m.group(1))
    return None


def _find_addition(
    name: str,
    parent_title: str,
    additions: list[dict[str, Any]],
    game_id: Optional[int] = None,
) -> dict[str, Any] | None:
    if game_id is not None:
        for row in additions:
            if row.get("game_id") == game_id:
                return row
    for row in additions:
        game = row.get("game") if isinstance(row.get("game"), dict) else {}
        title = str(game.get("name") or "")
        slug = str(game.get("slug") or "")
        if title and _names_match(name, title, parent_title):
            return row
        if slug and _names_match(name, slug.replace("-", " "), parent_title):
            return row
    return None


def _owned_title_hit(name: str, parent_title: str, titles: list[str]) -> Optional[str]:
    for title in titles:
        if _names_match(name, title, parent_title):
            return title
    return None
