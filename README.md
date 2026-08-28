# Bookpile

**For people who love books and want to know what they have actually been reading.**

Tell it what you finished, the way you would tell a friend. It keeps the data in
a library that stays yours.

![Using Bookpile: a Telegram conversation, and the seven steps each message passes through](docs/images/how-it-works.png)

Every reply in that transcript is real output from the reference implementation.

## Why this exists

Reading apps want your library to live inside them. Bookpile does the opposite:
it agrees on a **shape** for your reading data and leaves the storage to you — a
folder of notes, a database file, a spreadsheet, whatever you already use.

Two people can run builds that share no code at all and still hand each other a
library without losing anything, because both honour the same record contract.

> The test of success is an export and re-import, not a resemblance.

Underneath, Bookpile is a specification, a conformance suite and a fixed safety
core, so a coding agent can inspect the setup you already have, build something
shaped to it, and **prove the result correct against portable test vectors**.

## Try it in thirty seconds

```bash
git clone https://github.com/madeforaworld/bookpile
cd bookpile
./scripts/check.sh                       # privacy gate + 43 tests + 58 vectors
python3 -c "
import sys; sys.path[:0] = ['.', 'reference']
from bookpile.adapters import SQLiteRepository
from bookpile.service import LibraryService
from bookpile.intake.cli import CLIIntake
cli = CLIIntake(LibraryService(SQLiteRepository()))
for line in ['add The Tin Almanac by Marguerite Sowande',
             'start The Tin Almanac', 'finished The Tin Almanac', 'The Tin Almanac 4 stars']:
    print('>', line); print(' ', cli.handle(line))
"
```

No credentials, no network, no AI key. Open `site/index.html` for the live
dashboard.

## How a message becomes a record

```mermaid
flowchart LR
    M[Message] --> A[Allowlist]
    A -->|not listed| X[Silence]
    A --> P[Deterministic parse]
    P -->|no match| L[LLM proposes intent JSON]
    L --> V[Validate]
    P --> V
    V -->|invalid| R[Reject]
    V --> D{Ambiguous?}
    D -->|yes| Q[Ask, never guess]
    D --> O[One named operation]
    O --> S[(Storage)]
    S --> B[Read back]
    B --> Y[Reply]
```

Natural language is untrusted input. Model output is an untrusted proposal.
**Only validated named operations may mutate storage.**

## The widgets fit what you read

You do not get whatever charts we happened to build. A novel reader and a
history reader want genuinely different things, and both get the basics.

### The basics — everyone

Nine widgets that work for any library, however little you record. Answer
nothing during setup and this is what you get.

![Completions per year, shelf time, status, ownership, shelves, field completeness](docs/images/dashboard.png)

### If you read fiction

Stories happen somewhere in time. Because Bookpile keeps *when a story is set*
separately from *when the book was published*, it can show you the shape of your
reading across the centuries.

![Column chart of how many novels are set in each century](docs/images/fiction-pack.png)

And the chart nothing else can draw — publication year against setting year. The
diagonal is the present tense, below it is historical, above it is speculative,
and distance from the line is how far the author was reaching.

![Scatter of publication year against the year each story is set](docs/images/three-clocks.png)

Books set in invented worlds have no real-world year, so they are **excluded and
counted**, never plotted at zero.

### If you read non-fiction

Different questions entirely. Not *when is this set* but *what is it about*, and
*how old is what I am learning from*.

![Subject spread and publication-age histogram for non-fiction](docs/images/nonfiction-pack.png)

A twenty-year-old novel is not a problem. A twenty-year-old book on a moving
subject might be — which is why that widget is offered for non-fiction only.

## Where your library lives

**Examples, not a menu.** Anything that can hold a record and pass the
conformance vectors qualifies.

| | |
|---|---|
| **Markdown** | One note per book. Readable, greppable, git-friendly. Shipped. |
| **SQLite** | A single file. Easy to back up and query. Shipped. |
| **Google Sheets** | Cannot hold full re-read history, so it *declares* that limit rather than quietly dropping data. Specified. |
| **Notion, Airtable, a folder of text files…** | Anything else. A generated adapter passes exactly the same vectors — no exemptions for being bespoke. |

## Status

```
./scripts/check.sh
  privacy gate     clean
  safety tests     27 passed
  reference tests  16 passed
  vectors          58/58 passed   (sqlite and markdown)
```

**Not verified:** the Telegram network path. Its policy layer — allowlist,
idempotency, audit redaction — is tested, but nothing has spoken to the live
API, because that needs a real bot token. The source says so.

**Not built:** Sheets and PostgreSQL adapters, the projection HTTP API,
`docker compose`, a dashboard wired to a live store rather than the fixture.

## Repository

| | |
|---|---|
| `spec/` | Schema, nine numbered invariants, intents, storage port, API contract. Normative. |
| `conformance/` | 58 vectors in language-agnostic JSON, plus the runner. **The real contract.** |
| `safety/` | Allowlist, validation, idempotency, redaction. Fixed code, never generated. |
| `onboarding/` | What to inspect, what to default, the two questions worth asking. |
| `reference/` | Domain, service, adapters, intake, projection. Evidence the spec is buildable. |
| `docs/METRICS.md` | 29-entry metrics catalogue with acceptance tests and widget packs. |
| `site/` | The demo dashboard. No backend. |

All demo data is a synthetic 42-book fixture. No real reading history appears
anywhere in this repository.

## Setup asks almost nothing

An earlier draft specified nine setup questions. That was wrong — most are
answerable by inspection, and interrogating someone is the lazy route to
customization. Two questions survive, plus one optional, and **a zero-question
path must produce a working build**.

Safety decisions are never inferred toward permissive. Write authority,
allowlist membership and dashboard exposure take the safe default or are asked
outright — never resolved by confidence.

## Licence

Not yet licensed for reuse — see `LICENSE.md`. Intended Apache-2.0, pending a
dependency and provenance review.
