# API contract

Derived from `docs/METRICS.md`. The metrics decide what the API exposes.

| Endpoint | Serves | Must expose |
|---|---|---|
| `GET /summary` | M01–M05 | counts by status, rating aggregate + excluded count, **declared capabilities** |
| `GET /catalogue` | M10–M13, M30–M31 | full records, nulls preserved |
| `GET /chronology` | M06–M09, M20–M21, M27 | per-**reading** records with book id and outcome, period-bucketed |
| `GET /distributions` | M22–M23, M25, M32 | pre-bucketed histograms with explicit bucket edges |
| `GET /setting` | M26–M27 | publication year, anchor year, kind, exclusion counts |
| `GET /quality` | M30–M32 | per-field non-null counts and denominators |

## Three rules

**Nulls serialize as `null`.** Never `0`, never `""`, never an omitted key.
This is where "missing is not zero" dies if you are careless.

**Every exclusion is counted.** An endpoint that filters records returns the
count it dropped and why, so the UI can caption honestly rather than presenting
a partial set as complete.

**`/summary` reports capabilities.** The dashboard needs to know whether the
store can supply full reading history, so it can gate metrics rather than
rendering a truncated history as though it were whole.

## Chronology shape

`/chronology` returns readings, not books — the distinction that makes a re-read
countable:

```json
{
  "readings": [
    { "book_id": "lacquer-cabinet", "started_at": "2025-01-04",
      "finished_at": "2025-01-19", "outcome": "finished", "rating": 4 },
    { "book_id": "lacquer-cabinet", "started_at": "2026-02-20",
      "finished_at": "2026-03-06", "outcome": "finished", "rating": 5 }
  ],
  "excluded": { "no_dates": 6 }
}
```
