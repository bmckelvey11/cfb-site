# Running qualified-pick history

Completed September 12, 2026.

## Purpose and location

Preserve qualified OVER observations across model runs, including individual-book
signals that never qualify in the market-wide view. The running CSV is
`$CFB_DATA_ROOT/processed/over_zero/qualified_picks_history.csv`.

One row means one model/run/view/game observation, not a unique bet. Repeated
qualifications on later runs remain separate, as do different sportsbook views.
Rows include run time, available price timestamp, teams, kickoff, qualifying
spread/total, bias, probability (0–1), threshold, best price, playability, Bet to,
and source. Signals without an acceptable price are retained with their recorded
playability flag. Unknown historical fields remain blank.

## Collection and backfill

`scripts/best_line_slate.py` now records every view on every normal run, including
scheduled, terminal-only, and single-book runs. It reuses the same input snapshot
and fitted model. CSV history remains enabled when `--out-dir ''` suppresses the
separate scored-game snapshot. No website publication is needed to save history.
Runs without qualifications contribute no rows.

`scripts/pick_history.py` imports existing timestamped slate CSVs, older v1
prediction CSVs (including the cumulative file), committed site boards and the
current board. CSV values take priority over rounded board values; boards can
fill missing metadata. Repeated imports preserve existing observations and add
only new identities. A lock and atomic replacement protect the file from
concurrent writers and interrupted writes. A process killed while holding the
lock may leave a `.csv.lock` file; verify no writer remains before removing it.

Reproduce from repository root with CFB_DATA_ROOT configured:

```powershell
.venv\Scripts\python.exe models/over_zero/scripts/pick_history.py
.venv\Scripts\python.exe -m pytest tests/test_over_zero_pick_history.py -q
.venv\Scripts\python.exe models/over_zero/scripts/best_line_slate.py --out-dir ''
```

## Verification and limits

Initial backfill recovered 775 observations. Repeating it added zero rows and
left the file byte-for-byte unchanged. An end-to-end model run added 69 rows,
giving 844 observations from 37 distinct run timestamps, August 31–September 12,
2026. All 844 identities are unique. The latest per-view counts match all ten
views in the current board, including empty views. Five focused tests passed,
covering duplicate imports, separate books/runs, unplayable signals, invalid
identity preservation, timezone conversion, missing fields, and empty files.

This is an observation ledger, not a graded betting record. It does not recover
overwritten historical sportsbook views that were never saved, demonstrate
historical completeness, or establish performance. Historical thresholds and
feed configurations can differ. Frozen v1 remains unchanged; any new standalone
v1 outputs can be imported by rerunning the backfill command. Automatic recording
applies to the current slate runner. Historical CSVs without recorded thresholds
or price timestamps retain blanks unless a saved board supplies those fields.
