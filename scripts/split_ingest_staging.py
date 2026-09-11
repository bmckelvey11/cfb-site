"""Separate ingestion from warehouse staging inside ``$CFB_DATA_ROOT``.

``data/raw/`` did two jobs: it held the CFBD endpoint dumps the warehouse loads
*and* everything else that ever landed on disk. ``build_duckdb`` globs
``raw/*.json``, so any stray file became a permanent table -- a hand-saved PFF
export minted 4 tables, and seven dated line snapshots minted 11 more (see
``archive/docs/duckdb-audit-2026-09-02.md`` S7).

After this split:

* ``data/raw/``    -- warehouse inputs only. Everything here is meant to load.
* ``data/ingest/`` -- landed data the warehouse does not read: vendor one-offs,
  point-in-time snapshots, and sources not wired to the loader.

The glob is non-recursive, so subdirectories never leaked; they move because they
are ingestion-only by nature, not because they were a bug.

Action Network (``raw/actionnetwork/``, ``raw/actionnetwork_odds.csv``) is left
in place on purpose -- that data gets cleaned in a later pass.

    python scripts/split_ingest_staging.py            # dry run, prints the manifest
    python scripts/split_ingest_staging.py --apply
    python scripts/split_ingest_staging.py --revert   # move everything back
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cfb_paths  # noqa: E402

# Top-level raw/*.json stems that are not CFBD endpoint dumps. The loader groups
# files by `parse_dump_stem`, so each of these became its own table.
SNAPSHOT_PREFIX = "lines_2026_"
VENDOR_STEMS = {"pff_facet_offense_summary_21580"}

# Subdirectories under raw/ that the loader never reads (its glob is not
# recursive) and that are ingestion-only by nature.
MOVE_DIRS = ("massey", "prediction_tracker", "pt_snapshots")

# Loose files under raw/ that belong with their directory.
MOVE_FILES = ("prediction_tracker_lines.csv",)

# Never move these: Action Network is explicitly out of scope for now.
KEEP = {"actionnetwork", "actionnetwork_odds.csv"}


def plan(root: Path) -> list[tuple[Path, Path]]:
    raw, ingest = root / "raw", root / "ingest"
    moves: list[tuple[Path, Path]] = []

    for name in MOVE_DIRS:
        src = raw / name
        if src.is_dir():
            moves.append((src, ingest / name))
    for name in MOVE_FILES:
        src = raw / name
        if src.is_file():
            moves.append((src, ingest / name))

    for path in sorted(raw.glob("*.json")):
        if path.name in KEEP:
            continue
        if path.stem.startswith(SNAPSHOT_PREFIX):
            moves.append((path, ingest / "snapshots" / path.name))
        elif path.stem in VENDOR_STEMS:
            moves.append((path, ingest / "vendor" / path.name))
    return moves


def revert_plan(root: Path) -> list[tuple[Path, Path]]:
    raw, ingest = root / "raw", root / "ingest"
    moves: list[tuple[Path, Path]] = []
    for name in MOVE_DIRS:
        src = ingest / name
        if src.is_dir():
            moves.append((src, raw / name))
    for name in MOVE_FILES:
        src = ingest / name
        if src.is_file():
            moves.append((src, raw / name))
    for sub in ("snapshots", "vendor"):
        d = ingest / sub
        if d.is_dir():
            for path in sorted(d.iterdir()):
                moves.append((path, raw / path.name))
    return moves


def run(moves: list[tuple[Path, Path]], root: Path, apply: bool) -> int:
    if not moves:
        print("nothing to move -- already split.")
        return 0
    for src, dst in moves:
        kind = "dir " if src.is_dir() else "file"
        print(f"  {kind} {src.relative_to(root)}  ->  {dst.relative_to(root)}")
    if not apply:
        print(f"\n{len(moves)} move(s). Dry run -- pass --apply to execute.")
        return 0
    for src, dst in moves:
        if dst.exists():
            print(f"REFUSING: destination exists: {dst}", file=sys.stderr)
            return 1
    for src, dst in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    print(f"\nmoved {len(moves)} item(s).")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(cfb_paths.DATA_ROOT))
    p.add_argument("--apply", action="store_true")
    p.add_argument("--revert", action="store_true", help="move everything back into raw/")
    a = p.parse_args()
    root = Path(a.root)
    moves = revert_plan(root) if a.revert else plan(root)
    print(("REVERT" if a.revert else "SPLIT") + f" under {root}\n")
    return run(moves, root, a.apply)


if __name__ == "__main__":
    raise SystemExit(main())
