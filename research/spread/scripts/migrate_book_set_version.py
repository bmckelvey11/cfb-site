"""Stamp `book_set_version` on forward-log rows written before the book set was tagged.

Every row in `movement_forward_log.csv` up to 2026-09-09 had its `book_fair` -- and therefore
its `side`, `side_line`, `edge`, and membership in the bet set -- computed from Action Network's
five books alone. On 2026-09-09 the-odds-api's five offshore books were promoted into that
median (`BOOK_SET_VERSION` 2 in `weekly_slate.py`). Those older rows cannot be recomputed under
the new set: no the-odds-api snapshot exists for those moments, the 6-hourly schedule only
started that day. So the break is permanent, and the only honest thing to do is label which
side of it each row falls on -- the same job `model_set_version` does for the predictor.

Idempotent: rows that already carry a version are left alone, so a second run is a no-op.

    python research/spread/scripts/migrate_book_set_version.py --dry-run
    python research/spread/scripts/migrate_book_set_version.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weekly_slate as ws  # noqa: E402

PRE_PROMOTION = 1


def migrate(log: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    out = log.copy()
    if "book_set_version" not in out:
        out["book_set_version"] = pd.NA
    missing = out.book_set_version.isna()
    out.loc[missing, "book_set_version"] = PRE_PROMOTION
    return out, int(missing.sum())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not ws.FORWARD_LOG.exists():
        print(f"no forward log at {ws.FORWARD_LOG}")
        return 1
    log = pd.read_csv(ws.FORWARD_LOG)
    out, n = migrate(log)
    print(f"{ws.FORWARD_LOG.name}: {len(log)} rows, {n} stamped book_set_version={PRE_PROMOTION}")
    print(out.groupby("book_set_version", dropna=False).size().to_string())
    if args.dry_run:
        print("dry run; nothing written")
        return 0
    out.to_csv(ws.FORWARD_LOG, index=False)
    print(f"wrote {ws.FORWARD_LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
