# Questions

Two, plus one optional. Everything else is inferred (`INSPECTION.md`) or
defaulted (`DEFAULTS.md`).

An earlier draft of this project specified nine setup questions. That was wrong.
Interrogating someone is the lazy route to customization — it makes them
describe a system you could have read.

## Q1 — How do you want to message it? *(required)*

Genuinely unknowable by inspection, and it changes the build.
`telegram | discord | cli | email | none`. Default `cli`, which always works.

## Q2 — Confirm the library *(confirmation, not a question)*

> "I found 412 book notes in `Notes/Books`. Use these as the library?"

Answerable in one word. If inspection found nothing, this becomes
*"I'll start a new library at `./data/library` — fine?"*

## Q3 — Anything particular you want to know about your reading? *(optional, skippable)*

Free text. Maps to metric IDs via `DECISION_MAP.md`. **Skipping is normal** and
yields the default set: M01–M04, M06, M10, M30.

Never present the metrics catalogue as a checklist. Nobody knows which charts
they want before seeing any.

## The zero-question path

If the user says "just set it up," ask nothing. Infer everything, take every
default, build, and show them a working dashboard. This path must always work.

## Ask later, not now

The valuable questions are abstract at minute zero and obvious ten minutes
later. Once a dashboard exists:

> "You have 412 books and no setting data recorded. Adding it would give you
> the written-against-set chart. Want to start capturing it?"

That is answerable. The same question during setup is not.
