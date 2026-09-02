# Line-timing collector — runbook

Two Windows scheduled tasks that capture the one field the Prediction Tracker archive is
missing: **when each forecast was published**. Set up 2026-08-29.

Read `research/spread/docs/prediction-tracker-model-eval.md` §7–§9 for *why* this exists. This file is the
operational side: what runs, how to check it, what to do when it breaks.

## The one thing to understand

`http://www.thepredictiontracker.com/ncaapredictions.csv` is a **single file that Prediction
Tracker overwrites in place.** It keeps no history. Every overwrite that happens while this
collector is not running is gone permanently — there is no backfill, no archive, no API to
ask later.

That is the entire reason this is a scheduled task rather than something run by hand at the
end of the season. The Action Network half, by contrast, can be backfilled at any time,
because that endpoint replays the whole price path in one call.

Practical consequence: **if the machine is off for a weekend, that weekend is lost.** It is
the only failure mode here that cannot be repaired after the fact.

## What is registered

| Task | Command | Schedule | Repairable if missed? |
|---|---|---|---|
| `CFB-PT-Snapshot` | `collect_line_timing.cmd snapshot` | every 6 hours, from 00:30 | **No** |
| `CFB-AN-History` | `collect_line_timing.cmd history --weeks 1-16` | Mondays 09:00 | Yes — just run it |

When a snapshot is actually new, the snapshot run also executes `predict_upcoming.py` and
`weekly_slate.py` on it, so `pt_upcoming_predictions.csv`, `weekly_slate_<stamp>.csv` and
`movement_forward_log.csv` fill without a hand run. Their output lands in the same log.

Both run as `mckel`, unelevated, **only while that user is logged on** (see Limitations).

## What lands where

Everything is under `%CFB_DATA_ROOT%` (`C:\Users\mckel\data\cfb`), which the tasks inherit
as a persisted user environment variable.

```
raw/pt_snapshots/
    ncaapredictions_20260829T134307Z.csv        the forecasts as published at that instant
    ncaapredictions_20260829T134307Z.meta.json  captured_at, sha256, byte count, row count
raw/actionnetwork/
    history_event_{id}.json                     full-game price path, one file per game
logs/
    line_timing.log                             every run, appended, never rotated
```

`history_event_{id}.json` is deliberately a different name from the legacy
`history_{id}.json`, which holds first-half / first-quarter markets only. They coexist.

Snapshots are content-hashed against the previous one, so a run where Prediction Tracker
has not changed writes nothing. Running the task more often than necessary is harmless.

## Checking it is alive

```powershell
schtasks /Query /TN "CFB-PT-Snapshot" /FO LIST /V | Select-String "Last Run Time|Last Result|Next Run Time"
```

`Last Result: 0` is success. Then confirm data is actually accumulating:

```powershell
Get-ChildItem "$env:CFB_DATA_ROOT\raw\pt_snapshots\*.csv" | Measure-Object
Get-Content "$env:CFB_DATA_ROOT\logs\line_timing.log" -Tail 20
```

**A quiet log is not a healthy log.** `unchanged since … — nothing written` repeated for days
during the season means PT is not updating, which is itself worth investigating. During
football season expect several new snapshots a week.

As of setup: 1 snapshot, 99 history files (2026 week 1), last result 0.

## When it breaks

| Symptom | Cause | Fix |
|---|---|---|
| `Last Result: 267011` | Task has never run | Normal before the first fire. `schtasks /Run /TN "CFB-PT-Snapshot"` to force it. |
| Log shows `HTTP Error 403` | Cloudflare rejecting the User-Agent | The UA is set in `collect_line_timing.py` (`UA`). If PT or AN tighten this, a current browser UA string is the fix. |
| Log shows `empty body` | PT served a zero-byte file | Transient; the next run picks it up. Persistent means the URL moved — re-probe `ncaapredictions.csv`. |
| `history: … 0 written, N not yet posted` | Action Network has no history for those events yet | Expected for games far in the future. Re-runs pick them up; nothing is written until real ticks exist. |
| No new snapshots for a week mid-season | Machine was asleep/off, or PT genuinely static | Check `Last Run Time`. If the task did not fire, that week's forecasts are unrecoverable. |
| Snapshots piling up with identical content | Content hash not matching | Should not happen; check that `SNAP_DIR` files were not hand-edited. |

Run either half by hand at any time:

```bash
scripts\collect_line_timing.cmd snapshot
scripts\collect_line_timing.cmd history --season 2026 --weeks 1-16
```

## Limitations that were chosen, not overlooked

1. **Runs only while logged on.** Making a task run otherwise requires storing the account
   password in the task definition. That was deliberately not done. To change it yourself:
   Task Scheduler → the task → Properties → *Run whether user is logged on or not*, which
   prompts for your own password. Nobody else needs to handle it.
2. **`--season` defaults to the calendar year.** Correct August–December, wrong in January,
   when bowl games still belong to the prior season. Run that backfill by hand:
   `collect_line_timing.cmd history --season 2026 --weeks 1-16`.
3. **The log never rotates.** It is a few hundred bytes per run; a full season is trivial.
   Delete it if it ever matters.
4. **No alerting.** If the task silently stops, nothing tells you. Checking the snapshot
   count once a month during the season is the intended safeguard.

## Turning it off

```powershell
schtasks /Change /TN "CFB-PT-Snapshot" /DISABLE      # pause, keep the definition
schtasks /Delete /TN "CFB-PT-Snapshot" /F            # remove entirely
schtasks /Delete /TN "CFB-AN-History"  /F
```

Collected data is untouched by either.

## What the collected data is for

Nothing until roughly a season has accumulated. Then:

1. Join each snapshot's games to `game_id` (reuse `research/spread/scripts/build_prediction_tracker.py`).
2. For each game, read the Action Network price at that snapshot's `captured_at`.
3. Re-grade the `|edge| > 2` bets from §7 at that price.

That produces the number §8 could not: whether the +6.7% ROI found at the opening line
survives at a price you could actually have taken. Until then it stays an unreachable upper
bound, and no amount of additional collection changes the verdict on 2001–2025.
