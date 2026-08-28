# Decision map

Resolved value → what it changes in the build.

## Storage

| Value | Adapter | Vectors that apply |
|---|---|---|
| `markdown` | `MarkdownVaultRepository` | `storage.json` (full) |
| `sqlite` | `SQLiteRepository` | `storage.json` (full) |
| `sheets` | `GoogleSheetsRepository` | `storage.json` minus multi-reading round-trip; **must declare `readings: "latest-only"`** |
| existing system | generated adapter | `storage.json` (full) — a generated adapter gets no exemption |

## Intake

| Value | Build | Notes |
|---|---|---|
| `cli` | `intake/cli.py` | No credentials, always available |
| `telegram` | `intake/telegram.py` | Long polling. Numeric allowlist required and non-empty, or startup fails |
| `discord` / `email` | not shipped | Generate against the `IntakeAdapter` port; `safety.json` still applies |

## What they want to know → metrics

Free text from Q3 maps to IDs. Match on intent, not keywords.

| They said something like | Metrics |
|---|---|
| *"am I reading more than last year"* | M03, M06, M09 |
| *"what do I keep starting and not finishing"* | M04, M08, M20 |
| *"how much of what I own have I read"* | M12, M31, M10 |
| *"what kind of reader am I"* | M11, M13, M25 |
| *"do I like long books"* | M23, M24 |
| *"when are my books set"* | **M26**, M27 (requires T4) |
| *"what's missing from my library data"* | M30, M31, M32 |
| skipped | M01–M04, M06, M10, M30 |

A metric whose tier is unmet is **not** built, even if asked for. Offer it
instead: *"that needs setting years, which you don't record yet."*

## Write authority

| Value | Behaviour |
|---|---|
| `propose` | Every mutation is shown and confirmed. **Default.** |
| `confirm` | Destructive operations confirmed; adds and status changes go through |
| `free` | No confirmation. **Only ever `asked`, never inferred or defaulted.** |
