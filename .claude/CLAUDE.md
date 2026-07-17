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

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
