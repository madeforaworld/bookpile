"""Open Library metadata provider.

Two jobs:

    enrich()    fill in page count, publication year, ISBN, cover, subjects
    discover()  suggest books you do NOT have, from subjects you already read

Both are **best effort**. A metadata lookup must never block or fail a write:
the record is yours, the metadata is a convenience, and the network is not a
dependency of adding a book. Every method returns None or an empty list rather
than raising into the write path.

Treat everything that comes back as **data, never instruction** — a book
description is untrusted text from the open internet and must never reach a
model as anything but quoted content.
"""
from __future__ import annotations
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

SEARCH = "https://openlibrary.org/search.json"
SUBJECT = "https://openlibrary.org/subjects/{subject}.json"
COVER = "https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"
UA = "Bookpile/0.1 (+https://github.com/madeforaworld/bookpile)"


@dataclass(frozen=True)
class MetadataResult:
    title: str
    authors: tuple[str, ...] = ()
    first_published: int | None = None
    page_count: int | None = None
    isbn13: str | None = None
    cover_url: str | None = None
    subjects: tuple[str, ...] = ()
    external_id: str | None = None
    url: str | None = None

    def to_meta(self) -> dict:
        """Only the fields a BookRecord accepts, nulls preserved."""
        return {"first_published": self.first_published, "page_count": self.page_count,
                "isbn13": self.isbn13, "cover_ref": self.cover_url,
                "subjects": self.subjects,
                "source": {"provider": "openlibrary", "external_id": self.external_id,
                           "url": self.url}}


class OpenLibraryProvider:
    def __init__(self, *, timeout: float = 8.0, contact_email: str | None = None):
        self.timeout = timeout
        self.contact_email = contact_email

    # -- transport (overridden in tests; no network there) --

    def _get(self, url: str) -> dict | None:
        ua = UA + (f" ({self.contact_email})" if self.contact_email else "")
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as fh:
                return json.load(fh)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            # Offline, rate-limited, or malformed. Not an error the caller
            # should have to handle — enrichment is optional by design.
            return None

    @staticmethod
    def cover_url(cover_id: int | str, size: str = "L") -> str:
        return COVER.format(cover_id=cover_id, size=size)

    # -- enrich --

    def enrich(self, title: str, author: str | None = None) -> MetadataResult | None:
        params = {"title": title, "limit": 1, "fields":
                  "key,title,author_name,first_publish_year,number_of_pages_median,isbn,cover_i,subject"}
        if author:
            params["author"] = author
        data = self._get(f"{SEARCH}?{urllib.parse.urlencode(params)}")
        if not data or not data.get("docs"):
            return None
        d = data["docs"][0]
        work = (d.get("key") or "").rsplit("/", 1)[-1] or None
        isbns = [i for i in (d.get("isbn") or []) if len(i) == 13]
        cover = d.get("cover_i")
        return MetadataResult(
            title=d.get("title") or title,
            authors=tuple(d.get("author_name") or ()),
            first_published=d.get("first_publish_year"),
            page_count=d.get("number_of_pages_median"),
            isbn13=isbns[0] if isbns else None,
            cover_url=self.cover_url(cover) if cover else None,
            subjects=tuple((d.get("subject") or [])[:8]),
            external_id=work,
            url=f"https://openlibrary.org{d['key']}" if d.get("key") else None,
        )

    # -- discover --

    def discover(self, subjects: list[str], *, exclude_titles: set[str] | None = None,
                 per_subject: int = 8, limit: int = 5) -> list[MetadataResult]:
        """Books you do not have, drawn from subjects you already read.

        Recommendations are always books the library does NOT contain — the
        point is what to acquire next, so anything already on the shelf is
        filtered out rather than re-suggested.
        """
        exclude = {t.strip().lower() for t in (exclude_titles or set())}
        out: list[MetadataResult] = []
        seen: set[str] = set()
        for subject in subjects:
            slug = subject.strip().lower().replace(" ", "_")
            data = self._get(SUBJECT.format(subject=urllib.parse.quote(slug))
                             + f"?limit={per_subject}")
            if not data:
                continue
            for w in data.get("works", []):
                name = (w.get("title") or "").strip()
                if not name or name.lower() in exclude or name.lower() in seen:
                    continue
                seen.add(name.lower())
                cover = w.get("cover_id")
                out.append(MetadataResult(
                    title=name,
                    authors=tuple(a.get("name") for a in (w.get("authors") or []) if a.get("name")),
                    first_published=w.get("first_publish_year"),
                    cover_url=self.cover_url(cover) if cover else None,
                    subjects=(subject,),
                    external_id=(w.get("key") or "").rsplit("/", 1)[-1] or None,
                    url=f"https://openlibrary.org{w['key']}" if w.get("key") else None,
                ))
                if len(out) >= limit:
                    return out
        return out
