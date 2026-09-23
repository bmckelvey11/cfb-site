# Objective review — the pred-tracker-model against the user's stated intent, 2026-09-23

## 1. Question

On 2026-09-23 the user was asked what the pred-tracker-model was meant to be. The user chose this
option: *"A consensus fair spread built from many models. You bet wherever it disagrees with the
books and judge success on game results against the spread."* That option is the yardstick here,
and its provenance is in §6.

Five questions follow from it:

- **Q1.** What objective does the code implement?
- **Q2.** Is the served `edge` a fair-spread pick?
- **Q3.** What evidence already exists on the user's yardstick?
- **Q4.** What can the archive test at the number actually bet, and what can only the forward log test?
- **Q5.** Was the 2026-09-02 pivot to line movement a reframing of the user's goal, or a replacement of it?

**A conflict, named.** `research/spread/CLAUDE.md` and `docs/README.md` say the margin-vs-close
question is closed, and that `archive/` must never be cited as current. This review reads
`archive/spread-margin-era/` only as the historical record of what was already tested against
the user's yardstick. Every citation from it is labelled **(archived)**. The review does no new
modelling and computes no new ATS, ROI, CLV or hit-rate number. It does not reopen the margin
question. §9 proposes edits to the instruction files and does not make them.

## 2. Method

**Files read.**

- Code: `research/spread/scripts/eval_line_movement.py`, `weekly_slate.py`,
  `eval_version_b.py`, `edge_vs_market_move.py`, `version_b_ceiling.py`.
- Live docs: `research/spread/docs/actionable-picks-2026-09-17.md`, `line-movement-results.md`,
  `review-2026-09-02-composite-spread.md`, `session-guide-2026-09-02.md`,
  `model-columns-ats-2026-09-17.md`, `panel-ats-2026-09-17.md`, `panel-vs-line-2026-09-17.md`,
  `methods-review-2026-09-21.md`, `combining-predictions.md`, `line-shopping-results.md`, and the
  B4/B5 rows of `prereg-line-movement.md`.
- Archived: `archive/spread-margin-era/prediction-tracker-findings.md` **(archived)**.
- Standard: `docs/model-evaluation-standard.md` (hard gates and Tier 1 metrics).
- Memory and history: `.remember/today-2026-09-01.done.md`, `today-2026-09-02.done.md`,
  `archive.md`, and the agent memory note `spread-composite-goal-closed.md`.

**Commands run.** All of them were read-only.

- `grep`, `sed` and `cat` over the files above.
- `git log -L` on `add_side`, and `git log` / `git show` on `weekly_slate.py` since 2026-09-16.
- The header line of `data/processed/movement_forward_log.csv`, to list its columns. No values were read.
- A throwaway Python filter over the local Claude Code session transcripts
  (`~/.claude/projects/C--Users-mckel-dev-cfb/*.jsonl`). It printed only the messages the user
  typed and the agent's text turns, with UTC timestamps. It lived in the session scratchpad and
  is **not in the repo**. The transcripts are local to this machine, so a reader cannot
  reproduce §6 from the repository alone.
- The transcript search tool, for "composite point spread" and "closing line value is very
  valuable". It returned only the docs' own text.

No script that writes under `data/` was run, and no estimator, grader or backtest was run.

## 3. Data and date range used

Every number below comes from a file named beside it. None was computed for this review.

| Source | Coverage, as the cited file states it |
|---|---|
| PT archive (`ingest/prediction_tracker_lines.csv`), via the cited docs | 2001–2025; the movement support is 14,068 games, 2006–2025 |
| Action Network consensus close vs PT `line` | 1,440 matched games, 2024–25 (`line-movement-results.md` § target) |
| Forward log, reads in `line-movement-results.md` | 2026-08-31 to 2026-09-16: 91 graded games, 2 week clusters |
| Forward log, as audited in `methods-review-2026-09-21.md` | snapshot of 2026-09-21: 147 graded games, 3 week clusters |
| Served slate behind the §0 regression | 2026-09-16, 57 games (`actionable-picks-2026-09-17.md` §0) |
| User wording | transcript `4d457f0d…` (2026-09-02) and transcript `64710c25…` (2026-09-23) |

## 4. Implemented objective vs intent

**Q1.** The fit targets the closing line, anchored on the PT opener. It is scored on squared error
of the move. Forward, it is graded on the slope of the remaining move, with CLV and ATS reported
beside that slope. The ATS column is graded at PT's line, which is not the number the slate prints.

| dimension | user wanted | implemented | file:line |
|---|---|---|---|
| anchor | the books' number when the bet is made | **Fit:** the PT opener (`lineopen`) is the anchor for every estimator. **Served:** E4 is compared with the *current* book fair. **Version B:** the first capture on or after Monday 00:00 ET | `eval_line_movement.py:179,191,194`; `weekly_slate.py:84,210,647-649`; `eval_version_b.py:63-71` |
| target | a fair spread, meaning what the game should be priced at | the closing line: `y = -line`, "TARGET: the close". PT's `line` is a late line, and version B uses the Action Network consensus close (book 15) | `eval_line_movement.py:172`; `eval_version_b.py:132-145` |
| loss / metric | ATS win rate against 52.38% at the number bet | **Archive:** squared error of the move, R² relative to "the line does not move". **Forward, primary (B4):** slope of (close − line_Monday) on (pred − line_Monday) | `eval_line_movement.py:216-220`; `eval_version_b.py:282-290` |
| bet trigger | bet wherever the model disagrees with the books | side = sign(E4 − book fair), graded at \|E4 − book fair\| ≥ 1. **This matches the user's words in form only; Q2 shows why.** Version B uses a different trigger: \|E4 − `line_pt`\| ≥ 1 | `weekly_slate.py:648-671,751-753`; `eval_version_b.py:306-308` |
| grading unit | game result against the spread (cover or not) | **Primary:** points of line movement (B4 slope). **Secondary (B5):** CLV, beat-close share, and ATS | `eval_version_b.py:285-290,304-318` |
| graded against | the number the bet was placed at | B4 and CLV are graded against the AN consensus close. B5's ATS is the final margin against `line_pt`, PT's line at the anchor capture. It is **not** the slate's `side_line` at `side_book` | `eval_version_b.py:282,315` |

The in-code documentation says the same. The docstring at `weekly_slate.py:53-57` calls the
opener-anchored move "worth 2-4 points of CLV AT THE OPENER" and says to treat `move_vs_fair` as
"the signal to grade, not a bet". The comment at `weekly_slate.py:139-157` stamps
`EDGE_DEF_VERSION = 1` and says "That definition is under review". Version B's docstring
(`eval_version_b.py:12-15`) names B4 as the slope and B5 as "CLV and ATS of a Monday bet".

## 5. Evidence on the user's yardstick

### Q2 — the served `edge` is not a fair-spread pick

**Confirmed against the current code.** `add_side` sets `gap = t.E4 - fair`, where `fair` is the
book fair, then `edge = |gap|` (`weekly_slate.py:648-649,671`). `git log -L` on `add_side` shows
its last change on 2026-09-09 (`2da82fbb`). That is before the 2026-09-16 slate that produced the
−0.908. The later commits touch the docstring, the `EDGE_DEF_VERSION` stamp and book pricing,
not `gap` or `fair`. E4 is still fit with the opener as its anchor (`BENCH = "lineopen"`,
`weekly_slate.py:84`).

The signed edge splits into two terms:

$$
\begin{gathered}
e = E_4 - F = (E_4 - O) - (F - O)
\\[1em]
\begin{array}{rl}
\text{where}\quad e: & \text{signed served edge, points; the slate's edge column is } |e| \\
E_4: & \text{E4's predicted close, PT sign (positive = home favoured), points} \\
F: & \text{book fair at capture, the median home spread across the book set, PT sign, points} \\
O: & \text{PT's recorded opener, PT sign, points}
\end{array}
\end{gathered}
$$

The first term, $E_4 - O$, is how far the model leaves the opener. The second, $F - O$, is how far
the market has already moved since the opener. E4 is a shrunk tilt away from the opener, so its
first term is small. On the 2026-09-16 slate, mean $|E_4 - O|$ was 0.51 against a mean $|e|$ of
1.11. The second term therefore dominates. `actionable-picks-2026-09-17.md` §0 reports
$\operatorname{corr}(e, \text{move since opener}) = -0.908$ on 57 games, and
$e = +0.28 - 0.97 \times \text{move}$. That script measures the move as PT's `line_pt` − `open_pt`,
not $F - O$, which is a close proxy.

Worked case from that doc: Ohio @ South Alabama opened 3.5 and the book fair was 7.0. E4 was 3.3,
so the edge was −3.7. Taking "Ohio +7" is a bet that the market's 3.5-point move reverses. It is
not a read on the game. `methods-review-2026-09-21.md` finds the same thing at the forward
grader: B4's regressor spends 71% of its variance on the revert-to-opener component.

So the served trigger bets wherever E4 disagrees with the books, as the user asked. But the
disagreement is mostly the market's past move with its sign flipped. E4 is not a fair spread
either: its target is the close (`eval_line_movement.py:172`), not the game.

### Q3 — every existing ATS test is graded against the close, and none clears break-even

Each test bets the side where the models disagree with the market, then grades the game result
against PT's `line`. That `line` is a late line: its mean distance from the AN consensus close is
0.69 points on 1,440 games (`line-movement-results.md` § target).

| test | source | bets / cells | ATS | reading |
|---|---|---|---|---|
| 10 combination rules (E1–E14), walk-forward | `archive/spread-margin-era/prediction-tracker-findings.md` "The betting objective" **(archived)** | 12,560 graded | **50.31%**, −2.07 pts vs break-even [−3.29, −0.91], p = 0.0020 | significantly *below* the vig; 89.1% of games sit within a point of the line |
| raw model median, no fitting | `review-2026-09-02-composite-spread.md` §1 | 17,166 | 49.7%; the widest-disagreement bucket (> 5 pts) is 49.0% on 1,948 | "the panel disagrees with the close often and by a lot, and when it does, the close is right" |
| best single column by prior skill, walk-forward | `model-columns-ats-2026-09-17.md` §1 | 15,311 over 22 seasons | season mean **0.5001** [0.4900, 0.5103], above break-even in 1 of 22 seasons | a well-powered coin flip; 0 of 109 columns has a CI lower bound above 0.5238 |
| every column × thresholds {1, 2, 3} | `panel-ats-2026-09-17.md` | 436 cells | pooled 0.4982; **0** survive BH q < 0.10 on week clusters | the one survivor, `linecrunch`, was retracted as a 3-cluster artifact |
| RMSE of each column against the realised margin | `panel-vs-line-2026-09-17.md` | 141 columns | not an ATS test, as the doc's own correction says | 0 of 141 beat the line; corr(RMSE ratio, sd of deviation from the line) = +0.970 |

These tests measure the user's yardstick, bet where the models disagree and grade ATS, at one
price: the late line. At that price the answer is uniform. The models' disagreement with the
market carries no ATS edge.

### Q4 — the number actually bet

**What the archive can test.** It can grade ATS at one earlier number: the opener. The A6
walk-forward table in `line-movement-results.md` bets E4's side at the opener when E4 predicts a
move:

| rule, A6 decontaminated | bets | CLV at the opener | ATS at the opener |
|---|---|---|---|
| E4, predicted move ≥ 1 | 2,902 | +1.24 [+0.76, +1.70] | **52.0% [49.3, 54.6]** |
| E4, predicted move ≥ 2 | 338 | +3.72 [+1.58, +5.85] | 60.4% [49.4, 72.4] |

This is the closest existing test of the user's yardstick. The proxy fails it even at a price the
live pipeline never gets. The same doc's 2026-09-09 correction reads the ≥ 1 row as "the point
estimate is on the losing side, ROI −0.72%, p vs break-even 0.79". The fixed-set decay curve in the
same doc runs E4 ≥ 1 from 52.5% at the opener to 48.5% at the close.

Two other opener numbers exist, both weaker:

- `review-2026-09-02-composite-spread.md` §1 gives 53.9% on 1,641 games at the opener for the
  raw-median disagreement above 5 points. It is exploratory: one bucket, no multiplicity adjustment.
- Its §6 quotes 55.9% for opener bets with ≥ 2 points of edge. That figure comes from
  `archive/spread-margin-era/prediction-tracker-model-eval.md` §8 **(archived)**.

**What the archive cannot test.** It cannot grade ATS at any number the live pipeline could have
bet, for three reasons.

- **The opener is not reachable.** Week 1 2026 openers were posted April to June. The median
  remaining move from Monday to the close was 0.0 points (`review-2026-09-02-composite-spread.md`
  §6, 106 games).
- **The archive's "close" is a late line.** PT's `line` sits 0.69 points from the real close on
  average, so there is no mid-week price to bet at.
- **Nothing in the archive is timestamped.** `tick-anchored-model-infeasible-2026-09-17.md`
  explains why a current-line anchor cannot be fit. There is also no per-book archive before 2024,
  so the "disagrees with the books" trigger has no historical book fair to disagree with.

`line-movement-results.md` says the same: "The archive can only price that rule at the opener."

**What only `movement_forward_log.csv` can test.** The forward log stores the decision-time fields
of the served bet on every row. The columns are `side`, `side_line`, `side_book`, `side_odds`,
`edge`, `book_fair`, `edge_def_version` and `book_set_version`. That is ATS at the number the slate
printed, on the side where E4 disagreed with the book fair. It is exactly the user's yardstick.
It also meets the evaluation standard's hard gate that prices be reconstructible at decision time
(`docs/model-evaluation-standard.md`, "Hard gates").

**No grader reads those columns.** `eval_version_b.py` B5 sets side = sign(E4 − `line_pt`) and grades
`margin − line_pt` (`eval_version_b.py:306-318`). The existing forward record, 19–24 ATS
(0.442 [0.287, 0.597]) on 43 bets over 2 week clusters (`line-movement-results.md`, read of
2026-09-15), is therefore ATS at PT's line on a different trigger. Two more details weaken it:

- The graded anchor is a Tuesday line for 62% of games (`methods-review-2026-09-21.md` F1).
- `actionable-picks-2026-09-17.md` §2 and `version_b_ceiling.py:46` both call
  |E4 − `line_pt`| "|edge|". That label mixes it up with the served edge, |E4 − book fair|.

**ATS at the printed number is not established.**

**When B3 allows a read.** The rule is quoted verbatim from `eval_version_b.py:59-60`:

> No verdict before season end; at season end, confirmatory inference requires ≥ 8 week clusters,
> and with fewer the read is reported as inconclusive.

In code, "season end" means the ET date falls outside 25 August to 15 December
(`eval_version_b.py:56,74-80`). The earliest version B verdict is therefore **2026-12-16**, and
only with ≥ 8 week clusters. B3 governs B4 and B5. An ATS read at `side_line` is not registered
anywhere, so it would need its own amendment, written before any of that data is looked at.

## 6. The pivot (Q5)

All times are UTC. The 09-02 transcript is `4d457f0d…`; the 09-23 transcript is `64710c25…`.

| when | who | words | source |
|---|---|---|---|
| 09-02 10:30 | **user** | "at the bottom line i want to make a composite point spread from all those different models to gain an edge over the books" | transcript 4d457f0d |
| 09-02 10:39 | **user** | "the predictions come out at the beginning of the week so if the composite can beat the closing line" | transcript 4d457f0d |
| 09-02 10:39 | agent | splits this into claim 1, "Composite as a better forecast of the game than the close. Dead.", and claim 2, "Composite as a forecast of where the close will go, bet at Monday's line. Alive." | transcript 4d457f0d |
| 09-02 11:10 | *pasted research memo* | a forecast-combination memo. It is not the user's own words and is not quoted as such | transcript 4d457f0d |
| 09-02 11:14 | **user** | "the sweep was targeting the wrong thing" | transcript 4d457f0d |
| 09-02 11:14–11:16 | agent | "Your goal is different: the panel publishes early, so the question is whether it forecasts where the line goes." Commits `prereg-line-movement.md`: "Target is the close, anchor is the line available when the forecasts appear." | transcript 4d457f0d; commit `c9bbab5`, 2026-09-02T11:16:20Z |
| 09-02 11:18 | **user** | "the whole thing is that if I can get points early on the closing line then the obvious closing line value is very valuable" | transcript 4d457f0d |
| 09-02 11:18 | agent | "Yes — that is the thesis exactly … Closing line value converts to win rate at about 3.2 points per point". *Later withdrawn:* `line-movement-results.md` says do not convert CLV to ROI with the 3.2 figure | transcript 4d457f0d |
| 09-02 11:24 | agent | "the ATS column shows it cashes: 57.8% is +10% ROI at −110". *Later withdrawn:* `line-movement-results.md` "Corrected 2026-09-09 — the ATS record does NOT confirm the CLV is cashable" | transcript 4d457f0d |
| 09-02 12:44 | **user** | "dont take the previous handoff's conclusions as a gate to not try models as it was targeting different things and was not clear on the goal" | transcript 4d457f0d |
| 09-02 | agent | `review-2026-09-02-composite-spread.md` line 3: "**build a composite point spread from all the models to gain an edge over the books.**" A close paraphrase of the user's 10:30 words, set in bold without quotation marks | the doc |
| 09-02 | agent | `session-guide-2026-09-02.md` §1: "The user's stated goal was **a composite point spread from all the models that gains an edge over the books.**" (paraphrase). It also quotes the user's 11:18 message in italics. The quote is faithful except that it drops "the whole thing is that" and "then" | the doc |
| 09-01/02 | agent | `.remember/today-2026-09-01.done.md`: "composite-vs-close closed (49.7% ATS); … direction: compose book lines not models". `today-2026-09-02.done.md` and `archive.md` have no entry on the pivot. No user wording appears in `.remember` | `.remember/` |
| to 09-23 | agent | memory `description:` "User's goal is closing-line value from an early composite spread" | `spread-composite-goal-closed.md` |
| 09-23 10:49 | **user** | "review the prediction tracker spread model and its objective vs what I wanted it to be" | transcript 64710c25 |
| 09-23 | **user** (chose an option the agent wrote) | chose "Fair spread with ATS edge". Turned down "Early number that beats the close" (CLV) and "Both, in layers" ("CLV as the near-term check and ATS as the final test") | transcript 64710c25 |

The order matters. The user's end goal was stated once and never changed: *an edge over the
books*. The user said the margin sweep targeted the wrong thing. The agent then turned that into
a movement target and committed the preregistration, and only after that did the user name CLV.
The user did name CLV, in their own words, as how the edge would be won: get points early, and
the closing line value follows. The two agent claims that made CLV look like the same thing as
ATS profit were both withdrawn by the tree within a week. The objective was not put back to the
user when they were.

The 2026-09-23 evidence is one choice among three options the agent wrote. It carries one
signal: offered CLV as a near-term check with ATS as the final test, the user chose ATS alone.
Reading more into a single choice would overreach.

## 7. Verdict: reframed

**Reframed, and the user has now withdrawn the reframing.** On 2026-09-02 the user asked for an
edge over the books. The user supplied the closing-line-value mechanism in their own words. The
move from margin to line movement was therefore a reframing the user endorsed, not an agent
substitution of the goal. Two things since have opened a gap between that reframing and the goal.

First, the step that made CLV look sufficient did not hold. The 3.2 points-per-point conversion
and "it cashes" were both withdrawn by the tree. Even at the unreachable opener, E4's +1.24 points
of CLV bought 52.0% [49.3, 54.6] ATS (`line-movement-results.md`, A6). The objective stayed
movement and CLV anyway.

Second, the served bet does not implement the user's 09-02 mechanism either. It does not get
points early. It bets after the move, against the current fair, and its edge is the move with its
sign flipped (Q2).

Measured against the 2026-09-23 yardstick, the result is:

- The target (the close), the loss (movement R², the B4 slope) and the grading price (`line_pt`)
  are all proxies the user has now declined.
- The bet trigger matches in form only.
- No grader measures ATS at the number bet.

## 8. What this does NOT support

- **Not a version B verdict.** B3 stands. Nothing here reads B4 or B5 as evidence either way.
- **Not a claim that E4 or amendment A6 is wrong.** E4 forecasts the move at the opener, as
  registered. This review is about whether that object is the one the user asked for.
- **Not a claim that the slate has no ATS value at the printed number.** That is not established.
  No grader has measured it.
- **Not a claim that the pivot was an agent error.** The user supplied the CLV mechanism. The
  errors on record are the two withdrawn claims, and both are already corrected in
  `line-movement-results.md`.
- **Not a reopening of the margin question.** The Q3 numbers are cited as they stand, not
  re-estimated. The archive is cited as a record **(archived)**, not as current.
- **Not strong evidence about the user's intent beyond one choice.** The 09-23 yardstick is option
  text the agent wrote, picked by the user.

## 9. Proposed edits (not made)

**`research/spread/CLAUDE.md`**

- Add an **Objective** line. The user's yardstick, per 2026-09-23 and this review, is ATS at the
  number actually bet, where the model disagrees with the books. Line movement and CLV are the
  mechanism the tree tests, not the measure of success.
- Qualify "do not cite it as current". Allow reading `archive/spread-margin-era/` as the record
  of what was tested against the ATS yardstick, when each citation is labelled (archived).

**`research/spread/docs/README.md`**

- The opening question ("is any of that reachable at a price you can bet?") and "Current
  position" never name the ATS yardstick. Add one sentence pointing here.
- Add `objective-review-2026-09-23.md` to "Reading order". This commit adds only its row in the
  Documents table.

**Agent memory**

- Rewrite the `description:` of `spread-composite-goal-closed.md`. Its present wording is "User's
  goal is closing-line value…". The replacement should say the goal is ATS at the bet number, and
  that CLV was the user's own 09-02 mechanism, which they declined as the yardstick on 09-23.
- Replace the note's "pending review" paragraph with a pointer to this doc.
- Drop its stale "57.8% ATS" E6 claim: amendment A7 retired E6.
- Update the matching `MEMORY.md` line, which still reads "objective review pending".

**Flagged, not edited.**

- `combining-predictions.md` is a living doc. Its `model_fair` and bet rule (§2–3) are not what
  `add_side` does, and it relies on the retired 3.2 constant.
- `version_b_ceiling.py:46` and `actionable-picks-2026-09-17.md` §2 label |E4 − `line_pt`| as
  "|edge|".
- The docstring at `weekly_slate.py:53-57` still presents opener CLV as the reason to grade
  `move_vs_fair`.

**What a build aimed at the user's yardstick would need.**

1. **A forward-log ATS grader at the printed number, registered first.** Side = the slate's
   `side`, graded at `side_line` and `side_odds`, at `edge` ≥ 1, one `edge_def_version` and one
   `book_set_version` era at a time. It should adopt B3's rule (no read before season end, ≥ 8
   week clusters). It should report the Tier 1 metrics of `docs/model-evaluation-standard.md`:
   ROI with an interval, a proper score against the same-time de-vigged market (the prices are in
   the log), and the trial count. It must be written as an amendment before anyone looks at those
   columns.
2. **A decision on the served `edge` before more weeks accrue.** Under `EDGE_DEF_VERSION` 1,
   grading (1) grades "fade the move since the opener" (Q2). It does not grade "fair spread against
   the books". Any redefinition bumps `EDGE_DEF_VERSION` in the same commit
   (`weekly_slate.py:154-157`), and the eras are graded separately.
3. **A new information source for the fair spread itself.** On this panel, disagreement with the
   close has no ATS edge in any test in Q3. `review-2026-09-02-composite-spread.md` already said
   the margin question should not be reopened "without a new information source". Examples:
   models pulled before PT compiles (`line-movement-results.md` "What follows" item 2), or inputs
   the panel does not carry.
4. **Keep line shopping as the one measured, mechanical gain.** The best number is worth +1.26
   [+0.94, +1.58] win-rate points per bet over the consensus (`line-shopping-results.md`). It does
   not make a positive-EV system by itself: sides with a full point available run 52.8% [48.7, 56.9]
   at the shopped number.
