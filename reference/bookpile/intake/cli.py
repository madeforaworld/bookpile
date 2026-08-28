"""CLI intake — the default. No credentials, always available.

Deliberately the reference path: an install with no LLM key and no bot token is
still a complete, working Bookpile.
"""
from __future__ import annotations
import sys
from dataclasses import dataclass

from ..intents import parse
from ..service import AmbiguousReference, LibraryService, NotFound

try:
    from safety import ValidationError, validate_intent
except ImportError:  # running from inside reference/
    import pathlib, sys as _s
    _s.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
    from safety import ValidationError, validate_intent


@dataclass
class CLIIntake:
    service: LibraryService
    confirm: bool = True          # DEFAULTS.md: propose, then confirm

    def handle(self, text: str) -> str:
        raw = parse(text)
        if raw is None:
            return ("I could not read that as a command. Try: add <title> · "
                    "start <title> · finished <title> · <title> 4 stars · find <text>")
        try:
            intent = validate_intent(raw)
        except ValidationError as exc:
            return f"Rejected: {exc}"

        try:
            if intent.intent == "add_book":
                r = self.service.add_book(intent.title, intent.authors, intent.categories)
                return (f"Added · {r.record.title}" if r.created
                        else f"Already in the library · {r.record.title}")
            if intent.intent == "set_reading_status":
                r = self.service.set_reading_status(intent.book_ref, intent.status, intent.date)
                if intent.rating is not None:
                    r = self.service.rate_book(intent.book_ref, intent.rating)
                book = r.record
                # read back before replying — never confirm an unverified write
                book = self.service.repo.get_book(book.book_id) or book
                extra = f" · {book.rating}/5" if book.rating else ""
                return f"{book.status.replace('_', ' ').title()} · {book.title}{extra}"
            if intent.intent == "set_owned":
                r = self.service.set_owned(intent.book_ref, intent.owned)
                label = {True: "owned", False: "not owned", None: "ownership unknown"}[intent.owned]
                return f"{r.record.title} · {label}"
            if intent.intent == "rate_book":
                r = self.service.rate_book(intent.book_ref, intent.rating)
                return f"{r.record.title} · {intent.rating}/5"
            if intent.intent == "search_library":
                hits = self.service.search_library(intent.query)
                if not hits:
                    return f"Nothing matching {intent.query!r}"
                return "\n".join(f"  {b.title} · {b.status}" for b in hits[:10])
        except AmbiguousReference as exc:
            return f"Which one? {exc}"
        except NotFound as exc:
            return str(exc)
        return "Nothing to do"

    def repl(self, stream=sys.stdin) -> None:
        for line in stream:
            line = line.strip()
            if not line or line in {"quit", "exit"}:
                break
            print(self.handle(line))
