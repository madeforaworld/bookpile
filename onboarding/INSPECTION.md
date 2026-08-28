# Inspection

What to look at before asking anything, and what each finding implies.

Every decision resolves to a value **plus a source**: `known` (prior context or
a project instruction file), `observed` (you looked this session), `default`
(`DEFAULTS.md`), or `asked`.

## The ask/don't-ask rule

|  | Low impact | High impact |
|---|---|---|
| **Confident** | Apply silently | Apply, but show it |
| **Unsure** | Take the default silently | **Ask** |

## What to look for

| Look at | Finding | Implies |
|---|---|---|
| Working directory, `AGENTS.md`, `CLAUDE.md` | Project conventions | Existing tooling, house style |
| Markdown files with book-shaped frontmatter | An existing library | `markdown` adapter, keep as canonical |
| `.obsidian/` nearby | An Obsidian vault | Never put code or dependencies inside it |
| Fields present in existing records | What they already track | Tier, and which metrics are possible |
| `*.csv` / `*.json` exports | An import path | `added_at_source: "import"` |
| `docker --version`, `compose` | Container support | Whether to offer the composed reference |
| Environment for provider keys | LLM availability | Deterministic-only if absent |
| Host, user, whether this is a server | Where it runs | Binding, service manager |
| Existing `.env` / secret files | **Do not read them** | Note existence only, never contents |

## Reporting

Present **one summary** of every decision, tagged by source, that the user can
correct line by line. Not a sequence of prompts.

```
Storage      markdown, ./Notes/Books          observed  412 records
Canonical    keep in place                    default
Intake       telegram                         asked
Dashboard    127.0.0.1:8080, private          default
Writes       propose then confirm             default
Metrics      M01–M04, M06, M10, M30           default   (nothing recorded beyond dates)
```

## Two constraints

**Show every inference.** Prior knowledge of someone's setup can be months
stale. Acting silently on a remembered fact is how a bot writes to the wrong
directory.

**Never read secrets.** Note that a credential file exists; never open it, never
print it, never copy a value into generated config.
