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
    def __init__(self, ref: str, candidates: list[BookRecord]):
        self.ref, self.candidates = ref, candidates
        super().__init__(
            f"{ref!r} matches {len(candidates)} books: "
            + ", ".join(c.title for c in candidates[:5])
        )


class NotFound(Exception):
    pass


class LibraryService:
    def __init__(self, repo: LibraryRepository, *, today: Callable[[], date] = date.today):
        self.repo = repo
        self._today = today

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

    def add_book(self, title: str, authors=(), categories=(), **meta) -> WriteResult:
        book_id = slugify(title, authors[0] if authors else "")
        existing = self.repo.get_book(book_id)
        if existing:
            # Idempotent: re-adding is not a duplicate and must not touch added_at.
            return WriteResult(book_id=book_id, created=False, record=existing)
        record = BookRecord(
            book_id=book_id, title=title.strip(),
            authors=tuple(authors), categories=tuple(categories),
            status="to_read", added_at=self._now(), **meta,
        )
        return self.repo.upsert_book(record)

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
