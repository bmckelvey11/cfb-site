"""Does the eligibility filter function as a tenure test?

Defect 4 cost two full rounds of analysis: the coverage filter measured completeness over
the whole training window, so a model that launched mid-panel could never qualify however
complete its record. It excluded the two best models in the panel from every regression
method.

This is the check that would have caught it from PANEL METADATA ALONE -- no fitting, no
skill estimate, no knowledge of which models are good. Compare the entry-year distribution
of the eligible set against the entry-year distribution of the ACTIVE set, per season. If
eligibility skews older, the filter is truncating on age whatever its stated purpose.

Run as a guard whenever the eligibility rule changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402
import eval_combination_sweep as sweep  # noqa: E402


def entry_years(df, models):
    """First season each model published anything."""
    return {m: int(df.loc[df[m].notna(), "season"].min())
            for m in models if df[m].notna().any()}


def audit(df, models, entry, legacy):
    rows = []
    for s in sorted(df.season.unique()):
        if s <= base.BURN_IN_THROUGH:
            continue
        tr, te = df[df.season < s], df[df.season == s]
        cols, active = sweep.regressor_cols(tr, te, models, legacy=legacy)
        if not active:
            continue
        ae = [entry[m] for m in active if m in entry]
        ce = [entry[m] for m in cols if m in entry]
        rows.append({
            "season": int(s), "n_active": len(active), "n_eligible": len(cols),
            "kept": len(cols) / len(active),
            "median_entry_active": float(np.median(ae)) if ae else np.nan,
            "median_entry_eligible": float(np.median(ce)) if ce else np.nan,
            # THE diagnostic. Positive = the filter is keeping older models than the
            # active panel contains, i.e. it is testing tenure, not completeness.
            "age_skew": (float(np.median(ae)) - float(np.median(ce))) if ce else np.nan,
        })
    return pd.DataFrame(rows)


def main():
    df, models = base.load()
    entry = entry_years(df, models)
    print(f"{len(entry)} models with an entry year, "
          f"{min(entry.values())}-{max(entry.values())}\n")

    for legacy, name in ((True, "LEGACY (the defect)"), (False, "FIXED")):
        t = audit(df, models, entry, legacy)
        last = t.iloc[-1]
        print(f"-- {name} --")
        print(t.tail(4).to_string(index=False))
        print(f"   mean age skew {t.age_skew.mean():+.1f} seasons, "
              f"mean kept {t.kept.mean():.0%}")
        print(f"   at {int(last.season)}: kept {int(last.n_eligible)}/"
              f"{int(last.n_active)}, median entry {last.median_entry_eligible:.0f} "
              f"vs active {last.median_entry_active:.0f}\n")


def _check():
    """A filter that truncates on age must show positive skew; one that does not, none."""
    rng = np.random.default_rng(4)
    rows = []
    for s in range(2000, 2012):
        for i in range(120):
            line = rng.normal(0, 10)
            r = {"season": s, "pt_week": i % 12, "y": -line + rng.normal(0, 14),
                 "line": line, "lineopen": line}
            r["old"] = line + rng.normal(0, 5)
            r["new"] = line + rng.normal(0, 5) if s >= 2009 else np.nan
            rows.append(r)
    df = pd.DataFrame(rows)
    entry = {"old": 2000, "new": 2009}
    base.BURN_IN_THROUGH = 2009
    legacy = audit(df, ["old", "new"], entry, legacy=True)
    fixed = audit(df, ["old", "new"], entry, legacy=False)
    assert (legacy.age_skew > 0).all(), "the tenure test must skew older"
    assert (fixed.age_skew == 0).all(), "the fixed rule must not skew on age"
    print("checks pass\n")


if __name__ == "__main__":
    _check()
    main()
