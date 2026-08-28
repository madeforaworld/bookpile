# Make it look like yours

The dashboard is **yours to restyle**. Every colour, typeface and radius comes
from a design token — there is not a single hard-coded colour in the markup — so
changing the look means editing one block, not hunting through a stylesheet.

## The tokens

All defined on `:root` in `site/index.html`.

| Role | Tokens |
|---|---|
| Surfaces | `--ground` (page), `--card` (panels and chart surface) |
| Ink | `--ink`, `--ink-2`, `--ink-3` |
| Lines | `--rule`, `--axis`, `--ring` |
| Structure | `--structure`, `--structure-2` — the UI accent, deliberately *not* a chart colour |
| Chart series | `--s1`, `--s2`, `--s3` — categorical, for telling things apart |
| Chart ramp | `--seq-100` … `--seq-650` — sequential, light to dark, for magnitude |
| Type | `--font-display`, `--font-body`, `--font-mono` |
| Layout | `--wrap` |

Change those values and the whole page re-themes: charts, chat bubbles, stat
tiles, tables, everything.

## Three theme states, not two

A viewer is in one of three states, and all three need to work:

```css
:root { /* complete light palette */ }

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* redefine the same tokens */ }
}

:root[data-theme="dark"] { /* redefine again, so a toggle wins both ways */ }
```

The default "system" setting stamps **nothing** on the root element, so a colour
defined only inside a `[data-theme]` block never applies for most viewers. That
is the classic unreadable-page bug: one theme's text on the other theme's
ground.

## Change freely

Palette · typefaces · radii and spacing · card and chat styling · layout and
section order · the whole visual identity. Make it warm, brutal, monochrome,
maximalist — none of it touches how the data works.

## Do not change

These are not aesthetic preferences:

- **The chart form.** Form follows the data's job. A bar chart does not become a
  donut because donuts look nicer; `docs/METRICS.md` is normative on this.
- **Empty states.** "No data" must never render as a value of zero. That is
  invariant I1, and it is the difference between an honest chart and a lying one.
- **Exclusion captions.** If a chart drops records, it says so and says how many.
- **Direct labels on the scatter.** They are the accessibility relief for a
  low-contrast series, not decoration.
- **Table views.** The accessibility floor.

## If you swap the chart colours

The series colours are not chosen by taste. They are validated for
colour-vision deficiency, for separation under normal vision, and for contrast
against both surfaces.

If you replace `--s1`/`--s2`/`--s3`, re-validate them. Rules that must still
hold:

- **Scatter and other all-pairs forms cap at three series.** Past three, fold
  into "Other" or facet.
- **Sequential means one hue, light to dark.** Never a rainbow.
- **A series colour never carries meaning alone** — legend or direct label,
  always.
- Any series below 3:1 against its surface needs visible labels or a table view.

## Asking an AI to restyle it

This prompt changes the look without touching anything load-bearing:

```text
Restyle only the presentation layer of this dashboard.

Read first: docs/THEME.md, docs/METRICS.md.

Do not:
- change the record schema, the API shapes, or any projection logic;
- change which chart form a metric uses;
- remove empty states, exclusion captions, direct labels, or table views;
- add analytics, telemetry, remote fonts, CDNs or third-party requests;
- embed real personal data, credentials, hostnames or filesystem paths.

Use only fixtures/synthetic-library.json. Keep all three theme states working:
system-light, system-dark, and an explicit data-theme stamp in both directions.
Put every visual choice in a design token and document it here.

Desired look: <describe it in your own words>

Before finishing: open the page, check it at 1280 and at 400 wide, in light and
dark, and confirm no console errors and no horizontal scrolling. Report what you
actually saw.
```
