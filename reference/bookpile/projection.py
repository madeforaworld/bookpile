"""Projection — the read model behind docs/METRICS.md and the API contract.

Two rules run through everything here: nulls are never counted as values, and
every exclusion is returned alongside the data so the UI can caption honestly.
"""
from __future__ import annotations
from collections import Counter
from datetime import date

from .models import BookRecord, STATUSES

PLOTTABLE_KINDS = ("historical", "contemporary", "speculative")
DEFAULT_METRICS = ("M01", "M02", "M03", "M04", "M06", "M10", "M30")


def _year(iso: str | None) -> str | None:
    return iso[:4] if iso else None


def summary(books: list[BookRecord], capabilities: dict, *, year: str | None = None) -> dict:
    """M01–M05."""
    year = year or str(date.today().year)
    readings = [r for b in books for r in b.readings]
    finished = [r for r in readings if r.outcome == "finished"]
    abandoned = [r for r in readings if r.outcome == "abandoned"]

    in_year = [r for r in finished if _year(r.finished_at) == year]
    books_in_year = sum(
        1 for b in books
        if any(r.outcome == "finished" and _year(r.finished_at) == year for r in b.readings))

    rated = [b.rating for b in books if b.rating is not None]
    concluded = len(finished) + len(abandoned)

    return {
        "library_size": len(books),                                    # M01
        "currently_reading": sum(1 for b in books if b.status == "reading"),  # M02
        "paused": sum(1 for b in books if b.status == "paused"),
        "completions_in_year": len(in_year),                           # M03
        "books_completed_in_year": books_in_year,
        "year": year,
        "pages_in_year": sum(
            (b.page_count or 0) * sum(
                1 for r in b.readings
                if r.outcome == "finished" and _year(r.finished_at) == year)
            for b in books),
        # M04 — over outcomes, not books. in_progress excluded from both terms.
        "abandonment_rate": (len(abandoned) / concluded) if concluded else None,
        "abandoned_readings": len(abandoned),
        "concluded_readings": concluded,
        # M05 — latest rating per book, so a re-read does not double-weight
        "mean_rating": (sum(rated) / len(rated)) if rated else None,
        "rated_books": len(rated),
        "unrated_books": len(books) - len(rated),
        "capabilities": dict(capabilities),
    }


def chronology(books: list[BookRecord]) -> dict:
    """M06–M09, M20. Per reading, never per book."""
    rows, no_dates = [], 0
    for b in books:
        if not b.readings:
            no_dates += 1
            continue
        for r in b.readings:
            rows.append({"book_id": b.book_id, "started_at": r.started_at,
                         "finished_at": r.finished_at, "outcome": r.outcome,
                         "rating": r.rating, "page_count": b.page_count})
    per_year = Counter(_year(r["finished_at"]) for r in rows
                       if r["outcome"] == "finished" and r["finished_at"])
    return {"readings": rows,
            "completions_per_year": dict(sorted(per_year.items())),
            "excluded": {"never_started": no_dates}}


def shelf_time(books: list[BookRecord]) -> dict:
    """M08. Measured to the FIRST reading — a re-read does not reset it."""
    edges = [(0, 7), (8, 30), (31, 90), (91, 365), (366, None)]
    labels = ["<=1wk", "1-4wks", "1-3mo", "3-12mo", "1yr+"]
    counts = [0] * len(edges)
    never_started = 0
    imported = 0
    for b in books:
        days = b.shelf_days()
        if days is None:
            never_started += 1
            continue
        if b.added_at_source == "import":
            imported += 1
        for i, (lo, hi) in enumerate(edges):
            if days >= lo and (hi is None or days <= hi):
                counts[i] += 1
                break
    return {"buckets": [{"label": l, "count": c} for l, c in zip(labels, counts)],
            "excluded": {"never_started": never_started},
            "caveats": {"imported_added_at": imported}}


def status_breakdown(books: list[BookRecord]) -> dict:
    """M10. All six statuses present even at zero."""
    counts = Counter(b.status for b in books)
    return {"statuses": [{"status": s, "count": counts.get(s, 0)} for s in STATUSES]}


def ownership(books: list[BookRecord]) -> dict:
    """M12. Three segments, always. Unknown is never folded into not-owned."""
    return {"owned": sum(1 for b in books if b.owned is True),
            "not_owned": sum(1 for b in books if b.owned is False),
            "unknown": sum(1 for b in books if b.owned is None)}


def setting_scatter(books: list[BookRecord]) -> dict:
    """M26 — three clocks. Invented worlds are excluded, never plotted at zero."""
    points, fictional, incomplete = [], 0, 0
    for b in books:
        if b.setting.kind == "fictional":
            fictional += 1
            continue
        if b.setting.kind not in PLOTTABLE_KINDS or b.first_published is None \
                or b.setting.anchor_year is None:
            incomplete += 1
            continue
        points.append({"book_id": b.book_id, "written": b.first_published,
                       "set": b.setting.anchor_year, "kind": b.setting.kind,
                       "reach": b.setting.anchor_year - b.first_published})
    return {"points": points,
            "excluded": {"invented_world": fictional, "missing_year": incomplete}}


def quality(books: list[BookRecord]) -> dict:
    """M30. Null is never counted as a value."""
    n = len(books) or 1
    fields = {
        "first_published": lambda b: b.first_published is not None,
        "page_count": lambda b: b.page_count is not None,
        "setting_year": lambda b: b.setting.anchor_year is not None,
        "rating": lambda b: b.rating is not None,
        "owned": lambda b: b.owned is not None,
        "isbn13": lambda b: b.isbn13 is not None,
    }
    return {"fields": [
        {"field": name, "present": sum(1 for b in books if fn(b)),
         "total": len(books), "share": sum(1 for b in books if fn(b)) / n}
        for name, fn in fields.items()]}


def available_metrics(books: list[BookRecord]) -> list[str]:
    """Tier gating: never offer a metric the data cannot fill."""
    have_dates = any(r.started_at or r.finished_at for b in books for r in b.readings)
    have_added = any(b.added_at for b in books)
    have_judgement = any(b.rating is not None or b.owned is not None for b in books)
    have_biblio = any(b.page_count is not None or b.first_published is not None for b in books)
    have_setting = any(b.setting.anchor_year is not None for b in books)

    out = ["M01", "M02", "M04", "M10", "M11", "M13", "M30", "M32"]
    if have_dates:
        out += ["M03", "M06", "M07", "M09", "M20"]
    if have_dates and have_added:
        out.append("M08")
    if have_judgement:
        out += ["M05", "M12", "M22", "M31"]
    if have_biblio:
        out += ["M21", "M23", "M24", "M25"]
    if have_setting:
        out += ["M26", "M27"]
    return sorted(set(out))
