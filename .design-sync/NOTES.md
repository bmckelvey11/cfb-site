# design-sync notes — CFB System Builder

- **This repo has no npm package.** `cfb_system_maker` is a Flask/Jinja app; the
  design system is `cfb_system_maker/static/tokens/*.css` + `static/styles.css`.
  There are no React components and none should be authored just to satisfy the
  converter — the sync runs in design-sync's supported **tokens-only** mode
  (`lib/source-kit.mjs` `[ZERO_MATCH]` → `tokensOnly`, `package-validate.mjs:367`).

- **`scripts/design_sync_stage.mjs` is a prerequisite for every build.** It stages a
  synthetic package at `.ds-sync/scratch/node_modules/cfb-system-builder` holding an
  empty entry plus verbatim copies of the app's `styles.css` and `tokens/*.css`.
  `cfg.cssEntry` is bounded to the package dir by the converter, which is why the CSS
  has to be copied in rather than referenced in place. Run it before `resync.mjs`,
  always — a stale scratch package silently ships the previous stylesheet.

- **Install order matters.** `npm i react react-dom` prunes anything in
  `node_modules` it doesn't know about, so the synthetic package must be written
  *after* the install. The staging script does both in that order; don't split them.

- **Build command:**
  ```
  node scripts/design_sync_stage.mjs
  node .ds-sync/resync.mjs --config .design-sync/config.json \
    --node-modules .ds-sync/scratch/node_modules \
    --entry .ds-sync/scratch/node_modules/cfb-system-builder/dist/index.js \
    --out ./ds-bundle
  ```

- `[FONT_REMOTE]` is expected: `tokens/typography.css` pulls Instrument Sans /
  Instrument Serif / JetBrains Mono from the Google Fonts CDN. Nothing to ship.
  The validator also names `Fira Code` and `Cascadia Code` — those are local
  fallbacks in `--font-mono`, not remote families. Harmless.

- The render check needs playwright + chromium (installed under `.ds-sync/`). With
  zero components it renders 0/0 and passes; without playwright it fails
  `[RENDER_SKIPPED]`.

## Re-sync risks

- **The staged copy is the drift risk.** `styles.css` and the token files are copied
  at build time, so an edit in `cfb_system_maker/static/` only reaches the project on
  the next full run of the staging script + driver. There is no watcher.
- **The conventions header enumerates real class and token names** and will rot when
  classes are renamed or dropped in `styles.css`. Re-validate every name against
  `ds-bundle/_ds_bundle.css` before republishing; a name that no longer resolves makes
  the design agent emit silently unstyled markup. `.active` was already cut once for
  exactly this reason (only `.active-filters*` exist).
- **Light mode only.** If a dark theme is ever added to the stylesheet, the header's
  "do not invent a dark theme" line becomes wrong.
- **If components ever ship** (a JS build, a React port), delete the tokens-only
  scaffold and re-run detection — `cfg.shape` is pinned to `package` and the synthetic
  entry would mask real exports.

## Sync history

- **2026-09-18** — first sync. Project `CFB System Builder`
  (`9a1f4da1-37d7-499a-ab29-3c8bfa1aad23`), created empty, 11 files uploaded,
  `package-validate.mjs` exit 0.

- **Saturday Signal is a separate, richer project** (`ddf9b44f-3d88-4b48-b3da-c9edcb3b5f7c`).
  It already holds a `design_handoff_cfb_system_maker/` slice (styles.css + tokens +
  6 screens), `ui_kits/cfb/`, `templates/cfb-system-maker/`, five React components
  (Avatar, Badge, Button, Card, Input) and eleven `guidelines/*.card.html`.
  **Do not sync this repo into it.** A design-sync upload carries delete globs over
  `components/`, `guidelines/`, `tokens/` and `_vendor/`, and the reconciliation pass
  would remove everything this repo's tokens-only build does not produce.

- `cfb_system_maker/static/tokens/*.css` are byte-identical to Saturday Signal's
  (down to its `@kind other` annotations), so the repo is a downstream consumer of
  that project, not the source. Token edits belong upstream in Saturday Signal; only
  `styles.css` (the 166-class app layer) originates here.

- Saturday Signal's root `styles.css` imports only the three token files, so designs
  built from it receive tokens but **not** the app's class vocabulary. That gap is why
  this repo syncs as its own project: the class layer reaches designs through this
  project's import closure without pushing app chrome classes
  (`.filter-modal__*`, `.grade-7`) into the house brand system. Revisit only if the
  user asks for the two to merge.
