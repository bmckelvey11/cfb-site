"""Ingest a hand-filled bet sheet and attach everything the books already know.

You type eleven columns -- when you placed it, the two teams, the market, your side, the
number and price you got, the stake, the book, and which system called it. Everything else
is looked up: the game_id, the opener and close, CLV, the result, and the P&L.

    placed_at,away,home,market,side,line,odds,stake,book,source,notes

`away` and `home` are loose: "East Carolina" / "Alabama". They are matched on team-name
tokens against games kicking off within +/-7 days of `placed_at`, so abbreviations and
mascots both work as long as one distinctive word survives. Which column is which matters
only for orienting the spread -- enter them the wrong way round and the row is reported as
reversed rather than silently mis-graded.

`line` is the number as YOU took it. For a spread that means from your side: taking the
home team at -3.5 is `-3.5`, taking the away dog at +3.5 is `+3.5`. For a total it is the
total. Moneylines leave it blank.

CLV conventions, which differ by market and are easy to invert:

    spread      clv = line_taken - close_on_your_side      (points)
    total       clv = close - line for OVER, line - close for UNDER   (points)
                delegated to models.totals.clv.clv_points, one definition for both
    moneyline   clv = implied(close) - implied(taken)       (probability)

Positive always means the market moved your way after you bet. Spread and total CLV are
in points and comparable to each other; moneyline CLV is a probability and is not.

The close comes from the book you actually typed when the warehouse has it, and from the
median across providers when it does not -- `close_source` says which, so a median-derived
CLV is never mistaken for your book's number. Openers are thin on purpose: only bovada,
espn bet and draftkings carry `spread_open`/`total_open`, so `open_line` is often null.

Coverage: `core.fact_game_line` starts at 2023. Older bets still get a result and P&L, but
no line history and therefore no CLV.

Never writes to your input file. Unmatched rows are reported and carried into the output
with `match_status`, never dropped.

Usage:
    python ledgers/ingest_bets.py --init     # create the sheet from the template
    python ledgers/ingest_bets.py --dry-run  # match only, write nothing
    python ledgers/ingest_bets.py

`--add` appends one bet instead of hand-editing the CSV, which is where a transposed
line or a column-shifted row comes from. It validates the row, refuses to write one
that could never grade, and then says whether the warehouse can find the game:

    python ledgers/ingest_bets.py --add \\
        --away Miami --home "Wake Forest" --market total --side UNDER \\
        --line 55.5 --odds -112 --stake 1.1 --book DraftKings --source totals
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

import duckdb
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "research" / "totals" / "scripts"))

from cfb_paths import DB_PATH, INGEST, PROCESSED  # noqa: E402
from match_greenline_books import strong, toks  # noqa: E402
from models.totals.clv import clv_points  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent / "manual_bets_template.csv"
SHEET = INGEST / "bet_history" / "manual_bets.csv"
OUT = PROCESSED / "bet_history_graded.csv"

MATCH_WINDOW = pd.Timedelta(days=7)
MARKETS = {"spread", "total", "moneyline"}
OVER_UNDER = {"OVER": "over", "UNDER": "under", "O": "over", "U": "under"}

REQUIRED_COLS = ["placed_at", "away", "home", "market", "side", "line", "odds", "stake"]

OUT_COLS = [
    "placed_at", "away", "home", "market", "side", "side_role", "line", "odds", "stake",
    "book", "source", "notes",
    "game_id", "season", "week", "kickoff", "away_team", "home_team",
    "open_line", "close_line", "close_source", "clv", "clv_unit",
    "home_points", "away_points", "result", "payout", "net", "roi",
    "match_status", "match_note",
]


# ------------------------------------------------------------------------ primitives

def american_payout(odds: float, stake: float) -> float:
    """Profit on a won bet, excluding the returned stake."""
    if odds > 0:
        return stake * odds / 100.0
    return stake * 100.0 / abs(odds)


def implied_prob(odds: float) -> float:
    """American odds -> break-even probability."""
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def spread_result(own_margin: float, line: float) -> str:
    """`line` is from the bettor's side, so the cover test is one addition."""
    margin = own_margin + line
    if margin > 0:
        return "win"
    if margin < 0:
        return "loss"
    return "push"


def total_result(points: float, line: float, side: str) -> str:
    if points == line:
        return "push"
    went_over = points > line
    return "win" if (went_over == (side == "over")) else "loss"


def settle(result: str, odds: float, stake: float) -> tuple[float, float, float]:
    """(payout, net, roi). A push returns the stake and nets nothing."""
    if result == "win":
        payout = american_payout(odds, stake)
        return payout, payout, payout / stake
    if result == "loss":
        return 0.0, -stake, -1.0
    return 0.0, 0.0, 0.0


# --------------------------------------------------------------------------- matching

def find_game(away: str, home: str, placed: pd.Timestamp, games: pd.DataFrame):
    """Unique games whose teams both share a distinctive token, near `placed`."""
    at, ht = toks(away), toks(home)
    window = games[(games["utc"] >= placed - MATCH_WINDOW)
                   & (games["utc"] <= placed + MATCH_WINDOW)]
    hits = [g for g in window.itertuples()
            if strong(at & toks(g.away_team)) and strong(ht & toks(g.home_team))]
    if len(hits) == 1:
        return hits[0], "matched", ""
    if not hits:
        # Teams may have been entered the wrong way round; say so rather than guess.
        flipped = [g for g in window.itertuples()
                   if strong(ht & toks(g.away_team)) and strong(at & toks(g.home_team))]
        if len(flipped) == 1:
            g = flipped[0]
            return None, "unmatched", (
                f"looks reversed: warehouse has {g.away_team} @ {g.home_team}")
        return None, "unmatched", "no game with both teams within +/-7d of placed_at"
    return None, "ambiguous", f"{len(hits)} games matched: " + ", ".join(
        f"{g.away_team}@{g.home_team} {g.utc:%Y-%m-%d}" for g in hits[:3])


def resolve_side(market: str, side: str, game) -> tuple[str, str]:
    """(side_role, note). Spread/moneyline sides name a team; totals name a direction."""
    if market == "total":
        role = OVER_UNDER.get(str(side).strip().upper())
        return (role, "") if role else ("", f"side must be OVER or UNDER, got {side!r}")
    raw = str(side).strip()
    if raw.upper() in {"HOME", "AWAY"}:
        return raw.lower(), ""
    st = toks(raw)
    if strong(st & toks(game.home_team)):
        return "home", ""
    if strong(st & toks(game.away_team)):
        return "away", ""
    return "", f"side {side!r} matches neither {game.away_team} nor {game.home_team}"


# ------------------------------------------------------------------------ line lookup

def book_lines(con: duckdb.DuckDBPyConnection, game_ids: list[int]) -> pd.DataFrame:
    if not game_ids:
        return pd.DataFrame()
    ids = ",".join(str(int(g)) for g in game_ids)
    return con.sql(f"""
        select game_id, lower(provider_key) provider_key,
               spread_close, spread_open, total_close, total_open,
               moneyline_home, moneyline_away
        from core.fact_game_line
        where game_id in ({ids})
    """).df()


def pick_close(lines: pd.DataFrame, game_id: int, market: str, side_role: str,
               book: str) -> tuple[float | None, float | None, str]:
    """(open, close, source). Your book if the warehouse has it, else the median."""
    if lines.empty:
        return None, None, "no line data"
    rows = lines[lines["game_id"] == game_id]
    if rows.empty:
        return None, None, "no line data"

    if market == "spread":
        close_col, open_col = "spread_close", "spread_open"
    elif market == "total":
        close_col, open_col = "total_close", "total_open"
    else:
        close_col = "moneyline_home" if side_role == "home" else "moneyline_away"
        open_col = None

    def orient(value: float | None) -> float | None:
        # spread_close is home-relative; flip it for an away-side bet.
        if value is None or pd.isna(value):
            return None
        if market == "spread" and side_role == "away":
            return -float(value)
        return float(value)

    want = str(book or "").strip().lower()
    mine = rows[(rows["provider_key"] == want) & rows[close_col].notna()]
    if not mine.empty:
        r = mine.iloc[0]
        opener = None if open_col is None else r.get(open_col)
        return orient(opener), orient(r[close_col]), want

    have = rows[rows[close_col].notna()]
    if have.empty:
        return None, None, f"no {market} close at any provider"
    close = float(have[close_col].median())
    opener = None
    if open_col is not None:
        o = rows[rows[open_col].notna()][open_col]
        opener = float(o.median()) if not o.empty else None
    return orient(opener), orient(close), f"median({len(have)} providers)"


def compute_clv(market: str, side_role: str, line: float | None,
                close: float | None, odds: float | None) -> tuple[float | None, str]:
    if close is None:
        return None, ""
    if market == "spread":
        if line is None:
            return None, ""
        return round(float(line) - float(close), 2), "points"
    if market == "total":
        if line is None:
            return None, ""
        side = "OVER" if side_role == "over" else "UNDER"
        return round(clv_points(side, float(line), float(close)), 2), "points"
    if odds is None:
        return None, ""
    return round(implied_prob(float(close)) - implied_prob(float(odds)), 4), "probability"


# --------------------------------------------------------------------------- appending

SHEET_COLS = ["placed_at", "away", "home", "market", "side", "line", "odds", "stake",
              "book", "source", "notes"]


def validate_add(row: dict) -> str:
    """Reject a row that could never grade correctly. Returns '' when the row is fine."""
    market = row["market"]
    if market not in MARKETS:
        return f"market must be one of {sorted(MARKETS)}, got {market!r}"

    try:
        pd.Timestamp(row["placed_at"])
    except (ValueError, TypeError):
        return f"unparseable placed_at {row['placed_at']!r}"

    if market == "total" and row["side"].strip().upper() not in OVER_UNDER:
        return f"a total needs side OVER or UNDER, got {row['side']!r}"
    if market != "total" and not row["side"].strip():
        return f"a {market} needs a side naming a team"

    for field in ("line", "odds", "stake"):
        try:
            _num(row[field])
        except ValueError:
            return f"{field} must be a number, got {row[field]!r}"

    if market == "moneyline":
        if _num(row["line"]) is not None:
            return "a moneyline has no line; leave it blank"
    elif _num(row["line"]) is None:
        return f"a {market} needs a line"

    if _num(row["odds"]) is None:
        return "odds are required"
    if (stake := _num(row["stake"])) is None or stake <= 0:
        return f"stake must be a positive number, got {row['stake']!r}"
    return ""


def check_match(row: dict) -> str:
    """Say whether the warehouse can find this game, so a typo surfaces now.

    Advisory only -- the bet is appended either way, matching the rule that unmatched
    rows are reported rather than dropped.
    """
    try:
        con = duckdb.connect(str(DB_PATH), read_only=True)
    except (duckdb.Error, OSError) as exc:
        return f"could not open the warehouse to check the match: {exc}"
    try:
        games = load_games(con)
    finally:
        con.close()

    placed = pd.Timestamp(row["placed_at"])
    placed = placed.tz_localize("UTC") if placed.tz is None else placed.tz_convert("UTC")
    game, status, note = find_game(row["away"], row["home"], placed, games)
    if game is None:
        return f"{status}: {note}" if note else status

    side_role, side_note = resolve_side(row["market"], row["side"], game)
    if not side_role:
        return side_note
    return ""


def append_row(sheet: Path, row: dict) -> None:
    """Append one bet, creating the sheet with a header when it does not exist yet."""
    sheet.parent.mkdir(parents=True, exist_ok=True)
    new = not sheet.exists()
    with sheet.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SHEET_COLS)
        if new:
            writer.writeheader()
        writer.writerow(row)


def add(sheet: Path, args: argparse.Namespace) -> None:
    row = {
        "placed_at": args.placed_at or pd.Timestamp.now("UTC").strftime("%Y-%m-%d %H:%M"),
        "away": str(args.away).strip(),
        "home": str(args.home).strip(),
        "market": str(args.market).strip().lower(),
        "side": str(args.side).strip(),
        "line": "" if args.line is None else str(args.line).strip(),
        "odds": str(args.odds).strip(),
        "stake": str(args.stake).strip(),
        "book": str(args.book).strip(),
        "source": str(args.source).strip(),
        "notes": str(args.notes).strip(),
    }

    problem = validate_add(row)
    if problem:
        raise SystemExit(f"not appended -- {problem}")

    append_row(sheet, row)
    line = "" if row["market"] == "moneyline" else f" {row['line']}"
    print(f"appended to {sheet}\n"
          f"  {row['away']} @ {row['home']}  {row['market']} {row['side']}{line} "
          f"{row['odds']}  stake {row['stake']}  ({row['book'] or 'no book'})")

    warning = check_match(row)
    print(f"  WARNING: {warning}" if warning else "  matched a warehouse game")


# ------------------------------------------------------------------------------ driver

def load_games(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    g = con.sql("""
        select game_id, season, week, start_date, home_team, away_team,
               home_points, away_points
        from core.fact_game
    """).df()
    g["utc"] = pd.to_datetime(g["start_date"], utc=True)
    return g


def _num(value) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    return float(s)


def build(sheet: Path) -> pd.DataFrame:
    bets = pd.read_csv(sheet, dtype=str, keep_default_na=False)
    missing = [c for c in REQUIRED_COLS if c not in bets.columns]
    if missing:
        extra = " (the single `game` column was split into `away` and `home`)" \
            if "game" in bets.columns else ""
        raise SystemExit(f"{sheet} is missing columns: {missing}{extra}")
    bets = bets[(bets["away"].str.strip() != "") & (bets["home"].str.strip() != "")]
    if bets.empty:
        raise SystemExit(f"{sheet} has no rows with both teams filled in")

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        games = load_games(con)
        staged, ids = [], []
        for rec in bets.to_dict("records"):
            row = {c: None for c in OUT_COLS}
            row.update({k: rec.get(k) for k in
                        ("placed_at", "away", "home", "market", "side",
                         "book", "source", "notes")})
            row["line"] = _num(rec.get("line"))
            row["odds"] = _num(rec.get("odds"))
            row["stake"] = _num(rec.get("stake"))
            market = str(rec.get("market", "")).strip().lower()
            row["market"] = market

            if market not in MARKETS:
                row["match_status"] = "invalid"
                row["match_note"] = f"market must be one of {sorted(MARKETS)}"
                staged.append((row, None))
                continue
            try:
                placed = pd.Timestamp(rec["placed_at"]).tz_localize("UTC") \
                    if pd.Timestamp(rec["placed_at"]).tz is None \
                    else pd.Timestamp(rec["placed_at"]).tz_convert("UTC")
            except (ValueError, TypeError):
                row["match_status"] = "invalid"
                row["match_note"] = f"unparseable placed_at {rec.get('placed_at')!r}"
                staged.append((row, None))
                continue

            game, status, note = find_game(
                str(rec.get("away", "")), str(rec.get("home", "")), placed, games)
            row["match_status"], row["match_note"] = status, note
            if game is None:
                staged.append((row, None))
                continue

            side_role, side_note = resolve_side(market, rec.get("side"), game)
            if not side_role:
                row["match_status"], row["match_note"] = "invalid", side_note
                staged.append((row, None))
                continue

            row.update({
                "side_role": side_role,
                "game_id": int(game.game_id),
                "season": int(game.season),
                "week": int(game.week),
                "kickoff": pd.Timestamp(game.utc).isoformat(),
                "away_team": game.away_team,
                "home_team": game.home_team,
                "home_points": None if pd.isna(game.home_points) else int(game.home_points),
                "away_points": None if pd.isna(game.away_points) else int(game.away_points),
            })
            ids.append(int(game.game_id))
            staged.append((row, game))

        lines = book_lines(con, ids)
    finally:
        con.close()

    out = []
    for row, game in staged:
        if game is not None:
            row["open_line"], row["close_line"], row["close_source"] = pick_close(
                lines, int(game.game_id), row["market"], row["side_role"], row["book"])
            row["clv"], row["clv_unit"] = compute_clv(
                row["market"], row["side_role"], row["line"],
                row["close_line"], row["odds"])

            hp, ap = row["home_points"], row["away_points"]
            if hp is not None and ap is not None:
                if row["market"] == "total":
                    row["result"] = total_result(hp + ap, row["line"], row["side_role"])
                elif row["market"] == "spread":
                    own = (hp - ap) if row["side_role"] == "home" else (ap - hp)
                    row["result"] = spread_result(own, row["line"])
                else:
                    own = (hp - ap) if row["side_role"] == "home" else (ap - hp)
                    row["result"] = "win" if own > 0 else "loss" if own < 0 else "push"

            if row["result"] and row["odds"] is not None and row["stake"] is not None:
                row["payout"], row["net"], row["roi"] = settle(
                    row["result"], row["odds"], row["stake"])
        out.append(row)

    return pd.DataFrame(out)[OUT_COLS]


def report(df: pd.DataFrame) -> None:
    bad = df[df["match_status"] != "matched"]
    print(f"  rows: {len(df)}   matched: {len(df) - len(bad)}")
    for r in bad.itertuples():
        print(f"    {r.match_status.upper():<10} {r.away} @ {r.home} "
              f"({r.market} {r.side}) -- {r.match_note}")

    graded = df[df["result"].isin(["win", "loss", "push"])]
    if graded.empty:
        print("\n  nothing graded yet")
    else:
        dec = graded[graded["result"] != "push"]
        print(f"\n  graded {len(graded)} ({len(graded) - len(dec)} push)")
        if not dec.empty:
            print(f"    record  {int((dec['result'] == 'win').sum())}-"
                  f"{int((dec['result'] == 'loss').sum())}  "
                  f"({100 * (dec['result'] == 'win').mean():.1f}%)")
        staked = graded.dropna(subset=["net", "stake"])
        if not staked.empty:
            print(f"    staked  {staked['stake'].sum():,.2f}   "
                  f"net {staked['net'].sum():+,.2f}   "
                  f"roi {100 * staked['net'].sum() / staked['stake'].sum():+.2f}%")
            for src, grp in staked.groupby("source", dropna=False):
                print(f"      {str(src) or '(none)':<14} n={len(grp):>3}  "
                      f"net {grp['net'].sum():+9,.2f}  "
                      f"roi {100 * grp['net'].sum() / grp['stake'].sum():+6.2f}%")

    for unit, grp in df.dropna(subset=["clv"]).groupby("clv_unit"):
        print(f"\n  CLV ({unit}): n={len(grp)}  mean {grp['clv'].mean():+.3f}  "
              f"median {grp['clv'].median():+.3f}  "
              f"positive {100 * (grp['clv'] > 0).mean():.0f}%")
        med = grp[grp["close_source"].str.startswith("median", na=False)]
        if not med.empty:
            print(f"    ({len(med)} of these priced off a provider median, "
                  f"not the book you typed)")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", type=Path, default=SHEET)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--init", action="store_true",
                    help="copy the template to the sheet path if it does not exist")
    ap.add_argument("--dry-run", action="store_true", help="match only, write nothing")
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--add", action="store_true",
                    help="append one bet to the sheet and exit")
    g = ap.add_argument_group("--add fields")
    g.add_argument("--away")
    g.add_argument("--home")
    g.add_argument("--market", choices=sorted(MARKETS))
    g.add_argument("--side", help="OVER/UNDER for a total, else the team you took")
    g.add_argument("--line", help="the number as you took it; blank for a moneyline")
    g.add_argument("--odds")
    g.add_argument("--stake")
    g.add_argument("--book", default="")
    g.add_argument("--source", default="")
    g.add_argument("--notes", default="")
    g.add_argument("--placed-at", dest="placed_at", help="default: now, UTC")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    if args.add:
        missing = [f"--{f}" for f in ("away", "home", "market", "side", "odds", "stake")
                   if not getattr(args, f)]
        if missing:
            raise SystemExit(f"--add needs {', '.join(missing)}")
        add(args.sheet, args)
        return

    if args.init:
        args.sheet.parent.mkdir(parents=True, exist_ok=True)
        if args.sheet.exists():
            print(f"{args.sheet} already exists, left alone")
        else:
            shutil.copy(TEMPLATE, args.sheet)
            print(f"created {args.sheet} -- fill it in, then rerun without --init")
        return

    if not args.sheet.exists():
        raise SystemExit(f"{args.sheet} not found. Run with --init to create it.")

    print(f"sheet: {args.sheet}")
    df = build(args.sheet)
    report(df)

    if args.dry_run:
        print("\n  --dry-run, nothing written")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"\n  wrote {args.out}  ({len(df)} rows)")


def self_check() -> None:
    """Pin the sign and settlement rules. The CLV signs invert if these are wrong."""
    # American odds both ways.
    assert american_payout(-110, 110) == 100.0
    assert american_payout(150, 100) == 150.0
    assert abs(implied_prob(-110) - 0.5238) < 1e-4
    assert abs(implied_prob(150) - 0.40) < 1e-9

    # Spread, line from the bettor's side. Home -3.5 winning by 7 covers; the away
    # +3.5 on the same game does not.
    assert spread_result(7, -3.5) == "win"
    assert spread_result(-7, 3.5) == "loss"
    assert spread_result(3, -3.0) == "push"
    assert spread_result(-3, 3.0) == "push"

    # Totals, both directions, and the push.
    assert total_result(60, 54.5, "over") == "win"
    assert total_result(50, 54.5, "over") == "loss"
    assert total_result(50, 54.5, "under") == "win"
    assert total_result(54, 54.0, "under") == "push"

    # Settlement: a push is not a loss.
    assert settle("push", -110, 100) == (0.0, 0.0, 0.0)
    assert settle("loss", -110, 100) == (0.0, -100, -1.0)
    payout, net, roi = settle("win", -110, 110)
    assert (payout, net) == (100.0, 100.0) and abs(roi - 0.909) < 1e-3

    # CLV signs. Spread and total are points, positive = market came to you.
    assert compute_clv("spread", "home", -3.5, -4.5, -110) == (1.0, "points")
    assert compute_clv("spread", "away", 3.5, 2.5, -110) == (1.0, "points")
    assert compute_clv("total", "over", 54.5, 56.5, -110) == (2.0, "points")
    assert compute_clv("total", "under", 54.5, 52.5, -110) == (2.0, "points")
    # Moneyline is a probability: taking +150 and watching it close +120 is positive.
    clv, unit = compute_clv("moneyline", "away", None, 120, 150)
    assert unit == "probability" and clv > 0, (clv, unit)
    assert compute_clv("spread", "home", -3.5, None, -110) == (None, "")

    # An away-side spread bet flips the home-relative warehouse number.
    lines = pd.DataFrame([{
        "game_id": 1, "provider_key": "draftkings", "spread_close": -7.0,
        "spread_open": -6.0, "total_close": 55.0, "total_open": 54.0,
        "moneyline_home": -300, "moneyline_away": 240,
    }])
    assert pick_close(lines, 1, "spread", "home", "DraftKings") == (-6.0, -7.0, "draftkings")
    assert pick_close(lines, 1, "spread", "away", "DraftKings") == (6.0, 7.0, "draftkings")
    # A book the warehouse does not carry falls back to the median, and says so.
    opener, close, src = pick_close(lines, 1, "total", "over", "SomeLocalBook")
    assert (opener, close) == (54.0, 55.0) and src.startswith("median"), src
    assert pick_close(lines, 2, "spread", "home", "DraftKings") == (None, None, "no line data")

    print("self-check ok")


if __name__ == "__main__":
    main()
