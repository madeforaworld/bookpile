"""Markdown adapter — one note per book, YAML-ish frontmatter.

Deliberately not a copy of any private vault's schema. The repository owns
paths: a title never becomes a filename unsanitised.
"""
from __future__ import annotations
import json
from pathlib import Path

from ..models import BookRecord, LibraryQuery, WriteResult

_FENCE = "---"
_MARKER = "bookpile_record:"


class MarkdownVaultRepository:
    """Frontmatter holds a single JSON line under `bookpile_record:`.

    Lossless round-tripping matters more than hand-editability for the
    reference adapter; a richer YAML mapping is a valid alternative so long as
    it passes the same storage vectors.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def capabilities(self) -> dict:
        return {"readings": "full"}

    def _path(self, book_id: str) -> Path:
        # book_id is already slugged by the domain; re-check anyway so a
        # crafted id can never escape the root.
        safe = "".join(c for c in book_id if c.isalnum() or c in "-_")[:80] or "untitled"
        return self.root / f"{safe}.md"

    def upsert_book(self, book: BookRecord) -> WriteResult:
        path = self._path(book.book_id)
        prior = self.get_book(book.book_id)
        if prior is not None and prior.added_at:
            book = book.with_(added_at=prior.added_at, added_at_source=prior.added_at_source)
        doc = book.to_dict()
        body = (
            f"{_FENCE}\n"
            f"title: {book.title}\n"
            f"status: {book.status}\n"
            f"{_MARKER} {json.dumps(doc, ensure_ascii=False)}\n"
            f"{_FENCE}\n\n"
            f"# {book.title}\n\n"
            f"{', '.join(book.authors) if book.authors else ''}\n"
        )
        path.write_text(body, encoding="utf-8")
        return WriteResult(book_id=book.book_id, created=prior is None, record=book)

    def get_book(self, book_id: str) -> BookRecord | None:
        path = self._path(book_id)
        if not path.exists():
            return None
        return self._parse(path)

    @staticmethod
    def _parse(path: Path) -> BookRecord | None:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(_MARKER):
                return BookRecord.from_dict(json.loads(line[len(_MARKER):].strip()))
        return None

    def list_books(self) -> list[BookRecord]:
        out = []
        for p in sorted(self.root.glob("*.md")):
            rec = self._parse(p)
            if rec:
                out.append(rec)
        return sorted(out, key=lambda b: b.title)

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
