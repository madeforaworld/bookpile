# Storage port

Every adapter implements this and passes `conformance/vectors/storage.json`.
The domain never knows which adapter it is talking to.

```python
class LibraryRepository(Protocol):
    def capabilities(self) -> dict: ...
    def upsert_book(self, book: BookRecord) -> WriteResult: ...
    def get_book(self, book_id: str) -> BookRecord | None: ...
    def list_books(self) -> list[BookRecord]: ...
    def find_books(self, query: LibraryQuery) -> list[BookRecord]: ...
```

## Rules

**The repository owns paths.** A title never becomes a filename unsanitised.
Identifiers are slugged by the adapter; a book called `../../etc/passwd` is
stored as a slug, not a traversal.

**Writes are idempotent on `book_id`.** Upserting the same record twice is one
record. Duplicate message delivery must not duplicate rows.

**Nulls survive the round trip.** A `null` that comes back as `0`, `""` or a
missing key is a failure. This is the boundary where I1 usually dies.

**`added_at` survives.** An upsert of an existing record must not overwrite it,
even if the incoming record carries a different value.

**Derived fields are recomputed, not trusted.** The repository recomputes the
top-level triple from `readings[]` on write, whatever the caller passed.

## Conformance

An adapter is conformant when it passes the storage vectors. `latest-only`
adapters are permitted to fail the multi-reading round-trip vectors **only if**
`capabilities()` declares the limitation — the runner checks the declaration
before excusing the failure.
