"""Deterministic intent parsing.

Tried FIRST, before any model. An install with no LLM key stays fully
functional — that is a requirement, not a fallback. Output is a raw dict that
must still pass safety.validate_intent before it reaches the service.
"""
from __future__ import annotations
import re

# Ordered most-specific first. "don't own X" must beat "own X"; the
# discovery phrases must beat the general "<someone> recommended X"; and
# "<someone> recommended X" must beat the bare add.
_RULES: list[tuple[re.Pattern, str]] = [
    # Order is the whole design here. Each rule must be reachable, so the more
    # specific phrasing always sits above the general one it would otherwise
    # be swallowed by. Evaluated top to bottom, first match wins.

    # "don't own X" before "own X"
    (re.compile(r"^\s*(?:i\s+)?(?:don'?t|do not)\s+own\s+(?P<title>.+?)\s*$", re.I), "disown"),

    # buy something new (external discovery) before "<someone> recommended X"
    (re.compile(r"^\s*(?:what\s+should\s+i\s+buy"
                r"|recommend\s+(?:me\s+)?something\s+new"
                r"|what\s+(?:else|new)\s+should\s+i\s+read"
                r"|(?:find|suggest)\s+(?:me\s+)?(?:a\s+)?new\s+books?)"
                r"\s*[?.]?\s*$", re.I), "discover"),

    # pick from the shelf I already have
    (re.compile(r"^\s*(?:what\s+(?:should\s+i|to)\s+read(?:\s+next)?|what\s+next"
                r"|recommend\s+me\s+something|pick\s+(?:me\s+)?something)"
                r"(?:\s*[,:]?\s*(?P<vibe>.+?))?\s*[?.]?\s*$", re.I), "next"),
    (re.compile(r"^\s*(?:i'?m\s+in\s+the\s+mood\s+for|something)\s+(?P<vibe>.+?)\s*[?.]?\s*$", re.I), "next"),

    # heard about a book you do not have yet — capture it before you forget
    (re.compile(r"^\s*(?:(?P<who>[\w .'-]{2,40})\s+)?recommend(?:ed|s)\s+(?P<title>.+?)"
                r"(?:\s+by\s+(?P<author>.+?))?\s*$", re.I), "wishlist"),
    (re.compile(r"^\s*(?:add\s+)?(?P<title>.+?)\s+to\s+(?:my\s+)?(?:wishlist|tbr|to[- ]?read)\s*$", re.I), "wishlist"),
    (re.compile(r"^\s*(?:i\s+)?want\s+to\s+read\s+(?P<title>.+?)(?:\s+by\s+(?P<author>.+?))?\s*$", re.I), "wishlist"),

    # acquiring something already on the list
    (re.compile(r"^\s*(?:i\s+)?(?:bought|picked\s+up|got|acquired)\s+(?P<title>.+?)\s*$", re.I), "bought"),

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
    for pattern, kind in _RULES:
        m = pattern.match(text)
        if not m:
            continue
        g = m.groupdict()

        if kind == "wishlist":
            # Recommended but not yet acquired: owned is FALSE, not unknown.
            # Someone told you about it, so you know you do not have it.
            out = {"intent": "add_book", "title": g["title"].strip(), "owned": False}
            if g.get("author"):
                out["authors"] = [g["author"].strip()]
            return out
        if kind == "bought":
            return {"intent": "set_owned", "book_ref": g["title"].strip(), "owned": True}
        if kind == "discover":
            return {"intent": "discover"}
        if kind == "next":
            out = {"intent": "recommend"}
            if g.get("vibe"):
                out["vibe"] = g["vibe"].strip()
            return out
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
