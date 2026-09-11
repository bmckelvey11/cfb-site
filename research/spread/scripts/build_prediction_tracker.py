"""Union the Prediction Tracker season CSVs and attach a CFBD game_id to every row.

Source: $CFB_DATA_ROOT/ingest/prediction_tracker/ncaa*.csv (seasons come from files present, so a
        new ncaa{year}.csv is picked up without a code change)
CFBD:   stg.game in data/cfb.duckdb -- the GraphQL-fed table. data/raw/games_*.json holds
        regular-season rows only, which would drop every bowl (~35/season); games.csv is
        additionally 2013+ only.
Out:    data/ingest/prediction_tracker_lines.csv

Spreads are negated on the way in: Prediction Tracker writes them positive when the home
team is favored, the opposite of GameRecord.spread everywhere else in this repo.

Join key is (season, {home, away}) as an unordered pair -- deliberately not week, because
CFBD numbers postseason weeks from 1 while Prediction Tracker keeps counting regular weeks
(19, 20), and not oriented, because neutral-site home/road designations disagree. Rematches
(regular season + conference title or bowl) are separated by final score, then by week.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "cfb_paths.py").is_file()
)
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402  (repo's CFB_DATA_ROOT resolver, honors the env override)

DEFAULT_SRC = cfb_paths.INGEST / "prediction_tracker"
DEFAULT_DB = cfb_paths.DB_PATH
DEFAULT_OUT = cfb_paths.INGEST / "prediction_tracker_lines.csv"

# Prediction Tracker name -> extra CFBD candidates. Each name resolves against that
# season's own CFBD team set, so era drift (Central Florida -> UCF) resolves itself.
ALIASES = {
    "Appalachian St.": ["App State"],
    "Central Florida": ["UCF"],
    "Central Mich.": ["Central Michigan"],
    "Connecticut": ["UConn"],
    "Eastern Mich.": ["Eastern Michigan"],
    "Florida Intl.": ["Florida International", "FIU"],
    "Hawaii": ["Hawai'i"],
    "Kent": ["Kent State"],
    "Louisiana-Lafaye": ["Louisiana-Lafayette", "Louisiana"],
    "Louisiana-Lafayette": ["Louisiana"],
    "Louisiana-Monroe": ["Louisiana Monroe", "UL Monroe"],
    "Miami (Fla.)": ["Miami"],
    "Miami (Ohio)": ["Miami (OH)"],
    "Middle Tenn.": ["Middle Tennessee", "Middle Tennessee State"],
    "Mississippi": ["Ole Miss"],
    "NC St.": ["NC State", "North Carolina State"],
    "Northern Ill.": ["Northern Illinois"],
    "Sam Houston St.": ["Sam Houston", "Sam Houston State"],
    "San Jose St.": ["San José State"],
    "Southern Miss.": ["Southern Mississippi", "Southern Miss"],
    "Texas-San Antoni": ["UT San Antonio", "UTSA"],
    "Texas-San Antonio": ["UT San Antonio", "UTSA"],
    "Troy St.": ["Troy"],
    "West Va.": ["West Virginia"],
    "Western Mich.": ["Western Michigan"],
}

# Output columns, in blocks. CFBD owns the unprefixed names because it is the
# authoritative side; Prediction Tracker columns keep their upstream spelling except for
# the one that collides, week, which becomes pt_week.
IDENTITY = [
    "game_id",
    "season",
    "week",
    "season_type",
    "home_team",
    "away_team",
    "home_points",
    "away_points",
    "orientation_flipped",
    "match_status",
]
PT_RENAMES = {"week": "pt_week"}
# Prediction Tracker's own game meta -- kept for traceability, but CFBD is authoritative
# where the two disagree (see match_status). hscore/vscore are PT's scores, actual is the
# home margin, total the combined points, ph* PT's cover/win probabilities.
PT_META = [
    "home",
    "road",
    "pt_week",
    "date",
    "hscore",
    "vscore",
    "actual",
    "total",
    "phcover",
    "phwin",
]
MARKET = ["line", "lineopen"]  # closing and opening market spread
CONSENSUS = ["lineavg", "linemedian", "linestd"]  # PT's own aggregates over the models
# Score-like columns are integers; every other line* column is a spread. Non-numeric
# cells are blanked -- the source carries a few (a team name in linecoll, NUL bytes in
# lineanderson, and one 2006 row whose whole tail is shifted by a column).
INT_COLUMNS = ["pt_week", "hscore", "vscore", "actual", "total"]
# Prediction Tracker writes spreads positive when the home team is favored; this repo's
# GameRecord.spread is negative when the home team is favored. Every line* column is
# negated on the way in so the two agree -- except linestd, which is a dispersion across
# the models rather than a spread and has no side.
UNSIGNED_LINES = {"linestd"}


def seasons_on_disk(src):
    """Seasons taken from the CSVs present, so a new ncaa{year}.csv is picked up."""
    return sorted(int(m.group(1)) for m in (re.fullmatch(r"ncaa(\d{4})", p.stem)
                                           for p in src.glob("ncaa*.csv")) if m)


def candidates(name):
    """CFBD spellings to try for a Prediction Tracker team name, best guess first."""
    out = [name]
    if name.endswith(" St."):
        out.append(name[: -len(" St.")] + " State")
    out.extend(ALIASES.get(name, ()))
    seen, uniq = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def load_cfbd(db_path, seasons):
    """{season: (games_by_unordered_pair, team_names)} for every season we care about."""
    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    # the GraphQL re-pull has renamed this column before (id -> gameId); tolerate either
    cols = {c[0] for c in con.execute("describe stg.game").fetchall()}
    id_col = "gameId" if "gameId" in cols else "id"
    rows = con.execute(
        f"""
        select season, {id_col}, homeTeam, awayTeam, week, seasonType, homePoints, awayPoints
        from stg.game
        where season between ? and ?
        """,
        [min(seasons), max(seasons)],
    ).fetchall()
    con.close()

    by_season = {}
    for season, gid, home, away, week, season_type, hp, ap in rows:
        if not home or not away:
            continue
        pairs, teams = by_season.setdefault(season, (defaultdict(list), set()))
        pairs[frozenset((home, away))].append(
            {
                "game_id": gid,
                "home": home,
                "away": away,
                "week": week,
                "season_type": season_type,
                "home_points": hp,
                "away_points": ap,
            }
        )
        teams.add(home)
        teams.add(away)
    return by_season


def read_season_csv(path, season):
    """Rows keyed by the case-folded header; ruler rows dropped, season attached.

    Headers are only case-folded (2001 ships HOME/LINESAG, later years Home/linesag) --
    model names are never fuzzy-merged, because linemore and linemoore may well be
    different modelers.
    """
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = [PT_RENAMES.get(h, h) for h in (c.strip().lower() for c in next(reader))]
        rows = []
        for raw in reader:
            if not any(c.strip() for c in raw):
                continue
            row = dict(zip(header, (c.strip().replace("\x00", "") for c in raw)))
            # ruler rows: the home cell is a run of digits (e.g. 1234567890123456)
            if re.fullmatch(r"\d+", row.get("home", "")):
                continue
            row["season"] = str(season)
            rows.append(clean_cells(row))
    return rows, header


def as_int(value):
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def flip_sign(text):
    """Negate a numeric string without reformatting it. '9.5' -> '-9.5', '0' -> '0'."""
    if float(text) == 0:
        return text
    return text[1:] if text.startswith("-") else "-" + text


def clean_cells(row):
    """Blank cells that aren't the number the column should hold, and flip spread signs."""
    for col in INT_COLUMNS:
        value = row.get(col)
        if value and not re.fullmatch(r"-?\d+", value):
            row[col] = ""
    for col, value in list(row.items()):
        if not col.startswith("line") or not value:
            continue
        try:
            float(value)
        except ValueError:
            row[col] = ""
            continue
        if col not in UNSIGNED_LINES:
            row[col] = flip_sign(value)
    return row


def order_columns(rows, model_columns):
    """Identity, then Prediction Tracker meta, market, consensus, then models.

    Models sort by how many rows they cover, descending, so the ones worth using come
    first and the long tail of one-season modelers sits at the end. Empty columns drop.
    """
    fill = {c: sum(1 for r in rows if r.get(c)) for c in model_columns}
    models = sorted((c for c in model_columns if fill[c]), key=lambda c: (-fill[c], c))
    return IDENTITY + PT_META + MARKET + CONSENSUS + models, models


def pick_game(hits, home, pt_home, pt_away, week):
    """Choose one CFBD game for a Prediction Tracker row.

    Returns (game, flipped, reason). Rematches -- a regular-season meeting plus a
    conference title game or bowl -- are split by final score first, week second.
    """
    scored = []
    for g in hits:
        flipped = g["home"] != home
        cf_home, cf_away = as_int(g["home_points"]), as_int(g["away_points"])
        if flipped:
            cf_home, cf_away = cf_away, cf_home
        agrees = (
            None not in (pt_home, pt_away, cf_home, cf_away)
            and pt_home == cf_home
            and pt_away == cf_away
        )
        scored.append((g, flipped, agrees))

    agreeing = [s for s in scored if s[2]]
    if len(agreeing) == 1:
        return agreeing[0][0], agreeing[0][1], "matched"
    if len(hits) == 1:
        g, flipped, agrees = scored[0]
        return g, flipped, "matched" if agrees else "matched_score_mismatch"
    near = [s for s in scored if week is not None and s[0]["week"] == week]
    if len(near) == 1:
        return near[0][0], near[0][1], "matched_score_mismatch"
    return None, False, "ambiguous"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    seasons = seasons_on_disk(args.src)
    if not seasons:
        print(f"no ncaa*.csv under {args.src}", file=sys.stderr)
        return 1
    cfbd = load_cfbd(args.db, seasons)
    all_rows = []
    columns = ["season"]
    unresolved = defaultdict(int)
    mismatches = []
    per_season = {}

    for season in seasons:
        path = args.src / f"ncaa{season}.csv"
        rows, header = read_season_csv(path, season)
        for col in header:
            if col not in columns:
                columns.append(col)

        by_pair, teams = cfbd.get(season, (defaultdict(list), set()))

        def resolve(name):
            for cand in candidates(name):
                if cand in teams:
                    return cand
            return None

        counts = defaultdict(int)
        for row in rows:
            home_pt, away_pt = row.get("home", ""), row.get("road", "")
            home, away = resolve(home_pt), resolve(away_pt)
            if home is None or away is None:
                for pt, res in ((home_pt, home), (away_pt, away)):
                    if res is None:
                        unresolved[f"{season}:{pt}"] += 1
                row["match_status"] = "no_team_match"
                counts["no_team_match"] += 1
                all_rows.append(row)
                continue

            hits = by_pair.get(frozenset((home, away)), [])
            if not hits:
                row["match_status"] = "no_game_match"
                counts["no_game_match"] += 1
                all_rows.append(row)
                continue

            game, flipped, status = pick_game(
                hits,
                home,
                as_int(row.get("hscore")),
                as_int(row.get("vscore")),
                as_int(row.get("pt_week")),
            )
            counts[status] += 1
            row["match_status"] = status
            if game is None:
                all_rows.append(row)
                continue

            row["game_id"] = game["game_id"]
            row["home_team"] = game["home"]
            row["away_team"] = game["away"]
            row["week"] = game["week"]
            row["season_type"] = game["season_type"]
            row["home_points"] = game["home_points"]
            row["away_points"] = game["away_points"]
            row["orientation_flipped"] = "1" if flipped else "0"
            counts["flipped"] += int(flipped)
            if status == "matched_score_mismatch":
                mismatches.append(
                    f"{season} {game['game_id']}: PT {home_pt} "
                    f"{row.get('hscore') or '?'}-{row.get('vscore') or '?'} {away_pt} | CFBD "
                    f"{game['home']} {game['home_points']}-{game['away_points']} {game['away']}"
                )
            all_rows.append(row)
        per_season[season] = counts

    known = set(IDENTITY) | set(PT_META) | set(MARKET) | set(CONSENSUS)
    fieldnames, models = order_columns(all_rows, [c for c in columns if c not in known])
    dropped = [c for c in columns if c not in known and c not in models]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    statuses = ["matched", "matched_score_mismatch", "ambiguous", "no_team_match", "no_game_match"]
    total = len(all_rows)
    got_id = sum(c["matched"] + c["matched_score_mismatch"] for c in per_season.values())
    clean = sum(c["matched"] for c in per_season.values())
    print(
        f"wrote {args.out} -- {total} rows, {len(fieldnames)} columns "
        f"({len(IDENTITY)} identity + {len(PT_META)} pt meta + {len(MARKET)} market + "
        f"{len(CONSENSUS)} consensus + {len(models)} models)"
    )
    if dropped:
        print(f"dropped {len(dropped)} column(s) with no data: {', '.join(dropped)}")
    print(f"game_id attached: {got_id}/{total} ({got_id / total:.1%})")
    print(f"  of those, scores agree with CFBD: {clean}/{got_id} ({clean / got_id:.2%})")
    print(f"  orientation-flipped: {sum(c['flipped'] for c in per_season.values())}")
    print("\nseason  rows  matched  scoremis  ambig  noteam  nogame    rate")
    for season, c in sorted(per_season.items()):
        n = sum(c[s] for s in statuses)
        ok = c["matched"] + c["matched_score_mismatch"]
        print(
            f"{season}  {n:4d}  {c['matched']:7d}  {c['matched_score_mismatch']:8d}"
            f"  {c['ambiguous']:5d}  {c['no_team_match']:6d}  {c['no_game_match']:6d}  {ok / n:6.1%}"
        )

    if unresolved:
        print(f"\nunresolved team names ({len(unresolved)}):", file=sys.stderr)
        for key, n in sorted(unresolved.items(), key=lambda kv: -kv[1])[:40]:
            print(f"  {key}  x{n}", file=sys.stderr)
    if mismatches:
        print(f"\nscore mismatches on matched rows ({len(mismatches)}):", file=sys.stderr)
        for line in mismatches[:60]:
            print(f"  {line}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
