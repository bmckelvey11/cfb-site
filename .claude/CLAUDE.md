<!-- GSD:project-start source:PROJECT.md -->

## Project

**Bet Labs Parity for cfb-site**

`cfb_system_maker` is a Python CLI + Flask tool that backtests college football betting systems against 2013-2025 CFBD data (13k games, enriched with running-stats features). It already has the backtest engine, feature registry, stats validation (Wilson CI, permutation p, holdout split), and a save/load/compare web UI. This project reshapes the web UI to function like Sports Insights Bet Labs — the product this whole feature set is modeled on — and grows the underlying data/feature registry to support it.

**Core Value:** A saved system's main page reads like a Bet Labs system editor (stat chips, cumulative money-won graph, plain-English active filters) and configuring any filter opens a live popup — slider or value table, per-value Record/ROI/Money, before you commit — instead of static inline form fields.

### Constraints

- **Tech stack**: Python + Flask + vanilla JS/CSS, no frontend framework — popup modals must be built with plain JS/fetch, consistent with existing `index.html`/`compare.html` pattern.
- **No lookahead**: any new registry feature must be computable pre-game (entering-game state only) or explicitly tagged into the `result_lookahead` group and visually quarantined, per existing `running_stats.py` convention.
- **Storage backward compatibility**: `SavedSystem` JSON changes (e.g. adding `theory`, `fade`) must default gracefully for systems saved before the field existed.
- **CSV schema stability**: `GameRecord` field order is the CSV read/write contract — any new game-level field needs a deliberate `storage.py` migration, not an ad hoc column add.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->

## Technology Stack

Python 3 + Flask + vanilla JS/CSS (no frontend framework). Vendored `cfbd-python` (pydantic v1, path-injected). Optional DuckDB warehouse. Waitress for `web` unless `--debug`. Full commands and architecture: repo-root `CLAUDE.md`.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

No lookahead unless tagged `result_lookahead` and UI-quarantined. `GameRecord` CSV field order is frozen — new game-level data goes in `features.json`. `SavedSystem` missing keys must default. Do not edit `cfbd-python/`. Details in root `CLAUDE.md`.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

CLI package `cfb_system_maker/` + Flask `web.py`. Acquire (`fetch` / `scrape` / `graphql` / `actionnetwork`) → build `games.csv` → enrich `features.json` → backtest/web/search. Live week is `upcoming` (separate CSV). Optional `duckdb` warehouse; serving still csv+features. Sibling trees: `over_zero/`, `cfb_totals_model/`. Root `CLAUDE.md` is the agent source of truth.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Prefer GSD so planning artifacts stay in sync:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Small fixes and doc edits may go straight to the files. Root `CLAUDE.md` is the agent source of truth; this file is the GSD overlay (`claude_md_path`).
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
