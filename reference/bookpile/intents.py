"""Deterministic intent parsing.

Tried FIRST, before any model. An install with no LLM key stays fully
functional — that is a requirement, not a fallback. Output is a raw dict that
must still pass safety.validate_intent before it reaches the service.
"""
from __future__ import annotations
import re

_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*add\s+(?P<title>.+?)(?:\s+by\s+(?P<author>.+?))?\s*$", re.I), "add_book"),
    (re.compile(r"^\s*(?:start|starting|begin|began|reading)\s+(?P<title>.+?)\s*$", re.I), "start"),
    (re.compile(r"^\s*(?:finished|finish|done with|completed)\s+(?P<title>.+?)"
                r"(?:\s+(?:today|now))?"
                r"(?:\s*[,-]?\s*(?P<rating>[1-5])\s*(?:\*|stars?|/\s*5))?\s*$", re.I), "finished"),
    (re.compile(r"^\s*(?:abandoned|gave up on|dnf)\s+(?P<title>.+?)\s*$", re.I), "abandoned"),
    (re.compile(r"^\s*(?:paused|pausing)\s+(?P<title>.+?)\s*$", re.I), "paused"),
    (re.compile(r"^\s*rate\s+(?P<title>.+?)\s+(?P<rating>[1-5])\s*(?:\*|stars?|/\s*5)?\s*$", re.I), "rate"),
    (re.compile(r"^\s*(?P<title>.+?)\s+(?P<rating>[1-5])\s*(?:\*|stars?|/\s*5)\s*$", re.I), "rate"),
    (re.compile(r"^\s*(?:i\s+)?own\s+(?P<title>.+?)\s*$", re.I), "own"),
    (re.compile(r"^\s*(?:i\s+)?(?:don'?t|do not)\s+own\s+(?P<title>.+?)\s*$", re.I), "disown"),
    (re.compile(r"^\s*(?:search|find|look for)\s+(?P<query>.+?)\s*$", re.I), "search"),
]

_STATUS = {"start": "reading", "finished": "finished",
           "abandoned": "abandoned", "paused": "paused"}


def parse(text: str) -> dict | None:
    """Return a raw intent dict, or None if nothing matched deterministically.

    None means "ask a model, then validate", not "guess".
    """
    if not isinstance(text, str) or not text.strip():
        return None
    # longest-match ordering matters: "don't own X" must beat "own X"
    for pattern, kind in sorted(_RULES, key=lambda r: r[1] != "disown"):
        m = pattern.match(text)
        if not m:
            continue
        g = m.groupdict()

        if kind == "add_book":
            out = {"intent": "add_book", "title": g["title"].strip()}
            if g.get("author"):
                out["authors"] = [g["author"].strip()]
            return out
        if kind in _STATUS:
            out = {"intent": "set_reading_status",
                   "book_ref": g["title"].strip(), "status": _STATUS[kind]}
            if g.get("rating"):
                out["rating"] = int(g["rating"])
            return out
        if kind == "rate":
            return {"intent": "rate_book", "book_ref": g["title"].strip(),
                    "rating": int(g["rating"])}
        if kind == "own":
            return {"intent": "set_owned", "book_ref": g["title"].strip(), "owned": True}
        if kind == "disown":
            return {"intent": "set_owned", "book_ref": g["title"].strip(), "owned": False}
        if kind == "search":
            return {"intent": "search_library", "query": g["query"].strip()}
    return None
