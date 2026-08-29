# Design system: Saturday Signal

Repo-wide visual rules for the Flask UI. Tokens ship at `cfb_system_maker/static/tokens/{colors,typography,spacing}.css`; the stylesheet that
consumes them is `cfb_system_maker/static/styles.css`. Change a value here, change it
in the token files — `styles.css` defines no raw hex of its own except `#fff`.

Originally delivered as a design handoff; the sections below are that document,
with paths updated to where the files actually live.

## Overview

CFB System Maker is a college-football backtesting workbench: the user composes a betting "system" out of filters (bet type, side, line range, conference, situational features), runs it against historical game and line data, and reads the result as a record, ROI, significance statistics and a profit curve. Systems can be saved, compared against each other on a holdout season, and tracked forward against this week's posted lines.

The existing app is a Flask + Jinja2 application (`cfb_system_maker/`) with server-rendered templates and a single hand-written stylesheet. **This handoff covers a visual restyle only.** Every screen, route, control and data field is unchanged from the current app — what changes is typography, color, spacing, radius, table density and control styling, all now sourced from the Saturday Signal design system.

## About the Design Files

The files in `screens/` are **design references created in HTML** — prototypes showing intended look and behavior, not production code to copy directly.

There is one important exception, called out because it changes the work substantially:

> **`screens/cfb.css` is intended to ship.** It is a drop-in replacement for the app's existing `cfb_system_maker/static/styles.css`. It deliberately preserves every class name from the original stylesheet, so the Jinja templates need **no markup changes** for the restyle to take effect. The six HTML files in `screens/` exist to show that stylesheet rendering against realistic content; they are not templates and should not be checked in.

So the task is: replace the stylesheet, then reconcile the handful of places where the templates need a small structural change (listed under **Template changes required** below). If you are instead porting this UI into a different environment (React, Vue, etc.), treat the HTML files as pixel references and the token files as the source of truth for values.

## Fidelity

**High-fidelity.** Colors, typography, spacing, radii and states are final and specified exactly. Recreate pixel-perfectly.

Two caveats on the content, not the styling:

- All numbers, team names, system names and dates in the HTML files are **realistic placeholders**, not real backtest output. Do not treat any figure as a target value.
- The screens render one representative state each. Empty states, error banners, the `missing_data` state and the filter modal are styled in `cfb.css` but not shown in the HTML files. Their class names are documented below.

## Design tokens

All tokens live in `styles.css`, which imports the three files in `tokens/`. Ship these as-is or port the values into the codebase's existing token layer. `cfb.css` consumes them exclusively through `var(--*)` — it defines no raw hex values of its own except `#fff`.

### Color

The palette is cool slate throughout. There is no warm neutral anywhere in the system.

**Signal (brand accent)**

| Token | Value | Use |
|---|---|---|
| `--signal-50` | `#EEF2F8` | — (see Known issues) |
| `--signal-100` | `#DDE5F1` | Selected filter chip / checked control background |
| `--signal-200` | `#BAC9E3` | |
| `--signal-300` | `#8AAACE` | |
| `--signal-400` | `#567298` | |
| `--signal-500` | `#2E4A6B` | **Brand primary** — buttons, active tab, focus ring, links |
| `--signal-600` | `#233856` | Button hover |
| `--signal-700` | `#192840` | Text on `--signal-100` backgrounds |
| `--signal-800` | `#0F1C2E` | |
| `--signal-900` | `#070D18` | |

**Ink (neutrals)**

| Token | Value | Use |
|---|---|---|
| `--ink-0` | `#FFFFFF` | Panel / card / table surface |
| `--ink-50` | `#EEF2F8` | Page background, table row hover, range-filter fill |
| `--ink-100` | `#E2E6EE` | Table row divider, hairline borders |
| `--ink-200` | `#CDD2DC` | Default border (1px), control border (1.5px) |
| `--ink-300` | `#A8ADB9` | Emphasized border, chart zero line, disabled text |
| `--ink-400` | `#7E8494` | Micro-labels, overlines, placeholder, footer text |
| `--ink-500` | `#5C6272` | Secondary copy, fieldset legends |
| `--ink-600` | `#424854` | Verdict copy, match-row detail |
| `--ink-700` | `#2C3038` | Theory / long-form body copy |
| `--ink-800` | `#1B1E24` | **Table header background** |
| `--ink-900` | `#111318` | Primary text |

**Semantic**

| Token | Value | Use |
|---|---|---|
| `--success-500` | `#2A7A4E` | Positive ROI, profit, winning chart segment |
| `--success-50` / `--success-700` | `#F0FAF5` / `#1A5234` | `win` pill background / text |
| `--error-500` | `#C23030` | Negative ROI, loss, losing chart segment |
| `--error-50` / `--error-700` | `#FEF3F1` / `#8A1F1F` | `loss` pill background / text |
| `--warning-500` / `--warning-50` / `--warning-700` | `#B87314` / `#FDFBF0` / `#7A4D0D` | Lookahead warning, stale-registry banner |
| `--info-50` / `--info-700` | `#EEF3FC` / `#133470` | `Search` badge |

### Typography

Three faces, loaded from Google Fonts in `tokens/typography.css`:

```
Instrument Serif   --font-display   400 + italic
Instrument Sans    --font-body      400 / 500 / 600 / 700 + italic 400
JetBrains Mono     --font-mono      400 / 500
```

**Three rules that are easy to get wrong:**

1. **Instrument Serif is reserved for 48px and up.** Heroes, covers, marketing. It appears **nowhere** in this product — every screen here tops out at a 24px heading. If you find yourself setting the serif in an app screen, that is a bug.
2. **JetBrains Mono is for stat values only** — the big numbers in metric chips, and the chart axis labels. It is **not** used in tables. (This changed late; earlier drafts had mono throughout the tables.)
3. **Tables run in Instrument Sans with `font-variant-numeric: tabular-nums`**, which is also set on `body`. That is what keeps numeric columns aligned without a monospace face.

Applied sizes:

| Element | Font | Size | Weight | Tracking | Line-height |
|---|---|---|---|---|---|
| `h1` (sidebar brand, page title) | Sans | 20px | 600 | −0.02em | 1.5 |
| `h2` (workspace heading) | Sans | 24px | 600 | −0.02em | 1.25 |
| `h3` / panel headings | Sans | 9px | 600 | 0.14em, uppercase | 1.5 |
| Body / default | Sans | 14px | 400 | 0 | 1.5 |
| Table header `th` | Sans | 9px | 600 | 0.08em, uppercase | — |
| Table cell `td` | Sans | 12px | 400 | 0 | — |
| Metric chip label | Sans | 9px | 600 | 0.14em, uppercase | — |
| Metric chip value | **Mono** | 18px | 500 | −0.04em | 1.15 |
| Quality-stat value | **Mono** | 14px | 500 | −0.04em | 1.15 |
| Fieldset legend | Sans | 10px | 600 | 0.14em, uppercase | — |
| Control / input / button | Sans | 12px | 400–500 | 0 | — |
| Result pill | Sans | 10px | 600 | 0.04em, uppercase | — |
| Chart axis | **Mono** | 10px | 400 | — | — |
| Footer disclaimer | Sans | 10px | 400 | 0 | 1.65 |

### Spacing

4px base. `--space-1` 4 · `--space-2` 8 · `--space-3` 12 · `--space-4` 16 · `--space-5` 20 · `--space-6` 24 · `--space-8` 32 · `--space-10` 40 · `--space-12` 48 · `--space-16` 64.

### Radius

Deliberately tight — the previous app used 6px everywhere.

`--radius-xs` 1px · `--radius-sm` **2px** (buttons, inputs, controls, pills, active-filter rows) · `--radius-md` **4px** (range-filter card, brand mark) · `--radius-lg` **8px** (metric chips, panels, table wrappers) · `--radius-full` 9999px (timeframe pills).

### Shadows & transitions

Only one shadow is used in these screens: `--shadow-focus` (`0 0 0 3px var(--color-focus-ring)`) on focused inputs. Panels rely on 1px borders rather than elevation.

`--transition-fast` 150ms ease-out is used on every interactive state change.

## Screens

All six live in `screens/` and share `cfb.css`. Two shell types:

- **`.app-shell`** — `display: grid; grid-template-columns: 320px minmax(0, 1fr)`. Used by System Editor and Past Matches. Left column is a sticky, independently-scrolling filter panel (`position: sticky; top: 0; max-height: 100dvh; overflow-y: auto; overflow-x: hidden`).
- **`.dash-shell`** — centered column, `max-width: var(--container-2xl)` (1440px), `padding: 24px 32px`, `gap: 20px`. Used by My Systems, Compare, Bet Log, Search Run.

Both are followed by `.site-footer`, a full-width white bar with the responsible-gambling disclaimer at 10px `--ink-400`.

---

### 1. System Editor — `screens/system-editor.html`

Maps to `templates/index.html`, `tab=graph`. Design width 1440px.

**Purpose.** Compose a system in the left panel, read its backtest in the right.

**Left panel (320px).** In order: brand lockup (38px `--signal-500` square with mono "CFB", then `h1` and a season range); Bet Type select; Spread Side segmented pair; Position checkbox pair; a 2-column `.field-grid` of five filter-launcher buttons (Season, Week, Team, Conference, Sportsbook — Sportsbook spans both columns via `.full-width`); the Line Range card; the Feature Filters section; a Theory textarea; the form actions; and the Load System block.

- **`.filter-launcher`** — the app's characteristic control. Full-width, left-aligned, 34px tall, 1.5px `--ink-200` border, 2px radius, white. **Must have `min-width: 0` and `text-overflow: ellipsis`** — the labels carry filter values ("Spread Between −21 and −7") and overflowed the panel before this was added. When a filter is set, the template adds `data-has-filter="1"`, which switches it to `--signal-500` border, `--signal-100` fill, `--signal-700` text, weight 500.
- **`.segmented label` / `.check`** — flex row, 8px gap, 34px min-height, 1.5px border, 2px radius. Checked state (via `:has(input:checked)`) matches the active launcher: signal border, `--signal-100` fill, `--signal-700` text, weight 500. Accent color on the native input is `--signal-500`.
- **`.stat-row`** — team-scoped numeric features render the stat name once with two compact 28px "Bet-side" / "Opponent" buttons to its right, each an independent filter.
- **Run system** button — full-width, 36px, `--signal-500` fill, white 12px/500 sentence-case label. Hover `--signal-600`. **Sentence case, not uppercase** — this differs from the design system's `Button` component, see Known issues.

**Right workspace.** 24px padding, 16px flex-column gap.

1. `.workspace-header` — `h2` "Backtest Results" + bet count, with a "Fade System" checkbox pushed right.
2. **`.metrics.stat-chips`** — `repeat(auto-fit, minmax(158px, 1fr))`. Six chips: Record, Hit Rate, Margin, Money Won, ROI, Grade. White, 1px `--ink-200`, 8px radius, 12px/16px padding. Label 9px uppercase `--ink-400`; value 18px mono 500 with `white-space: nowrap; overflow: hidden; text-overflow: ellipsis`. Money Won and ROI take `.positive` (`--success-500`) or `.negative` (`--error-500`).
3. `.theory-panel` — the system's rationale, 14px/1.65 `--ink-700`, capped at `--content-narrow` (640px).
4. **`.active-filters-panel`** — every applied filter as a plain-English sentence. Each `li` is a 12px row on `--ink-50` with a 1px `--ink-100` border and 2px radius, containing the sentence (`flex: 1`), an "Edit" button (26px, transparent, signal text — inverts to signal fill on hover), and a `×` remove link (26px square, `--ink-400`, goes `--error-500` on `--error-50` on hover).
5. `.tabs` — Results Graph / Past Matches. 1px bottom border on the nav; the active link takes `--signal-500` text and a 2px `--signal-500` bottom border with `margin-bottom: -1px` so it sits on the rule.
6. `.metrics.stats-panel` — twelve significance statistics, `minmax(126px, 1fr)`, 14px mono values.
7. `.stats-verdict` — prose interpretation, 14px/1.65 `--ink-600`.
8. `.season-breakdown` — a small per-season table inside a padded card.
9. `.coverage` — bulleted list of feature-filter coverage percentages.
10. **Two charts.** Both `viewBox="0 0 520 170"`, `preserveAspectRatio="none"`, 170px tall. Each draws the same geometry twice, clipped above and below the zero line, so the curve paints `--success-500` where it is above zero and `--error-500` where it dips below. Areas are the same color at `opacity: 0.10`; strokes are 1.75px with round joins; the zero line is 1px `--ink-300` dashed `3 3`. Point markers render only when there are ≤60 of them. Axis labels are 10px mono `--ink-400`.

### 2. Past Matches — `screens/past-matches.html`

Same shell and sidebar; `tab=matches`. The charts are replaced by a ten-column table: Season, Week, Team, Opponent, Score, Side, Spread, Total, Result, Profit.

**Table styling (applies to every table in the app).**

- Wrapper `.table-wrap`: white, 1px `--ink-200`, 8px radius, `overflow: auto`.
- `thead th`: `position: sticky; top: 0`, background `--ink-800`, text `--ink-100`, 9px 600 uppercase 0.08em tracking, 8px/10px padding, `white-space: nowrap`.
- `tbody td`: 12px sans, 8px/10px padding, 1px `--ink-100` top border, `vertical-align: top`, **`white-space: nowrap`** (team names wrapped to two lines before this).
- `.systems-table` and `.finalist-table` override back to `white-space: normal` because they carry wrapping prose.
- Row hover: `--ink-50`.
- **`.pill`** — result marker, 19px min-height, 7px horizontal padding, 2px radius, 10px 600 uppercase. `.win` → `--success-50` / `--success-700`; `.loss` → `--error-50` / `--error-700`; `.push` → `--ink-100` / `--ink-600`.
- Profit cells take `.positive` / `.negative`.

### 3. My Systems — `screens/my-systems.html`

Maps to `templates/dashboard.html`. `.dash-columns` is `minmax(0, 1fr) 340px`.

- **`.dash-header`** — brand lockup left, `.dash-cta` buttons right. A CTA is a 34px outline button: transparent, 1.5px `--signal-500`, signal text, 12px/500 — inverting to a signal fill on hover.
- Two tab rows: standard `.tabs` for My Systems / Example Systems, then `.timeframe-tabs` — borderless, 11px mono, fully-rounded pills; the active one is a `--signal-500` fill with white text.
- **`.systems-table`** — System, Type, Record, Money Won, ROI, Trend, actions. The System cell holds a 14px/500 link plus an 11px `--ink-500` theory line capped at 46ch; search-derived systems add a `.badge-search` chip (9px uppercase, `--info-50` / `--info-700`) and a mono candidates-tested line.
- **`.sparkline`** — 96×24 SVG polyline, no fill, 1.5px stroke, `--success-500` when up and `--error-500` when down; an em-dash in `--ink-300` when empty.
- **`.dash-side`** (340px, sticky at 16px) — "Current Matches". Each `.match-row` is a card on `--ink-50` with a **2px `--signal-500` left border**, containing a mono kickoff/type row, the play at 14px/500, the matchup, the source system link, and `.cm-tag` chips for the match reasons.

### 4. Compare — `screens/compare.html`

Maps to `templates/compare.html`. `.compare-picker` is a card holding an `auto-fill minmax(200px, 1fr)` grid of system checkboxes, a multi-select for holdout seasons, and a Compare button.

`.compare-table` is transposed — metrics down the left, one column per system. **The first column is `position: sticky; left: 0`** with a white background, `--ink-500` text and weight 500, so metric names stay visible while comparing many systems. The sticky header cell keeps the `--ink-800` background.

### 5. Bet Log — `screens/bet-log.html`

Maps to `templates/betlog.html`. Three CLV chips (N, Mean CLV, t-stat), a coverage note, a by-season table, a single-line CLV chart (`viewBox="0 0 520 150"`, one `--success-500` polyline, no clipped bands), and the bet history table.

Rows missing a closing line collapse their last two cells into one `colspan="2"` `.clv-missing` cell in `--ink-400`.

### 6. Search Run — `screens/search-run.html`

Maps to `templates/search_run.html`. A finalist table (index, filters text, holdout record, ROI, raw p, corrected p, BH significance) inside a `.dash-shell` + `.workspace`, followed by `.narration-panel` — a theory-panel card with a "Narrate results" button and the generated narration at 14px/1.65 `--ink-700`.

## Interactions & behavior

Behavior is entirely unchanged; the restyle adds no new interactions. For completeness:

- **Filter launchers** open `<dialog id="filter-modal">`, driven by `static/filter_modal.js`, which reads the `data-candidate-id` / `data-control` / `data-perspective` / `data-description` attributes off the button. `cfb.css` does not restyle the modal internals — see Known issues.
- **Every filter control submits `#filters-form` by GET**; system state lives entirely in the query string. The Fade System checkbox sits in the workspace but binds back via `form="filters-form"`.
- **Sorting, pagination and tab switching are all server round-trips.** No client-side table state.
- **Hover:** buttons darken to `--signal-600`; unselected controls take an `--ink-300` border; table rows take an `--ink-50` background; CTAs invert to a signal fill. All at 150ms ease-out.
- **Focus:** inputs take a `--signal-500` border plus the 3px `--color-focus-ring` glow. Do not remove the focus ring — several controls have no other affordance.
- **Reduced motion:** not currently handled. Only 150ms color transitions exist, so this is low-risk, but wrapping them in a `prefers-reduced-motion` guard would be correct.

## Template changes required

The restyle is class-compatible, but four things in the Jinja templates need touching:

1. **`templates/index.html` and `dashboard.html` — split the Record chip.** The template currently renders `{{ wins }}-{{ losses }}-{{ pushes }}, {{ hit_rate }}%` into one chip. That string is too wide and wrapped to four lines. Split it into two chips: Record (`W-L-P`) and Hit Rate (`NN.N%`).
2. **CTA casing.** Button labels are sentence case in the restyle ("Run system", "Save system", "Apply filters"), matching the design system's writing rules. The old templates use Title Case in places; normalize them.
3. **Add `.system-cell` / `.actions-cell` classes** where they are missing on the systems table, so the `white-space: normal` override lands on the right cells.
4. ~~Delete `static/styles.css` and replace it with `screens/cfb.css` renamed.~~ **Done** — the `url_for('static', filename='styles.css')` links are unchanged; the old stylesheet is recoverable at commit `2115c21`.

## Assets

- **Brand mark** — the app's own 38px rounded square with mono "CFB" text. No image asset; pure CSS.
- **Saturday Signal mark** — `assets/logo-mark.svg` in the design system (a dot with three radiating arcs, `currentColor`, any size). Not used in these screens, but available if the product picks up Saturday Signal branding.
- **Fonts** — Instrument Serif, Instrument Sans and JetBrains Mono via the Google Fonts `@import` in `tokens/typography.css`. Self-host the WOFF2 files for production.
- **Icons** — none in these screens. The design system nominates Lucide (2px stroke, round caps, no fill) if icons are added.
- No photography, no illustration, no emoji.

## Known issues to be aware of

These are real defects in the source design system, not things to reproduce faithfully:

1. **`--signal-50` and `--ink-50` are the same value** (`#EEF2F8`). Anything tinted with the accent-light token is invisible against the page background, which is why selected controls in `cfb.css` use `--signal-100` instead. If you fix the token, `--signal-100` usages can move back down a step.
2. **The shadow stack is still warm-tinted** — `--shadow-xs` through `--shadow-2xl` use `rgba(28, 21, 16, …)`, a brown left over from an earlier palette. They are barely used in these screens, but they are wrong against slate. `rgba(17, 19, 24, …)` is the correct tint.
3. **The design system's `Button` component force-uppercases every label**, which contradicts the sentence-case CTA rule in its own writing guidelines. `cfb.css` follows the guidelines, not the component. If you adopt the shared component library, expect this conflict.
4. **The filter modal is unstyled by this pass.** `filter_modal.js` builds its controls dynamically and the `.filter-modal__*` classes are only partially covered. Budget a follow-up for it.

## Files

```
docs/design-system.md                      ← this file (the rules)
cfb_system_maker/static/
├── styles.css                             ← the restyle; imports the three token files
└── tokens/
    ├── colors.css                         signal + ink palettes, semantic aliases
    ├── typography.css                     font imports, type scale, semantic type styles
    └── spacing.css                        space scale, radius, shadows, z-index, widths
```

The six reference screens (`system-editor.html`, `past-matches.html`, `my-systems.html`,
`compare.html`, `bet-log.html`, `search-run.html`) are prototypes, not templates, and are
deliberately not checked in. They live in the original handoff folder if you need to
compare pixels.
