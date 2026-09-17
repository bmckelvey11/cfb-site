"""Flatten scraped Massey Ratings editions into tidy CSVs, mapped to CFBD teams.

Reads $CFB_DATA_ROOT/ingest/massey/ranks_*.json (see massey_ranks.py) and writes
four normalized tables to $CFB_DATA_ROOT/processed/massey/:

  massey_teams.csv    137 rows  massey_id -> CFBD school, with match provenance
  massey_systems.csv  ~200 rows one row per rating system, with its date range
  massey_editions.csv ~62k rows one row per (date, team): conf, W-L, composite
  massey_ranks.csv    ~5M rows  the fact table: date, massey_id, system, rank

Long format, nulls dropped: a system that did not rank a team emits no row.

Massey team ids (`ranks?s=cf<YEAR>&t=<id>`) are stable across 1996-2025 --
110 ids shared between the 1997 and 2024 editions carry identical names -- so
the map is keyed on the bare id, not (season, id).
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from pathlib import Path

DATA_ROOT = Path(os.environ.get("CFB_DATA_ROOT", Path(__file__).resolve().parent.parent / "data"))
RAW_DIR = DATA_ROOT / "raw"
INGEST_DIR = DATA_ROOT / "ingest"
IN_DIR = INGEST_DIR / "massey"
OUT_DIR = DATA_ROOT / "processed" / "massey"

# Fixed column positions in every edition's DI rows.
C_TEAM, C_CONF, C_WL, C_DELTA, C_CMP = 0, 1, 2, 3, 4

_ID_RE = re.compile(r"t=(\d+)")
_WL_RE = re.compile(r"^(\d+)-(\d+)(?:-(\d+))?$")

# Token expansions for Massey's abbreviated names ("C Michigan", "FL Atlantic").
_TOKENS = {
    "st": "state", "c": "central", "e": "eastern", "n": "northern",
    "s": "southern", "w": "western", "fl": "florida", "ga": "georgia",
    "miss": "mississippi", "intl": "international", "car": "carolina",
    "la": "louisiana", "tex": "texas", "mich": "michigan", "wash": "washington",
}

# Massey name -> CFBD school, for the cases no normalization rule reaches.
# Populated from the unmatched report; `--report` re-derives it.
OVERRIDES = {
    "Hawaii": "Hawai'i",        # CFBD spells it with an okina
    "UT San Antonio": "UTSA",
    "CS Sacramento": "Sacramento State",  # FBS from 2026
}


def norm(s: str) -> str:
    """Normalize a school name for matching."""
    s = s.lower().replace("&", " and ")
    s = re.sub(r"\b(university|univ|college of|the)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return " ".join(_TOKENS.get(t, t) for t in s.split())


def load_cfbd_teams() -> dict:
    """Normalized name -> (school, cfbd_id), unioned over every teams_*.json."""
    index = {}
    for path in sorted(glob.glob(str(RAW_DIR / "teams_*.json"))):
        for team in json.load(open(path, encoding="utf-8")):
            school, tid = team.get("school"), team.get("id")
            if not school:
                continue
            for name in [school] + list(team.get("alternateNames") or []):
                if name:
                    index.setdefault(norm(name), (school, tid))
    return index


def collect_teams(files: list) -> dict:
    """massey_id -> dict(name, first_date, last_date, n_editions)."""
    teams = {}
    for path in files:
        date = edition_date(path)
        for row in json.load(open(path, encoding="utf-8"))["DI"]:
            m = _ID_RE.search(row[C_TEAM][2] or "")
            if not m:
                continue
            tid = int(m.group(1))
            rec = teams.setdefault(
                tid, {"name": row[C_TEAM][0], "first_date": date, "last_date": date, "n_editions": 0}
            )
            rec["first_date"] = min(rec["first_date"], date)
            rec["last_date"] = max(rec["last_date"], date)
            rec["n_editions"] += 1
    return teams


def build_map(teams: dict, cfbd: dict) -> dict:
    """massey_id -> dict(cfbd_team, cfbd_id, match)."""
    out = {}
    for tid, rec in teams.items():
        name = rec["name"]
        if name in OVERRIDES:
            school = OVERRIDES[name]
            hit = cfbd.get(norm(school))
            out[tid] = {
                "cfbd_team": school,
                "cfbd_id": hit[1] if hit else "",
                "match": "override",
            }
            continue
        hit = cfbd.get(norm(name))
        out[tid] = (
            {"cfbd_team": hit[0], "cfbd_id": hit[1], "match": "normalized"}
            if hit
            else {"cfbd_team": "", "cfbd_id": "", "match": "unmatched"}
        )
    return out


def edition_date(path) -> str:
    """``ranks_19960916.json`` -> ``1996-09-16``.

    ISO so read_csv_auto types the column DATE rather than an 8-digit integer.
    Still sorts and compares as a string, which the min/max bookkeeping relies on.
    """
    d = Path(path).stem[6:]
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def _split_wl(cell) -> tuple:
    m = _WL_RE.match((cell[0] or "").strip()) if cell else None
    if not m:
        return "", "", ""
    return m.group(1), m.group(2), m.group(3) or "0"


def flatten(files: list, tmap: dict) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    systems = {}
    n_rank_rows = 0

    f_ed = open(OUT_DIR / "massey_editions.csv", "w", newline="", encoding="utf-8")
    f_rk = open(OUT_DIR / "massey_ranks.csv", "w", newline="", encoding="utf-8")
    w_ed = csv.writer(f_ed)
    w_rk = csv.writer(f_rk)
    w_ed.writerow(
        ["date", "season", "massey_id", "massey_team", "cfbd_team", "conference",
         "wins", "losses", "ties", "cmp_rank", "cmp_delta", "n_systems"]
    )
    w_rk.writerow(["date", "season", "massey_id", "cfbd_team", "system", "rank"])

    for path in files:
        date = edition_date(path)
        payload = json.load(open(path, encoding="utf-8"))
        season = int(str(payload.get("seas", "")).replace("cf", "") or 0)

        # Column index -> system code, for the rating-system columns only.
        sys_cols = []
        for ci, col in enumerate(payload["CI"]):
            if not col.get("fulltitle"):
                continue
            code = col["title"]
            sys_cols.append((ci, code))
            rec = systems.setdefault(
                code,
                {"fulltitle": col["fulltitle"], "url": col.get("url", ""),
                 "first_date": date, "last_date": date, "n_editions": 0},
            )
            rec["first_date"] = min(rec["first_date"], date)
            rec["last_date"] = max(rec["last_date"], date)
            rec["n_editions"] += 1

        for row in payload["DI"]:
            m = _ID_RE.search(row[C_TEAM][2] or "")
            if not m:
                continue
            tid = int(m.group(1))
            cfbd_team = tmap.get(tid, {}).get("cfbd_team", "")
            wins, losses, ties = _split_wl(row[C_WL])
            delta = row[C_DELTA][3] if isinstance(row[C_DELTA], list) and len(row[C_DELTA]) > 3 else ""

            n_sys = 0
            for ci, code in sys_cols:
                cell = row[ci]
                rank = cell[0] if isinstance(cell, list) else cell
                if rank is None:
                    continue
                w_rk.writerow([date, season, tid, cfbd_team, code, rank])
                n_sys += 1
                n_rank_rows += 1

            w_ed.writerow(
                [date, season, tid, row[C_TEAM][0], cfbd_team,
                 row[C_CONF][0] if isinstance(row[C_CONF], list) else row[C_CONF],
                 wins, losses, ties, row[C_CMP], delta, n_sys]
            )

    f_ed.close()
    f_rk.close()

    with open(OUT_DIR / "massey_systems.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["system", "fulltitle", "url", "first_date", "last_date", "n_editions"])
        for code in sorted(systems):
            r = systems[code]
            w.writerow([code, r["fulltitle"], r["url"], r["first_date"], r["last_date"], r["n_editions"]])

    return n_rank_rows


def write_team_map(teams: dict, tmap: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "massey_teams.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["massey_id", "massey_team", "cfbd_team", "cfbd_id", "match",
             "first_date", "last_date", "n_editions"]
        )
        for tid in sorted(teams, key=lambda t: teams[t]["name"]):
            rec, mp = teams[tid], tmap[tid]
            w.writerow(
                [tid, rec["name"], mp["cfbd_team"], mp["cfbd_id"], mp["match"],
                 rec["first_date"], rec["last_date"], rec["n_editions"]]
            )


def validate() -> int:
    """Check the written CSVs for the failure modes a bad flatten produces.

    Deliberately not asserted, because they are real source properties:
      * ranks above the edition's row count -- some raters rank a larger pool
        than Massey lists as FBS that week (e.g. 130 vs 127 in Oct 2020).
      * tied ranks -- most raters emit competition ranking (1, 2, 2, 4).
      * `ER` in 1996 publishes rating tiers, not ranks (~10 teams share a value).
    """
    import collections

    cmp_by_date, n_sys_total = {}, 0
    with open(OUT_DIR / "massey_editions.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cmp_by_date.setdefault(row["date"], []).append(int(row["cmp_rank"]))
            n_sys_total += int(row["n_systems"])

    seen, n_rows, no_team, bad_rank = set(), 0, 0, 0
    groups = collections.defaultdict(int)
    with open(OUT_DIR / "massey_ranks.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            n_rows += 1
            key = (row["date"], row["massey_id"], row["system"])
            if key in seen:
                print("DUPLICATE %s" % (key,), file=sys.stderr)
            seen.add(key)
            if not row["cfbd_team"]:
                no_team += 1
            if int(row["rank"]) < 1:
                bad_rank += 1
            groups[(row["date"], row["system"])] += 1

    bad_cmp = [d for d, v in cmp_by_date.items() if sorted(v) != list(range(1, len(v) + 1))]
    ok = True
    for label, value, want in (
        ("rank rows == sum(editions.n_systems)", n_rows, n_sys_total),
        ("duplicate (date, team, system)", n_rows - len(seen), 0),
        ("rows with no CFBD team", no_team, 0),
        ("ranks below 1", bad_rank, 0),
        ("dates whose CMP is not 1..N", len(bad_cmp), 0),
    ):
        status = "ok " if value == want else "FAIL"
        ok &= value == want
        print("%s %-38s %d (want %d)" % (status, label, value, want))
    print("    %d editions, %d (date, system) groups, %d rank rows" % (len(cmp_by_date), len(groups), n_rows))
    return 0 if ok else 1


def main(argv: list | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--report", action="store_true", help="print the team map and stop, writing nothing")
    p.add_argument("--validate", action="store_true", help="check the written CSVs and stop")
    args = p.parse_args(argv)

    if args.validate:
        return validate()

    files = sorted(glob.glob(str(IN_DIR / "ranks_*.json")))
    if not files:
        print("no editions in %s; run massey_ranks.py fetch first" % IN_DIR, file=sys.stderr)
        return 1

    cfbd = load_cfbd_teams()
    teams = collect_teams(files)
    tmap = build_map(teams, cfbd)
    unmatched = [(t, teams[t]["name"]) for t in teams if tmap[t]["match"] == "unmatched"]

    print("%d editions, %d Massey teams, %d CFBD name keys" % (len(files), len(teams), len(cfbd)))
    print("matched %d, unmatched %d" % (len(teams) - len(unmatched), len(unmatched)))
    for tid, name in sorted(unmatched, key=lambda x: x[1]):
        print("  UNMATCHED %-5d %-22s norm=%r" % (tid, name, norm(name)))
    if args.report:
        return 0

    write_team_map(teams, tmap)
    n = flatten(files, tmap)
    print("\nwrote %s" % OUT_DIR)
    for name in ("massey_teams.csv", "massey_systems.csv", "massey_editions.csv", "massey_ranks.csv"):
        path = OUT_DIR / name
        print("  %-22s %8.1f MB" % (name, path.stat().st_size / 1e6))
    print("%d rank rows" % n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
