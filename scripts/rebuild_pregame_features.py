"""Rebuild migrated pregame filters, preserve previous derived snapshots, and audit coverage.

Run from repository root: python -m scripts.rebuild_pregame_features
(--data-dir defaults to CFB_DATA_ROOT; pass it only to target a different root.)
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from cfb_paths import DATA_ROOT
from cfb_system_maker.enrich import load_features, run_enrich
from cfb_system_maker.features import FEATURE_BY_KEY, registry_version
from cfb_system_maker.storage import load_processed_games, load_upcoming_games
from cfb_system_maker.upcoming import enrich_upcoming


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DATA_ROOT)
    args = parser.parse_args()
    root = args.data_dir.resolve()
    processed = root / "processed"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = processed / "feature_backups" / stamp
    backup.mkdir(parents=True)
    for name in ("features.json", "upcoming_features.json", "pregame_coach_styles.json"):
        path = processed / name
        if path.exists():
            shutil.copy2(path, backup / name)
    print(f"Backup: {backup}", flush=True)
    games = load_processed_games(root)
    years = sorted({g.season for g in games})
    subprocess.run([sys.executable, "scripts/build_coach_style_clusters.py", "--data-dir", str(root), "--pregame", "--target-seasons", *map(str, years)], check=True)
    run_enrich(root)
    upcoming, _ = load_upcoming_games(root) if (processed / "upcoming.csv").exists() else ([], {})
    if upcoming:
        upcoming_years = {g.season for g in upcoming}
        if len(upcoming_years) != 1:
            raise ValueError("Expected one upcoming season; historical features rebuilt, upcoming untouched")
        enrich_upcoming(root, next(iter(upcoming_years)), upcoming)
    rows = load_features(root)
    migrated = [f.key for f in FEATURE_BY_KEY.values() if f.source_kind in {"computed_prior_game", "pregame_team_wp", "prior_coach_style"} or f.key == "core_overall"]
    audit = {"generated_at": stamp, "registry_version": registry_version(), "historical_games": len(rows), "seasons": years, "upcoming_games": len(upcoming), "backup": str(backup), "coverage": {}}
    for key in migrated:
        available = sum(row.get(side + "_" + key) is not None for row in rows.values() for side in ("home", "away"))
        latest = [rows[g.game_id] for g in games if g.season == max(years)]
        current = sum(row.get(side + "_" + key) is not None for row in latest for side in ("home", "away"))
        audit["coverage"][key] = {"team_game_values": available, "possible": len(rows) * 2, "latest_season_values": current, "latest_season_possible": len(latest) * 2}
    assert all("attendance" not in row for row in rows.values())
    destination = processed / "pregame_feature_audit.json"
    destination.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
