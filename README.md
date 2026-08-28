# Bookpile

**An executable specification for a personal reading system.**

Bookpile is not an app you install. It is a specification, a conformance suite and
a fixed safety core — so that a coding agent can inspect the setup you already
have, build a reading companion shaped to it, and prove the result correct against
portable test vectors.

Message it *"finished The Lacquer Cabinet today, four stars"* and get a validated
record in a library you own. Where that library lives — Markdown, SQLite, a Google
Sheet, the thing you already use — is an adapter, not a decision the project makes
for you.

## Status

Phases 0–3 built and verified. The reference implementation passes the vectors
on both shipped adapters.

| | |
|---|---|
| `spec/` | Schema, invariants, intents, storage port, API contract. Normative. |
| `conformance/` | **51 vectors** in language-agnostic JSON, plus the runner. The real contract. |
| `safety/` | Allowlist, validation, idempotency, redaction. Fixed code, never generated. 27 tests. |
| `onboarding/` | Inspection, defaults, the two questions worth asking, decision map. |
| `reference/` | Domain, service, SQLite + Markdown adapters, CLI and Telegram intake, projection. 16 tests. |
| `docs/METRICS.md` | 25-entry metrics catalogue with acceptance tests. |
| `fixtures/` | 30 invented books exercising re-reads, abandonment and unknown ownership. |
| `site/` | Working demo dashboard. No backend; charts computed from the fixture. |

```bash
./scripts/check.sh          # privacy gate + 43 tests + 51 vectors
```

**Verified:** 51/51 vectors pass against both the SQLite and Markdown adapters.
43 unit tests pass. The privacy gate is clean.

**Not verified:** the Telegram network path. Its policy layer — allowlist,
idempotency, audit redaction — is covered by tests, but nothing has spoken to
the live API, because that needs a real bot token. It is marked as such in the
source.

**Not built:** Google Sheets and PostgreSQL adapters, the projection HTTP API,
`docker compose`, the dashboard wired to a live store rather than the fixture.

## The idea in one chart

Bookpile records **publication time and narrative time as separate clocks**. That
single schema decision lets it plot when a book was written against when its story
is set: the diagonal is contemporary fiction, below it is historical, above it is
speculative, and distance from the line is how far the author was reaching.

No mainstream book tracker can draw this, because none separates those clocks.
Open `site/index.html` in a browser to see it running on synthetic data.

## Why a specification instead of an app

Every self-hosted tracker hands you its data model and its dashboard. Bookpile
hands you a contract. Two installs can share no code at all — one on Markdown and
Telegram, one on a spreadsheet and a CLI — and a record exported from either still
imports into the other without loss, because both agree that `owned: null` means
*unknown* rather than *false*, and that a re-read does not erase the first reading.

The test of success is an export–import round trip, not a resemblance.

## Two paths, once it is built

- **Run the reference.** `docker compose up`. Ordinary needs, no agent required.
- **Generate a build.** Point a coding agent at `AGENTS.md`; it inspects your
  system, builds against the spec, and proves the result with the vectors.

## The rule that shapes the security model

> The more of a project an agent generates, the more rigidly fixed its safety
> layer has to be.

The allowlist, intent validation, idempotency and the privacy scanner ship as
fixed, tested code. They are never generated. Natural language is untrusted input;
model output is an untrusted proposal; only validated named operations may mutate
storage.

## Licence

Not yet licensed — see `LICENSE.md`. Intended Apache-2.0, pending a dependency and
provenance review.
