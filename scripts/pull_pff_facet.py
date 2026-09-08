"""Pull a PFF leaderboard (facet) to CSV via the Restish CLI.

    python scripts/pull_pff_facet.py passing --league ncaa --season 2025
    python scripts/pull_pff_facet.py rushing --league ncaa --season 2025 --division fbs
    python scripts/pull_pff_facet.py passing --league ncaa --season 2025 --dry-run

Auth is the `ci` profile set up in docs/pff-cli.md: an API key read from
PFF_API, falling back to the gitignored env.env at the repo root. The key is
passed to restish through the environment, never on the command line.

Exports are metered at 20/minute per PFF account -- pull once, work from the
file. See docs/pff-cli.md.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cfb_paths import DATA_ROOT  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def api_key() -> str:
    key = os.environ.get("PFF_API")
    if key:
        return key
    env_file = REPO_ROOT / "env.env"
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("PFF_API="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"PFF_API not in the environment and not in {env_file}")


def restish_bin() -> str:
    found = shutil.which("restish")
    if found:
        return found
    # ponytail: one fallback for the install documented in docs/pff-cli.md
    fallback = Path.home() / "restish" / "restish.exe"
    if fallback.exists():
        return str(fallback)
    raise SystemExit("restish not on PATH; see docs/pff-cli.md")


def out_name(facet: str, league: str, season: str, division: str | None, week: str | None) -> str:
    parts = [facet.replace("-", "_"), league, season.replace(",", "-")]
    if division:
        parts.append(division.replace(",", "-"))
    if week:
        parts.append("wk" + week.replace(",", "-"))
    return "_".join(parts) + ".csv"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("facet", help="restish command or alias, e.g. passing, rushing, facet-defense-coverage")
    ap.add_argument("--league", required=True, help="nfl, ncaa, hs, aaf or ufl")
    ap.add_argument("--season", required=True, help="a year, or a comma-separated list")
    ap.add_argument("--division", help="ncaa only: fbs, fcs, lower (comma-separated)")
    ap.add_argument("--week", help="comma-separated week list")
    ap.add_argument("--out-dir", type=Path, default=DATA_ROOT / "raw" / "pff")
    ap.add_argument("--profile", default="ci", help="restish profile (default: ci)")
    ap.add_argument("--dry-run", action="store_true", help="print the command and target, call nothing")
    args = ap.parse_args()

    dest = args.out_dir / out_name(args.facet, args.league, args.season, args.division, args.week)
    cmd = [restish_bin(), "pff", args.facet,
           "--league", args.league, "--season", args.season,
           "--export", "true", "--rsh-print", "b", "-p", args.profile]
    if args.division:
        cmd += ["--division", args.division]
    if args.week:
        cmd += ["--week", args.week]

    if args.dry_run:
        print(" ".join(cmd))
        print(f"-> {dest}")
        return

    args.out_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PFF_API": api_key()}
    with dest.open("wb") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, env=env)
    if proc.returncode != 0:
        dest.unlink(missing_ok=True)
        raise SystemExit(proc.stderr.decode(errors="replace").strip() or f"restish exited {proc.returncode}")

    lines = dest.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        # PFF returns an empty body -- no header at all -- for an unentitled
        # league or report. An entitled query with no matches still has a header.
        dest.unlink(missing_ok=True)
        raise SystemExit(
            f"empty export: the account is not entitled to {args.league} {args.facet}. "
            "Re-run without --export to see the 'restricted' columns."
        )
    print(f"{dest}  {len(lines) - 1} rows, {len(lines[0].split(','))} columns")


if __name__ == "__main__":
    main()
