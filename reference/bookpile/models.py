"""Records, readings, and the derivation rule.

The one thing to understand here: `readings` is authoritative and the top-level
`started_at` / `finished_at` / `rating` are a projection of it, recomputed on
every write. See spec/INVARIANTS.md I4.
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import date

SCHEMA_VERSION = 1
STATUSES = ("to_read", "reading", "finished", "paused", "abandoned", "reference")
OUTCOMES = ("in_progress", "finished", "abandoned")
SETTING_KINDS = ("historical", "contemporary", "speculative", "fictional")


def slugify(*parts: str) -> str:
    """Stable, opaque id. The repository owns paths; a title never becomes one."""
    raw = " ".join(p for p in parts if p)
    norm = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    norm = re.sub(r"[^a-zA-Z0-9]+", "-", norm).strip("-").lower()
    norm = re.sub(r"-{2,}", "-", norm)
    return norm[:80] or "untitled"


@dataclass(frozen=True)
class Reading:
    started_at: str | None = None
    finished_at: str | None = None
    outcome: str = "in_progress"
    rating: int | None = None

    def __post_init__(self):
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}, got {self.outcome!r}")
        if self.outcome == "finished" and not self.finished_at:
            raise ValueError("a finished reading requires finished_at")
        if self.rating is not None and not (isinstance(self.rating, int) and 1 <= self.rating <= 5):
            raise ValueError(f"rating must be 1-5 or None, got {self.rating!r}")

    def to_dict(self) -> dict:
        return {"started_at": self.started_at, "finished_at": self.finished_at,
                "outcome": self.outcome, "rating": self.rating}

    @classmethod
    def from_dict(cls, d: dict) -> "Reading":
        return cls(started_at=d.get("started_at"), finished_at=d.get("finished_at"),
                   outcome=d.get("outcome", "in_progress"), rating=d.get("rating"))


@dataclass(frozen=True)
class Setting:
    period: str | None = None
    anchor_year: int | None = None
    kind: str | None = None

    def __post_init__(self):
        if self.kind is not None and self.kind not in SETTING_KINDS:
            raise ValueError(f"setting.kind must be one of {SETTING_KINDS}, got {self.kind!r}")
        if self.kind == "fictional" and self.anchor_year is not None:
            # An invented world has no real-world year. Storing one would put it
            # on the three-clocks plot, which is a spec violation.
            raise ValueError("a fictional setting cannot carry an anchor_year")

    def to_dict(self) -> dict:
        return {"period": self.period, "anchor_year": self.anchor_year, "kind": self.kind}

    @classmethod
    def from_dict(cls, d: dict | None) -> "Setting":
        d = d or {}
        return cls(period=d.get("period"), anchor_year=d.get("anchor_year"), kind=d.get("kind"))


@dataclass(frozen=True)
class BookRecord:
    book_id: str
    title: str
    authors: tuple[str, ...] = ()
    status: str = "to_read"
    owned: bool | None = None
    added_at: str | None = None
    added_at_source: str = "manual"
    readings: tuple[Reading, ...] = ()
    categories: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    page_count: int | None = None
    first_published: int | None = None
    edition_published: int | None = None
    isbn10: str | None = None
    isbn13: str | None = None
    cover_ref: str | None = None
    source: dict = field(default_factory=lambda: {"provider": None, "external_id": None, "url": None})
    setting: Setting = field(default_factory=Setting)
    sessions: tuple[dict, ...] | None = None
    metadata_updated_at: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got {self.status!r}")

    # ---- derived view of readings (I4) ----

    @property
    def started_at(self) -> str | None:
        return self.readings[-1].started_at if self.readings else None

    @property
    def finished_at(self) -> str | None:
        return self.readings[-1].finished_at if self.readings else None

    @property
    def rating(self) -> int | None:
        """Most recent non-null rating across readings."""
        for r in reversed(self.readings):
            if r.rating is not None:
                return r.rating
        return None

    @property
    def first_started_at(self) -> str | None:
        """Shelf time is measured to the FIRST reading — a re-read does not reset it."""
        for r in self.readings:
            if r.started_at:
                return r.started_at
        return None

    def shelf_days(self) -> int | None:
        if not self.added_at or not self.first_started_at:
            return None
        return (date.fromisoformat(self.first_started_at) - date.fromisoformat(self.added_at)).days

    def completions(self) -> tuple[Reading, ...]:
        return tuple(r for r in self.readings if r.outcome == "finished")

    # ---- serialization: nulls survive, always (I1) ----

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "book_id": self.book_id,
            "title": self.title,
            "authors": list(self.authors),
            "status": self.status,
            "owned": self.owned,
            "added_at": self.added_at,
            "added_at_source": self.added_at_source,
            "readings": [r.to_dict() for r in self.readings],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "rating": self.rating,
            "categories": list(self.categories),
            "subjects": list(self.subjects),
            "page_count": self.page_count,
            "first_published": self.first_published,
            "edition_published": self.edition_published,
            "isbn10": self.isbn10,
            "isbn13": self.isbn13,
            "cover_ref": self.cover_ref,
            "source": dict(self.source),
            "setting": self.setting.to_dict(),
            "sessions": [dict(s) for s in self.sessions] if self.sessions is not None else None,
            "metadata_updated_at": self.metadata_updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BookRecord":
        version = d.get("schema_version", SCHEMA_VERSION)
        if version > SCHEMA_VERSION:
            raise ValueError(
                f"record uses schema_version {version}; this build understands "
                f"{SCHEMA_VERSION} and will not write a record it cannot represent"
            )
        return cls(
            book_id=d["book_id"], title=d["title"],
            authors=tuple(d.get("authors") or ()),
            status=d.get("status", "to_read"),
            owned=d.get("owned"),
            added_at=d.get("added_at"),
            added_at_source=d.get("added_at_source", "manual"),
            readings=tuple(Reading.from_dict(r) for r in (d.get("readings") or ())),
            categories=tuple(d.get("categories") or ()),
            subjects=tuple(d.get("subjects") or ()),
            page_count=d.get("page_count"),
            first_published=d.get("first_published"),
            edition_published=d.get("edition_published"),
            isbn10=d.get("isbn10"), isbn13=d.get("isbn13"),
            cover_ref=d.get("cover_ref"),
            source=dict(d.get("source") or {"provider": None, "external_id": None, "url": None}),
            setting=Setting.from_dict(d.get("setting")),
            sessions=tuple(d["sessions"]) if d.get("sessions") is not None else None,
            metadata_updated_at=d.get("metadata_updated_at"),
            schema_version=version,
        )

    def with_(self, **changes) -> "BookRecord":
        return replace(self, **changes)


@dataclass(frozen=True)
class WriteResult:
    book_id: str
    created: bool
    record: BookRecord


@dataclass(frozen=True)
class LibraryQuery:
    text: str | None = None
    status: str | None = None
    owned: bool | None = None
    owned_filter: bool = False
