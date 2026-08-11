
## [2026-07-22 02:40:13] - What should backlog cover?
**Choice**: Different spec/design file
**Alternatives**: Bet Labs parity plan, Single task description
**Context**: You'll give a path under .solopreneur/specs/ or .solopreneur/designs/
---

## [2026-07-22 02:57:26] - Git comfort level? (needed for ticket branch setup)
**Choice**: What's git?
**Alternatives**: Daily user, Know basics
**Context**: Plain-language explanations, no jargon
---

## [2026-07-23 18:15:17] - Build MVP-002 (candidate generation module) now, or just plan?
**Choice**: Build it now
**Alternatives**: Plan only
**Context**: Write search.py + tests/test_search.py directly, right here
---

## [2026-07-23 22:53:50] - MVP-003 already built+tested here (not via sprint worktree flow). How proceed?
**Choice**: Finish MVP-003 solo (Recommended)
**Alternatives**: Discard, redo via sprint, Run sprint on MVP-003 + MVP-004
**Context**: Commit current MVP-003 work now via QA+finish flow, skip sprint's parallel-worktree machinery since only 1 ticket was unblocked anyway.
---

## [2026-07-23 23:02:46] - Scope: which items to execute now?
**Choice**: P0 + P1 (8 items)
**Alternatives**: P0 only (3 items), All P0-P2 (10 items)
**Context**: Adds wind→wave means, R3/R4 pressure, country adj, shot-level transform (blocked), neutral-SG baseline. Bigger, some blocked/uncertain.
---

## [2026-07-23 23:02:46] - Where's this repo? cfb-site session has no golf-master context loaded.
**Choice**: C:\Users\mckel\dev\golf-master
**Alternatives**: Other path
**Context**: Standard sibling path guess based on doc location.
---

## [2026-07-23 23:02:46] - Item 7 (shot-level transform) is explicitly BLOCKED on upstream pre-2025 penalty-row reconstruction. How to handle?
**Choice**: Skip it, note blocker
**Alternatives**: Also do the upstream unblock first
**Context**: Do P0/P1 minus item 7, report it stays blocked.
---

## [2026-07-23 23:05:20] - Only MVP-004 unblocked right now (005/006/P1 all chain behind it). Build it now?
**Choice**: Yes, build MVP-004 (Recommended)
**Alternatives**: Skip sprint, I'll build inline
**Context**: Spawn engineer agent in isolated worktree for MVP-004 (holdout finalist grading + BH correction + result assembly), then QA review.
---

## [2026-07-30 21:41:52] - Default search params take ~26min+ at real scale (2.5x over the 10min target). How close the gate?
**Choice**: Accept & document reality (Recommended)
**Alternatives**: Bound the benchmark's scope, Tighten search defaults now
**Context**: Raise the benchmark's threshold to reflect measured runtime (~40min covering beam_search+grade_finalists), document the finding in the module docstring. Gate passes honestly, defaults unchanged, ticket closes as 'NFR not met as originally hoped, documented and accepted'.
---

## [2026-07-31 02:20:46] - P2-001 needs to narrate 'top-K search results' (candidate list, holdout grades, raw/corrected p-values). I confirmed: that data only exists transiently in `cli.py search` output — nothing persists a run's full top-K to disk. Only single-int `search_candidates_tested` gets saved per system. How to resolve?
**Choice**: Persist run artifact, build view for it
**Alternatives**: Narrate single saved system instead, Stop and don't build yet
**Context**: Add a `search --save-run` (or similar) that writes the full HoldoutFinalist list (candidates, p-values, holdout grades) to disk as a run record; add a route to view it; narrate that. Matches spec literally but expands scope beyond P2-001's stated 'no new screen' constraint.
---

## [2026-07-31 04:24:32] - Ticket leaves LLM stack unspecified. Repo has zero LLM deps today (CFBD token convention exists but is unrelated). What to use for the narration call?
**Choice**: Anthropic API (Claude)
**Alternatives**: OpenAI API, Something else / I'll specify
**Context**: Add `anthropic` pip dep. Key via env var (e.g. ANTHROPIC_API_KEY), same pattern as CFBD token resolution (env var then env.env file). Small, fast model (e.g. Haiku) for cost.
---

## [2026-07-31 05:00:30] - Not in isolated worktree, on master, uncommitted unrelated changes present (filter_modal.js/styles.css/index.html + untracked backlog/docs files). Set up isolated worktree for P2-001 build?
**Choice**: Yes, create worktree
**Alternatives**: No, work in place on master
**Context**: Protects master + your pending unrelated changes. New branch/worktree for P2-001 work only.
---

## [2026-07-31 05:31:01] - How many earlier seasons to scrape?
**Choice**: 2023-2024 (2 seasons)
**Alternatives**: 2021-2024 (4 seasons), As far back as API allows
**Context**: Smaller/faster pull, recent-only
---

## [2026-07-31 05:31:01] - Scoreboard + history, or scoreboard only first?
**Choice**: Both (scoreboard then history), all seasons
**Alternatives**: Scoreboard only first
**Context**: Full pull matching current 2025 dataset shape, one go
---

## [2026-07-31 07:08:53] - Pending uncommitted changes are a real, working feature bundle (Max ROI auto-select in filter modal, fieldset enable/disable sync, Load System dropdown swap, stats-verdict plain-English translator) — 224 lines, tests pass (382/382). No plan file or branch tracks it. What now?
**Choice**: Just commit as-is
**Alternatives**: Review then commit, Something else
**Context**: Skip review, commit now since tests already pass — fastest path if you already know this work is done.
---

## [2026-07-31 07:29:19] - Full diff is bigger than first shown: backtest.py adds MDE (minimum detectable edge), cluster block-bootstrap ROI CI, ICC (intraclass correlation), design-effect adjustment — real econometrics, not just a stats_verdict string. Tests pass (382/382) but that only proves no crash, not that the ICC/DEFF/MDE formulas are correct. Still want a blind commit, or should I verify the stats first?
**Choice**: Verify stats first, then commit (recommended)
**Alternatives**: Commit as-is now
**Context**: Use the econometrics skill to audit the ICC/DEFF/MDE/cluster-bootstrap math before committing — catches a wrong formula before it ships to a betting-stats display.
---

## [2026-07-31 07:49:24] - Audit done. Formulas (ICC, DEFF, MDE) verified correct against econometrics skill references + manual run — no bug found. But zero tests exist for any of the 4 new stats functions (240 lines). How to proceed?
**Choice**: Write tests, then commit (recommended)
**Alternatives**: Commit without tests now, Commit everything else, hold this one back
**Context**: I write unit tests for _icc_one_way, cluster_dependence_stats, _mde, stats_verdict before committing — closes the gap the audit found.
---

## [2026-07-31 07:58:43] - Where's "over-zero"? Not a path/host I recognize in this repo.
**Choice**: A local path — I'll type it
**Alternatives**: A remote host (scp/ssh alias), Different filename in same folder
**Context**: e.g. another drive/folder on this machine
---

## [2026-08-11 15:30:01] - Which solopreneur thing do you want run?
**Choice**: [User dismissed — do not proceed, wait for next instruction]
**Alternatives**: /solopreneur:sprint, visualize-org.py, /solopreneur:standup, /solopreneur:build
---
