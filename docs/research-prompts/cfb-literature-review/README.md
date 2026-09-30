# CFB Literature Review Prompt Pack

Nine Perplexity Deep Research prompts that survey the academic and quantitative literature on predictive and descriptive statistics for FBS college football, weighted toward against-the-spread and totals prediction.

## How to run

1. Paste one complete file into Perplexity with Research mode on. One file is one run.
2. Run `01` first. It stands alone as a full annotated bibliography, and its gap list can steer the rest.
3. Run `02`–`08` in any order. Export and save each report.
4. Run `09` last, with the eight reports attached.

Every file carries the same shared evidence rules, so each one runs on its own. Files are about 10 KB. If Perplexity truncates a paste, put the "Shared research instructions" section in a Perplexity Space's instructions and paste only the title and research assignment.

## Prompts

| File | What it asks |
| --- | --- |
| [01-literature-map.md](01-literature-map.md) | Breadth-first map of every FBS predictive and descriptive stats study; a complete bibliography if you run only one prompt |
| [02-rating-and-outcome-models.md](02-rating-and-outcome-models.md) | Which rating and prediction models are published, and how they do against the opening and closing lines |
| [03-score-and-margin-distributions.md](03-score-and-margin-distributions.md) | What is published on FBS margin and total distributions, and on turning a point forecast into a cover or over probability |
| [04-descriptive-metrics-and-stability.md](04-descriptive-metrics-and-stability.md) | Which team statistics explain FBS results, how predictive and stable each is |
| [05-ats-market-efficiency.md](05-ats-market-efficiency.md) | Whether the FBS spread market is efficient, which biases are documented, which betting rules survived publication |
| [06-totals-markets.md](06-totals-markets.md) | FBS totals-market evidence beyond the studies already in hand |
| [07-line-movement-and-bookmaker-behavior.md](07-line-movement-and-bookmaker-behavior.md) | Opener versus close, predictable movement, CLV as a skill measure, how books set lines |
| [08-evaluation-methods-and-pitfalls.md](08-evaluation-methods-and-pitfalls.md) | Standards and critiques for evaluating football betting research: snooping, decay, power, scoring rules, leakage |
| [09-final-synthesis.md](09-final-synthesis.md) | Reconciles `01`–`08` into one verdict, a deduplicated table, ranked hypotheses, and a citation audit |

## Related packs

`research/totals/docs/research-prompts/fbs-totals/` asks how to build the totals system (odds-data audit, score distributions, price discovery, staking). This pack asks only what has been published and what it found.

A report from this pack that answers a question the repo's docs do not already answer gets written up in the owning unit's `docs/`, per the root `CLAUDE.md` rule on new findings.
