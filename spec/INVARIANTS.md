# Invariants

Nine rules. Each has conformance vectors. Breaking one is a failure regardless
of how convenient it would be.

### I1 — Missing is not false and not zero
`owned: null` means unknown. An absent rating is not a zero rating. A metric
with no qualifying data shows an empty state, never a bar of height zero.

### I2 — Categories and subjects stay separate
`categories` are the user's shelves. `subjects` come from metadata providers.
Merging them destroys the distinction between what a person decided and what a
database asserted.

### I3 — Three clocks stay separate
Publication, narrative setting and reading time are never conflated or derived
from one another.

### I4 — `readings[]` is authoritative
Top-level `started_at`, `finished_at` and `rating` are derived on every write.
Never authored, never allowed to diverge.

### I5 — `added_at` is immutable
Written once. Any code path that updates it is a defect.

### I6 — Uncertain data stays uncertain
An exact date or year requires provenance. Never infer a precise value from a
vague one; a decade does not become its first year.

### I7 — Covers are replace-never by default
Binary assets are never overwritten unless the user explicitly opts in.

### I8 — Declare limitations, never drop data
An adapter that cannot represent a structure declares reduced capability. It
does not silently truncate.

### I9 — Only validated named operations mutate storage
Natural language is untrusted input. Model output is an untrusted proposal.
No inbound message ever produces a shell command, SQL string, file path or
patch.
