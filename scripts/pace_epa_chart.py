"""Scatter of offensive neutral tempo against opponent-adjusted offensive EPA per play.

x is `tempo_s` from scripts/pace_stats.py (median neutral seconds per snap); y is
`stg.adjusted_team_season.epa_total` (CFBD opponent-adjusted offensive EPA per play).
One season per chart, because league tempo drifted from 30 to 36 s per snap across
2012-2026. Also prints the pooled 2024-2025 within-season-z correlation: 2015-2023
clean-clock games lean toward ABC/ESPN broadcasts, so earlier seasons are left out.

Needs PROCESSED/pace/pace_team_season.csv (run `python -m scripts.pace_stats` first).

    python -m scripts.pace_epa_chart               # 2025
    python -m scripts.pace_epa_chart --season 2024

Writes PROCESSED/pace/tempo_vs_off_epa_<season>.png.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DB_PATH, PROCESSED  # noqa: E402

POOLED = (2024, 2025)  # seasons with near-full clean-clock coverage
INK, MUTED, GRID, SERIES = "#0b0b0b", "#898781", "#e1e0d9", "#2a78d6"


def load(seasons: list[int]) -> pd.DataFrame:
    pace = pd.read_csv(PROCESSED / "pace" / "pace_team_season.csv")
    pace = pace[pace["season"].isin(seasons) & pace["tempo_s"].notna()]
    con = duckdb.connect(str(DB_PATH), read_only=True)
    epa = con.execute(
        "select season, team, epa_total as off_epa from stg.adjusted_team_season"
    ).df()
    df = pace.merge(epa, on=["season", "team"], how="left")
    missing = df.loc[df["off_epa"].isna(), ["season", "team"]]
    if len(missing):
        raise SystemExit(f"{len(missing)} rated teams have no adjusted EPA:\n{missing}")
    return df[["season", "team", "tempo_s", "n_neutral", "off_epa"]]


def pooled_r(df: pd.DataFrame) -> tuple[float, int]:
    """r of within-season z-scores, so league-wide tempo drift does not enter."""
    z = df.groupby("season")[["tempo_s", "off_epa"]].transform(lambda c: (c - c.mean()) / c.std())
    return z["tempo_s"].corr(z["off_epa"]), len(z)


def chart(d: pd.DataFrame, season: int, out: Path) -> None:
    r = d["tempo_s"].corr(d["off_epa"])
    # ponytail: tempo_s sits on a 0.5 s grid, so teams stack into columns; jitter is display-only.
    x = d["tempo_s"] + np.random.default_rng(0).uniform(-0.15, 0.15, len(d))

    fig, ax = plt.subplots(figsize=(10, 7), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, labelsize=9)

    ax.scatter(x, d["off_epa"], s=36, color=SERIES, alpha=0.75, edgecolor="#fcfcfb", linewidth=1)
    slope, icept = np.polyfit(d["tempo_s"], d["off_epa"], 1)
    xs = np.array([d["tempo_s"].min(), d["tempo_s"].max()])
    ax.plot(xs, icept + slope * xs, color=MUTED, linewidth=1.5, linestyle="--")

    # Label the tempo extremes and the EPA extremes, not every point.
    lab = pd.concat([d.nsmallest(5, "tempo_s"), d.nlargest(5, "tempo_s"),
                     d.nlargest(4, "off_epa"), d.nsmallest(4, "off_epa")]).drop_duplicates("team")
    for i, row in lab.iterrows():
        ax.annotate(row["team"], (x[i], row["off_epa"]), xytext=(5, 3),
                    textcoords="offset points", fontsize=8, color=INK)

    ax.invert_xaxis()  # faster tempo reads to the right
    ax.set_xlabel("Neutral tempo: median seconds per snap  (faster →)", color=INK, fontsize=10)
    ax.set_ylabel("Offensive EPA per play, opponent-adjusted  (adjusted_team_season.epa_total)",
                  color=INK, fontsize=10)
    ax.set_title(f"{season}: offensive tempo vs offensive EPA", color=INK, fontsize=13,
                 loc="left", fontweight="bold", pad=22)
    ax.text(0.0, 1.01, f"r = {r:.2f}   n = {len(d)} FBS teams   dashed: least-squares fit",
            transform=ax.transAxes, color=MUTED, fontsize=9, va="bottom")
    fig.tight_layout()
    fig.savefig(out, dpi=150)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    season = ap.parse_args().season

    df = load(sorted({season, *POOLED}))
    d = df[df["season"] == season].reset_index(drop=True)
    out = PROCESSED / "pace" / f"tempo_vs_off_epa_{season}.png"
    chart(d, season, out)

    print(f"{season}: r(tempo_s, off_epa) = {d['tempo_s'].corr(d['off_epa']):.3f}, n {len(d)}")
    r, n = pooled_r(df[df["season"].isin(POOLED)])
    print(f"pooled {POOLED[0]}-{POOLED[1]} within-season z: r = {r:.3f}, n {n}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
