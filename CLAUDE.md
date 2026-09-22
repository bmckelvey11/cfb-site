# Shared repository instructions

This file owns rules shared by every unit. Closer nested `CLAUDE.md` files add
unit-specific commands and conventions. `AGENTS.md` points here; `.claude/CLAUDE.md`
owns only GSD workflow; `CONTEXT.md` owns current terminology; `PRODUCT.md` owns
human-facing product intent. None should duplicate another file's rules.

## Standing Rules

- After finishing tasks/findings tracked in a doc (review docs, plans, TODO lists), update that doc marking each  item done + the completion date — don't leave it stale once the work lands.

- Any modelling, backtesting, or analysis that might be reproduced gets a reusable script, not a one-off. Write the script as part of the task.

- Scoring models and systems is governed by [`docs/model-evaluation-standard.md`](docs/model-evaluation-standard.md). It binds any new work that reports ROI, CLV, a hit rate, or forecast skill — the totals harness, over-zero, spread research, vendor-pick grading, saved system-maker filters. Report the Tier 1 metrics it names (interval, not just a point estimate; proper score against the same-time de-vigged market; trial count; walk-forward folds), and treat its hard gates as invalidating: leakage, prices not reconstructible at decision time, or a threshold chosen on the test set means the result does not count, however good the ROI. Existing dated docs are records and are not re-scored.

- **New findings get written up — not every analysis.** A result is new when it answers a question the unit's `docs/` does not already answer, or when it changes what an existing doc concludes. That gets a markdown file in the owning unit's `docs/` (`research/spread/docs/`, `models/totals/docs/`, ...), else root `docs/`, named `<topic>-<YYYY-MM-DD>.md`. Minimum: the question, the method, the data and date range used, the numbers, and what the result does *not* support. Point at the script that reproduces it. Ad-hoc digging counts — a new finding is a new finding whether or not it was planned.

  A result that is **not** new does not get a doc. Re-running a script whose conclusion already stands, confirming a known null on more data without moving the verdict, or re-deriving a number an existing doc reports: update that doc's living summary or add a row to it, and say so in the commit message. Confirmations are worth recording and are not worth a file.

  The judgement call is "does anything downstream change?" If a reader would act differently, write it up. If they would not, the finding is a line, not a document. When it is genuinely unclear, prefer the line — an over-full `docs/` costs more than a missing paragraph, because the next reader has to read all of it to find out what is current.

- **Math in Markdown.** Any `.md` with equations follows three rules. Applies to new docs and to any equation you touch; dated records are not rewritten to comply.
  - **Delimiters.** Inline math is `$...$`; display math is `$$` on its own line above and below. Never `\( \)` or `\[ \]` — GitHub and Obsidian do not render them. Watch for `\b`, `\t`, `\n` being eaten as escapes (`\beta` turning into `eta`).
  - **Declare variables inside the fence.** Under each display equation, in the same `$$` block, a `where` table defines every symbol with its units and sign convention: `\begin{gathered} <equation> \\[1em] \begin{array}{rl} \text{where}\quad x: & \text{...} \end{array} \end{gathered}`.
  - **Explain in prose after the fence.** What the equation computes, how to read its sign or edge cases, and a worked number where it helps. A symbol used before it is defined, or an equation with no prose after it, is not done.

  Pattern: [`docs/feature-evaluation-framework.md`](docs/feature-evaluation-framework.md).

- Docs lifecycle (`tests/test_docs_index.py` enforces the first point):
  - **Check first.** Before writing a doc, grep its `docs/README.md` for the topic. If a doc already answers the question, update it or supersede it — don't write a sibling.
  - **Index.** Every `.md` in a `docs/` dir gets a row in that dir's `README.md`: one line, what question it answers. Unindexed doc = task not done.
  - **Dated docs are records.** Never rewrite `<topic>-<date>.md` after the fact. A new answer to the same question is a new dated doc.
  - **Supersede, don't accumulate.** When a doc supersedes an older one, put `**Superseded by** [new](path)` as the old doc's first line and `git mv` it to `archive/docs/`. Delete its README row.
  - **Undated docs are living.** Guides, specs, and plans must match the code. When the code changes, fix the doc in the same commit or archive it.
  - **A unit with more than a handful of dated records keeps a living summary** — one undated doc saying where the questions stand, each claim pointing at the dated record that establishes it. That is where a confirmation lands instead of a new file. `research/totals/docs/greenline-findings.md` is the pattern. If the summary and a dated record disagree, the record wins and the summary is stale.

## Units

| Unit | Home | Instructions |
| --- | --- | --- |
| System maker, Flask app, scrapers, warehouse | `cfb_system_maker/` | `cfb_system_maker/CLAUDE.md` |
| Totals model | `models/totals/` | `models/totals/CLAUDE.md` |
| Over-zero models and floor-bias research | `models/over_zero/` | `models/over_zero/CLAUDE.md` |
| Spread forecast research | `research/spread/` | `research/spread/CLAUDE.md` |
| Totals research not yet in the harness (Greenline evaluation, modeling reading) | `research/totals/` | `research/totals/CLAUDE.md` |
| Bankroll, staking, and combined-strategy projection | `research/bankroll/` | `research/bankroll/CLAUDE.md` |

## Shared rules

- `CFB_DATA_ROOT` is required and resolves through root `cfb_paths.py`. Working data is
  `C:\Users\mckel\dev\cfb\data`; local `cfb.duckdb` is source of truth. MotherDuck
  `md:cfb` is a manual mirror.
- Data is never committed. It lives in `data/`, which `.gitignore` excludes. Keep only
  explicit fixtures, examples, research records, and documentation artifacts in git.
- Do not edit `cfbd-python/`; it is vendored upstream.
- No lookahead: pre-game features use only information available before kickoff. Any
  result-informed feature must be tagged `result_lookahead` and quarantined in UI.
- Run commands from repository root unless a nested instruction says otherwise.
- Default verification: `python -m pytest`. `pytest.ini` excludes slow tests by default.
- Preserve unrelated dirty work. Keep moves and content edits in separate commits when
  practical.

## Archive rule

`archive/` contains documents superseded by later answers. Retain them for audit history,
but never cite them as current. Historical `.planning/` records remain in place and may
contain old paths; do not rewrite them merely to modernize history.

## Git: splitting a mixed unit

Global `CLAUDE.md` §5 governs auto-commit and auto-push. When a finished unit holds more than one logical change (a feature tangled with a fix, a refactor mixed into new behavior, two unrelated fixes, or one file whose hunks serve different purposes):

- Group by concern. Present the grouping and wait — that's the only pause.
- Stage by path, never `git add .`. Use `git add -p` when one file holds two concerns.
- Confirm with `git diff --staged` before each commit.
- After the grouping is confirmed, commit and push per §5. Don't ask again.
- Full test suite once before splitting, once after the last commit.
- Conventional Commits, subject ≤72 chars. `revert` is not an accepted type here.
