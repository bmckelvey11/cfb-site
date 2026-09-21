"""Parse the PFF Greenline archives into one tidy long-form history.

Two source shapes, one output. Both are TWO-SIDED tables: every game/market appears
once per side, so pooling all rows returns 50% hit and ~0 CLV by arithmetic, not as a
finding. The pick is derived, and `is_greenline_pick` is the only column that makes a
row a bet.

  PFF_hist.xlsx          2020 season. Banded two-row header, three line snapshots
                         (opening market, opening Greenline, close), cover and
                         break-even probabilities, graded result, and PFF's own CLV.
                         Full school names, no kickoff -> joined on season+week+names.

  ncaa-best-bets*.csv    Three slates in 2022-2023. Greenline value plus the public
                         cash/ticket split. Short abbreviations, exact kickoffs ->
                         joined on kickoff, abbreviations solved (see solve_abbrevs).

Conventions verified against core.fact_game_line rather than assumed:

  ncaa-best-bets `line` on game_away_home_spread is the HOME team's spread, same sign
  as CFBD (negative = home favored): corr +0.994 over n=219, mean |line - spread_close|
  = 0.80, median 0.50, 96% within 3 points. The away side is therefore -line.
  `line` on game_point_total is the total, shared by both sides; empty on moneylines.

  The two sides' Difference sums to minus the book's overround (mean -0.0459, median
  -0.0480, 98.1% within [-0.09, -0.01], matching 1 - 2*110/210 = -0.0476), and no
  game/market ever has two positive sides (0 of 1292). So `Difference > 0` picks at
  most one side and is unambiguous.

LOOKAHEAD: the pick flag comes from the OPENING GREENLINE snapshot, which is when the
number was actually available. Selecting on the closing Difference would be
result-informed: it yields a different, smaller set (323 vs 368 picks in 2020). The
closing block is retained for grading and CLV only, never for selection.

Usage:
    python research/totals/scripts/parse_greenline_history.py
    python research/totals/scripts/parse_greenline_history.py --src DIR --out CSV
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

import duckdb
import pandas as pd

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cfb_paths import DB_PATH, INGEST  # noqa: E402
from match_greenline_books import strong, toks  # noqa: E402

DEFAULT_SRC = Path.home() / "OneDrive" / "Betting" / "NCAA_betting"
EXPORT_GLOB = "ncaa-best-bets*.csv"
HIST_NAME = "PFF_hist.xlsx"

# propType -> (market, sideOne label, sideTwo label)
EXPORT_MARKETS = {
    "game_away_home_spread": ("spread", "away", "home"),
    "game_away_home_win": ("moneyline", "away", "home"),
    "game_point_total": ("total", "over", "under"),
}
HIST_MARKETS = {"Spread": "spread", "Total": "total", "Money Line": "moneyline"}

# Kickoffs drift between feeds; a few slots need a window plus a unique name match.
KICK_WINDOW = pd.Timedelta(hours=6)

OUT_COLS = [
    "season", "week", "game_id", "kickoff_utc", "home_team", "away_team",
    "market", "side", "market_line", "greenline_line",
    "cover_prob", "breakeven_prob", "difference", "is_greenline_pick",
    "bet_result", "clv", "cash_pct", "tickets_pct",
    "home_points", "away_points", "snapshot", "source_file",
]


# --------------------------------------------------------------------------- parsing

def parse_value(raw) -> float | None:
    """Greenline edge. Some exports write '1%', others a raw fraction, others 'null'.

    The percent form was rounded to whole points by whatever produced it, so those
    rows carry ~1e-2 precision while the raw-fraction rows carry full precision.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in {"null", "nan", "none"}:
        return None
    if s.endswith("%"):
        return float(s[:-1]) / 100.0
    return float(s)


def parse_num(raw) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in {"null", "nan", "none"}:
        return None
    return float(s)


def parse_int(raw) -> int | None:
    v = parse_num(raw)
    return None if v is None else int(v)


def side_line(market: str, side: str, line: float | None) -> float | None:
    """The number as that side actually takes it."""
    if line is None:
        return None
    if market == "spread":
        return -line if side == "away" else line
    if market == "total":
        return line
    return None  # moneyline carries no line


# ------------------------------------------------------------------ warehouse lookup

def load_games(con: duckdb.DuckDBPyConnection, seasons: set[int]) -> pd.DataFrame:
    if not seasons:
        return pd.DataFrame()
    q = f"""
        select game_id, season, week, start_date, home_team, away_team,
               home_points, away_points
        from core.fact_game
        where season in ({','.join(str(int(s)) for s in sorted(seasons))})
    """
    g = con.sql(q).df()
    g["utc"] = pd.to_datetime(g["start_date"], utc=True)
    return g


# ------------------------------------------------------------- ncaa-best-bets exports

def read_exports(src: Path) -> tuple[list[dict], list[str]]:
    """Every export row, de-duplicated. Byte-identical copies are dropped whole."""
    kept: dict[str, Path] = {}
    notes: list[str] = []
    for path in sorted(src.glob(EXPORT_GLOB)):
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        if digest in kept:
            notes.append(f"skipped {path.name}: byte-identical to {kept[digest].name}")
            continue
        kept[digest] = path

    rows: list[dict] = []
    seen: set[tuple] = set()
    for path in kept.values():
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        # One export was saved straight from a browser data: URL and kept the prefix.
        if lines and lines[0].startswith("data:text/csv"):
            lines = lines[1:]
        n_new = 0
        for rec in csv.DictReader(lines):
            if not rec.get("propType"):
                continue
            key = (rec["propType"], rec["team"], rec["opponent"], rec["start"])
            if key in seen:
                continue
            seen.add(key)
            rec["_source_file"] = path.name
            rows.append(rec)
            n_new += 1
        notes.append(f"read {path.name}: {n_new} new rows")
    return rows, notes


def solve_abbrevs(slots, by_kick) -> dict[str, str]:
    """Pin each abbreviation to one school using kickoffs as the only evidence.

    An abbreviation's candidates are the teams playing at every kickoff it appears at,
    intersected. Whatever that leaves ambiguous is then resolved by propagation: once a
    slot has only one consistent game, its partner abbreviation is pinned too.
    """
    possible: dict[str, set[str]] = {}

    def narrow(abbrev: str, names) -> None:
        cand = set(names)
        possible[abbrev] = cand if abbrev not in possible else possible[abbrev] & cand

    for away, home, kick in slots:
        games = by_kick.get(kick, [])
        if not games:
            continue
        narrow(away, [g.away_team for g in games])
        narrow(home, [g.home_team for g in games])

    solved = {a: next(iter(s)) for a, s in possible.items() if len(s) == 1}
    for _ in range(len(possible) or 1):
        grew = False
        for away, home, kick in slots:
            games = [
                g for g in by_kick.get(kick, [])
                if (away not in solved or g.away_team == solved[away])
                and (home not in solved or g.home_team == solved[home])
            ]
            if len(games) != 1:
                continue
            for abbrev, name in ((away, games[0].away_team), (home, games[0].home_team)):
                if abbrev not in solved:
                    solved[abbrev] = name
                    grew = True
        if not grew:
            break
    return solved


def match_by_kickoff(slots, by_kick, games: pd.DataFrame, solved: dict[str, str]):
    """slot -> game row. Exact kickoff first, then a windowed unique name match."""
    hit: dict[tuple, object] = {}
    missed: list[tuple] = []
    for away, home, kick in slots:
        want_a, want_h = solved.get(away), solved.get(home)
        exact = [g for g in by_kick.get(kick, [])
                 if g.away_team == want_a and g.home_team == want_h]
        if len(exact) == 1:
            hit[(away, home, kick)] = exact[0]
            continue
        near = games[(games["away_team"] == want_a) & (games["home_team"] == want_h)
                     & ((games["utc"] - kick).abs() <= KICK_WINDOW)]
        if len(near) == 1:
            hit[(away, home, kick)] = next(near.itertuples())
        else:
            missed.append((away, home, kick, want_a, want_h, len(near)))
    return hit, missed


def build_exports(src: Path, con: duckdb.DuckDBPyConnection):
    raw, notes = read_exports(src)
    for n in notes:
        print(f"    {n}")
    if not raw:
        return pd.DataFrame(columns=OUT_COLS), {}

    for rec in raw:
        rec["_kick"] = pd.Timestamp(rec["start"]).tz_convert("UTC")
    slots = sorted({(r["team"], r["opponent"], r["_kick"]) for r in raw})
    seasons = {k.year for _, _, k in slots} | {k.year - 1 for _, _, k in slots}

    games = load_games(con, seasons)
    by_kick = defaultdict(list)
    for g in games.itertuples():
        by_kick[g.utc].append(g)

    solved = solve_abbrevs(slots, by_kick)
    hit, missed = match_by_kickoff(slots, by_kick, games, solved)
    print(f"    abbreviations solved: {len(solved)}/"
          f"{len({a for s in slots for a in s[:2]})}")
    print(f"    game slots matched:   {len(hit)}/{len(slots)}")
    for m in missed:
        print(f"      UNMATCHED {m[0]}@{m[1]} {m[2]:%Y-%m-%d %H:%M} -> "
              f"{m[3]}@{m[4]} ({m[5]} candidates in +/-6h)")

    out = []
    for rec in raw:
        spec = EXPORT_MARKETS.get(rec["propType"])
        if spec is None:
            continue
        market, one, two = spec
        game = hit.get((rec["team"], rec["opponent"], rec["_kick"]))
        line = parse_num(rec.get("line"))
        for side, tag in ((one, "sideOne"), (two, "sideTwo")):
            out.append({
                "season": None if game is None else int(game.season),
                "week": None if game is None else int(game.week),
                "game_id": None if game is None else int(game.game_id),
                "kickoff_utc": rec["_kick"].isoformat(),
                "home_team": solved.get(rec["opponent"]),
                "away_team": solved.get(rec["team"]),
                "market": market,
                "side": side,
                "market_line": side_line(market, side, line),
                "greenline_line": None,
                "cover_prob": None,
                "breakeven_prob": None,
                "difference": parse_value(rec.get(f"{tag}Value")),
                "bet_result": None,
                "clv": None,
                "cash_pct": parse_int(rec.get(f"{tag}Cash")),
                "tickets_pct": parse_int(rec.get(f"{tag}Tickets")),
                "home_points": None if game is None else parse_int(game.home_points),
                "away_points": None if game is None else parse_int(game.away_points),
                "snapshot": "export",
                "source_file": rec["_source_file"],
            })
    return pd.DataFrame(out), solved


# ------------------------------------------------------------------- PFF_hist.xlsx

def flatten_hist_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [b if str(a).startswith("Unnamed") else f'{str(a).split(" (")[0]}|{b}'
                  for a, b in df.columns]
    return df


def read_hist(path: Path) -> tuple[pd.DataFrame, list[str]]:
    """The one distinct sheet. Tabs that are byte-identical copies are dropped."""
    notes: list[str] = []
    xl = pd.ExcelFile(path)
    seen: dict[str, str] = {}
    frames: list[tuple[str, pd.DataFrame]] = []
    for sheet in xl.sheet_names:
        digest = hashlib.md5(
            pd.read_excel(path, sheet_name=sheet, header=None).to_csv().encode()
        ).hexdigest()
        if digest in seen:
            notes.append(f"skipped sheet '{sheet}': identical to sheet '{seen[digest]}'")
            continue
        seen[digest] = sheet
        frames.append((sheet, flatten_hist_columns(
            pd.read_excel(path, sheet_name=sheet, header=[0, 1]))))
    for sheet, df in frames:
        got = sorted(df["Game|Season"].dropna().unique())
        notes.append(f"read sheet '{sheet}': {len(df)} rows, season(s) {got}")
    return (pd.concat([f for _, f in frames], ignore_index=True)
            if frames else pd.DataFrame()), notes


def match_by_name(df: pd.DataFrame, games: pd.DataFrame):
    """PFF_hist has no kickoff, so join on season + week + both school names.

    PFF numbers the postseason straight on from the regular season (weeks 17-18) while
    CFBD restarts it, so a week-scoped join drops the bowls. Anything the week-scoped
    pass misses is retried against the whole season, which is safe here because the
    pairing itself is unique within a season -- a rematch would show up as >1 candidate
    and stay unmatched.
    """
    by_week: dict[tuple, list] = defaultdict(list)
    by_season: dict[int, list] = defaultdict(list)
    for g in games.itertuples():
        by_week[(int(g.season), int(g.week))].append(g)
        by_season[int(g.season)].append(g)

    def candidates(pool, home_t, away_t):
        return [g for g in pool
                if strong(home_t & toks(g.home_team))
                and strong(away_t & toks(g.away_team))]

    out: dict[tuple, object] = {}
    missed: list[tuple] = []
    for key in df[["Game|Season", "Game|Week", "Game|Home Team",
                   "Game|Away Team"]].dropna().drop_duplicates().itertuples(index=False):
        season, week, home, away = int(key[0]), int(key[1]), key[2], key[3]
        ht, at = toks(home), toks(away)
        best = candidates(by_week.get((season, week), []), ht, at)
        if len(best) != 1:
            best = candidates(by_season.get(season, []), ht, at)
        if len(best) == 1:
            out[(season, week, home, away)] = best[0]
        else:
            missed.append((season, week, home, away, len(best)))
    return out, missed


def build_hist(path: Path, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df, notes = read_hist(path)
    for n in notes:
        print(f"    {n}")
    if df.empty:
        return pd.DataFrame(columns=OUT_COLS)

    seasons = {int(s) for s in df["Game|Season"].dropna().unique()}
    games = load_games(con, seasons)
    hit, missed = match_by_name(df, games)
    slots = len(df[["Game|Season", "Game|Week", "Game|Home Team",
                    "Game|Away Team"]].dropna().drop_duplicates())
    print(f"    game slots matched:   {len(hit)}/{slots}")
    if missed:
        by_week: dict[int, int] = defaultdict(int)
        for m in missed:
            by_week[m[1]] += 1
        print(f"    unmatched by week:    {dict(sorted(by_week.items()))}")
        for m in missed[:8]:
            print(f"      UNMATCHED {m[0]} wk{m[1]} {m[3]} @ {m[2]} "
                  f"({m[4]} candidates)")

    # The pick comes from the opening Greenline block. See LOOKAHEAD in the docstring.
    pick_col = "Opening Greenline Line|Difference"
    out = []
    for r in df.itertuples(index=False):
        rec = dict(zip(df.columns, r))
        season, week = rec.get("Game|Season"), rec.get("Game|Week")
        home, away = rec.get("Game|Home Team"), rec.get("Game|Away Team")
        if pd.isna(season) or pd.isna(week) or pd.isna(home) or pd.isna(away):
            continue
        game = hit.get((int(season), int(week), home, away))
        market = HIST_MARKETS.get(str(rec.get("Bet Side|Bet Type")))
        if market is None:
            continue
        diff = parse_num(rec.get(pick_col))
        for block, tag in (("Opening Market Line", "open_market"),
                           ("Opening Greenline Line", "open_greenline"),
                           ("Closing Line", "close")):
            out.append({
                "season": int(season),
                "week": int(week),
                "game_id": None if game is None else int(game.game_id),
                "kickoff_utc": None if game is None else pd.Timestamp(
                    game.utc).isoformat(),
                "home_team": home,
                "away_team": away,
                "market": market,
                "side": rec.get("Bet Side|Side"),
                "market_line": parse_num(rec.get(f"{block}|Market Line")),
                "greenline_line": parse_num(rec.get(f"{block}|Greenline Line")),
                "cover_prob": parse_num(rec.get(f"{block}|Cover Probability")),
                "breakeven_prob": parse_num(rec.get(f"{block}|Break-Even Probability")),
                "difference": parse_num(rec.get(f"{block}|Difference")),
                # One flag per bet, from the opening Greenline block, carried on all
                # three snapshots so a snapshot filter never changes the pick set.
                "is_greenline_pick": None if diff is None else bool(diff > 0),
                "bet_result": rec.get(f"{block}|Bet Result"),
                "clv": parse_num(rec.get("Closing Line|CLV")) if tag == "close" else None,
                "cash_pct": None,
                "tickets_pct": None,
                "home_points": parse_int(rec.get("Game|Home Score")),
                "away_points": parse_int(rec.get("Game|Away Score")),
                "snapshot": tag,
                "source_file": path.name,
            })
    return pd.DataFrame(out)


# ------------------------------------------------------------------------- reporting

def summarize(df: pd.DataFrame) -> None:
    """Pick-only next to all-rows, so the mirrored-table identity stays visible."""
    # Graded at the line in the capture, not the close -- the unit's standing rule, and
    # the same snapshot greenline_archive_review.py uses, so the two never disagree.
    graded = df[df["bet_result"].isin(["W", "L", "P"])
                & (df["snapshot"] == "open_greenline")].copy()
    if graded.empty:
        print("    no graded rows")
        return

    def line(pool: pd.DataFrame, label: str) -> None:
        dec = pool[pool["bet_result"].isin(["W", "L"])]
        if dec.empty:
            print(f"      {label:<22} n=0")
            return
        hit = 100.0 * (dec["bet_result"] == "W").mean()
        clv = pool["clv"].dropna()
        clv_txt = f"{clv.mean():+.4f}" if len(clv) else "n/a"
        print(f"      {label:<22} n={len(dec):>5}  hit={hit:5.1f}%  mean CLV={clv_txt}")

    print("    ALL ROWS (both sides -- 50% and ~0 CLV are arithmetic, not a result):")
    line(graded, "all")
    print("    GREENLINE PICKS ONLY (difference > 0 at the opening Greenline):")
    picks = graded[graded["is_greenline_pick"] == True]  # noqa: E712
    line(picks, "all picks")
    for (season, market), grp in picks.groupby(["season", "market"], dropna=False):
        line(grp, f"{int(season)} {market}")


def self_check() -> None:
    """Pin the two conventions that silently invert the data if wrong."""
    # Spread sign: `line` is the home number, so the away side is its negation.
    # A home favourite at -7 means the away side is taking +7.
    assert side_line("spread", "home", -7.0) == -7.0
    assert side_line("spread", "away", -7.0) == 7.0
    # A total is shared by both sides; a moneyline carries no line at all.
    assert side_line("total", "over", 54.5) == 54.5
    assert side_line("total", "under", 54.5) == 54.5
    assert side_line("moneyline", "away", None) is None
    assert side_line("moneyline", "home", 3.0) is None

    # Value parsing: the exports mix a rounded percent string with a raw fraction,
    # and spell missing three different ways.
    assert parse_value("1%") == 0.01
    assert parse_value("-2%") == -0.02
    assert abs(parse_value("-0.052809524") + 0.052809524) < 1e-12
    assert parse_value("null") is None and parse_value("") is None
    assert parse_value(None) is None

    # Abbreviation solving: two slates sharing a kickoff, where neither abbreviation
    # is resolvable from one slot alone but the pair is across both.
    class G:
        def __init__(self, gid, away, home, kick=None):
            self.game_id, self.away_team, self.home_team, self.utc = gid, away, home, kick
    k1, k2 = pd.Timestamp("2020-10-03T19:00Z"), pd.Timestamp("2020-10-10T19:00Z")
    by_kick = {
        k1: [G(1, "Ole Miss", "Kentucky", k1),
             G(2, "Mississippi State", "Louisiana State", k1)],
        k2: [G(3, "Ole Miss", "Louisiana State", k2),
             G(4, "Alabama", "Kentucky", k2)],
    }
    slots = [("MISS", "UK", k1), ("MST", "LSU", k1),
             ("MISS", "LSU", k2), ("BAMA", "UK", k2)]
    solved = solve_abbrevs(slots, by_kick)
    assert solved["MISS"] == "Ole Miss", solved
    assert solved["MST"] == "Mississippi State", solved
    assert solved["BAMA"] == "Alabama", solved
    assert solved["UK"] == "Kentucky" and solved["LSU"] == "Louisiana State", solved

    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC,
                    help=f"directory holding the archives (default: {DEFAULT_SRC})")
    ap.add_argument("--out", type=Path, default=None,
                    help="output CSV (default: "
                         "$CFB_DATA_ROOT/ingest/pff_scoreboard/greenline_history_archive.csv)")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return
    out = args.out or (INGEST / "pff_scoreboard"
                       / "greenline_history_archive.csv")

    print(f"source: {args.src}")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        print(f"\n  {HIST_NAME}")
        hist = build_hist(args.src / HIST_NAME, con) \
            if (args.src / HIST_NAME).exists() else pd.DataFrame(columns=OUT_COLS)
        if not (args.src / HIST_NAME).exists():
            print(f"    not found, skipped")
        print(f"\n  {EXPORT_GLOB}")
        exports, solved = build_exports(args.src, con)
    finally:
        con.close()

    df = pd.concat([hist, exports], ignore_index=True)
    for c in OUT_COLS:
        if c not in df.columns:
            df[c] = None
    df = df[OUT_COLS].sort_values(
        ["season", "week", "home_team", "market", "side", "snapshot"],
        na_position="last").reset_index(drop=True)

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\n  wrote {out}  ({len(df)} rows)")
    if solved:
        map_path = out.with_name(out.stem + "_team_map.csv")
        pd.DataFrame(sorted(solved.items()),
                     columns=["pff_abbrev", "school"]).to_csv(map_path, index=False)
        print(f"  wrote {map_path}  ({len(solved)} abbreviations)")

    print("\n  rows by source and season:")
    cov = df.groupby(["source_file", "season"], dropna=False).size()
    print("    " + cov.to_string().replace("\n", "\n    "))
    print(f"\n  game_id attached: {df['game_id'].notna().sum()}/{len(df)}")
    print("\n  summary:")
    summarize(df)


if __name__ == "__main__":
    main()
