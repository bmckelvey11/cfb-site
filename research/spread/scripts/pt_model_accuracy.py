"""Rank Prediction Tracker models by accuracy against game results, paired with the market.

For each PT model column, over the chosen seasons, computes MAE of the model's home margin
against the actual home margin, and the same games' MAE for PT's last recorded line (the
close proxy). `vs_line` = model MAE - line MAE on identical games; negative means the model
was closer to the result than the market. Archive convention: negative line = home favoured.

    python research/spread/scripts/pt_model_accuracy.py --archive data/ingest/prediction_tracker_lines.csv \
        --seasons 2022-2025 --min-games 500 --out pt_model_accuracy.csv
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

NOT_MODELS = {"line", "lineopen", "lineavg", "linemedian", "linestd", "lineca", "linemidweek"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--seasons", default="2022-2025")
    ap.add_argument("--min-games", type=int, default=500)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    lo, hi = map(int, a.seasons.split("-"))
    df = pd.read_csv(a.archive, low_memory=False)
    df = df[df.season.between(lo, hi) & df.hscore.notna() & df.vscore.notna() & df.line.notna()]
    actual = df.hscore - df.vscore
    rows = []
    for col in [c for c in df.columns if c.startswith("line") and c not in NOT_MODELS]:
        m = df[col].notna()
        if m.sum() < a.min_games:
            continue
        err_model = (-df.loc[m, col] - actual[m]).abs()
        err_line = (-df.loc[m, "line"] - actual[m]).abs()
        d = err_model - err_line
        rows.append({"model": col, "n": int(m.sum()), "mae": err_model.mean(), "line_mae": err_line.mean(),
                     "vs_line": d.mean(), "vs_line_se": d.std(ddof=1) / np.sqrt(m.sum())})
    out = pd.DataFrame(rows).sort_values("vs_line").reset_index(drop=True)
    out.to_csv(a.out, index=False)
    print(f"{len(df)} games {lo}-{hi}; {len(out)} models with >= {a.min_games}")
    print(out.round(3).head(20).to_string())


if __name__ == "__main__":
    main()
