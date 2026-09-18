# CFB System Builder — how to build with this design system

**This design system ships no JavaScript components.** `window.CFBSystemBuilder` is
empty by design — the source is a Flask/Jinja app, and what it exports is a token
layer plus a semantic CSS class layer. Build screens as plain HTML (or JSX) elements
carrying these class names. Do not import components from the bundle; there are none.

## Setup

Link `styles.css` and write markup inside a layout shell. There is no provider and no
root wrapper class — tokens are defined on `:root` by the stylesheet's own `@import`
chain (`tokens/typography.css`, `tokens/colors.css`, `tokens/spacing.css`), so they are
live as soon as `styles.css` loads. `body` already sets the background, body font, and
`font-variant-numeric: tabular-nums`; do not re-declare them.

**Light mode only.** `:root` sets `color-scheme: light` and there is no
`prefers-color-scheme` block. Do not invent a dark theme.

Fonts load from Google Fonts via an `@import` inside `tokens/typography.css` — nothing
to add.

## Layout shells

Pick one as the page root: `.app-shell` (320px filter rail + workspace, pairs with
`.filter-panel` and `.workspace`) or `.dash-shell` (centered max-width column, pairs
with `.dash-header`, `.dash-columns`, `.dash-main`, `.dash-side`).

## The styling idiom

Two vocabularies, used together:

**1. Tokens — always `var(--*)`, never a literal color, size, or radius.**

| Family | Real names |
|---|---|
| Local aliases (use these first) | `--bg` `--panel` `--panel-strong` `--text` `--muted` `--border` `--accent` `--accent-dark` `--win` `--loss` `--win-bg` `--loss-bg` `--push-bg` |
| Palettes | `--signal-50…900` (brand, 500 = `#2E4A6B`), `--ink-0…900` (neutrals), `--success/--warning/--error/--info-{50,100,500,700,900}` |
| Semantic colors | `--color-bg` `--color-surface` `--color-surface-raised` `--color-border` `--color-text-primary` `--color-text-secondary` `--color-accent` `--color-focus-ring` (+ `-subtle`/`-hover`/`-active`/`-surface` variants) |
| Type | `--font-display` `--font-body` `--font-mono`; `--text-xs…7xl`; `--weight-light…bold`; `--leading-*`; `--tracking-tightest…widest`; composites `--type-heading-{sm,md,lg,xl,2xl}` `--type-body-{sm,md,lg}` `--type-label-{md,lg}` `--type-stat-{md,lg}` `--type-overline` `--type-caption` `--type-code` |
| Space / shape | `--space-0…24` (4px base) · `--radius-{none,xs,sm,md,lg,xl,2xl,full}` · `--shadow-{xs…2xl,focus}` · `--transition-{fast,normal,slow,modal}` · `--container-{xs…2xl}` · `--z-{base,raised,dropdown,sticky,overlay,modal,toast}` |

**2. Classes — semantic, not utility.** There are no `p-4`/`text-sm` utilities; do not
write any. Existing families: layout shells (above); blocks (`.metrics` `.table-wrap`
`.stats-panel` `.chart-card` `.picks-panel` `.theory-panel` `.narration-panel`
`.empty-state` `.banner` + `.banner-error` `.pill` `.tabs` `.stat-row` `.brand`
`.active-filters` `.active-filters-panel`
`.brand-mark` `.dash-cta`); BEM children on the modal and feature groups
(`.filter-modal__header` `.filter-modal__body` `.filter-modal__footer`,
`.feature-group__toggle`, `.row-menu__pop`, `.stat-row__label`); state modifiers
(`.is-active` `.is-selected` `.is-collapsed` `.is-searching` `.graded` `.full-width`);
outcome modifiers (`.win` `.loss` `.push` `.positive` `.negative` `.up` `.down`);
and the 0–10 quality ramp `.grade-0`…`.grade-10`, which drives a red→green
`color-mix` on `.metrics article.graded`.

For layout glue of your own, write a plain CSS rule built from tokens. Coin a new
semantic class name only when nothing above fits.

## House rules for numbers

This is a betting-analytics UI; numerals are the content.

- All stat values and table numerals: `font-family: var(--font-mono)`.
- Stat labels and table headers: uppercase, `var(--tracking-widest)`, `--muted`, ~9–10px.
- Percentages to one decimal, units to two, `+` prefix on positives, show `n=` on every stat.
- `--font-display` (Instrument Serif) is for 48px and up only. Below that use
  `--font-body` at `--weight-semibold`.
- No gradients, no emoji in copy.

## Read the real files

`_ds/<folder>/styles.css` and the three files it `@import`s under `_ds/<folder>/tokens/`
are the truth. Read them before styling — every class and token above is defined there.

## Idiomatic snippet

```html
<section class="dash-shell">
  <header class="dash-header">
    <div class="brand"><span class="brand-mark">CFB</span><h1>Season Summary</h1></div>
  </header>
  <div class="metrics">
    <article class="graded grade-8"><span>ROI</span><strong>+4.7%</strong></article>
    <article><span>Record</span><strong>112-97-4</strong></article>
    <article><span>Sample</span><strong>n=213</strong></article>
  </div>
  <div class="table-wrap"><table>…</table></div>
</section>
```
