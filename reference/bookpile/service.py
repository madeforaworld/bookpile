"""LibraryService — the only thing permitted to mutate storage.

Every mutation is a named operation with validated arguments. There is no
generic update, no passthrough, no path or query built from user text.
"""
from __future__ import annotations
from datetime import date
from typing import Callable

from .models import BookRecord, LibraryQuery, Reading, WriteResult, slugify
from .ports import LibraryRepository


class AmbiguousReference(Exception):
    """Two matches is a question, never a guess.

    Carries title, author and year for each candidate — a list of bare titles
    is not enough to choose between two editions or two books of the same name.
    """

    def __init__(self, ref: str, candidates: list[BookRecord]):
        self.ref, self.candidates = ref, candidates
        super().__init__(f"{ref!r} matches {len(candidates)} books: "
                         + "; ".join(self.describe(c) for c in candidates[:5]))

    @staticmethod
    def describe(book: BookRecord) -> str:
        author = book.authors[0] if book.authors else "unknown author"
        year = f", {book.first_published}" if book.first_published else ""
        return f"{book.title} — {author}{year}"


class NotFound(Exception):
    pass


class LibraryService:
    def __init__(self, repo: LibraryRepository, *,
                 today: Callable[[], date] = date.today, metadata=None):
        self.repo = repo
        self._today = today
        self.metadata = metadata      # optional; None means never touch the network

    def _now(self) -> str:
        """Dates are resolved here, server-side. A model never decides what today is."""
        return self._today().isoformat()

    # ---- resolution -------------------------------------------------

    def resolve(self, book_ref: str) -> BookRecord:
        exact = self.repo.get_book(book_ref)
        if exact:
            return exact
        needle = book_ref.strip().lower()
        books = self.repo.list_books()
        titles = [b for b in books if b.title.lower() == needle]
        if len(titles) == 1:
            return titles[0]
        if len(titles) > 1:
            raise AmbiguousReference(book_ref, titles)
        partial = [b for b in books if needle in b.title.lower()]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            # Ambiguity is a question, never a guess. See spec/INTENTS.md.
            raise AmbiguousReference(book_ref, partial)
        raise NotFound(f"no book matching {book_ref!r}")

    # ---- named operations -------------------------------------------

    def add_book(self, title: str, authors=(), categories=(), owned=None,
                 enrich: bool = False, **meta) -> WriteResult:
        book_id = slugify(title, authors[0] if authors else "")
        existing = self.repo.get_book(book_id)
        if existing:
            # Idempotent: re-adding is not a duplicate and must not touch added_at.
            return WriteResult(book_id=book_id, created=False, record=existing)
        record = BookRecord(
            book_id=book_id, title=title.strip(),
            authors=tuple(authors), categories=tuple(categories),
            status="to_read", owned=owned, added_at=self._now(), **meta,
        )
        if enrich and self.metadata is not None:
            record = self._enriched(record)
        return self.repo.upsert_book(record)

    def _enriched(self, book: BookRecord) -> BookRecord:
        """Fill blanks from the metadata provider. Never overwrite, never fail.

        A lookup that is slow, offline or wrong must not stop a book being
        added — the record is yours, the metadata is a convenience.
        """
        try:
            found = self.metadata.enrich(book.title, book.authors[0] if book.authors else None)
        except Exception:
            return book
        if found is None:
            return book
        changes: dict = {}
        for field_name in ("first_published", "page_count", "isbn13"):
            if getattr(book, field_name) is None and getattr(found, field_name) is not None:
                changes[field_name] = getattr(found, field_name)
        if not book.authors and found.authors:
            changes["authors"] = found.authors
        if not book.subjects and found.subjects:
            changes["subjects"] = found.subjects          # never merged into categories (I2)
        if book.cover_ref is None and found.cover_url:
            changes["cover_ref"] = found.cover_url        # replace-never (I7)
        if found.external_id:
            changes["source"] = {"provider": "openlibrary",
                                 "external_id": found.external_id, "url": found.url}
        return book.with_(**changes) if changes else book

    def discover(self, limit: int = 5) -> dict:
        """Pool two: what to buy.

        Two sources, in priority order:

        1. Books already in your library marked ``owned: false`` — you have
           already decided you want these, so they are the obvious purchases.
        2. New titles from the subjects you actually read, excluding everything
           the library already knows about.

        Unknown ownership is never treated as "not owned"; an unverified book
        does not become a shopping suggestion.
        """
        books = self.repo.list_books()
        # Unowned AND still unread. A borrowed book you already finished is not
        # a shopping suggestion — that is a different list ("read but do not
        # own"), and conflating them fills the buy list with books you have
        # already been through.
        wishlist = [b for b in books if b.owned is False and b.status == "to_read"]
        wishlist.sort(key=lambda b: (b.added_at or "", b.title))

        if self.metadata is None:
            return {"wishlist": wishlist[:limit], "new": [],
                    "note": "metadata lookups are off, so only your own wishlist is shown"}
        counts: dict[str, int] = {}
        for b in books:
            for s_ in b.subjects:
                counts[s_] = counts.get(s_, 0) + 1
            for c in b.categories:
                counts[c] = counts.get(c, 0) + 1
        top = [s_ for s_, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:4]]
        room = max(limit - len(wishlist), 0)
        found = []
        if top and room:
            try:
                found = self.metadata.discover(
                    top, exclude_titles={b.title for b in books}, limit=room)
            except Exception:
                found = []
        return {"wishlist": wishlist[:limit], "new": found, "note": None}

    def set_reading_status(self, book_ref: str, status: str, when: str | None = None) -> WriteResult:
        book = self.resolve(book_ref)
        when = when or self._now()
        readings = list(book.readings)
        open_idx = next((i for i, r in enumerate(readings) if r.outcome == "in_progress"), None)

        if status == "reading":
            if open_idx is None:
                # finished -> reading APPENDS. It never edits the previous
                # reading; that is the bug the old flat schema had.
                readings.append(Reading(started_at=when, outcome="in_progress"))
        elif status in ("finished", "abandoned"):
            if open_idx is not None:
                r = readings[open_idx]
                readings[open_idx] = Reading(
                    started_at=r.started_at,
                    finished_at=when if status == "finished" else r.finished_at,
                    outcome=status, rating=r.rating,
                )
            else:
                readings.append(Reading(
                    started_at=None,
                    finished_at=when if status == "finished" else None,
                    outcome=status,
                ))
        # to_read / reference / paused change status only; paused deliberately
        # leaves the reading open — the status carries the pause.

        return self.repo.upsert_book(book.with_(status=status, readings=tuple(readings)))

    def set_owned(self, book_ref: str, owned: bool | None) -> WriteResult:
        book = self.resolve(book_ref)
        return self.repo.upsert_book(book.with_(owned=owned))

    def rate_book(self, book_ref: str, rating: int) -> WriteResult:
        book = self.resolve(book_ref)
        readings = list(book.readings)
        if not readings:
            readings.append(Reading(outcome="in_progress", rating=rating))
        else:
            last = readings[-1]
            readings[-1] = Reading(last.started_at, last.finished_at, last.outcome, rating)
        return self.repo.upsert_book(book.with_(readings=tuple(readings)))

    def search_library(self, query: str, **filters) -> list[BookRecord]:
        return self.repo.find_books(LibraryQuery(text=query, **filters))

    # ---- read-only: what should I read next ------------------------

    #: vibe word -> (field to inspect, value to match)
    _MOODS = {
        "historical": ("kind", "historical"), "history": ("kind", "historical"),
        "period": ("kind", "historical"), "past": ("kind", "historical"),
        "speculative": ("kind", "speculative"), "sci-fi": ("kind", "speculative"),
        "scifi": ("kind", "speculative"), "future": ("kind", "speculative"),
        "contemporary": ("kind", "contemporary"), "modern": ("kind", "contemporary"),
        "invented": ("kind", "fictional"), "fantasy": ("kind", "fictional"),
        "fiction": ("form", "fiction"), "novel": ("form", "fiction"),
        "nonfiction": ("form", "nonfiction"), "non-fiction": ("form", "nonfiction"),
        "factual": ("form", "nonfiction"), "true": ("form", "nonfiction"),
    }
    _SHORT = {"short", "quick", "light", "brief", "small"}
    _LONG = {"long", "big", "chunky", "meaty", "substantial"}

    def recommend(self, vibe: str | None = None, limit: int = 3) -> dict:
        """Pool one: books you can start tonight.

        Deliberately excludes anything you have not bought. A book you do not
        own is not something you can read next — it belongs to the buying pool.
        Unknown ownership stays a candidate, flagged, because unknown is not no.
        """
        unread = [b for b in self.repo.list_books() if b.status == "to_read"]
        pool = [b for b in unread if b.owned is not False]
        on_wishlist = [b for b in unread if b.owned is False]
        if not pool:
            return {"picks": [], "wishlist_waiting": len(on_wishlist)}

        words = set((vibe or "").lower().replace(",", " ").split())
        scored: list[tuple[int, list[str], BookRecord]] = []

        for book in pool:
            score, why = 0, []
            for word in words:
                target = self._MOODS.get(word)
                if not target:
                    continue
                field, want = target
                if field == "kind" and book.setting.kind == want:
                    score += 3; why.append(want)
                elif field == "form" and book.form == want:
                    score += 3; why.append(want.replace("nonfiction", "non-fiction"))
            # shelves and subjects are free-text; match them directly
            for word in words:
                if any(word == c.lower() for c in book.categories):
                    score += 2; why.append(word)
                elif any(word == s.lower() for s in book.subjects):
                    score += 2; why.append(word)
            if book.page_count is not None:
                if words & self._SHORT and book.page_count <= 300:
                    score += 2; why.append(f"{book.page_count} pages")
                if words & self._LONG and book.page_count >= 450:
                    score += 2; why.append(f"{book.page_count} pages")
            # a book you certainly have beats one whose ownership is unknown
            if book.owned is True:
                score += 1
            scored.append((score, why, book))

        scored.sort(key=lambda t: (-t[0], t[2].page_count or 10**6, t[2].title))
        picks = [{
            "book": b,
            "score": s,
            "reason": ", ".join(dict.fromkeys(w)) if w else "still unread",
            "check_shelf": b.owned is None,
        } for s, w, b in scored[:limit]]
        return {"picks": picks, "wishlist_waiting": len(on_wishlist)}
