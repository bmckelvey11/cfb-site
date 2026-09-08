"""Collect the two things needed to answer the timing question, going forward.

`archive/spread-margin-era/prediction-tracker-model-eval.md` §8 could not run the timing test because the
archive is missing one field that no amount of scraping can recover retrospectively:
**when each Prediction Tracker forecast was published**. This script captures it from now on.

Two halves, with very different urgency:

    snapshot   Prediction Tracker's live weekly CSV, stamped with the fetch time.
               EPHEMERAL -- PT overwrites this file in place and keeps no history, so a
               week not captured is a week lost forever. This is the time-critical half.

    history    Action Network full-game line history per event. NOT time-critical: the
               endpoint replays the whole path (ticks back to April on a week-1 game), so
               one call any time before the odds are pulled down gets everything.

    python research/spread/scripts/collect_line_timing.py snapshot
    python research/spread/scripts/collect_line_timing.py history --season 2026
    python research/spread/scripts/collect_line_timing.py both --season 2026

The full-game period on Action Network is **`event`** -- not `game`, which returns an empty
payload. `actionnetwork_client.DEFAULT_PERIODS` asks only for firsthalf/firstquarter, which
is why full-game history was never on disk despite 10,868 history files existing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "cfb_paths.py").is_file()
)
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402
from cfb_system_maker.actionnetwork_client import TERMINAL_STATUSES  # noqa: E402

PT_URL = "http://www.thepredictiontracker.com/ncaapredictions.csv"
AN_SCOREBOARD = "https://api.actionnetwork.com/web/v2/scoreboard/ncaaf"
AN_HISTORY = "https://api.actionnetwork.com/web/v2/markets/event/{event_id}/history"
FULL_GAME_PERIOD = "event"
# Cloudflare 403s urllib's default User-Agent.
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

SNAP_DIR = cfb_paths.INGEST / "pt_snapshots"
AN_DIR = cfb_paths.RAW / "actionnetwork"


def _get(url: str, params: dict | None = None, *, timeout: int = 45) -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 2:
                time.sleep(5.0 * 2**attempt)
                continue
            raise
    raise RuntimeError("max retries exceeded")


# ------------------------------------------------------------------------- snapshot


def snapshot(now: datetime | None = None) -> Path | None:
    """Capture PT's live CSV with the fetch time. Returns the path, or None if unchanged.

    The filename carries the capture instant -- that timestamp IS the deliverable, since
    it is the field the historical archive lacks.
    """
    now = now or datetime.now(timezone.utc)
    body = _get(PT_URL)
    if not body.strip():
        raise RuntimeError(f"{PT_URL} returned an empty body")

    digest = hashlib.sha256(body).hexdigest()
    SNAP_DIR.mkdir(parents=True, exist_ok=True)

    # PT overwrites in place and may not change between runs; don't pile up duplicates
    previous = sorted(SNAP_DIR.glob("ncaapredictions_*.csv"))
    if previous and hashlib.sha256(previous[-1].read_bytes()).hexdigest() == digest:
        print(f"unchanged since {previous[-1].name} -- nothing written")
        return None

    rows = max(body.count(b"\n") - 1, 0)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = SNAP_DIR / f"ncaapredictions_{stamp}.csv"
    path.write_bytes(body)
    (SNAP_DIR / f"ncaapredictions_{stamp}.meta.json").write_text(
        json.dumps(
            {
                "captured_at": now.isoformat(),
                "url": PT_URL,
                "sha256": digest,
                "bytes": len(body),
                "rows": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {path.name}  ({len(body)} bytes, {rows} games)")
    return path


# -------------------------------------------------------------------------- history


def event_ids(season: int, weeks: range) -> list[tuple[int, bool]]:
    """(event id, settled) per game. Settled means the game can no longer move."""
    seen: dict[int, bool] = {}
    for week in weeks:
        try:
            payload = json.loads(
                _get(AN_SCOREBOARD, {"season": season, "week": week, "seasonType": "reg"})
            )
        except Exception as exc:  # one bad week must not abort the season
            print(f"  wk{week}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        for game in payload.get("games", []):
            if game.get("id") is None:
                continue
            seen[int(game["id"])] = game.get("status") in TERMINAL_STATUSES
        time.sleep(1.0)
    return sorted(seen.items())


def history(season: int, weeks: range, *, force: bool = False) -> int:
    """Pull full-game line history per event.

    Written as history_event_{id}.json so it never collides with the legacy
    history_{id}.json files, which hold firsthalf/firstquarter only.

    A file on disk only ends the job once the game is settled. The endpoint replays
    the whole path on every call, so re-pulling an unsettled event is lossless and
    picks up every tick since the last run -- skipping on mere file existence froze
    the series at whenever the event was first seen.
    """
    AN_DIR.mkdir(parents=True, exist_ok=True)
    events = event_ids(season, weeks)
    unsettled = sum(1 for _, settled in events if not settled)
    print(f"{len(events)} events in {season} weeks {weeks.start}-{weeks.stop - 1} "
          f"({unsettled} still moving)")
    written = skipped = empty = errors = 0
    for eid, settled in events:
        path = AN_DIR / f"history_event_{eid}.json"
        if path.exists() and settled and not force:
            skipped += 1
            continue
        try:
            body = _get(AN_HISTORY.format(event_id=eid), {"periods": FULL_GAME_PERIOD})
        except Exception as exc:
            errors += 1
            print(f"  event {eid}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        # an empty payload means AN has no history yet -- don't write, re-probe next run
        if b"updated_at" not in body:
            empty += 1
        else:
            path.write_bytes(body)
            written += 1
        time.sleep(1.0)
    print(f"history: {written} written, {skipped} settled and on disk, "
          f"{empty} not yet posted, {errors} errors")
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=("snapshot", "history", "both"), nargs="?", default="snapshot")
    ap.add_argument("--season", type=int, default=cfb_paths.current_season())
    ap.add_argument("--weeks", default="1-16", help="inclusive week range, e.g. 1-16")
    ap.add_argument("--force", action="store_true", help="re-pull history already on disk")
    args = ap.parse_args()

    lo, _, hi = args.weeks.partition("-")
    weeks = range(int(lo), int(hi or lo) + 1)

    if args.mode in ("snapshot", "both"):
        written = snapshot()
        if written is not None:
            # Log E4/E14 against the line at capture time, then every movement model plus the
            # live book fair (weekly_slate.py -> movement_forward_log.csv). Both are recomputable
            # from the snapshot, but the forward test is only as good as what is written per week.
            for script in ("predict_upcoming.py", "weekly_slate.py"):
                subprocess.run(
                    [sys.executable, str(Path(__file__).with_name(script)),
                     "--snapshot", str(written)],
                    check=False,
                )
    if args.mode in ("history", "both"):
        history(args.season, weeks, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
