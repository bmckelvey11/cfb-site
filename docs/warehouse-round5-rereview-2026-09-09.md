# Round 5 re-review — the one open item from the Codex loop

**2026-09-09.** Closes the item `PLAN-REVIEW-LOG.md` left open and
`docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md` §10 carries forward:
*"Round 5's fixes are applied but were never re-reviewed."*

**This is not the loop's sixth round.** Codex reviewed a plan and Claude answered it. This
checks something different and narrower: whether those answers survived into the plan of record,
and whether they are still true against the live warehouse. A sixth Codex round would re-argue
the specification; this asks whether the specification we have is the one that was agreed.

**Verdict: the open item was understated.** Round 5's fixes were applied to root `PLAN.md` —
correctly, and I confirmed them there. But `PLAN.md` was superseded on 2026-09-08, and the
absorption into the master plan carried only part of them. The accurate statement of the open
item is not "applied but never re-reviewed." It is **"applied to a superseded document, two of
four not carried forward, and one of the four now refuted by the data."**

The deadlock itself does not reopen. What is left is four carry-forward decisions, not another
review round.

---

## Scoreboard

| # | Round 5 finding | Fix correct? | Survived into the plan of record? |
|---|---|---|---|
| F1 | Coach-season merge lacks team bridge | **No — refuted** | Partly: source named, mitigation dropped |
| F2 | Line period normalization missing | Yes | Substance yes, **gate lost** |
| F3 | New raw version promoted too early | Yes | **No — lost entirely** |
| F4 | Coach target omits `coach_seasons` grain | Yes, with drift | Partly: row named, grain table dropped |

---

## F1 — Codex was right, and the mitigation is the piece that got dropped

**Round 5 said:** `coaches` has name+season grain; the target needs `coachId+teamId+season`. A
real mid-season team change means one REST row can match multiple GraphQL rows. Preserve
unmatched or ambiguous REST rows outside the merged fact.

**The response said** the bridge already exists — `stg.coaches__seasons` carries
`seasons_school` beside `seasons_year`, "so a REST coach-season resolves to a team without
inference" — and added `core.coach_season_unmatched` for rows that resolve ambiguously.

**Measured 2026-09-09.** The row count is exactly right: 1,937, with both columns present. But

```
rows                              1,937
distinct (seasons_school, seasons_year)  1,816
school-seasons with >1 coach row    118
```

The bridge resolves *coach → team*. It does not resolve *team-season → coach*, and 118
school-seasons carry two or three coach rows apiece:

| School | Season | Coach rows (games) |
|---|---|---|
| Southern Miss | 2020 | Hopson (1), Walden (4), Billings (5) |
| USC | 2013 | Kiffin (5), Orgeron (8), Helton (1) |
| Wisconsin | 2022 | Chryst (5), Leonhard (7), Fickell (1) |

These are the exact case Codex named — a coach fired after week 1, an interim, a hire. So
"resolves without inference" is true in one direction and false in the direction the merge
needs. **The response under-credited the finding, then the master plan dropped the artifact that
made it safe anyway:** `core.coach_season_unmatched` appears once in `PLAN.md` and **zero times**
in the plan of record.

This is the finding that changes work. §8 step 3 merges Bucket C into `core`; at
`(coachId, teamId, season)` grain, 118 team-seasons have no single answer, and there is now
nowhere for them to go.

## F2 — substance holds, the gate has no home

**Round 5 said:** REST offers have no period; GraphQL's encoding may be NULL, `0`, an enum or a
string. Define a canonical full-game value, normalize both sides, and gate on the expected
matched full-game offer count.

**Confirmed 2026-09-09.** `stg_gql.game_lines.period` is `VARCHAR`, exactly three values, **zero
NULLs**: `game` 47,225, `firsthalf` 8,274, `firstquarter` 8,254. `game` is the canonical
full-game value. Round 5's response reported `game` at 46,765 — the drift is refreshes, and is
exactly why §7 now cites `scripts/verify_warehouse_plan.py` instead of an inline number.

**What is missing is the gate.** The response promised "step 6 gates on the expected match
count." §7 describes the correspondence and asserts uniqueness, but no step gates on a matched
full-game offer count — and my 2026-09-09 renumbering left steps 0–6, where step 6 is "remove
scraper entries." The gate was promised against a step number that no longer means what it did.

## F3 — lost entirely, and my renumbering is part of why

**Round 5 said:** the manifest promotes a new raw version after steps 5–7, before the drops and
the agreement gates. A late failure leaves the new source active. Stage it through every step
and promote atomically only after all validation passes.

**The response accepted this outright** — "correct and I had it wrong" — and moved promotion to
"after step 9 validates in full."

**It is not in the plan of record.** `manifest` appears three times in `PLAN.md` (lines 54–58,
70) and **zero times** in the master plan. The whole staged-promotion mechanism is absent, and
there is no step 9 to promote after: the plan now ends at step 6.

Two causes, and the second is mine. The absorption did not carry the manifest; and my 2026-09-09
revision deleted two steps and renumbered the rest, which would have orphaned this fix even had
it been carried. Step 0 still says re-scrapes "write to **new versioned paths**" — the premise
the manifest was built on — so the plan retains the hazard and not the control.

## F4 — carried, with a drift worth recording

**Round 5 said:** the three-source merge names `coaches` and `coach_seasons` but gives grain,
authority and key proof only for `coaches`.

**Confirmed 2026-09-09.** `stg.coach_seasons` is 1,961 rows and `(coach_id, team_id, season)` is
unique across all 1,961 — the key proof holds exactly. The response said **72 columns; there are
70.**

§6 names both REST sources in its merge row, so the source survived. The per-source grain table
— each source's exact grain, authority, conflict policy and row-preservation gate — did not.

---

## How this happened

§11's absorption table already declared it. It records what came forward from `PLAN.md` as
"Goal, pair manifest, key decisions, containment gate, result-informed separation." The merge
grain tables, the unmatched-row policy and the version manifest are simply **not on that list**.

The loss was disclosed, not silent. Nobody read the list as a gap, because a list of what was
carried does not look like a list of what was dropped. That is the same failure mode as §5's
column census: a claim sitting in prose that nothing re-checked. The difference is that §5 was
caught by a script, and this was not — because no script can check "did the successor document
keep the argument."

---

## What to do — four carry-forward decisions

Not a review round. Each is a decision about the plan of record.

1. **Restore `core.coach_season_unmatched`, or decide the 118 ambiguous team-seasons another
   way.** This is the only one that blocks: §8 step 3 cannot merge coach-seasons at
   `(coachId, teamId, season)` without an answer. Add it to §6's target column and to §12's core
   scope. *(Recommended: restore it — Codex's original reasoning is confirmed by the data.)*
2. **Give F2's gate a step.** Either fold "matched full-game offer count is as expected" into §8
   step 3's merge criteria, or add it to §7 as a stated post-merge check. It is cheap and it
   catches a whole class of normalization error.
3. **Decide whether the version manifest comes back.** Step 0 still creates new versioned paths,
   so the hazard it guarded is still real. Either carry the staged-promotion rule into §8 —
   re-anchored on step 4, the drop, which is the irreversible one — or state in §12 that
   single-writer local rebuilds do not need it and delete the versioned-paths language with it.
   *(Recommended: carry it. Step 4 drops tables; that is exactly the "late failure" case.)*
4. **Carry F4's grain table into §6**, and correct 72 → 70 columns.

**Not doing:** reopening the Codex loop. The findings were specificational by round 5, 30 of 31
were accepted, and none of the four above needs an adversarial reviewer to settle — they need
someone to decide and write them down.

---

## Reproduce

```bash
# F1 — the ambiguity
.venv/Scripts/python.exe -c "import duckdb;c=duckdb.connect(r'data/cfb.duckdb',read_only=True);print(c.execute('select count(*), count(distinct (seasons_school, seasons_year)) from stg.coaches__seasons').fetchone())"

# F2 — period encoding
.venv/Scripts/python.exe -c "import duckdb;c=duckdb.connect(r'data/cfb.duckdb',read_only=True);print(c.execute('select period, count(*) from stg_gql.game_lines group by 1 order by 2 desc').fetchall())"

# F3/F4 — what the absorption dropped
grep -c manifest PLAN.md docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md
grep -c coach_season_unmatched PLAN.md docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md
```
