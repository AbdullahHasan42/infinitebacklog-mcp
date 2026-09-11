"""Value parsers, aliases, and collection-row shaping."""
from __future__ import annotations

import json
import math
import re
from typing import Any

from .config import (
    ACQUISITION_ALIASES,
    ACQUISITION_NAMES,
    COMPLETION_ALIASES,
    COMPLETION_NAMES,
    DIGITAL_STORE_NAMES,
    PLAY_RECORD_TYPE_ALIASES,
    PLAY_RECORD_TYPES,
    RATING_SCORE_LABELS,
    STATUS_ALIASES,
    STATUS_NAMES,
    WINDOWS_PC_PLATFORM,
)

def _dumps(obj: Any, limit: int = 15000) -> str:
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    if len(text) > limit:
        return text[:limit] + "\n...[truncated]"
    return text


def _alias_key(value: str) -> str:
    return re.sub(r"[_\-]+", " ", (value or "").strip().lower())


def rating_label(score: float | int | None) -> str | None:
    if score is None:
        return None
    try:
        n = int(round(float(score)))
    except (TypeError, ValueError):
        return None
    return RATING_SCORE_LABELS.get(n)


def score_to_star_event(score: float | int) -> dict[str, Any]:
    """Map a 1-10 IB export score to vue-star-rating setRating({id, position})."""
    n = float(score)
    if n < 1:
        n = 1
    if n > 10:
        n = 10
    stars = n / 2.0
    star_id = max(1, int(math.ceil(stars - 1e-9)))
    frac = stars - (star_id - 1)
    position = int(round(frac * 100))
    if position <= 0:
        position = 100
        star_id = max(1, star_id - 1)
    if position > 100:
        position = 100
    return {"id": star_id, "position": position, "stars": stars, "score": n}


def normalize_status(value: str) -> str | None:
    if not (value or "").strip():
        return None
    raw = value.strip()
    if raw in STATUS_NAMES:
        return raw
    key = _alias_key(raw)
    return STATUS_ALIASES.get(key) or STATUS_ALIASES.get(key.replace(" ", ""))


def normalize_completion(value: str) -> str | None:
    if not (value or "").strip():
        return None
    raw = value.strip()
    if raw in COMPLETION_NAMES:
        return raw
    key = _alias_key(raw)
    compact = key.replace(" ", "")
    return COMPLETION_ALIASES.get(key) or COMPLETION_ALIASES.get(compact)


def normalize_platform_alias(value: str) -> str:
    """Map caller text like PC/Windows to IB's Windows PC label. Empty stays empty."""
    raw = (value or "").strip()
    if not raw:
        return ""
    key = _alias_key(raw).replace(" ", "")
    if key in ("pc", "windows", "windowspc", "winpc", "win"):
        return WINDOWS_PC_PLATFORM
    return raw


def parse_score(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def parse_progress_pct(value: str | float | int | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    pct = int(round(float(text)))
    return max(0, min(100, pct))


def parse_clear_fields(value: str | list | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    return [p.strip() for p in re.split(r"[,|]", text) if p.strip()]


def normalize_acquisition(value: str) -> str | None:
    if not (value or "").strip():
        return None
    raw = value.strip()
    if raw in ACQUISITION_NAMES:
        return raw
    key = _alias_key(raw)
    compact = key.replace(" ", "")
    return ACQUISITION_ALIASES.get(key) or ACQUISITION_ALIASES.get(compact)


def normalize_digital_store(value: str) -> str | None:
    if not (value or "").strip():
        return None
    raw = value.strip()
    if raw in DIGITAL_STORE_NAMES:
        return raw
    key = _alias_key(raw)
    for api_id, name in DIGITAL_STORE_NAMES.items():
        if key == _alias_key(name) or key == _alias_key(api_id):
            return api_id
        if key in _alias_key(name) or _alias_key(name) in key:
            return api_id
    return None


def normalize_play_record_type(value: str) -> str | None:
    if not (value or "").strip():
        return None
    raw = value.strip()
    if raw in PLAY_RECORD_TYPES:
        return raw
    key = _alias_key(raw)
    compact = key.replace(" ", "")
    return PLAY_RECORD_TYPE_ALIASES.get(key) or PLAY_RECORD_TYPE_ALIASES.get(compact)


def profile_scope(reason: str, detail: Any = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "error": "profile_scope",
        "reason": reason,
        "hint": "This would write the existing profile or a global category/tag library. Name the change in chat first.",
    }
    if detail is not None:
        out["detail"] = detail
    return out


def refuse_global_play_record_category(
    confirm_new: bool,
    name: str,
    url: str = "",
    heading: str = "",
) -> dict[str, Any] | None:
    text = f"{url} {heading}"
    if "/settings" in (url or ""):
        return profile_scope("settings_url", {"name": name, "url": url})
    looks_global = bool(re.search(r"user-global|profile categor|global categor", text, re.I))
    if looks_global and not confirm_new:
        return profile_scope("global_category", {"name": name, "url": url, "heading": heading})
    return None


def slim_collection_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    rating = row.get("rating") if isinstance(row.get("rating"), dict) else None
    platform = None
    plat_obj = row.get("platform")
    if isinstance(plat_obj, dict):
        platform = plat_obj.get("name") or plat_obj.get("abbreviation")
    acq = row.get("acquisition")
    store = row.get("digital_store")
    return {
        "id": row.get("id"),
        "game_id": row.get("game_id"),
        "platform_id": row.get("platform_id"),
        "platform": platform,
        "status": row.get("status"),
        "status_name": STATUS_NAMES.get(str(row.get("status") or ""), row.get("status")),
        "completion": row.get("completion"),
        "completion_name": COMPLETION_NAMES.get(str(row.get("completion") or ""), row.get("completion")),
        "ownership": row.get("ownership"),
        "physical": row.get("physical"),
        "format": "Physical" if row.get("physical") else "Digital",
        "notes": row.get("notes") or "",
        "manual_progress": row.get("manual_progress"),
        "progress": row.get("progress"),
        "edition_id": row.get("edition_id"),
        "rating": rating,
        "acquisition": acq,
        "acquisition_name": ACQUISITION_NAMES.get(str(acq or ""), acq),
        "digital_store": store,
        "digital_store_name": DIGITAL_STORE_NAMES.get(str(store or ""), store),
        "subscription": row.get("subscription"),
        "purchase_place_id": row.get("purchase_place_id"),
        "purchase_place_name": row.get("purchase_place_name"),
        "purchase_date": row.get("purchase_date"),
        "purchase_price": row.get("purchase_price"),
        "additional_cost": row.get("additional_cost"),
        "acquisition_notes": row.get("acquisition_notes"),
        "gameplay_stats_id": row.get("gameplay_stats_id"),
        "borrowed_from": row.get("borrowed_from"),
        "lent_to": row.get("lent_to"),
        "condition": row.get("condition"),
        "region": row.get("region"),
    }


def _reviews_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("reviews", "data", "results"):
            val = payload.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        if payload.get("id") and ("content" in payload or "body" in payload or "title" in payload):
            return [payload]
    return []
