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
    enrich: bool = False          # metadata lookups are opt-in, never assumed

    def handle(self, text: str) -> str:
        raw = parse(text)
        if raw is None:
            return ("I could not read that as a command. Try: add <title> · "
                    "start <title> · finished <title> · <title> 4 stars · "
                    "what should I read next · what should I buy · find <text>")
        try:
            intent = validate_intent(raw)
        except ValidationError as exc:
            return f"Rejected: {exc}"

        try:
            if intent.intent == "add_book":
                r = self.service.add_book(intent.title, intent.authors, intent.categories,
                                          owned=intent.owned if intent.owned_present else None,
                                          enrich=self.enrich)
                if not r.created:
                    return f"Already in the library · {r.record.title}"
                b = r.record
                bits = [f"Added · {b.title}"]
                if b.owned is False:
                    bits.append("not bought yet")
                if b.first_published:
                    bits.append(str(b.first_published))
                if b.page_count:
                    bits.append(f"{b.page_count}pp")
                return " · ".join(bits)
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
            if intent.intent == "recommend":
                result = self.service.recommend(intent.vibe)
                waiting = result["wishlist_waiting"]
                tail = (f"\n({waiting} more on your wishlist, not bought yet — "
                        f'ask "what should I buy")' if waiting else "")
                if not result["picks"]:
                    return ("Nothing on your shelf left unread." + tail) if waiting else \
                           "Nothing unread on the shelf."
                head = ("On your shelf" if not intent.vibe
                        else f"For {intent.vibe!r}, on your shelf")
                lines = [head + ":"]
                for pick in result["picks"]:
                    flag = "  (ownership unknown — check the shelf)" if pick["check_shelf"] else ""
                    lines.append(f"  {pick['book'].title} — {pick['reason']}{flag}")
                return "\n".join(lines) + tail
            if intent.intent == "discover":
                result = self.service.discover()
                lines = []
                if result["wishlist"]:
                    lines.append("Already on your list, not bought yet:")
                    for b in result["wishlist"]:
                        who = f" — {b.authors[0]}" if b.authors else ""
                        lines.append(f"  {b.title}{who}")
                if result["new"]:
                    if lines:
                        lines.append("")
                    lines.append("New, from subjects you read:")
                    for m in result["new"]:
                        who = f" — {m.authors[0]}" if m.authors else ""
                        yr = f" ({m.first_published})" if m.first_published else ""
                        lines.append(f"  {m.title}{who}{yr}")
                if not lines:
                    return ("Nothing to buy — your wishlist is empty and metadata "
                            "lookups are off. Bookpile works fine without them.")
                if result["note"]:
                    lines.append("")
                    lines.append(f"({result['note']})")
                return "\n".join(lines)
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
