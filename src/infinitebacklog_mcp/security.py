"""Allowlists and sanitizers for Infinite Backlog MCP tool arguments."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from posixpath import normpath
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

from .config import IB_ORIGIN, env_bool

IB_HOSTS = frozenset({"infinitebacklog.net", "www.infinitebacklog.net"})
SLUG_RE = re.compile(r"^[a-zA-Z0-9]+(?:-{1,2}[a-zA-Z0-9]+)*$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
COLLECTION_ID_RE = re.compile(r"^\d+$")
SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
EDIT_PATH_RE = re.compile(
    r"^/users/(?P<user>[A-Za-z0-9._-]+)/collection/"
    r"(?P<slug>[a-zA-Z0-9]+(?:-{1,2}[a-zA-Z0-9]+)*)/edit/?$"
)
URL_IN_TEXT_RE = re.compile(r"(?i)\b(?:https?|file|javascript|data|vbscript):[^\s<>\"']+")
MAX_WAIT_MS = 30000
MAX_CHARS = 50000
MAX_LINKS = 200
MAX_STEPS = 25

DESTRUCTIVE_CLICK_HINT = (
    "Use the dedicated collection/review tools with confirm=true instead of "
    "clicking DELETE GAME, DELETE DRAFT, YES/NO, or UNLOCK CUSTOM TAGS."
)
PASSWORD_FILL_HINT = "Refusing to fill password or credential fields."


class SecurityError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _host_ok(hostname: str | None) -> bool:
    host = (hostname or "").lower().rstrip(".")
    return host in IB_HOSTS


def is_ib_origin(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    if parsed.scheme.lower() != "https":
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if parsed.port not in (None, 443):
        return False
    return _host_ok(parsed.hostname)


def ib_url_from_path(path: str) -> str:
    """Resolve a tool path to an https://infinitebacklog.net URL. Never pass through caller URLs."""
    raw = (path or "").strip() or "/"
    lowered = raw.lower()
    if lowered.startswith(("javascript:", "file:", "data:", "vbscript:", "about:")):
        raise SecurityError("off_origin", "Refusing non-https navigation.")
    if lowered.startswith("http://") or lowered.startswith("https://"):
        if not is_ib_origin(raw):
            raise SecurityError("off_origin", "Refusing navigation off infinitebacklog.net.")
        parsed = urlparse(raw)
        rel = parsed.path or "/"
        if parsed.query:
            rel += "?" + parsed.query
        raw = rel
    elif raw.startswith("//") or "://" in raw:
        raise SecurityError("off_origin", "Refusing navigation off infinitebacklog.net.")
    if "\\" in raw or "\x00" in raw:
        raise SecurityError("invalid_path", "Invalid navigation path.")
    if not raw.startswith("/"):
        raw = "/" + raw
    parsed = urlparse(IB_ORIGIN + raw)
    rebuilt = urlunparse(("https", "infinitebacklog.net", parsed.path or "/", "", parsed.query, ""))
    if not is_ib_origin(rebuilt):
        raise SecurityError("off_origin", "Refusing navigation off infinitebacklog.net.")
    return rebuilt


def sanitize_slug(slug: str) -> str:
    s = (slug or "").strip().strip("/")
    if s.lower().startswith("http://") or s.lower().startswith("https://"):
        if not is_ib_origin(s):
            raise SecurityError("off_origin", "Refusing a non-IB slug URL.")
        s = urlparse(s).path.strip("/")
    if s.startswith("games/"):
        s = s.split("/", 1)[1]
    if not s or "/" in s or "\\" in s or ".." in s:
        raise SecurityError("invalid_slug", "Invalid game slug.")
    if not SLUG_RE.fullmatch(s):
        raise SecurityError("invalid_slug", "Invalid game slug.")
    return s


def sanitize_username(username: str, *, allow_empty: bool = False) -> str:
    u = (username or "").strip()
    if not u:
        if allow_empty:
            return ""
        raise SecurityError("invalid_username", "Invalid username.")
    if not USERNAME_RE.fullmatch(u):
        raise SecurityError("invalid_username", "Invalid username.")
    return u


def sanitize_collection_id(cid: str, *, allow_empty: bool = True) -> str:
    s = str(cid or "").strip()
    if not s:
        if allow_empty:
            return ""
        raise SecurityError("collection_id_required", "collection_id is required.")
    if not COLLECTION_ID_RE.fullmatch(s):
        raise SecurityError("invalid_collection_id", "collection_id must be digits.")
    return s


def sanitize_path_segment(value: str, *, name: str = "segment") -> str:
    s = (value or "").strip().strip("/")
    if not s or "/" in s or "\\" in s or ".." in s or not SEGMENT_RE.fullmatch(s):
        raise SecurityError("invalid_path", f"Invalid {name}.")
    return s


def parse_collection_edit_path(edit_path: str) -> str:
    """Return an IB-relative /users/{user}/collection/{slug}/edit path (optional ?id=digits)."""
    raw = (edit_path or "").strip()
    if not raw:
        raise SecurityError("invalid_edit_path", "edit_path must be /users/{user}/collection/{slug}/edit")
    lowered = raw.lower()
    query = ""
    if lowered.startswith("http://") or lowered.startswith("https://"):
        if not is_ib_origin(raw):
            raise SecurityError("off_origin", "Refusing navigation off infinitebacklog.net.")
        parsed = urlparse(raw)
        rel = parsed.path or "/"
        query = parsed.query or ""
    else:
        if raw.startswith("//") or "://" in raw:
            raise SecurityError("off_origin", "Refusing navigation off infinitebacklog.net.")
        rel = raw if raw.startswith("/") else "/" + raw
        if "?" in rel:
            rel, query = rel.split("?", 1)
    rel = rel.rstrip("/") or "/"
    match = EDIT_PATH_RE.match(rel)
    if not match:
        raise SecurityError(
            "invalid_edit_path",
            "edit_path must be /users/{user}/collection/{slug}/edit",
        )
    out = f"/users/{match.group('user')}/collection/{match.group('slug')}/edit"
    if query:
        qs = parse_qs(query, keep_blank_values=False)
        extra = set(qs) - {"id"}
        if extra:
            raise SecurityError("invalid_edit_path", "Only the id query parameter is allowed.")
        if "id" in qs:
            cid = sanitize_collection_id(qs["id"][0], allow_empty=False)
            out += f"?id={cid}"
    return out


def _cookie_host_ok(hostname: str | None) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    if host.startswith("."):
        host = host[1:]
    if not host:
        return False
    return host == "infinitebacklog.net" or host.endswith(".infinitebacklog.net")


def filter_ib_cookies(cookies: Any) -> list[dict[str, Any]]:
    """Fail closed unless every cookie is scoped to infinitebacklog.net."""
    if not isinstance(cookies, list):
        raise SecurityError("invalid_cookies", "Cookies must be a JSON array.")
    cleaned: list[dict[str, Any]] = []
    for item in cookies:
        if not isinstance(item, dict):
            raise SecurityError("invalid_cookies", "Each cookie must be an object.")
        url = item.get("url")
        domain = item.get("domain")
        if url is not None and str(url).strip():
            parsed = urlparse(str(url).strip())
            if not _cookie_host_ok(parsed.hostname):
                raise SecurityError("cookie_domain", "Cookie url must be on infinitebacklog.net.")
        if domain is not None and str(domain).strip():
            if not _cookie_host_ok(str(domain)):
                raise SecurityError("cookie_domain", "Cookie domain must be infinitebacklog.net.")
        elif not (url and str(url).strip()):
            raise SecurityError("cookie_domain", "Cookie must include an IB domain or url.")
        entry = dict(item)
        if url and str(url).strip():
            parsed = urlparse(str(url).strip())
            host = (parsed.hostname or "").lower().rstrip(".")
            entry["url"] = urlunparse(("https", host, parsed.path or "/", "", "", ""))
        cleaned.append(entry)
    return cleaned


def screenshot_dir() -> Path:
    root = Path(tempfile.gettempdir()).resolve() / "infinitebacklog-mcp"
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_screenshot_path(user_path: str = "") -> Path:
    root = screenshot_dir()
    name = Path(user_path or "screenshot.png").name
    if not name or name in {".", ".."}:
        name = "screenshot.png"
    if not name.lower().endswith(".png"):
        name = f"{name}.png"
    dest = (root / name).resolve()
    try:
        dest.relative_to(root)
    except ValueError as exc:
        raise SecurityError("invalid_screenshot_path", "Screenshot path must stay in the temp dir.") from exc
    return dest


def clamp_wait_ms(value: Any, default: int = 2000) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, min(parsed, MAX_WAIT_MS))


def clamp_max_chars(value: Any, default: int = 8000, cap: int = MAX_CHARS) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, cap))


def clamp_max_links(value: Any, default: int = 50, cap: int = MAX_LINKS) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, cap))


def clamp_max_steps(value: Any, default: int = 25, cap: int = MAX_STEPS) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, cap))


def eval_js_allowed() -> bool:
    return env_bool("IB_ALLOW_EVAL_JS", False)


def destructive_click_blocked(selector: str) -> str | None:
    raw = (selector or "").strip()
    if not raw:
        return "Selector is required."
    text = raw[5:] if raw.lower().startswith("text=") else raw
    compact = re.sub(r"\s+", " ", text).strip()
    if re.fullmatch(r"yes|no", compact, re.I):
        return DESTRUCTIVE_CLICK_HINT
    blob = f"{raw} {compact}"
    if re.search(r"delete\s*game|delete\s*draft|unlock\s*custom\s*tags", blob, re.I):
        return DESTRUCTIVE_CLICK_HINT
    return None


def credential_fill_blocked(selector: str) -> str | None:
    raw = (selector or "").strip().lower()
    if not raw:
        return "Selector is required."
    if "password" in raw or "passwd" in raw or "type=password" in raw:
        return PASSWORD_FILL_HINT
    if re.search(r"cookie|csrf|api[_-]?key|secret|token", raw):
        return PASSWORD_FILL_HINT
    return None


def api_fetch_path(path: str) -> str:
    raw = (path or "").strip()
    if not raw:
        raise SecurityError("invalid_api_path", "API path is required.")
    lowered = raw.lower()
    if lowered.startswith("http") or raw.startswith("//") or "://" in raw or "\\" in raw or "\x00" in raw:
        raise SecurityError("invalid_api_path", "API path must be a same-origin /api path.")
    if raw.startswith("/api/") or raw == "/api":
        rel = raw
    elif raw.startswith("/"):
        rel = "/api" + raw
    else:
        rel = "/api/" + raw
    parsed = urlparse(rel)
    normalized = normpath(parsed.path)
    if normalized != "/" and not normalized.startswith("/api"):
        raise SecurityError("invalid_api_path", "API path must stay under /api.")
    if normalized == "/":
        raise SecurityError("invalid_api_path", "API path must stay under /api.")
    if ".." in parsed.path.split("/"):
        raise SecurityError("invalid_api_path", "API path must stay under /api.")
    if parsed.query:
        return f"{normalized}?{parsed.query}"
    return normalized


def agent_task_error(task: str) -> str | None:
    text = task or ""
    for match in URL_IN_TEXT_RE.findall(text):
        candidate = match.rstrip(").,]>\"'")
        lowered = candidate.lower()
        if lowered.startswith("https://") and is_ib_origin(candidate):
            continue
        return "Rejected a non-IB URL in the agent task."
    return None


def scope_agent_task(task: str) -> str:
    return (
        "Stay only on https://infinitebacklog.net (and www.infinitebacklog.net). "
        "Do not visit any other origin. "
        f"Task: {task}"
    )


def model_name_allowed(model: str) -> bool:
    raw = (model or "").strip()
    if not raw or "://" in raw or "\\" in raw or "\x00" in raw:
        return False
    return True


def chromium_launch_args() -> list[str]:
    args = ["--disable-dev-shm-usage"]
    if env_bool("IB_CHROMIUM_NO_SANDBOX", False):
        args.append("--no-sandbox")
    return args
