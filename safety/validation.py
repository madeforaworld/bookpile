"""Strict intent validation.

Model output is an untrusted proposal. Nothing here coerces, guesses or
repairs — a malformed intent is rejected, never fixed up.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date

INTENTS = {"add_book", "set_reading_status", "set_owned", "rate_book",
           "search_library", "recommend", "discover"}
STATUSES = {"to_read", "reading", "finished", "paused", "abandoned", "reference"}
OUTCOMES = {"in_progress", "finished", "abandoned"}

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ALLOWED_KEYS = {
    "intent", "book_ref", "title", "authors", "categories", "status", "date",
    "rating", "owned", "query", "vibe", "confidence", "needs_confirmation",
}


class ValidationError(Exception):
    pass


@dataclass(frozen=True)
class Intent:
    intent: str
    book_ref: str | None = None
    title: str | None = None
    authors: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    status: str | None = None
    date: str | None = None
    rating: int | None = None
    owned: bool | None = None
    owned_present: bool = False   # distinguishes "set to null" from "not mentioned"
    query: str | None = None
    vibe: str | None = None
    needs_confirmation: bool = False


def _iso(value, field_name: str) -> str:
    if not isinstance(value, str) or not _ISO.match(value):
        raise ValidationError(
            f"{field_name} must be an ISO date resolved by the server, got {value!r}"
        )
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{field_name} is not a real date: {value!r}") from None
    return value


def _text(value, field_name: str, *, limit: int = 500) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string, got {type(value).__name__}")
    stripped = value.strip()
    if not stripped:
        raise ValidationError(f"{field_name} must not be empty")
    if len(stripped) > limit:
        raise ValidationError(f"{field_name} exceeds {limit} characters")
    if "\x00" in stripped:
        raise ValidationError(f"{field_name} contains a null byte")
    return stripped


def _str_list(value, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValidationError(f"{field_name} must be a list")
    return tuple(_text(v, f"{field_name}[]") for v in value)


def validate_intent(raw: object) -> Intent:
    """Validate an untrusted intent proposal. Raises ValidationError."""
    if not isinstance(raw, dict):
        raise ValidationError("intent must be an object")

    unknown = set(raw) - _ALLOWED_KEYS
    if unknown:
        # An unexpected key means the producer and this validator disagree
        # about the contract. Refuse rather than ignore it.
        raise ValidationError(f"unknown keys: {sorted(unknown)}")

    name = raw.get("intent")
    if name not in INTENTS:
        raise ValidationError(f"unknown intent {name!r}")

    kw: dict = {"intent": name}

    if name == "add_book":
        kw["title"] = _text(raw.get("title"), "title")
        kw["authors"] = _str_list(raw.get("authors"), "authors")
        kw["categories"] = _str_list(raw.get("categories"), "categories")
        if "owned" in raw:
            owned = raw["owned"]
            if owned is not None and not isinstance(owned, bool):
                raise ValidationError(f"owned must be true, false or null, got {owned!r}")
            kw["owned"] = owned
            kw["owned_present"] = True
    elif name in ("recommend", "discover"):
        # neither names a book: one picks from your shelf, one from outside it
        if raw.get("vibe") is not None:
            kw["vibe"] = _text(raw["vibe"], "vibe", limit=200)
    elif name == "search_library":
        kw["query"] = _text(raw.get("query"), "query")
    else:
        kw["book_ref"] = _text(raw.get("book_ref"), "book_ref")

    if name == "set_reading_status":
        status = raw.get("status")
        if status not in STATUSES:
            raise ValidationError(f"status must be one of {sorted(STATUSES)}, got {status!r}")
        kw["status"] = status
        if raw.get("date") is not None:
            kw["date"] = _iso(raw["date"], "date")

    if name == "set_owned":
        if "owned" not in raw:
            raise ValidationError("set_owned requires an 'owned' field (true, false or null)")
        owned = raw["owned"]
        if owned is not None and not isinstance(owned, bool):
            raise ValidationError(f"owned must be true, false or null, got {owned!r}")
        kw["owned"] = owned
        kw["owned_present"] = True

    if name == "rate_book" or raw.get("rating") is not None:
        rating = raw.get("rating")
        if name == "rate_book" and rating is None:
            raise ValidationError("rate_book requires a rating")
        if rating is not None:
            if isinstance(rating, bool) or not isinstance(rating, int):
                raise ValidationError(f"rating must be an integer 1-5, got {rating!r}")
            if not 1 <= rating <= 5:
                raise ValidationError(f"rating must be between 1 and 5, got {rating}")
            kw["rating"] = rating

    conf = raw.get("confidence")
    if conf is not None:
        if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not 0 <= conf <= 1:
            raise ValidationError(f"confidence must be a number 0-1, got {conf!r}")
        if conf < 0.75:
            raise ValidationError(f"confidence {conf} below threshold; ask instead of writing")

    kw["needs_confirmation"] = bool(raw.get("needs_confirmation", False))
    return Intent(**kw)
