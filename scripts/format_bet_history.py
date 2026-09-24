"""Reformat a sportsbook-tracker bet history export into a filterable Excel workbook.

The export packs market and side into one `Type` value (spread_home, under, home_over).
This splits it into Market plus separate Home/Away and Over/Under columns, so a team
total fills both, a spread or moneyline fills only Home/Away, and a game total fills only
Over/Under. Parlay/teaser legs are parsed like straights and tied to their ticket.

    python scripts/format_bet_history.py "C:/Users/mckel/Downloads/history (1).csv"

Writes `<input stem>_formatted.xlsx` beside the input unless --out is given.
"""
import argparse
import csv
from pathlib import Path

import pandas as pd

# export Type -> (Market, Home/Away, Over/Under). An unknown Type raises KeyError on purpose.
TYPES = {
    "spread_home": ("Spread", "Home", None),
    "spread_away": ("Spread", "Away", None),
    "ml_home": ("Moneyline", "Home", None),
    "ml_away": ("Moneyline", "Away", None),
    "over": ("Total", None, "Over"),
    "under": ("Total", None, "Under"),
    "home_over": ("Team Total", "Home", "Over"),
    "home_under": ("Team Total", "Home", "Under"),
    "away_over": ("Team Total", "Away", "Over"),
    "away_under": ("Team Total", "Away", "Under"),
    "custom": ("Custom", None, None),
}
MONEY = ["Units Wagered", "Units Net", "$ Wagered", "$ Net"]


def num(s):
    return float(s) if s.strip() else None


def bet_row(f):
    """One straight bet (or parlay leg) from the export's 14 fields."""
    league, start, game, desc, typ, period, odds, line, result, *money, tag = f
    market, ha, ou = TYPES[typ]
    away, _, home = game.partition(" @ ")
    kick = pd.Timestamp(start).tz_convert("America/New_York").tz_localize(None) if start else None
    return {
        "Kickoff (ET)": kick, "League": league, "Period": period,
        "Away": away or None, "Home": home or None,
        "Market": market, "Home/Away": ha, "Over/Under": ou,
        "Team": {"Home": home, "Away": away}.get(ha),
        # one export field holds spread, total, or (moneyline) the odds again
        "Spread": num(line) if market == "Spread" else None,
        "Total": num(line) if market in ("Total", "Team Total") else None,
        "Odds": num(odds), "Result": result,
        **dict(zip(MONEY, map(num, money))),
        "Tag": tag or None, "Pick Desc": desc,
    }


def parse(path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    straights, tickets, legs, custom = [], [], [], []
    section = "straights"
    for f in csv.reader(lines):
        head = f[0].strip() if f else ""
        if not head and len(f) <= 1 or head.startswith("data:") or head in ("League", "Pick Desc"):
            continue
        if head == "Parlays/Teasers":
            section = "parlays"
        elif head == "Custom Picks":
            section = "custom"
        elif section == "straights":
            straights.append(bet_row(f))
        elif section == "parlays" and head:  # ticket row
            desc, typ, odds, result, *money, tag, teaser = f
            tickets.append({"Ticket #": len(tickets) + 1, "Pick Desc": desc, "Type": typ.replace("_", " ").title(),
                            "Odds": num(odds), "Result": result,
                            **dict(zip(MONEY, map(num, money))),
                            "Tag": tag or None, "Teaser Pts": num(teaser), "Legs": 0})
        elif section == "parlays":  # leg row: blank first field, then a straight bet
            tickets[-1]["Legs"] += 1
            legs.append({"Ticket #": tickets[-1]["Ticket #"], **bet_row(f[1:])})
        else:
            # This section's rows carry 8 fields under a 9-field header (Type is missing).
            desc, odds, result, *money, tag = f
            custom.append({"Pick Desc": desc or None, "Odds": num(odds), "Result": result,
                           **dict(zip(MONEY, map(num, money))), "Tag": tag or None})
    return pd.DataFrame(straights), pd.DataFrame(tickets), pd.DataFrame(legs), pd.DataFrame(custom)


def record(df, keys):
    settled = df[df["Result"].isin(["win", "loss", "push"])].fillna({k: "" for k in keys})
    g = settled.groupby(keys, sort=False)
    out = pd.DataFrame({
        "Bets": g.size(),
        "W": g["Result"].apply(lambda r: (r == "win").sum()),
        "L": g["Result"].apply(lambda r: (r == "loss").sum()),
        "P": g["Result"].apply(lambda r: (r == "push").sum()),
        "Units Wagered": g["Units Wagered"].sum(),
        "Units Net": g["Units Net"].sum(),
    }).reset_index()
    return out


def summary(straights, tickets):
    keys = ["Market", "Home/Away", "Over/Under"]
    s = record(straights, keys).sort_values(keys)
    p = record(tickets.rename(columns={"Type": "Market"}).assign(**{"Home/Away": None, "Over/Under": None}), keys)
    out = pd.concat([s, p], ignore_index=True)
    total = out[["Bets", "W", "L", "P", "Units Wagered", "Units Net"]].sum()
    out = pd.concat([out, pd.DataFrame([{"Market": "All", **total}])], ignore_index=True)
    out["Win %"] = out["W"] / (out["W"] + out["L"])
    out["ROI"] = out["Units Net"] / out["Units Wagered"]
    return out


def write(path, sheets):
    with pd.ExcelWriter(path, engine="xlsxwriter", datetime_format="m/d/yy h:mm AM/PM") as w:
        fmt = {k: w.book.add_format({"num_format": v}) for k, v in
               {"units": "0.00;[Red]-0.00", "money": "#,##0.00;[Red]-#,##0.00",
                "pct": "0.0%", "odds": "+0;-0;0", "spread": '+0.0;-0.0;"PK"'}.items()}
        col_fmt = {"Units Wagered": fmt["units"], "Units Net": fmt["units"],
                   "$ Wagered": fmt["money"], "$ Net": fmt["money"], "Odds": fmt["odds"],
                   "Spread": fmt["spread"], "Win %": fmt["pct"], "ROI": fmt["pct"]}
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False, startrow=1, header=False)
            ws = w.sheets[name]
            ws.add_table(0, 0, max(len(df), 1), len(df.columns) - 1,
                         {"columns": [{"header": c} for c in df.columns],
                          "style": "Table Style Medium 2", "name": name.replace(" ", "")})
            for i, c in enumerate(df.columns):
                width = max([len(c), *(len(str(v)) for v in df[c].head(500))]) + 2
                ws.set_column(i, i, min(width, 40) if c != "Kickoff (ET)" else 18, col_fmt.get(c))
            ws.freeze_panes(1, 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    straights, tickets, legs, custom = parse(a.csv)

    # Every leg belongs to a ticket and no leg was lost between them.
    assert tickets["Legs"].sum() == len(legs), (tickets["Legs"].sum(), len(legs))
    # Custom Picks has so far been the parlay tickets again, stripped of their
    # descriptions. Drop it when that holds; keep it as its own sheet when it stops holding.
    cols = ["Odds", "Result", *MONEY]
    dup = len(custom) == len(tickets) and custom[cols].equals(tickets[cols]) if len(custom) else True

    sheets = {"Straights": straights, "Parlays": tickets, "Parlay Legs": legs,
              "Summary": summary(straights, tickets)}
    if not dup:
        sheets["Custom Picks"] = custom
    out = a.out or a.csv.with_name(f"{a.csv.stem}_formatted.xlsx")
    write(out, sheets)
    print(f"{len(straights)} straights, {len(tickets)} tickets, {len(legs)} legs, "
          f"custom picks {'dropped (duplicate of tickets)' if dup else f'kept ({len(custom)})'}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
