# Record schema — v1

Normative. An implementation that violates anything here is not Bookpile,
regardless of how it looks.

## The record

```yaml
schema_version: 1
book_id: "stable-slug"        # stable, opaque, never reused
title: "Example Book"
authors: ["Example Author"]   # ordered; may be empty, never null
status: "to_read"             # to_read | reading | finished | paused | abandoned | reference
owned: null                   # true | false | null (unknown)

added_at: "2026-08-28"        # set once on first write; NEVER updated
added_at_source: "manual"     # manual | import

readings:                     # ordered oldest -> newest, one per pass through the book
  - started_at: null          # ISO date or null
    finished_at: null         # ISO date or null
    outcome: "in_progress"    # in_progress | finished | abandoned
    rating: null              # 1-5 integer or null

# DERIVED — a projection of readings. Never authored directly.
started_at: null              # latest reading's started_at
finished_at: null             # latest reading's finished_at
rating: null                  # most recent non-null rating across readings

categories: []                # user's own shelves
subjects: []                  # imported/external subject terms — kept separate
page_count: null
first_published: null         # year the work was first published
edition_published: null
isbn10: null
isbn13: null
cover_ref: null
source:
  provider: "example"
  external_id: null
  url: null
setting:
  period: null                # free-text label, e.g. "Restoration London"
  anchor_year: null           # single representative year, or null
  kind: null                  # historical | contemporary | speculative | fictional
sessions: null                # optional extension: [{date, pages}] or null
metadata_updated_at: null
```

## Field rules

**`book_id`** — stable and opaque. Derived from title+author at creation, then
frozen. Renaming a book does not change its id. Never reused after deletion.

**`status`** describes the book's *current* state, not its history. A book
finished twice is `finished` with two readings. A book being re-read is
`reading` whose last reading is `in_progress`.

**`owned`** is three-valued. `null` means nobody has said. It is not `false`.

**`added_at`** is immutable. Set on the first write and never touched again.
Shelf time is measured from it. `added_at_source: "import"` marks a date that
records when the *record* arrived, not when the book did — any metric derived
from it must say so.

**`readings[]`** is authoritative. `started_at`, `finished_at` and `rating` at
the top level are a derived view, recomputed on every write. An implementation
that lets them diverge is broken.

**`setting.anchor_year`** is a real-world year. A story set in an invented world
has `kind: "fictional"` and `anchor_year: null` — it is excluded from
setting-based metrics, never plotted at zero.

**`sessions`** is optional and usually `null`. Its absence is why the reading
calendar is named a *completion* calendar.

## Three clocks

Publication time (`first_published`), narrative time (`setting.anchor_year`) and
reading time (`readings[].finished_at`) are independent. Never conflate them,
never derive one from another.

## Adapter capabilities

An adapter that cannot represent a structure declares it:

```yaml
capabilities:
  readings: "full"      # full | latest-only
```

`latest-only` stores the most recent reading plus `reading_count`. Metrics
needing complete history gate off. **Declaring a limitation is legitimate;
silently discarding a re-read is a conformance failure.**

## Versioning

Every record carries `schema_version`. A reader encountering a higher version
than it understands must refuse to write rather than silently drop fields.
