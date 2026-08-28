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

## Resolution order

1. **Parse deterministically first.** Explicit commands never reach a model.
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

## Status transitions

| From | To | Effect on `readings[]` |
|---|---|---|
| any | `reading` | Append a new `in_progress` reading |
| `reading` | `finished` | Close the open reading with `finished` |
| `reading` | `abandoned` | Close the open reading with `abandoned` |
| `reading` | `paused` | Leave the reading open; status carries the pause |
| `finished` | `reading` | **Append a new reading.** Never edit the previous one. |

The last row is the one that used to lose data.
