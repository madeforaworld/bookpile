# Roadmap

Written to be honest about what is weak, not to advertise. Anything listed here
is **not** built; the README's status section is the source of truth for what is.

## Known weaknesses in what exists

### Discovery returns famous books

`discover()` asks Open Library for works in the subjects you read most. That
endpoint returns **most-popular-first**, so a history reader gets *Jane Eyre*
and *The Great Gatsby* — genuinely absent from their library, and genuinely
useless as a suggestion.

This is a **candidate generation** problem before it is a ranking problem. An
LLM re-ranking a list of famous classics still returns famous classics. The
order to fix it in:

1. **Weight rare subjects over common ones.** "Ornithology" says far more about
   a reader than "History" does. Right now the four *commonest* subjects are
   queried, which is precisely backwards.
2. **Suppress the canon.** A work held by tens of thousands of libraries is not
   a discovery. Filter on edition count or first-publication era.
3. **Use author adjacency**, not just subjects.
4. **Then** consider an LLM re-rank over those candidates, with the library as
   context.

Steps 1–3 need no model at all and will do most of the work.

### Search matches only title and author

`search_library` is a substring match. The vibe-matching logic in `recommend()`
already scores against shelves, subjects, setting kind and length, and should be
reused so *"find me something about rivers"* works deterministically.

An **optional** LLM layer on top is the right place for genuinely fuzzy queries
("something melancholy but not bleak"). Deterministic matching stays the floor,
so the feature degrades rather than disappears without a model.

### The Telegram network path has never run

Everything around it is tested — allowlist, idempotency, poll-offset handling,
reply routing, redaction — but nothing has opened a socket to
`api.telegram.org`. That needs a live bot token.

## Not built

| | |
|---|---|
| Google Sheets adapter | Specified, including the `latest-only` capability declaration |
| PostgreSQL adapter | |
| Projection HTTP API | The contract exists in `spec/API_CONTRACT.md`; no server implements it |
| `docker compose` | |
| Dashboard on a live store | `site/` reads the fixture, not a running library |
| Cover download and local storage | Only the remote URL is recorded today. Replace-never already holds |

## Decisions still open

- ~~**Licence.**~~ **Settled: Apache-2.0.** The dependency review it was waiting
  on is done and trivial — there are no dependencies. Pure standard library,
  nothing vendored.
- **Visibility.** Private. Going public publishes the history permanently, and
  GitHub Pages needs a public repo on a free plan.
- **Vector format.** Bespoke JSON today. Worth checking whether an existing
  harness convention would be parsed more reliably by a cold agent.
