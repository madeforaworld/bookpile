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

## Status: Phase 0, in progress

This repository is early and deliberately incomplete. What is here is real; what
is not here is listed honestly.

**Present**

| | |
|---|---|
| `docs/METRICS.md` | The metrics catalogue — 25 entries, each with data requirements, chart form, tier and acceptance test. Normative. |
| `fixtures/synthetic-library.json` | 30 invented books exercising re-reads, abandonment, unknown ownership and missing fields. |
| `site/index.html` | A working demo dashboard. No backend — every chart is computed in the browser from the fixture. |
| `scripts/privacy-check.js` | The release gate. Runs clean on this tree. |

**Not yet written**

`spec/` (schema, intents, API contract) · `conformance/` (the test vectors) ·
`safety/` (allowlist, validation, idempotency) · `onboarding/` ·
`reference/` (the runnable implementation) · adapters · the bot.

The vectors are the part that matters most and the part that does not exist yet.
Until they do, this is a well-specified idea rather than a working system.

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
