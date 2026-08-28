"""SQLite adapter. One file, structured queries, easy backup."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

from ..models import BookRecord, LibraryQuery, WriteResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    book_id     TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL,
    owned       INTEGER,              -- 1 / 0 / NULL — three-valued, never coerced
    added_at    TEXT,
    document    TEXT NOT NULL         -- full record as JSON, nulls preserved
);
CREATE INDEX IF NOT EXISTS books_status ON books(status);
"""


class SQLiteRepository:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def capabilities(self) -> dict:
        return {"readings": "full"}

    def close(self) -> None:
        self._conn.close()

    def upsert_book(self, book: BookRecord) -> WriteResult:
        prior = self.get_book(book.book_id)
        if prior is not None and prior.added_at:
            # added_at is immutable (I5). An incoming record may not move it,
            # whatever it claims.
            book = book.with_(added_at=prior.added_at, added_at_source=prior.added_at_source)
        doc = book.to_dict()
        self._conn.execute(
            "INSERT INTO books (book_id, title, status, owned, added_at, document) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(book_id) DO UPDATE SET "
            "title=excluded.title, status=excluded.status, owned=excluded.owned, "
            "added_at=excluded.added_at, document=excluded.document",
            (book.book_id, book.title, book.status,
             None if book.owned is None else int(book.owned),
             book.added_at, json.dumps(doc)),
        )
        self._conn.commit()
        return WriteResult(book_id=book.book_id, created=prior is None, record=book)

    def get_book(self, book_id: str) -> BookRecord | None:
        row = self._conn.execute(
            "SELECT document FROM books WHERE book_id = ?", (book_id,)).fetchone()
        return BookRecord.from_dict(json.loads(row["document"])) if row else None

    def list_books(self) -> list[BookRecord]:
        rows = self._conn.execute("SELECT document FROM books ORDER BY title").fetchall()
        return [BookRecord.from_dict(json.loads(r["document"])) for r in rows]

    def find_books(self, query: LibraryQuery) -> list[BookRecord]:
        out = self.list_books()
        if query.text:
            needle = query.text.lower()
            out = [b for b in out
                   if needle in b.title.lower()
                   or any(needle in a.lower() for a in b.authors)]
        if query.status:
            out = [b for b in out if b.status == query.status]
        if query.owned_filter:
            out = [b for b in out if b.owned is query.owned]
        return out
