# Design system: Minimalist Modern

Repo-wide visual rules for the Flask UI (`cfb_system_maker/`) and the matchup page, which
serves the same token files. Tokens ship at
`cfb_system_maker/static/tokens/{colors,typography,spacing}.css`; the stylesheet that
consumes them is `cfb_system_maker/static/styles.css`. Change a value here, change it in
the token files. `styles.css` takes every color, font, radius and shadow through
`var(--*)` and holds no raw hex.

Adopted 2026-10-17, replacing Saturday Signal (slate blue, Instrument Sans, near-square
corners). The old version of this file is in git history at the commit before that date.

## What the system is, and what this app takes from it

Minimalist Modern is "clarity through structure, character through bold detail": a
near-monochrome slate palette, one Electric Blue accent used as a gradient, a
serif/sans/mono type pairing, soft layered shadows, and gentle motion.

The source spec was written for a marketing landing page (React, Tailwind, Framer Motion,
hero graphic, pricing, testimonials). This app is a data tool with server-rendered Jinja
templates and one hand-written stylesheet, so it adopts the parts that help people read
numbers and leaves out the rest:

| Taken | Left out, and why |
|---|---|
| Electric Blue gradient on primary buttons, brand mark, active timeframe pill | Hero graphic, rotating rings, floating cards: they compete with charts |
| Off-white canvas, white cards, layered slate shadows | Gradient text in headlines: hurts scanning of page titles |
| Calistoga titles, Inter UI, JetBrains Mono labels and stat values | Asymmetric layouts: the editor's two-column shell already works |
| Section-label pills with an accent dot | Tailwind / cva / Framer Motion: the app has no build step; plain CSS does the same |
| One inverted dark band for the headline backtest numbers | Section padding of 7–11rem: far too sparse for a workbench |
| Hover lifts, staggered fade-up on load, pulsing dot on live picks | |

## Tokens

Token **names** are unchanged from Saturday Signal (`--signal-*`, `--ink-*`, `--space-*`,
`--radius-*`, `--shadow-*`), so no rule in `styles.css` had to be renamed; only values moved.

### Color (`colors.css`)

| Token | Value | Use |
|---|---|---|
| `--signal-500` | `#0052FF` | **Accent** — links, active tab, focus ring, checked controls |
| `--signal-400` | `#4D7CFF` | Gradient endpoint (the spec's `accent-secondary`) |
| `--signal-50` / `--signal-700` | `#EEF4FF` / `#0035A6` | Selected control fill / its text |
| `--gradient-accent` | `--signal-500 → --signal-400`, left to right | Primary buttons, active timeframe pill, label dots |
| `--gradient-accent-diag` | same, 135° | Brand mark |
| `--canvas` | `#FAFAFA` | Page background (`--bg`) |
| `--ink-0` | `#FFFFFF` | Cards, panels, tables |
| `--ink-50` … `--ink-900` | Tailwind slate 50–900 | Neutrals; `--ink-900` `#0F172A` is text and the dark band |
| `--ink-200` | `#E2E8F0` | Default border |
| `--success-500` / `--error-500` | `#2A7A4E` / `#C23030` | Profit / loss on light surfaces (unchanged) |
| `--success-on-dark` / `--error-on-dark` | `#4ADE80` / `#F87171` | Profit / loss inside the dark band |

Green and red stay the data colors for profit and loss everywhere, including charts. The
blue accent is for interaction and emphasis, never for a result.

### Type (`typography.css`)

Three Google Fonts faces: **Calistoga** (`--font-display`, one weight, 400), **Inter**
(`--font-body`, 400–700), **JetBrains Mono** (`--font-mono`, 400/500).

1. Calistoga is for page titles only: `h1` (20px, sidebar brand and dashboard titles) and
   `h2` (24px, workspace heading, `--type-title-md`). Never set it bold; the browser would
   fake a weight it does not have.
2. Mono is for stat values, chart axes and section labels (`--type-section-label`: 11px,
   uppercase, 0.15em tracking). It is **not** used in table cells.
3. Tables and body copy are Inter with `font-variant-numeric: tabular-nums` (set on
   `body`), which keeps numeric columns aligned without a monospace face.
4. CTA labels are sentence case: "Run system", "Save filter", "New system".

### Radius, shadow, motion (`spacing.css`)

- Radius: `--radius-sm` **8px** controls, buttons, pills; `--radius-lg` **12px** cards,
  panels, table wrappers; `--radius-xl` **16px** the filter modal and the stats band;
  `--radius-full` label pills and timeframe pills.
- Shadows are slate-tinted (`rgba(15, 23, 42, …)`), `--shadow-sm` on panels, `--shadow-md`
  on hover and the dashboard side panel, `--shadow-xl` on the stats band and popovers.
  `--shadow-accent` / `--shadow-accent-lg` are the blue glow under a hovered primary button.
- Focus: `--shadow-focus` is a 2px canvas gap plus a 2px `--signal-500` ring on inputs;
  other controls use a 2px `--signal-500` outline with offset. Never remove it.
- Motion: `--transition-lift` (200ms, `--ease-out-expo` = `cubic-bezier(0.16, 1, 0.3, 1)`)
  for hover lifts. All animation and transition is switched off under
  `prefers-reduced-motion: reduce` by the last rule in `styles.css`.

## Components

- **Primary button** (bare `button`): gradient fill, white 14px/500 label, 40px tall,
  8px radius. Hover lifts 1px, brightens, and takes `--shadow-accent`; active scales to
  0.98. Secondary buttons (`.edit-filter`, modal toggles, `#theory-suggest`, …) override the
  fill and are listed in one `:is(...)` rule that drops the glow but keeps the lift.
- **Secondary CTA** (`.dash-cta`): white, 1px border, slate text; hover fills
  `--ink-100` and tints the border blue.
- **Controls** (`input`, `select`, `.segmented label`, `.check`, `.filter-launcher`):
  40px tall, 1px `--ink-200` border. Checked or set: `--signal-500` border,
  `--signal-50` fill, `--signal-700` text.
- **Section label**: panel headings (`.theory-panel h3`, `.chart-card h3`,
  `.season-breakdown h3`, `.coverage h3`, `.picks-heading h3`,
  `.system-summary-heading h3`, `.cm-heading`, or any `.section-label`) render as a mono
  pill with a 30%-blue border, 5%-blue fill and a gradient dot. On
  `.picks-panel.is-live` (this week has picks) the dot pulses.
- **Stats band** (`.metrics.stat-band`, the six headline chips on the editor): `--ink-900`
  background with a corner blue glow and a 32px dot grid at 4% opacity. Inside it,
  `--text`, `--border`, `--success-500` and `--error-500` are re-pointed to their on-dark
  values, so the graded colors and `.positive` / `.negative` need no rules of their own.
  This is the only inverted surface in the app; keep it that way so it stays the focus.
- **Metric cards** (`.metrics article` outside the band): white, 12px radius,
  `--shadow-xs`, lift 2px on hover.
- **Tables**: light sticky header (`--ink-50`, `--ink-500` 10px uppercase text, 1px
  bottom rule), 12px Inter cells, `white-space: nowrap` except `.systems-table` and
  `.finalist-table`. Win/loss/push pills keep the semantic success/error/ink fills.
- **One gradient button per area.** In the sidebar that is Run; the two save buttons
  (`.form-actions button[formaction]`) use the secondary white treatment.
- **Entrance**: children of `.workspace` and `.dash-main` fade up 16px over 0.7s,
  staggered 50ms. The sticky "Current system" panel fades only, since a transform would
  break its sticky positioning mid-animation.

## Layout

Unchanged: `.app-shell` (320px sticky sidebar + workspace) for the editor, `.dash-shell`
(centered, max 1440px) for My Systems, Compare, Bet Log and Search Run. Below 900px the
sidebar collapses behind a "Show filters" button and metric grids go to two columns.

## Pages that copy the tokens instead of linking them

`scripts/weekly_rankings_page.html` and `models/middle/middle_calculator.html` inline
their own copy of the old Saturday Signal values. They are standalone outputs and were not
moved; if they should match the app, copy the new token values in.

## Files

```
docs/design-system.md                      ← this file (the rules)
cfb_system_maker/static/
├── styles.css                             ← consumes the tokens; signature elements at the end
└── tokens/
    ├── colors.css                         signal + ink palettes, gradient, semantic aliases
    ├── typography.css                     font imports, type scale, semantic type styles
    └── spacing.css                        space, radius, shadows, z-index, widths, motion
```
