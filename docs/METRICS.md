# Metrics

This is a **menu, not a dashboard.**

Bookpile does not ship one fixed set of charts. Selection happens in three layers, and only one involves a choice:

1. **Tier gating — automatic.** What the user records determines what is possible. A metric whose data is absent is never offered; an empty chart is worse than a missing one.
2. **The default set — what you get for answering nothing.** M01–M04, M06, M10, M30. Seven things, buildable from title, author, status and dates.
3. **Progressive disclosure — the real selection.** Once a dashboard exists, the build offers what the data would unlock: *"400 books, no setting recorded — that would give you this."* Concrete, and answerable, in a way the same question is not during setup.

### Widget packs

Tier gating asks *what have you recorded*. Packs ask a blunter question: **what
do you actually read?**

| Pack | Offered when | Widgets |
|---|---|---|
| **Standard** | Always | M01–M04, M06, M08, M10, M11, M30 |
| **Fiction** | Any book with `form: fiction` | M26, M27, **M28** |
| **Non-fiction** | Any book with `form: nonfiction` | **M33**, **M34** |

A novel reader and a history reader want genuinely different things. *"Which
centuries do my stories live in"* is meaningless for a shelf of biographies;
*"how out of date are my sources"* is meaningless for fiction. A library
containing both gets both packs; a library where `form` is unknown gets the
standard pack only, and is offered the others once the field is populated.

This catalogue is written for the **agent**, not the user. Nobody is asked whether they would like a horizontal bar chart; they are asked what they want to know, and at most once.

This file is normative for two audiences: the agent building a dashboard, and anyone implementing the projection API. **It is written before `spec/API_CONTRACT.md`**, because the metrics determine what the API must expose, not the other way round.

## How to read an entry

Every metric specifies:

| Field | Meaning |
|---|---|
| **ID** | Stable identifier. Referenced by the onboarding decision map and the conformance vectors. |
| **Answers** | The question in the reader's words. If you cannot state it this way, the metric does not belong here. |
| **Requires** | Schema fields that must be non-null for the metric to render at all. |
| **Form** | The chart type, chosen by the data's job. Not negotiable per-install — a bar chart does not become a donut because someone prefers donuts. |
| **Colour job** | Categorical (identity), sequential (magnitude), diverging (polarity), or none. |
| **Tier** | The minimum tracking depth at which this becomes available. See below. |
| **Acceptance** | What the conformance vector asserts. |

## Tiers

An install only offers metrics its data can support. Advertising a chart that renders empty is worse than omitting it.

| Tier | The user records | Metrics unlocked |
|---|---|---|
| **T0 — Presence** | Title, author, status | M01, M02, M04, M10, M11, M13, M30, M32 |
| **T1 — Dates** | + `added_at`, `readings[]` dates | M03, M06, M07, M08, M09, M20 |
| **T2 — Judgement** | + `rating`, `owned` | M05, M12, M22, M31 |
| **T3 — Bibliographic** | + `page_count`, `first_published` | M21, M23, M24, M25 |
| **T4 — Setting** | + `setting.anchor_year`, `setting.kind` | **M26**, M27, **M28** |
| **Form** | `form` on any record | M35, and pack eligibility above |

M07b sits outside the ladder: it needs `sessions[]`, which is an optional extension rather than a tier.

T4 is the tier no other book tracker reaches, and M26 is the reason to reach it.

## Global rules

1. **Every chart renders from `fixtures/synthetic-library.json`.** No metric may be demonstrated, screenshotted, or tested against real data. This is a release gate, not a preference.
2. **No dual-axis charts.** Two measures of different scale become two charts, small multiples, or an indexed series. Books-finished and pages-read never share a plot.
3. **Categorical palettes are validated, not eyeballed.** Run the validator; fix every FAIL before shipping. A contrast WARN obliges visible direct labels or a table view.
4. **Scatter, bubble and small-multiple forms cap at three categorical series.** Past three, fold into "Other" or facet.
5. **Sequential means one hue, light to dark. Diverging means two hues with a neutral midpoint.** Never a rainbow.
6. **Missing is not zero.** A metric must visibly distinguish "no data" from "a value of nought". A library with no ratings shows an empty state, not a bar of height zero.
7. **Every chart has a table view.** It is the accessibility floor and the relief mechanism for low-contrast series.
8. **Text wears text tokens, never the series colour.**

---

## Schema gaps found while writing this file — resolved

> [!note]
> Drafting the metrics before the API surfaced three problems with the schema. All three are now fixed in `spec/SCHEMA.md` at v1, before any vectors froze. Recorded here because the fixes constrain the catalogue below.

**1. `added_at` added.** Set once on first write, never updated; `metadata_updated_at` moves and could not serve. M08 (shelf time) was unbuildable without it. Imported records carry `added_at_source: "import"`, and any metric derived from an imported date must caption it — an import artefact is not a reading habit.

**2. `readings[]` is now authoritative.** A single date triple meant `finished → reading → finished` silently destroyed the first completion, corrupting M05, M06 and M20. Each entry is `{started_at, finished_at, outcome, rating}`; top-level `started_at`, `finished_at` and `rating` survive as **derived** projections of the latest reading. Every metric over completions iterates readings, not books — this is the single largest change to the catalogue.

**3. M07 stays a completion calendar.** Session data (`sessions[]` of `{date, pages}`) is an optional extension most users will never record, so the default calendar is named honestly rather than implying activity it cannot see. M07b below covers the session case.

**Adapter degraded mode.** Adapters that cannot store arrays declare `capabilities: {readings: "latest-only"}` and store the latest reading plus `reading_count`. Metrics requiring full history gate off for those installs. Declaring the limitation is legitimate; silently dropping a re-read is a vector failure.

---

## Headline numbers

Single current values. A stat tile, never a one-bar bar chart.

### M01 · Library size
**Answers** How many books are in here? · **Requires** any record · **Form** Stat tile · **Colour** None · **Tier** T0
**Acceptance** Count equals fixture record count, including `to_read` and `reference`.

### M02 · Currently reading
**Answers** What am I in the middle of? · **Requires** `status` · **Form** Stat tile with title list · **Colour** None · **Tier** T0
**Acceptance** Counts `status == reading` only; `paused` is excluded and surfaced separately.

### M03 · Finished this year
**Answers** How am I doing this year? · **Requires** `readings[].finished_at` · **Form** Stat tile · **Colour** None · **Tier** T1
**Acceptance** Counts **completions, not books** — a book read twice this year counts twice, and the tile says "12 finished across 11 books" whenever the two differ. Year boundary resolved in the user's configured timezone, not UTC.

### M04 · Abandonment rate
**Answers** How often do I give up? · **Requires** `readings[].outcome` · **Form** Stat tile · **Colour** None · **Tier** T0
**Acceptance** `abandoned / (finished + abandoned)` over reading **outcomes**. `in_progress` readings are excluded from both terms — an unfinished book is not yet an abandoned one. A book abandoned once and later finished contributes to both numerator and denominator, which is the truthful account.

### M05 · Mean rating
**Answers** Am I generous? · **Requires** `readings[].rating` · **Form** Stat tile + distribution sparkline · **Colour** None · **Tier** T2
**Acceptance** Averages the **latest non-null rating per book**, not every rating ever given, so a re-read does not double-weight a book. Unrated books are excluded and the tile states how many. Never impute.

---

## Change over time

### M06 · Books finished per period
**Answers** Am I reading more or less than I was? · **Requires** `readings[].finished_at` · **Form** Bar (column) · **Colour** Sequential, single hue · **Tier** T1
**Acceptance** Iterates readings, not books, so a re-read appears in the period it was actually finished. Periods with zero completions render as a visible empty slot, not a gap in the axis. On a `latest-only` adapter this metric is gated off for any period before the latest reading, because the history is not there to plot.

### M07 · Completion calendar
**Answers** What does my reading year look like? · **Requires** `readings[].finished_at` · **Form** Calendar heatmap · **Colour** Sequential, single hue · **Tier** T1
**Acceptance** The empty state (no completions) renders a full grid at step zero, not a blank box. Labelled "books finished", never "reading activity" — it can only see completions. A day with two completions is a darker step, not two squares.

### M07b · Reading activity calendar *(optional extension)*
**Answers** Which days did I actually read? · **Requires** `sessions[]` · **Form** Calendar heatmap · **Colour** Sequential, single hue · **Tier** T1 + sessions
**Acceptance** Offered **only** when the install records sessions. A build must not present M07 as though it were M07b.

### M08 · Shelf time
**Answers** How long do books wait before I start them? · **Requires** `added_at`, first `readings[].started_at` · **Form** Histogram · **Colour** Sequential, single hue · **Tier** T1
**Acceptance** Measured to the **first** reading's start, not the latest — a re-read does not reset shelf time. Books never started are excluded and reported as a separate count: they have no shelf time yet, which is not a shelf time of zero. Records with `added_at_source: "import"` are captioned as such, since their wait time predates the library.

*This is the quietly revealing one. Most trackers can tell you what you read; few can tell you what you meant to read and didn't.*

### M09 · Cumulative library
**Answers** How has the pile grown? · **Requires** `added_at` or `finished_at` · **Form** Line / area, single series · **Colour** Sequential · **Tier** T1
**Acceptance** Monotonic non-decreasing. A decrease indicates a projection bug and must fail the vector.

---

## Composition

### M10 · Status breakdown
**Answers** Where is everything? · **Requires** `status` · **Form** Horizontal bar, sorted by count · **Colour** Sequential, single hue · **Tier** T0
**Acceptance** All six statuses present in the output even at count zero, so the reader can see what they are not using.

*Deliberately not a six-hue categorical chart. Status counts are a magnitude comparison, and one hue reads better than six.*

### M11 · Shelves and categories
**Answers** What kind of reader am I? · **Requires** `categories` · **Form** Horizontal bar or treemap · **Colour** Sequential · **Tier** T0
**Acceptance** A book in two categories counts once in each; the total therefore exceeds the library size, and the caption says so.

### M12 · Ownership
**Answers** What do I actually own? · **Requires** `owned` · **Form** Three-segment stacked bar · **Colour** Categorical (3) · **Tier** T2
**Acceptance** **Three segments, always: owned, not owned, unknown.** Collapsing `null` into "not owned" is a spec violation and the vector must fail it.

*The clearest expression of the "missing is not false" invariant anywhere in the UI.*

### M13 · Top authors
**Answers** Who do I keep coming back to? · **Requires** `authors` · **Form** Horizontal bar · **Colour** Sequential · **Tier** T0
**Acceptance** Multi-author books count once per author. Ties broken alphabetically, so the chart is stable between rebuilds.

---

## Distributions

### M20 · Days to finish
**Answers** How fast do I read? · **Requires** `readings[].started_at`, `readings[].finished_at` · **Form** Histogram · **Colour** Sequential · **Tier** T1
**Acceptance** One data point **per completed reading**, so a re-read contributes its own duration. Readings with `outcome: abandoned` are excluded — an abandoned book has no finish time. Same-day completions land in a visible first bucket, not an off-axis zero.

### M21 · Pages per period
**Answers** How much did I actually get through? · **Requires** `finished_at`, `page_count` · **Form** Bar, **separate chart from M06** · **Colour** Sequential · **Tier** T3
**Acceptance** Books without a page count are excluded and counted in a caption. Never estimate a page count.

### M22 · Rating distribution
**Answers** How do I use the scale? · **Requires** `rating` · **Form** Histogram · **Colour** Sequential · **Tier** T2
**Acceptance** Renders the full scale including unused values.

### M23 · Page count distribution
**Answers** Do I prefer short or long books? · **Requires** `page_count` · **Form** Histogram · **Colour** Sequential · **Tier** T3

---

## Relationships

### M24 · Rating against length
**Answers** Do I reward long books? · **Requires** `rating`, `page_count` · **Form** Scatter · **Colour** Categorical, max 3 · **Tier** T3
**Acceptance** No trend line unless the implementation also reports n and states the method. A regression drawn through 30 points is decoration, not evidence.

### M25 · Publication era
**Answers** How old is my reading? · **Requires** `first_published` · **Form** Histogram by decade · **Colour** Sequential · **Tier** T3

### M26 · Three clocks — written against set
**Answers** *When were these books written, and when are they set?*
**Requires** `first_published`, `setting.anchor_year`, `setting.kind` · **Form** Scatter with reference diagonal · **Colour** Categorical, exactly 3 · **Tier** T4

The x-axis is publication year; the y-axis is the year the story is set. The diagonal `y = x` is the present tense.

- **On the line** — contemporary: written about its own moment.
- **Below** — historical: the author looking back.
- **Above** — speculative: the author looking forward.
- **Distance from the line** is how far the author was reaching.

**Acceptance**
- Books with `setting.kind == "fictional"` have no real-world anchor year and are **excluded from the plot**, then reported as a count beneath it. Plotting an invented world at year zero is a spec violation.
- Exactly three series (historical, contemporary, speculative), satisfying the all-pairs three-series cap.
- All three series are directly labelled, satisfying the relief rule for the low-contrast series.
- The diagonal is drawn as chart chrome, in the axis token — never in a series colour.

> This is the chart no mainstream tracker can draw, because none separates publication time from narrative time. It is the argument for the schema, made visually.

### M27 · Setting kind over reading time
**Answers** Has my taste in eras drifted? · **Requires** `setting.kind`, `finished_at` · **Form** Small multiples, one panel per kind · **Colour** Sequential within panel · **Tier** T4
**Acceptance** Faceted rather than a four-series stack, because four categorical series exceed the safe cap for this form.

### M28 · Setting timeline
**Answers** Which centuries do my novels live in? · **Requires** `form: fiction`, `setting.anchor_year` · **Form** Column chart, one band per century · **Colour** Sequential · **Tier** T4 · **Pack** Fiction
**Acceptance** Bands are **contiguous** from the earliest to the latest century — an empty century in the middle renders as a visible zero band, not a gap, because the gap is the finding. Non-fiction is excluded even when it carries an anchor year. Invented worlds are excluded and counted separately.

*The companion to M26. Where the scatter shows how far each author reached, this shows the shape of a collection: whether someone lives in one century or ranges across six.*

### M33 · Subjects
**Answers** What is my non-fiction actually about? · **Requires** `form: nonfiction`, `subjects` · **Form** Horizontal bar · **Colour** Sequential · **Pack** Non-fiction
**Acceptance** Counts **non-fiction only** — a novel tagged with an imported subject must not appear. Reports distinct-subject count alongside the top N so a long tail is visible rather than hidden by truncation. Never merges `subjects` with `categories` (I2).

### M34 · Source recency
**Answers** How old is what I am learning from? · **Requires** `form: nonfiction`, `first_published` · **Form** Column histogram by age · **Colour** Sequential · **Pack** Non-fiction
**Acceptance** Offered for non-fiction only. A twenty-year-old novel is not a defect; a twenty-year-old book on a moving subject may be, and the metric would be actively misleading applied to fiction. Books with no publication year are excluded and counted.

### M35 · Fiction and non-fiction
**Answers** What is the shape of my library? · **Requires** `form` · **Form** Three-segment stacked bar · **Colour** Categorical (3)
**Acceptance** **Three segments, always: fiction, non-fiction, unknown.** Same rule as M12 — inferring `form` from a shelf name is a spec violation. Unknown is a real answer.

---

## Data quality

### M30 · Field completeness
**Answers** What does my library not know about itself? · **Requires** any record · **Form** Horizontal bars, one per field · **Colour** Sequential · **Tier** T0
**Acceptance** Reports the share of records with a non-null value for each of `page_count`, `isbn13`, `first_published`, `setting.anchor_year`, `rating`, `owned`. Never counts `null` as a value.

### M31 · Unknown ownership
**Answers** What do I need to check the shelf for? · **Requires** `owned` · **Form** Stat tile + list · **Colour** None · **Tier** T2

### M32 · Metadata staleness
**Answers** What has not been refreshed? · **Requires** `metadata_updated_at` · **Form** Histogram by age · **Colour** Sequential · **Tier** T0

*A dashboard that is honest about what it does not know is more trustworthy than one that quietly fills the gaps. Data-quality metrics are a feature, not an admission.*

---

## API implications

Each selected metric obliges the projection API to expose its inputs. `spec/API_CONTRACT.md` is derived from this table, not written independently.

| Endpoint | Serves | Must expose |
|---|---|---|
| `GET /summary` | M01–M05 | counts by status, rating aggregate + excluded count |
| `GET /catalogue` | M10–M13, M30–M31 | full records with explicit nulls preserved |
| `GET /chronology` | M06–M09, M20–M21, M27 | **per-reading** date records, period-bucketed, each carrying its book id and outcome |
| `GET /distributions` | M22–M23, M25, M32 | pre-bucketed histograms with bucket edges |
| `GET /setting` | M26–M28 | publication year, anchor year, kind, century bands, exclusion counts |
| `GET /subjects` | M33 | non-fiction subject counts, distinct total, exclusions |
| `GET /recency` | M34 | non-fiction age buckets with edges, median age |
| `GET /quality` | M30–M32 | per-field non-null counts and denominators |

**Three contract rules.** Nulls must survive serialization as `null` — never as `0`, `""` or an omitted key, or the "missing is not zero" invariant dies at the API boundary. Every endpoint that excludes records must return the exclusion count alongside the data, so the UI can caption it truthfully. And `/summary` must report the store's declared `capabilities`, so the dashboard knows which metrics to gate off rather than rendering a partial history as though it were complete.

## Conformance vectors

Each metric contributes at least four vectors:

1. **Happy path** — the synthetic fixture in, known values out.
2. **Empty** — no qualifying records; asserts an empty state rather than a zero.
3. **Null-handling** — records with the required field missing; asserts exclusion plus an exclusion count.
4. **Re-read** — a book with two readings; asserts the metric counts completions or books deliberately, per its acceptance clause, rather than by accident.

Three metrics carry a fifth, because each has a failure mode that looks like success:

- **M12** must fail if `null` ownership is folded into "not owned".
- **M26** must fail if `fictional`-kind books appear in the plot.
- **M08** must fail if shelf time is measured to the *latest* reading rather than the first — a re-read must not reset how long the book originally waited.
