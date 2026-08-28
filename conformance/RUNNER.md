# Running the vectors

The vectors are the contract. `runner.py` is only the harness that applies them
to the reference implementation — a build in any language is conformant when it
satisfies the same vectors, however it does so internally.

```bash
python3 conformance/runner.py                    # every suite, both adapters
python3 conformance/runner.py --suite metrics
python3 conformance/runner.py --adapter markdown
```

Exit code is non-zero if any vector fails.

## Vector format

Language-agnostic given/when/then JSON. No test framework, no Python.

```json
{
  "id": "reread-appends-never-overwrites",
  "invariant": "I4",
  "given": { "books": [ { "title": "Salt in the Wiring" } ] },
  "when":  { "messages": ["start Salt in the Wiring", "finished Salt in the Wiring",
                          "start Salt in the Wiring", "finished Salt in the Wiring"] },
  "then":  { "book": { "ref": "Salt in the Wiring", "reading_count": 2, "completions": 2 } }
}
```

Every vector names the invariant it defends (`spec/INVARIANTS.md`), so a failure
says which rule broke rather than which assertion tripped.

## `when` clauses

| Clause | Meaning |
|---|---|
| `message` / `messages` | Parse → validate → execute a named operation |
| `validate` | Validation only; asserts `then.rejected` |
| `deliver` / `deliver_twice` | Delivery with idempotency keys |
| `reload` | Reopen the store from disk — round-trip fidelity |
| `upsert_with` / `upsert_twice` | Adapter-level writes |
| `project` | Run a projection and assert its output |
| `noop` | Assert the given state itself |

## `then` clauses

`library_size` · `book` (field-by-field, plus `reading_count` and `completions`)
· `error` · `unparsed` · `rejected` · `expect` · `expect_bucket` ·
`expect_excluded` · `expect_field` · `point_count` · `status_keys` ·
`excludes_metrics` · `no_path_escape`

## Writing a new implementation against these

1. Implement the storage port. Run `--suite storage`; it runs against your
   adapter the same way it runs against the two shipped ones.
2. Implement the intents. Run `--suite intents`.
3. Implement the projection. Run `--suite metrics`.
4. Copy `safety/` verbatim. Run `--suite safety`.

A `latest-only` adapter may fail vectors marked `"requires": "readings=full"`
**only if** `capabilities()` declares the limitation. Silently dropping a
re-read is a failure, not a limitation.
