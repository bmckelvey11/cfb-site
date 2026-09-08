"""Has The Prediction Tracker's live slate flipped to a new week yet?

PT serves one rolling CSV and overwrites it in place, so there is no week field to read and
no publish feed to subscribe to -- the only way to know is to compare the matchups it is
serving now against the newest snapshot on disk. The file changes constantly as lines move,
so a content hash (what `collect_line_timing.snapshot` uses to avoid duplicates) does NOT
answer this question; the set of games does.

Exit 0 when the slate has rolled over, 1 when it has not, so it can gate a wait:

    until python research/spread/scripts/pt_rollover.py; do sleep 1800; done

    python research/spread/scripts/pt_rollover.py       # one check, prints the verdict
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_line_timing as clt  # noqa: E402

# A rollover replaces the whole slate. Some overlap survives -- a game can be listed a week
# early, and PT occasionally drops one -- so require a clear majority to be new, not all.
NEW_SLATE_FRAC = 0.5


def pairs(df: pd.DataFrame) -> set[tuple[str, str]]:
    return set(zip(df["road"].astype(str), df["home"].astype(str)))


def rolled_over() -> tuple[bool, str]:
    snaps = sorted(clt.SNAP_DIR.glob("ncaapredictions_*.csv"))
    if not snaps:
        return False, "no snapshot on disk to compare against"
    have = pairs(pd.read_csv(snaps[-1]))
    try:
        live = pairs(pd.read_csv(io.BytesIO(clt._get(clt.PT_URL))))
    except Exception as exc:                       # transient: a poll loop must survive it
        return False, f"fetch failed: {type(exc).__name__}: {exc}"
    if not live:
        return False, "live CSV had no games"
    shared = len(live & have)
    frac_new = 1 - shared / len(live)
    verdict = frac_new >= NEW_SLATE_FRAC
    return verdict, (f"{'ROLLED OVER' if verdict else 'same slate'}: "
                     f"{len(live)} live games, {shared} shared with {snaps[-1].name}, "
                     f"{frac_new:.0%} new")


def _check() -> None:
    a = pd.DataFrame({"road": ["x", "y"], "home": ["p", "q"]})
    b = pd.DataFrame({"road": ["m", "n"], "home": ["r", "s"]})
    assert pairs(a) & pairs(b) == set()
    assert len(pairs(a) & pairs(a)) == 2


if __name__ == "__main__":
    _check()
    ok, msg = rolled_over()
    print(msg)
    raise SystemExit(0 if ok else 1)
