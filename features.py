"""Persistent, UI-independent productivity features for the calculator."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json


HISTORY_LIMIT = 60
PRECISION_MIN = 3
PRECISION_MAX = 10


def normalize_state(data):
    """Return a safe state mapping while preserving recognized preferences."""
    if not isinstance(data, dict):
        return {}
    normalized = dict(data)
    for key, fallback in (("history", []), ("favorites", [])):
        if not isinstance(normalized.get(key, fallback), list): normalized[key] = fallback
    for key, fallback in (("variables", {}), ("engineering_values", {})):
        if not isinstance(normalized.get(key, fallback), dict): normalized[key] = fallback
    engineering_values = normalized.get("engineering_values", {})
    normalized["engineering_values"] = {
        key:value for key,value in engineering_values.items()
        if isinstance(key, str) and isinstance(value, dict)
    }
    return normalized


@dataclass(frozen=True)
class HistoryEntry:
    kind: str
    title: str
    result: str
    payload: dict
    timestamp: str = ""

    def serialized(self):
        data = asdict(self)
        if not data["timestamp"]:
            data["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return data


def normalized_precision(value, default=6):
    try:
        return max(PRECISION_MIN, min(PRECISION_MAX, int(value)))
    except (TypeError, ValueError):
        return default


def add_history(state, entry, limit=HISTORY_LIMIT):
    """Add a newest-first entry, suppressing consecutive duplicates."""
    history = state.setdefault("history", [])
    if not isinstance(history, list):
        history = state["history"] = []
    item = entry.serialized() if isinstance(entry, HistoryEntry) else dict(entry)
    signature = (item.get("kind"), item.get("title"), item.get("result"), _payload_key(item.get("payload", {})))
    if history:
        first = history[0]
        first_signature = (first.get("kind"), first.get("title"), first.get("result"), _payload_key(first.get("payload", {})))
        if signature == first_signature:
            history[0] = item
            return history
    history.insert(0, item)
    del history[max(1, int(limit)):]
    return history


def toggle_favorite(state, key):
    favorites = state.setdefault("favorites", [])
    if not isinstance(favorites, list):
        favorites = state["favorites"] = []
    if key in favorites:
        favorites.remove(key)
        return False
    favorites.append(key)
    favorites.sort()
    return True


def is_favorite(state, key):
    favorites = state.get("favorites", [])
    return isinstance(favorites, list) and key in favorites


def search_items(items, query, favorites=()):
    """Return compact command records ranked by favorite, prefix, then label."""
    words = [word.casefold() for word in query.split() if word]
    favorite_set = set(favorites)
    matches = []
    for item in items:
        haystack = " ".join(str(item.get(field, "")) for field in ("label", "detail", "keywords")).casefold()
        if words and not all(word in haystack for word in words):
            continue
        label = str(item.get("label", ""))
        prefix = bool(words and label.casefold().startswith(words[0]))
        matches.append((item.get("key") not in favorite_set, not prefix, label.casefold(), item))
    return [match[-1] for match in sorted(matches)]


def _payload_key(payload):
    try:
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(payload)
