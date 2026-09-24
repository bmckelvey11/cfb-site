# Tuning lab GUI: what it does and how to use it

The GUI is a local web page over the [tuning lab](tuning-lab-guide.md). Mostly it lets you
**look**:
- the live shadow test's health;
- each game's predictions and probability table;
- runs, comparisons, data freshness, and the question ledger.

It can **start one thing**: a tuning run. Everything else that changes the lab stays on the
command line: freezing, the daily tick, alias moves, and the priced replay.

For what the models are and how the lab works, read the [lab guide](tuning-lab-guide.md)
first. This page covers only the GUI.

---

## Quick start

1. Start it from the repo root:
   ```text
   .venv-lab-ui\Scripts\python -m streamlit run models/tuning/ui/app.py
   ```
   Or pick **Tuning Lab** in the Claude app's preview list.
2. Open **http://127.0.0.1:8501**. Use that address, not `localhost`: the page may
   half-load on `localhost`.
3. Look at the sidebar. A **red box** there means something needs you (see
   [Alerts](#alerts-and-what-to-do)).
4. Pick a page from the sidebar list.

**First-time setup:** the GUI has its own Python environment, kept separate so the
shadow tick's `.venv` never changes. Create it once:

```text
python -m venv .venv-lab-ui
.venv-lab-ui\Scripts\pip install -r requirements-lab-ui.txt
```

It also calls the main `.venv` behind the scenes, so that must exist too.

**It only listens on this PC** (127.0.0.1). Nothing on your network can reach it.

---

## The sidebar

Always visible, whatever page you're on.

| Item | Meaning |
| --- | --- |
| **Page** | The page list |
| **Lab root** | Which lab folder the GUI reads. Normally `data\processed\tuning`. A **scratch lab** label means a test copy |
| **Reload** | Re-reads everything from disk. Use it after a tick or when a job finishes |
| **Jobs in flight** | Tuning runs queued, starting, running, retrying, or being cancelled |
| **Champion / Challenger** | The live model and the one being tested against it |
| **CFBD games file** | Hours since the schedule and scores file was refreshed. More than ~24 h means the 05:00 refresh didn't run |
| **Latest shadow snapshot** | The last week the live test predicted, and when. "(rehearsal)" means week 4, which never counts |
| **Drafts saved** | Run specs saved by New run, and whether this session's draft passed validation |
| **Red boxes** | Blocking alerts from the live test. Act on these |

---

## The pages

### Shadow: is the live test healthy?

**For:** checking the 2026 weeks 5–8 live test. It's read-only.

**What you see:**
1. **Alerts** at the top. Green "Nothing needs you right now" is the good state.
2. **Three numbers:** hours since the last daily tick, whether the ledger's hash chain holds
   ("ok"), and how many ledger records exist.
3. **Weeks table**, one row per week:
   - role (period or rehearsal) and cutoff;
   - how many snapshots, and the last one before the cutoff;
   - games predicted and games scored so far;
   - average miss for the champion and the challenger, the challenger's CRPS, and how often
     its 80% interval held the result;
   - whether the week was missed.
4. **Aliases:** which model is champion and challenger, and why.
5. **Priced replay:** how many replay files exist. Read them on the Betting page.
6. **status.md:** the tick's own report, in an expander.

**How to use it:** open it once a day during the test windows. If the alerts are green and
"Last tick" is under a day, nothing is needed.

### Distributions: what does the model expect for a game?

**For:** seeing each game's full probability table and asking what-ifs.

Pick a **Source** at the top.

**2026 shadow predictions:**
1. Pick a **Week**. Only weeks with a snapshot are listed.
2. The caption names the snapshot, when it was made, and whether it's a rehearsal.
3. The table lists every game by kickoff:
   - the champion's total and the challenger's total;
   - the challenger's 10th, 50th and 90th percentiles;
   - the home team's chance to win.
4. Pick a **Game** to see its table as a bar chart.
5. Type a **Line**. The page shows P(over), P(under) and P(push) at that number, and draws
   the line in red on the chart. It defaults to the challenger's total.

**2021–25 outer folds (Release D):**
1. Pick the distribution run, then a **Season** and **Week**.
2. The table shows each game's actual total, the Bovada open, the table's mean, its 10–90%
   range, and PIT (where the actual landed in the table, from 0 to 1).
3. Pick a game. The chart shows the actual total as a black line. The line box defaults to
   the open.
4. **What-if: expected possessions.** Change either team's pace rating P. You see:
   - possessions per team;
   - the champion's total and the lab model's total, each with its change.

   Both changes are exact. A yellow box warns when your pace is outside anything seen in
   training. The table above is not redrawn, because the distribution model's own response
   to pace isn't stored.

**Remember:** every number you type here is sensitivity analysis. It isn't a stored
prediction, a price, or an edge. The tables have shown no skill at picking over or under
against the open.

### Betting: the priced replay

**For:** reading the priced replay once it exists. The page prices nothing itself.

- **Until a replay is run** it says "No replay yet". The week 4 rehearsal can run from
  2026-09-28; the real replay runs after the verdict (~2026-10-26), from the command line.
- **A rehearsal** shows a red REHEARSAL banner: a mechanics check, never a result.
- **The real (period) replay** stays hidden until the ledger holds the verdict.
- **What it shows**, after the replay's own framing text (always descriptive):
  - games priced, bets, games with no fresh quote, missed fills;
  - units per bet, and closing-line value with its interval. CLV counts only bets whose
    close is proven; the rest are counted as unknown;
  - P(over) scored against the de-vigged market;
  - the declared threshold table: what 0–8% minimum EV would have done;
  - every decision, one row per game;
  - the frozen policy and execution settings, in an expander.

### New run: build and launch a tuning run

**For:** trying a different feature set, fold design or search on the lab's data. This is the
only page that starts anything.

**Walkthrough:**

1. **Template.** Pick a committed spec (`spec: total_ratings_v1`) or any published run's spec
   (`run: …`). The form fills from it.
2. **01 Dataset and task.**
   - Source: `cfb_release_b` is real data. `synthetic_v1` is made-up data for testing, which
     spends no real season.
   - Snapshot: the ratings file; there is one.
   - Seasons loaded.
   - Fixed and shown as text: the target (full-game total), the decision time (each week's
     cutoff), and the population (FBS vs FBS, week 2+). 2026 is sealed and not offered.
3. **02 Features.** Choose the inputs **in column order**; order changes the run's identity.
   Refused features are marked "(blocked)". The table below lists each one's availability
   class and, for refused ones, the reason. Give the feature set an id and version.
4. **03 Opponent adjustment and priors.** Read-only. The ratings come fixed from the
   Release B snapshot. Changing them takes a new snapshot, not a setting.
5. **04 Validation design.**
   - Inner seasons: used to choose settings.
   - Outer seasons: each evaluated once.
   - Excluded seasons.
   - Embargo days: a gap between the training games and each test block.
6. **05 Model and search space.**
   - Search profile: Ridge and Elastic Net, with their ranges listed.
   - Number of trials and the objective (MAE or RMSE).
   - Retries.
   - Sampler and pruner settings. Leave them unless you know why.
7. **Acceptance and seeds.**
   - Baselines to compare against.
   - Bias tolerance (points) and maximum features.
   - Three seeds.
8. **Identity.** A spec id, your name, and notes. Notes go on the model card and don't
   change the run's identity.
9. Click **Validate**. The draft is saved under `drafts/`, named by its content, and every
   check runs.

**Review and launch** appears under the form:
- **Red errors** block launch. The full list is in [Guardrails](#guardrails).
- **Yellow warnings** don't block. The usual one says the outer seasons were already used,
  and counts the earlier trials. That means the result is descriptive, not new evidence.
- **Green "Valid"** names the run it will launch, for example `run-de1927346ab0-r1`. An
  `-r1`, `-r2` suffix is a replicate: a repeat of the same spec. Stale earlier replicates are
  listed as skipped.
- **Diff against the template:** exactly what you changed.
- **Canonical spec:** what the run's identity hash covers.
- **Holdout text:** which seasons it tunes on and evaluates on, and how many trials already
  hit them.
- **Launch:** tick "I understand; launch …", then click Launch.
  - Launch re-checks the exact saved file first.
  - The run starts in the background and keeps going if you close the GUI.
  - It takes about 16 seconds to appear on the Jobs page.
  - If the same spec already completed on this code, Launch is disabled: open that run on
    the Runs page instead.

### Jobs: follow or cancel a run

**For:** watching runs in progress.

1. The table lists every job, newest first: state, attempt, retries, error kind, created
   and updated times.
2. Pick a job to see:
   - its state;
   - trials complete out of started;
   - the best objective so far;
   - a line chart of the best-so-far;
   - every trial and its settings;
   - the last 40 log lines, open automatically while it runs.
3. **To cancel:** tick the confirmation, then click **Request cancel**. The run stops between
   folds, and finished trials are kept.

**Job states:**

| State | Meaning |
| --- | --- |
| queued | Waiting for a worker |
| claimed | A worker has taken it |
| running | Trials in progress |
| retry_wait | The worker died, and it will be retried |
| completed | Done; results are on the Runs page |
| failed | Out of retries; see the log |
| cancellation_requested | Stopping at the next fold |
| cancelled | Stopped; finished trials kept |

### Runs: read a finished run

**For:** everything a published run produced.

- **Pinned for Compare** (tuning runs only): tick it to shortlist the run for Compare. Pins
  last for this browser session.
- **Card:** the model card: settings, data hashes, folds, results against each baseline,
  gates, and how to reproduce it.
- **Trials:** every Optuna trial. Distribution runs have none.
- **Comparisons:** the raw comparison or score files.
- **Spec:** the exact spec file.

### Compare: two runs game by game

**For:** asking whether run A forecast better than run B on the same games.

1. It needs two published tuning runs. With two or more pinned, a toggle limits the choice to
   those.
2. Pick **Run A** and **Run B**.
3. **Blocked** with a red list if the runs differ in data source, snapshot, target,
   population, decision time, outer seasons, excluded seasons, or grouping. Those runs
   can't be compared fairly.
4. Otherwise it shows:
   - **MAE of A minus B**: negative means A was closer. It comes with a 95% interval and a
     verdict: improves, matches or worse;
   - the number of games, the week clusters, and the smallest difference it could detect;
   - a bar chart of the difference by season;
   - every game's forecasts and errors.

It's descriptive, because outer seasons get reused across runs.

### Registry: who is champion?

**For:** the model lineup. Read-only; aliases move only with
`python -m models.tuning shadow alias`, which records a reason.

- **Champion and challenger:** the current holder of each alias, the reason, and when it was
  set.
- **Every alias move**, in an expander.
- **Published runs:** id, kind (tuning or distribution), spec, when generated, git commit,
  code version, and whether it has a card.

### Replay: a past week as the lab saw it

**For:** checking the ratings and the champion's forecasts on any past week.

1. Pick a **Season** and **Week**, from 2014–2025.
2. The header shows the cutoff time, how many teams were rated, and league averages: points
   per possession, possessions, home edge, and the overtime allowance.
3. **Mean absolute miss** for the week.
4. Each game in kickoff order: forecast, actual total, miss.
5. **Ratings at the cutoff:** every team's O, D and P, in an expander.

It uses only games that kicked off before the cutoff, exactly as the lab did. These forecasts
match Release B's to 1e-9.

### Data: is the data fresh and unchanged?

**For:** trusting the inputs.

- **Freshness:** when CFBD games, drives and lines, and the newest Action Network file, were
  last updated, and their age in hours.
- **Sources behind each published run:** each run's recorded file hashes against today's files.
  - Green "All N recorded sources match": nothing was revised.
  - Red means a file changed since the run, so its numbers no longer reproduce from today's
    files.
- **Why games leave the frame:** Release B's excluded games per season, by reason (not
  regular season, not FBS vs FBS, and so on).

### Hypotheses: what has been tried

**For:** not repeating old work. Every question the lab has tested, nulls included, from
`models/tuning/hypotheses.json`.

- Filter by **Status** (closed or pending).
- Each row: the question, the answer, which seasons it used, the trial count, and the record
  that proves it. If the record and this table disagree, the record wins.

---

## Common tasks

| I want to… | Do this |
| --- | --- |
| Check the live test | Sidebar: no red boxes? Then Shadow: green alert, "Last tick" under 24 h |
| See this week's numbers for a game | Distributions → 2026 shadow predictions → Week → Game |
| Know P(over) at a line | Distributions → pick the game → type the line |
| Test a feature set | New run → template → change features → Validate → review → tick → Launch |
| Watch a run | Jobs → pick it; Reload to refresh |
| Stop a run | Jobs → pick it → tick the confirmation → Request cancel |
| Compare two runs | Runs → pin both → Compare |
| Check for data revisions | Data → Sources behind each published run |
| Read the replay | Betting, after the command-line replay has run |
| Try something without touching the real lab | Start with a scratch lab (below) |

**Scratch lab:** give the GUI a different lab folder, and every page reads and launches
there instead:

```text
.venv-lab-ui\Scripts\python -m streamlit run models/tuning/ui/app.py -- --lab-root C:\path\to\scratch
```

Setting the environment variable `CFB_LAB_ROOT` does the same. The sidebar shows
"scratch lab".

---

## Guardrails

Every check runs in one place (`models/tuning/ui/api.py validate`), so the GUI can't skip one.
Launch re-runs them on the exact saved file.

**Red: launch is blocked**

| Message starts with | Why |
| --- | --- |
| `seasons [2026] are sealed` | 2026 belongs to the shadow test and prior_v3's one look |
| `feature X: <reason>` | The catalog refuses it, for example no capture time, or known only after kickoff |
| `feature X: declared v… catalog says v…` | The spec's feature version or class doesn't match the catalog |
| `feature X: not in the catalog` | Unknown feature |
| `<run_id> is running` (or queued, …) | The same spec is still in flight. Wait or cancel |
| A field name and a message | The spec breaks a rule, for example an outer season before an inner one |

**Yellow: allowed, but read it**

- `Outer seasons … were already evaluated by …`: the result is descriptive.
- `… already completed on this code`: launching returns the finished run; nothing is refit.
- On Distributions, **outside training support**: the what-if is extrapolating.

**Launch refusals** (after you click Launch):
- `the lab changed since validation`: someone launched a replicate meanwhile. Validate
  again.
- `a worker … is still starting`: a launch from under 10 minutes ago hasn't shown up yet.
  Check Jobs.

**What the GUI never does:**
- write anything in the repo;
- delete anything;
- move an alias, freeze, tick, or replay;
- price a quote;
- launch on a sealed season.

It writes only two folders under the lab root: `drafts/` and `logs/`.

---

## Alerts and what to do

These show on the Shadow page. Red ones also show in the sidebar.

| Alert | Meaning | Do |
| --- | --- | --- |
| Nothing needs you right now | All good | Nothing |
| Next: week W needs a snapshot before … | The next deadline, more than 7 days away | Nothing; the 05:00 refresh handles it |
| Week W needs a snapshot before … (N days) | The deadline is within 7 days | Make sure the PC is on at 05:00 ET |
| No tick for N h (last …) | The daily tick hasn't run in over 26 h | Check Task Scheduler for `CFB-CFBD-Daily`; was the PC on and logged in? |
| No status.md: the tick has never run | The shadow test was set up but never ticked | Run the tick once, or check the task |
| Week W MISSED | A cutoff passed with no snapshot | The period is a NO-GO. Nothing can fix it; note why |
| Ledger chain fails | The ledger was altered or corrupted | Stop and investigate; no prediction can be trusted |
| Period verdict: GO / NO-GO | The period is over | Run the priced replay, then read it on Betting |

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| The page half-loads or shows "connection refused" | Use `http://127.0.0.1:8501`, not `localhost` |
| `KeyError` or a traceback after the code was updated | Stop the GUI and start it again. Streamlit keeps old code loaded until restarted |
| The port is already in use | A GUI is already running: use it. A second copy opens on the next free port (8502) |
| New results don't show | Click **Reload** in the sidebar. The feature list refreshes every 10 minutes |
| Launch was clicked but no job appears | Wait about 20 s and Reload. Check `logs/<run_id>.log` under the lab root |
| "lab api failed" | The main `.venv` is missing or broken. The GUI needs it for every check |
