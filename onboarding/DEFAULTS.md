# Defaults

Taken silently when nothing is known. Every one is the safe or reversible
option.

| Decision | Default | Why |
|---|---|---|
| Canonical store | **keep what exists** | Migration is destructive and rarely wanted |
| Storage adapter | `markdown` if a vault was found, else `sqlite` | Match the person's existing world |
| Intake | `cli` | Always works, needs no credentials |
| Dashboard binding | `127.0.0.1` | Never exposed by accident |
| Dashboard auth | required if binding is not loopback | Exposure implies authentication |
| Write authority | **propose, then confirm** | See the safety rule below |
| LLM use | off; deterministic parsing only | Must stay fully functional without a key |
| Telemetry | off | Not a decision to make on someone's behalf |
| Cover replacement | off | I7: replace-never |
| Metric set | M01–M04, M06, M10, M30 | Buildable from title/author/status/dates |
| Log message bodies | off | Audit records actions, not content |
| Timezone | system | Year boundaries resolve locally, not in UTC |

## The safety rule

**Never infer a safety decision toward permissive.**

Write authority, allowlist membership and dashboard exposure are not resolved by
confidence. They take the safe default or they are asked outright. An agent that
is *sure* the user wants unconfirmed writes is still wrong to grant them
silently.
