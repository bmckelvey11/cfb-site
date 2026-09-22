"""Compare legacy features.json against features.duckdb size and load time.

Reproduces the numbers in cfb_system_maker/docs/feature-store-duckdb-2026-09-18.md.
Read-only; does not modify either sidecar.

    python scripts/measure_feature_store.py
    python scripts/measure_feature_store.py --data-dir C:\\Users\\mckel\\dev\\cfb\\data
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import duckdb

REPO = next(parent for parent in Path(__file__).resolve().parents if (parent / "cfb_paths.py").is_file())
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402
from cfb_system_maker.enrich import load_features  # noqa: E402


def _size_mb(path: Path) -> float | None:
    if not path.is_file():
        return None
    return path.stat().st_size / (1024 * 1024)


def _time_json_load(json_path: Path) -> float | None:
    if not json_path.is_file():
        return None
    start = time.perf_counter()
    json.loads(json_path.read_text(encoding="utf-8"))
    return time.perf_counter() - start


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data-dir", type=Path, default=cfb_paths.DATA_ROOT)
    args = ap.parse_args()
    processed = args.data_dir / "processed"
    json_path = processed / "features.json"
    duckdb_path = processed / "features.duckdb"

    print(f"data_dir={args.data_dir}")
    print(f"features.json:     {_size_mb(json_path):.2f} MB" if json_path.is_file() else "features.json:     (missing)")
    print(f"features.duckdb:   {_size_mb(duckdb_path):.2f} MB" if duckdb_path.is_file() else "features.duckdb:   (missing)")

    if duckdb_path.is_file():
        con = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            n = con.execute("SELECT count(*) FROM features").fetchone()[0]
            cols = len(con.execute("DESCRIBE features").fetchall())
        finally:
            con.close()
        print(f"features rows:     {n:,}")
        print(f"features columns:  {cols} (includes game_id)")

    t_json = _time_json_load(json_path)
    if t_json is not None:
        print(f"json parse:        {t_json:.3f}s (full file read + json.loads)")

    if duckdb_path.is_file():
        start = time.perf_counter()
        rows = load_features(args.data_dir)
        t_duck = time.perf_counter() - start
        print(f"load_features():   {t_duck:.3f}s ({len(rows):,} games via DuckDB path)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
