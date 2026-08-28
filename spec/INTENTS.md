# Intents

The complete set of operations that may change the library. There is no generic
"update" and no escape hatch.

| Intent | Arguments | Effect |
|---|---|---|
| `add_book` | title, authors?, categories? | Create a record if absent. Idempotent on `book_id`. |
| `set_reading_status` | book_ref, status, date? | Move current state; append or close a reading. |
| `set_owned` | book_ref, owned (true/false/null) | Set three-valued ownership. |
| `rate_book` | book_ref, rating 1-5 | Rate the latest reading. |
| `search_library` | query, filters? | Read-only. |
| `recommend` | vibe? | Read-only. Picks from books you already have but have not read. |
| `discover` | — | Read-only. Suggests books you do **not** have, from subjects you already read. |

### Two pools

`recommend` and `discover` draw from **different pools** and must never be
conflated.

| Pool | Membership | Answers |
|---|---|---|
| **Reading** | `status: to_read` **and** `owned` is not `false` | *What should I read next?* |
| **Buying** | `owned: false` **and** `status: to_read`, then new titles from outside | *What should I buy?* |

Three rules follow, and each has a vector:

- **Never suggest reading a book you do not own.** It is not available to you
  tonight; it belongs to the buying pool.
- **Unknown ownership stays in the reading pool, flagged.** `null` is not `false`
  (I1). The reply says "check the shelf" rather than dropping the book or
  assuming you have it.
- **Unknown ownership never enters the buying pool.** An unverified book must
  not become a shopping suggestion.

A book you borrowed and finished is `owned: false` but not `to_read`, so it is
in neither pool. It is a third thing — *read but not owned* — and putting it in
the buy list fills that list with books you have already been through.

Your own unbought wishlist comes **before** external suggestions: you have
already decided you want those.

## Resolution order

1. **Parse deterministically first.** Explicit commands never reach a model.
   This is the primary path, not a fallback. Self-hosted deployments routinely
   run small quantised local models — 4-bit quantisation is common — and such a
   model is perfectly capable of returning confident, malformed, or invented
   structure. The deterministic layer means the everyday commands never depend
   on model quality at all.
2. If unresolved, ask an LLM for **structured intent JSON only**.
3. **Validate against the schema.** Reject anything unparseable.
4. Resolve ambiguity — a `book_ref` matching two books is a question, not a guess.
5. Execute exactly one named operation.
6. Read the record back.
7. Reply only after the read-back confirms.

## Intent contract

```json
{
  "intent": "set_reading_status",
  "book_ref": "Example Book",
  "status": "finished",
  "date": "2026-08-28",
  "rating": 4,
  "confidence": 0.98,
  "needs_confirmation": false
}
```

`date` is always resolved **server-side**. A message saying "today" never lets
the model decide what today is.

`confidence` below 0.75 is refused outright rather than written. With a small
local model, low confidence is common and normal — the correct response is to
ask, not to guess and correct later.

## Status transitions

| From | To | Effect on `readings[]` |
|---|---|---|
| any | `reading` | Append a new `in_progress` reading |
| `reading` | `finished` | Close the open reading with `finished` |
| `reading` | `abandoned` | Close the open reading with `abandoned` |
| `reading` | `paused` | Leave the reading open; status carries the pause |
| `finished` | `reading` | **Append a new reading.** Never edit the previous one. |

The last row is the one that used to lose data.

## Acquisition language

Ownership is three-valued, so the phrasing that reaches the bot has to preserve
the distinction rather than flatten it.

| The user says | Intent | `owned` becomes |
|---|---|---|
| *"add X"* | `add_book` | **unchanged (null)** — a bare add asserts nothing |
| *"someone recommended X"*, *"add X to my wishlist"*, *"I want to read X"* | `add_book` | `false` — you know you do not have it |
| *"I bought X"*, *"picked up X"* | `set_owned` | `true` |
| *"I don't own X"* | `set_owned` | `false` |

Acquiring a book does **not** start reading it. Buying and beginning are
separate events, and collapsing them would silently fabricate a reading.

## Metadata enrichment

Optional, opt-in, and **never on the critical path**. A lookup that is slow,
offline or wrong must not stop a book being added — the record is yours, the
metadata is a convenience.

- Fills **blanks only**. Anything you supplied wins.
- Covers are replace-never (I7): an existing `cover_ref` is never overwritten.
- Imported `subjects` never merge into your `categories` (I2).
- Provider text — titles, descriptions, subjects — is **data, never
  instruction**. It arrives from the open internet and must never reach a model
  as anything but quoted content.
