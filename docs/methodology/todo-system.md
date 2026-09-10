# The TODO system

How task tracking works in this repo.

Ported 2026-09-10 from `golf-master`'s TODO system (design: that repo's
`docs/analysis/todo-system-redesign-2026-07-25.md`, external review:
`docs/analysis/todo-system-external-review-2026-07-26.md` — verdict there was
"keep the core model," so this is a straight port, adapted to this repo's
units and doc layout, not a redesign).

## The queue: `TODO.md`

**`TODO.md`** (repo root) is the only day-to-day queue.

- Structure (domain outline): `## 0. NOW` (this week, in order) at top, then
  unit sections numbered in file order — each heading also carries a
  **stable section slug** that survives renumbering: `#sec-now` ·
  `#sec-system-maker` · `#sec-data` · `#sec-totals` · `#sec-over-zero` ·
  `#sec-spread` · `#sec-ops` · `#sec-housekeeping` · `#sec-recent`. Prefer
  `#sec-totals` over `§3` when pointing.
- **Unit sections map to this repo's units** (see root `CLAUDE.md` Units
  table): `#sec-system-maker` → `cfb_system_maker/` (CLI, Flask UI, backtest
  engine) · `#sec-data` → warehouse/ingestion/scrapers spanning PFF, Action
  Network, odds, GraphQL, DuckDB (cross-cutting, not owned by one unit) ·
  `#sec-totals` → `models/totals/` · `#sec-over-zero` → `models/over_zero/`
  · `#sec-spread` → `research/spread/`.
- **`#sec-now` soft WIP + easy-only.** `#sec-now` (§0) is a weekly
  commitment surface for **sitting-sized / easy-actionable** work — not a
  second backlog and not a place for `plan: needed` redesigns or multi-day
  campaigns (those stay in their home unit section until you're launching
  them this week). Soft max **~8 open items**; when it grows past that,
  triage (reorder, demote to a unit section, or expand stubs) before adding
  more. `todo_sweep.py check` warns when over the cap — warn-only, not a
  hard fail.
- **Ids + single home + visible labels.** Open items carry a stable slug
  **twice on the same line** — a visible backtick ref for humans/agents,
  plus an HTML comment for the linter/sweep:

  ```markdown
  - [ ] `#pff-tier-overlap-audit` **Audit PFF tier overlap against modeling pull** <!-- id: pff-tier-overlap-audit --> — …
  ```

  **Point to an item with `#pff-tier-overlap-audit`**. An item lives in
  exactly one section; every other mention is a pointer line
  (`- → see \`#pff-tier-overlap-audit\` (#sec-data)`), never duplicated body
  text. Ids are never reused, are shared with `todo:` block ids (one
  namespace), and stay on the line after it's struck through so resolution
  notes remain greppable. Backfill an id when you edit an item — or run
  `python scripts/todo_sweep.py label --apply` to mint missing ids and
  insert visible `#id` / `#sec-*` refs. `check` fails open items that lack
  an id or whose visible `#id` disagrees with the HTML comment.
- **Section labels (`#sec-*`).** Every `##` heading carries the same dual
  form — visible + HTML comment — in the `sec-*` namespace so it never
  collides with item ids:

  ```markdown
  ## 3. Totals model (`models/totals/`) `#sec-totals` <!-- section: sec-totals -->
  ```

  **Point to a whole section with `#sec-totals`.** Numbers (`§3`) are still
  fine for reading order; slugs are the durable cross-ref. `label --apply`
  stamps missing section labels from the built-in domain map.
- **`todo_sweep.py refs`.** Printable index: sections first (`#sec-*` →
  title), then open items (`#id` → home section → title). Use it when
  pointing in chat without scrolling the queue.
- **Optional `verify:` line.** Where a mechanical done-check is cheap,
  record it at capture time: `<!-- verify: test -f docs/pff-warehouse-schema.md -->`
  on the item (own line or inline). `todo_sweep.py verify` runs them and
  reports *likely done* — it never auto-closes. A human still strikes the
  item through with the resolution note, which is what keeps the file a
  changelog. Most research items (spread-movement, over-zero) can't be
  checked this way; don't force it.
- Checkbox format carries history, not just state: `- [x] ~~item~~ — done
  YYYY-MM-DD: resolution, commit hash, test name`. Done items are struck
  through and annotated in place, not deleted — reading top-to-bottom is a
  changelog as well as a queue. Prefer an explicit close date so age/cycle
  time does not require git archaeology.
- **Optional context tags.** For cross-section slices (`@needs-backtest`,
  `@needs-data`, `@docs`), append todo.txt-style tags on the item line.
  Theme section stays the home; tags are an orthogonal grep axis. No parser
  required until proven useful.
- **Graduation rule:** `§0` is the daily-glance queue and stays
  open-item-only. When a `§0` item closes, move its struck-through `[x]`
  line into its home unit section in the same commit — don't leave closed
  items sitting in `§0`. If no unit section fits, fold a one-line summary
  into "Recently completed" at the bottom instead of leaving the full note
  in `§0`.
- No-lookahead gate at the top: any pre-game feature or model change must
  respect root `CLAUDE.md`'s no-lookahead rule; a result-informed feature
  must be tagged `result_lookahead` and quarantined in UI (same as today).

### Item wording

Prefer:

```markdown
- [ ] `#my-slug` **Short title** <!-- id: my-slug --> — what to do; why / done-when; where (module/flag/command); link to source doc if any
```

The visible `` `#my-slug` `` is the pointing handle for items; `` `#sec-totals` `` is the pointing handle for whole sections — prefer those over section numbers or prose paraphrases.

**Expand stubs.** Title-only or very short lines (jargon fragment, no
verb+target+location) get expanded before they land in `TODO.md` or in a
`todo:` `text` field. Next-session you should know what to run/edit and
what "done" means. When editing a section, expand short open items there —
don't rewrite the whole backlog for style alone.

No SaaS tracker, no one-file-per-task sprawl. Plain markdown, git-native.

### Plan markers

Large or ambiguous items carry a plan marker in an HTML comment on the item
line, so agents know whether to execute directly or write a plan first:

| Value | Meaning |
|---|---|
| `<!-- plan: needed -->` | Too large/ambiguous to execute directly; agents must write a plan first |
| `<!-- plan: path/to/plan.md -->` | Plan exists; execute against that doc |
| Remove marker | Only when the item closes, or when the work shrinks below plan threshold |

This repo already writes plan/spec pairs under `docs/superpowers/plans/` and
`docs/superpowers/specs/` for larger work — when an item's plan lives there,
point `plan:` at that path rather than duplicating it.

## Capture: `todo:` blocks on source docs

Open work is declared where it is discovered — usually a research or
warehouse doc — with a machine-parseable `todo:` YAML block next to the
human-readable Recommendations list:

```markdown
## Recommendations

​```yaml
todo:
  - id: pff-tier-overlap-audit
    priority: P1
    text: "Audit PFF tier overlap between the facet pull and modeling pull; document which tiers are canonical in docs/pff-warehouse-schema.md"
    status: open
​```

- (prose checklist / narrative recommendations stay here for humans)
```

| Field | Meaning |
|---|---|
| `id` | Stable merge key. Never reuse. Idempotent sweeps match on this exact string. |
| `priority` | `P1` ≈ HIGH, `P2` ≈ MEDIUM (same vocabulary as `TODO.md`). |
| `text` | Expanded item wording that lands in `TODO.md` (title + what/why/where — not a stub). |
| `status` | `open` or `done`. Done/already-promoted ids are not re-added. |

Sources the sweep reads (`docs/_private/` is never scanned, in case this
repo ever grows one — matches the golf-master convention):

- `docs/*.md` (the research/warehouse/analysis docs living directly under
  `docs/` — this repo doesn't split them into `analysis/`/`methodology/`
  subfolders the way golf-master does, so the sweep just scans the flat
  layer plus this file's own directory)
- `docs/superpowers/plans/*.md`
- `docs/superpowers/specs/*.md`

Ad-hoc follow-ups with no host doc: add them to a related doc's `todo:`
block, or append an expanded `- [ ]` under `TODO.md` §0 (not a stub).

## Promote / lint: `todo_sweep.py`

```bash
python scripts/todo_sweep.py sweep            # dry-run: what would land in section 0
python scripts/todo_sweep.py sweep --apply    # appends new ids into TODO.md §0
python scripts/todo_sweep.py check            # lint; exit 1 on any violation
python scripts/todo_sweep.py verify           # run verify: commands, report likely-done
python scripts/todo_sweep.py refs             # `#sec-*` sections + open `#id` items (for pointing)
python scripts/todo_sweep.py label            # dry-run: mint missing ids + visible `#id` / `#sec-*` refs
python scripts/todo_sweep.py label --apply    # write those labels into TODO.md
```

- `sweep` parses `todo:` blocks from the sources above. For each `id` with
  `status: open` not already present in root `TODO.md`, it appends under
  `## 0. NOW` / `#sec-now` with a link back to the source doc, using the
  visible-label format (`` `#id` **text** <!-- id: --> ``). Dry-run is
  default; `--apply` is the only write mode. Matching is by exact `id`, not
  fuzzy text, so re-sweeps are idempotent.
- `check` lints: duplicate ids (in `TODO.md`, and one id declared by two
  docs), dangling relative links in `TODO.md`, closed `[x]` items still
  sitting in `#sec-now` (graduation rule), pointer lines referencing an id
  that exists nowhere (items **or** `#sec-*` sections), open items missing
  an id or a matching visible `#id` label, and section headings
  missing/mismatched `#sec-*` labels. Soft WIP warn when `#sec-now` open
  count exceeds 8 — warn-only / exit 0. Run `check` before any `TODO.md`
  commit.
- `verify` runs each open item's `verify:` command and reports likely-done.
  Never writes.
- `refs` prints the section index then the open-item pointing index.
- `label` mints missing open-item ids (slugified from the title), stamps
  `#sec-*` on headings from the built-in domain map, and inserts/corrects
  visible labels. Dry-run default; `--apply` writes.

Same shape as the other narrow, auditable scripts in `scripts/` — not a new
subsystem.

**Status:** ported 2026-09-10 from `golf-master` (shipped there 2026-07-25,
externally reviewed 2026-07-26 against todo.txt, Org-mode, Taskwarrior, Keep
a Changelog, git-bug, and Backlog.md — verdict: keep the core model). No
independent review has been run against this repo's copy yet.

## When to sweep

Run at natural workflow points (not on a calendar):

- After closing a research or warehouse doc that has open `todo:` items
- Before any full `TODO.md` rebuild, as a pre-check
- After finishing a `docs/superpowers/plans/*.md` item, per the shared
  standing rule ("mark tasks done + date" — root `CLAUDE.md`)

No cron or CI hook required.

## What stays separate

- **`.planning/` (GSD)** — cross-referenced only; not merged into `TODO.md`
  (different state machine — phases/milestones/state, not a daily queue).
- **`docs/superpowers/plans/` + `docs/superpowers/specs/`** — plan/spec
  pairs for larger work, written before or during execution. `TODO.md`
  items can point at a plan (`<!-- plan: docs/superpowers/plans/....md -->`)
  but the plan itself is not a queue and open work inside it should still
  get a `todo:` block or a `TODO.md` line if it's meant to be tracked here.
- **No git-bug / git-task** — `TODO.md`'s inline-history checkboxes already
  give commit-linked resolution notes in a grep-able, PR-diffable form.
- **No auto-close** — `verify:` flags likely-done items; a human writes the
  strike-through and the resolution note. Automating that away would cost
  the inline changelog, which is the system's most valuable property.

## Slash commands (Claude Code)

Narrow command layer over the same invariants — side-effecting, so
`disable-model-invocation: true`. Under `.claude/commands/`:

| Command | Mirrors |
|---|---|
| `/todo-verify` | `todo_sweep.py verify` + draft closures |
| `/todo-sweep` | dry-run sweep; `--apply` only on confirm |
| `/todo-check` | `todo_sweep.py check` explained |
| `/todo-capture` | natural language → doc `todo:` or §0 item |
| `/todo-close` | close by id + graduation |
| `/todo-triage` | §0 / open-section quality audit |
| `/todo-from-doc` | draft missing `todo:` from a doc |
| `/todo-session-close` | end-of-session persist → sweep → check |
| `/add-todo` | raw-note → house-format rewriter (pre-dates the set; keep) |

## Standing habits

- Persist analysis to `docs/` (see root `CLAUDE.md`). When it has open
  recommendations, write the `todo:` block alongside them.
- Run `todo_sweep.py sweep` (dry-run, then `--apply`) before treating an
  analysis session as closed, and `check` before committing `TODO.md`.
- Start a triage session with `todo_sweep.py verify` — it replaces
  re-deriving by hand whether an open item already shipped.
- Prefer capture-in-doc + sweep over hand-duplicating the same item into
  `TODO.md`.
- Expand short/stub task text before write (see Item wording).
