# AGENTS.md

Instructions for a coding agent working in this repository.

## What you are building

Bookpile is an **executable specification**, not an application. The deliverable is
the spec plus the conformance vectors; a reference implementation exists only as
evidence the spec is buildable.

When someone points you at this repo to build them a reading system, you are not
copying a template. You are reading the spec, inspecting *their* setup, and
generating an implementation that passes the vectors.

## Current state — read before planning

Phase 0, partial. `docs/METRICS.md`, `fixtures/` and `site/` exist. **`spec/`,
`conformance/`, `safety/`, `onboarding/` and `reference/` do not exist yet.**

Do not pretend otherwise, and do not generate a system claiming conformance to
vectors that have not been written. If asked to build the full thing today, say
what is missing first.

## Onboarding: look before you ask

An earlier draft of this project specified nine setup questions. That was wrong.
Most are answerable by inspection, and interrogating someone is the lazy route to
customization — it makes them describe a system you could have read.

Resolve every setup decision to a value **plus a source**: `known` (prior context
or a project instruction file), `observed` (you looked this session), `default`
(the spec's), or `asked`.

Ask only when impact is high *and* confidence is low:

|  | Low impact | High impact |
|---|---|---|
| **Confident** | Apply silently | Apply, but show it |
| **Unsure** | Take the default | **Ask** |

Then present **one summary** of every decision, tagged by source, that the person
can correct. A wizard that arrives already filled in, not an interrogation.

**A zero-question path must work.** If someone says "just set it up," infer
everything, take every default, and show them a working dashboard.

Two rules that keep this honest:

- **Show every inference.** Your memory of someone's setup can be months stale.
  Acting silently on a remembered fact is how a bot writes to the wrong directory.
- **Never infer a safety decision toward permissive.** Write authority, allowlist
  membership and dashboard exposure either take the safe default or get asked
  outright — never resolved by confidence.

## Hard rules

1. **Never generate the safety layer.** Allowlist, intent validation, idempotency
   and the privacy scanner are fixed, tested code. Copy them; do not improvise a
   trust boundary from prose.
2. **Only validated named operations may mutate storage.** Natural language is
   untrusted input. Model output is an untrusted proposal. Never generate a shell
   command, SQL statement, file path or patch from an inbound message.
3. **Missing is not false and not zero.** `owned: null` means unknown. Folding it
   into "not owned" is a spec violation, not a display choice.
4. **`readings[]` is authoritative.** Top-level `started_at` / `finished_at` /
   `rating` are derived from the latest reading. Never author them directly.
5. **Every chart renders from `fixtures/synthetic-library.json`.** Never
   demonstrate, screenshot or test a metric against someone's real library.
6. **Run `scripts/privacy-check.js` before any commit.** It is a gate, not advice.
7. **Never make this repository public, push, or change visibility** without the
   owner's explicit approval in the current conversation.

## Chart rules

`docs/METRICS.md` is normative. Chart form follows the data's job and is not a
per-install preference. No dual-axis charts. Categorical palettes are validated
with a tool, never eyeballed. Scatter and other all-pairs forms cap at three
series. Sequential means one hue light-to-dark; diverging means two hues with a
neutral midpoint.

## Verify, then report

Run things. Report actual output, including failures. Do not describe a test suite
as passing that you have not executed.
