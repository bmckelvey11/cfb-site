# Discovery Brief: Automated System Discovery for cfb_system_maker

**Date:** 2026-07-22
**Idea:** Add a layer after the backtest engine that auto-searches the filter space and surfaces profitable betting systems, instead of requiring a human to manually build filter combos in the UI.

## Problem Statement

Today, finding a profitable system in cfb_system_maker is manual: a human opens the filter modal, picks a combination of ~15 core `SystemFilter` fields (side, favorite/underdog, spread/total thresholds, seasons, teams, conferences) plus up to ~34 registry features (with perspective variants, ~60-70 effective dimensions), and checks the resulting grade one combo at a time. Good systems may exist in the space that a human never thinks to try, and manual search doesn't scale with the registry's growth.

## Target Audience

Internal — this is a feature for the existing cfb_system_maker user (the CEO/analyst using the tool), not a new customer segment. No external market to size.

## Competitive / Prior Art Landscape

Not a market analysis (internal feature), but relevant prior art on the *technique*:

| Approach | Fit |
|---|---|
| Brute-force grid search | Matches Bet Labs "Trends"-style exhaustive combo search. Simple, but the combo count explodes fast (see Risks). |
| Decision-tree / rule induction (CART, CN2) | Learns filter thresholds directly from data instead of human-guessed thresholds. Well-trodden technique. |
| Genetic/evolutionary search | Standard in quant "rule mining" (trading-rule GP literature) once grid search becomes intractable. |
| Quant factor-mining analog | This problem is structurally the same as multi-factor backtesting in quant finance — the multiple-comparisons literature there (Harvey/Liu/Zhu, López de Prado's Deflated Sharpe Ratio / PBO) is the most directly transferable body of work. |

Confidence: High on the techniques being standard; Low on specific competitor UI (no web access this session to verify what Bet Labs' own auto-finder, if any, actually shows users).

## Technical Feasibility

- **"AI agent" is the wrong frame for the search itself.** `matches_system`/`grade_bet` are deterministic, fast, pure functions over an in-memory list — a search loop calling `run_backtest` per candidate is combinatorial/statistical search (grid, greedy/beam, or genetic), not an LLM tool-calling loop. An LLM has a legitimate but narrower role: narrating the top-K results in plain English after the fact, or steering *which* dimensions a beam search explores next — not scoring candidates itself. Putting an LLM in the scoring loop would be slower, non-reproducible, and costs more for no benefit.
- **Integration point:** new `search.py` module, new CLI command (`search`), reusing `run_backtest`/`SystemFilter`/`compute_grade` as-is. No new data pipeline needed.
- **Combinatorial explosion is real.** ~15 core filter knobs alone is 2^15 subsets before even considering threshold discretization or the 60-70 feature dimensions. Brute force over the full space is intractable — needs greedy/beam search or genetic search. `compute_grade`'s existing `_overfit_score` (penalizes filter count) is a signal the codebase already treats large combos as suspect.
- **Effort:** Medium for a first version (plain statistical search, no LLM) — few days of focused work, reuses existing engine. LLM narration on top is a small increment *if* it stays out of the scoring loop; an LLM-driven candidate-proposer instead of greedy/beam search would push this to Medium-Large for no clear benefit — worth resisting if it comes up as a "requirement."

## The Core Risk: Multiple Comparisons / Data Dredging

This is the dominant risk and it's structural, not incidental. The existing stats guardrails (`_wilson_interval`, `_permutation_p_value`, `split_holdout`, `_overfit_score`) were built and validated for **one system tested by a human at a time**. A p=0.03 result means something when a human tests one hypothesis. It means almost nothing when an agent silently tests 50,000 combos and surfaces the ~1,500 that clear p<0.05 by chance alone.

None of the three existing statistical functions currently track *how many combinations were tried* — that bookkeeping doesn't exist yet and has to live in the new search layer. Required before this feature can be trusted:

1. **FDR correction** (Benjamini-Hochberg, field-standard for large-scale screening) on the significance threshold, scaled to the number of combos actually evaluated — not the raw single-system p-value cutoff.
2. **Mandatory out-of-sample routing.** Every candidate must be graded on `split_holdout`'s holdout seasons, never the seasons it was searched over. `split_holdout` exists today but isn't wired into a search loop.
3. **UI disclosure**, not just a backend fix: auto-generated systems need a visible marker (e.g. `SavedSystem.source: "manual" | "search"` + "tested against N candidates") so a user doesn't mistake a dredged result for a manually reasoned one. `SavedSystem` already defaults new fields gracefully (per the `theory`/`fade` precedent), so this is a low-risk schema change.

Skipping this isn't a "nice to have to add later" — an auto-search feature that surfaces ungated results is actively worse than the current manual process, because it manufactures false confidence at scale instead of one system at a time.

## Unique Angle

The codebase already has more of the statistical infrastructure needed to do this *safely* than most quick "auto-finder" implementations would (Wilson CI, permutation p-value, holdout split, overfit-penalized grading). The differentiator isn't "AI finds bets" — it's "auto-search that's honest about how much you should trust what it finds," using the existing `compute_grade` A-F composite score (already blends sample size, ROI z-score, consistency, permutation p, overfit penalty) as the surfaced confidence signal instead of raw ROI.

## Risk Factors

- **Data dredging / false discovery** (see above) — the dominant risk, must gate MVP scope.
- **False user confidence** if auto-found systems aren't visually distinguished from manually-built ones.
- **Combinatorial cost** without a smart search strategy (greedy/beam/genetic vs. brute force).
- **Scope creep toward "real AI agent"** — pressure to make this LLM-driven end-to-end when a deterministic search + optional LLM narration is simpler, cheaper, faster, and more reproducible.

## Go/No-Go Recommendation

**Go — but scope the MVP around the statistical guardrails, not the search algorithm.**

The search mechanics (greedy/beam search over the filter registry) are the easy, well-understood part. The multiple-comparisons correction and mandatory holdout routing are the part that makes this trustworthy rather than a liability. Build order should be: (1) wire `split_holdout` into a new search loop so every candidate is holdout-graded, (2) add combo-count-aware FDR correction on top of `_permutation_p_value`, (3) plain greedy/beam search using `compute_grade` as fitness, (4) `SavedSystem.source` marker + "N candidates tested" UI disclosure, (5) optional LLM narration layer on top, last and separable.

Do not build an LLM-in-the-loop "agent" for the search itself — reserve "AI agent" framing for the narration layer only, if built at all.

---
*Research conducted without live web access this session — competitor-specific claims (item 3 above) are flagged Low confidence and should be verified before being stated externally (e.g. in a spec or release notes).*
