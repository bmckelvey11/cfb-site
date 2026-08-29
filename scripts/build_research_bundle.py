"""Assemble every Prediction Tracker result into one self-describing JSON.

Written to be handed to an outside reviewer with no access to this repo. That constraint
drives two choices: every method code carries a plain-English label (an earlier reviewer
answered about "CSR" without knowing it was E14), and every headline number is the
post-fix value, since five specification defects were found mid-analysis.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from akm_winner_bound import bound  # noqa: E402

SRC = Path(r"C:/Users/mckel/data/cfb/processed")
OUT = Path(__file__).resolve().parents[1] / "docs" / "prediction-tracker-research-bundle.json"

METHODS = {
    "mkt": "The raw market line (opening or closing), used as published.",
    "R0": "Recalibrated line. OLS of margin on [1, line], refit each season on prior "
          "seasons. THE BENCHMARK: every method below is anchored on it by Frisch-Waugh, "
          "so all of them nest it and a zero correction lands on R0 exactly.",
    "E4": "Screened equal-weighted consensus. Take the K=20 models with the best "
          "prior-season market-relative skill, average their deviations from the line, "
          "fit one scalar gamma. K was fixed at 20 BEFORE any fitting.",
    "E6": "Market-residual ridge. Ridge of (y - mkt) on all active models' deviations.",
    "E7": "E4 with K chosen out-of-sample by the 1-SE rule instead of fixed at 20.",
    "E8": "Stock-Watson generalized shrinkage. Fit the unrestricted correction, shrink it "
          "toward zero by a scalar psi.",
    "E9": "Market-residual principal components. Regress (y - mkt) on the first r scores.",
    "E10": "Market-anchored peLASSO. LASSO-select a subset, equal-weight survivors, one gamma.",
    "E11": "Trimmed residual consensus. Drop top and bottom tau per game, average the rest.",
    "E12": "Combination elastic net. E6 with an l1+l2 penalty.",
    "E13": "Online residual aggregation. Hedge-style exponential weights updated per game.",
    "E14": "Complete subset regression after screening. Screen to the 10 best by prior-season "
           "residual skill, average all C(10,k) k-variable residual regressions. "
           "k=1 was selected in every season.",
}

GRIDS = {
    "E6": "lambda in {0.1,1,10,100,1000,10000}; conservative = larger",
    "E7": "K in {5,10,20,40,80,all}; conservative = larger",
    "E8": "psi in {0,0.1,...,1.0}; conservative = smaller",
    "E9": "r in {1,2,3}; conservative = smaller",
    "E10": "lambda in {0.001,0.01,0.1,1.0}; conservative = larger",
    "E11": "tau in {0,0.1,0.2,0.3,0.4}; conservative = larger",
    "E12": "lambda in {0.1,1,10,100,1000} x l1ratio {0.1,0.5,0.9}",
    "E13": "eta in {0.001,0.01,0.1}; conservative = smaller",
    "E14": "k in {3,2,1}; conservative = smaller",
}

DEFECTS = [
    ["Clark-West sign", "spreads passed to a function taking margins",
     "An absurd +23 adjusted mean where the correct value is +0.45."],
    ["Methods did not nest the benchmark",
     "fitting y-mkt ~ deviations pins the market coefficient at 1",
     "Every comparison against R0, Clark-West included, formally invalid. Rebuilt on "
     "Frisch-Waugh anchoring with a test asserting 1e-8 equivalence."],
    ["Support collapse", "one method that cannot fit before ~2011 silently deleted those "
     "seasons for every other method", "n fell 14347 -> 9234 with no indication why."],
    ["Coverage filter was a tenure test",
     "coverage measured over the whole training history, so a model launched in 2015 could "
     "never qualify however complete its record",
     "Regression methods fit on ~14 old models rather than the season's ~39 active ones, "
     "EXCLUDING THE TWO BEST FORECASTERS. Changed every headline in the regression family."],
    ["Giacomini-Rossi statistic uncentred", "while its bootstrap imposed the null by centring",
     "Tested 'is the difference nonzero', not 'does it change over time'."],
    ["Misleading RMSE column", "a reduced-support method printed beside the shared market RMSE",
     "Reproduced the coverage-difficulty confound inside a doc explaining that confound."],
    ["Stability gate half-inert", "sign_stability is bounded below at 0.50 and returns 1.00 "
     "for a consistently tiny coefficient", "The gate was one criterion, not two. Recorded, "
     "not retrofitted."],
]

SCORECARD = [
    ["sweep", "K-by-rule will score worse than K=20, exposing the latter as selection-inflated",
     "CORRECT, WRONG REASON", "the rule chose 'all' in 20/20 seasons -- K is not identifiable "
     "out-of-sample at all"],
    ["sweep", "Market-residual ridge beats E5, still not R0", "WRONG ON BOTH",
     "it beats R0 on opening, and is significantly WORSE than both on closing"],
    ["sweep", "Online aggregation and CSR will not help", "HALF WRONG",
     "CSR was the only exploratory method to survive Holm, on full support, p<0.0001, "
     "beating the reference in all 20 seasons"],
    ["sweep", "No method passes the stability gate", "WRONG",
     "seven did, and the gate was weaker than designed (defect 7)"],
    ["recency", "rho=1.00 selected in a majority of seasons", "CONFIRMED", "unanimously, 20/20"],
    ["recency", "No recency scheme changes the closing-line null", "CONFIRMED", ""],
    ["recency", "Giacomini-Rossi rejects on opening, not closing", "WRONG",
     "rejects on neither; the open/close gap is a difference in level, not drift over time"],
    ["recency", "Cohort trend small, will not reorder the screen", "WRONG ON BOTH CLAUSES",
     "the correction destroys signal because the best forecasters are recent entrants"],
]

DECONTAM = {
    "what": "Two panel columns (lineca, linemidweek) proved to BE market lines, not models. "
            "This check drops the 15 most market-like columns and refits.",
    "note": "Retention is the fraction of the original effect that survives.",
    "rows": [
        {"method": "E4", "family": "consensus", "all_154": -1.976, "p_all": 0.0030,
         "decontaminated": -1.446, "p_dec": 0.0415, "retained": 0.73},
        {"method": "E11", "family": "consensus", "all_154": -1.150, "p_all": 0.0665,
         "decontaminated": -0.867, "p_dec": 0.1420, "retained": 0.75},
        {"method": "E14", "family": "subset regression", "all_154": -2.615, "p_all": 0.0001,
         "decontaminated": -1.285, "p_dec": 0.0001, "retained": 0.49},
        {"method": "E6", "family": "shrinkage", "all_154": -3.521, "p_all": 0.0001,
         "decontaminated": -0.966, "p_dec": 0.2560, "retained": 0.27},
    ],
    "closing_line_lead": "On the CLOSING line E14 strengthens under decontamination: "
                         "-0.159 (p=0.0695) becomes -0.193 [-0.344,-0.045] p=0.0125. This is a "
                         "post-hoc variant of the winner of an eight-member family with no "
                         "confirmation window. Holm across that family puts it near 0.10. "
                         "A candidate for pre-registration, NOT a closing-line edge.",
}

LIMITS = [
    "No confirmation window exists. The 2021-25 minimum detectable effect is 0.161 RMSE "
    "against a full-window 0.078, so a holdout cannot confirm an effect this size.",
    "Prediction Tracker publishes mid-week with no publication timestamp, so it is unknown "
    "what price was available when a forecast appeared. The opening-line edge is an "
    "UNREACHABLE UPPER BOUND, not a strategy.",
    "25 season clusters is below the ~40 where analytic cluster SEs can be trusted; wild "
    "cluster bootstrap-t with Rademacher weights and the null imposed by centring is the "
    "primary inference. B=2000, so the p-value floor is 1/2000 = 0.0005.",
    "Missingness is almost certainly not at random: models enter and exit, and coverage "
    "correlates with game difficulty.",
    "sign_stability is inert (defect 7), so the viability gate is one criterion, not two.",
    "The pairwise correlation structure across the 8 candidate methods was never measured; "
    "the AKM bound below is constructed so that it does not need to be.",
]

QUESTIONS = [
    "Selection-adjusted inference with no confirmation window (see akm_bound -- believed "
    "closed by bound, would like this confirmed or refuted).",
    "Why did complete subset regression survive when every shrinkage estimator did not? "
    "Is CSR at k=1 effectively an equal-weighted average of many one-regressor corrections?",
    "Is the 1-SE rule the wrong selection rule for a SMALL correction to a STRONG benchmark? "
    "It always picks the more conservative end, which here means 'do nothing'.",
    "Benchmark contamination inside forecast panels -- is there a named detection method?",
    "4b. Why does an equal-weighted consensus resist contamination that a ridge amplifies "
    "(73% vs 27% retention)? Is there a diagnostic that finds this WITHOUT already having a "
    "contamination measure?",
    "When does cohort/vintage adjustment destroy signal rather than confounding?",
    "5b. Eligibility rules in unbalanced forecaster panels -- my filter silently became a "
    "tenure test, and eligibility correlated with entry year almost perfectly, which is the "
    "same confound the cohort correction was meant to address.",
    "Detecting slow decay in relative performance with ~20 time-series observations.",
    "Is squared error the right loss for a betting decision (which is a sign/threshold call)?",
    "Which market number is the right benchmark?",
    "Does closing line value actually predict realised profitability?",
    "Persistent skill without exploitable edge -- the mutual-fund analogy.",
    "Inference at 20-25 clusters.",
]


def load(name):
    return json.loads((SRC / name).read_text())


# Not models. Both proved to BE market lines published under a model name, which is why the
# single-model claims in the parent analysis were retracted. They top the leaderboard on raw
# skill, so leaving them unflagged invites exactly the misreading that was already made once.
MARKET_LINES = {"lineca", "linemidweek"}


def leaderboard(bench, top=25):
    df = pd.read_csv(SRC / f"pt_leaderboard_{bench}.csv")
    df = df[df.inference != "too few seasons"].nsmallest(top, "delta_mse")
    keep = ["model", "n", "seasons", "rmse", "delta_mse", "p", "q_bh"]
    rows = df[keep].round(4).to_dict("records")
    for r in rows:
        if r["model"] in MARKET_LINES:
            r["NOT_A_MODEL"] = ("This column is a market line, not a forecasting model. "
                                "Its skill is not model skill. Do not cite it.")
    return rows


def main():
    sweep, recency, parent = (load("pt_combination_sweep.json"),
                              load("pt_recency_screen.json"), load("pt_model_eval.json"))

    se, z, e, akm = bound(-2.614521, -3.595841, -1.583381, 8)

    doc = {
        "_readme": {
            "what": "Complete results from an evaluation of 154 public college-football "
                    "computer models against the betting market, 2001-2025.",
            "why": "Handed to an outside reviewer for methodological critique. Everything "
                   "needed to judge the analysis is in this file; no repo access required.",
            "read_this_first": [
                "Loss is MSE in points-squared. NEGATIVE d_vs_r0 = BETTER than the benchmark.",
                "Every number here is POST-FIX. Five specification defects were found during "
                "the analysis (see defects_found); all headline numbers were recomputed.",
                "Two benchmarks are reported separately and the answer differs completely "
                "between them. This IS the main finding.",
                "The bootstrap p-value floor is 1/2000 = 0.0005. A reported p of 0.000 means "
                "'below the floor', not zero. Do not quote corrected p-values to six decimals.",
                "Method codes are E4-E14; see method_catalog for what each one is.",
            ],
            "headline": "The panel decisively beats the OPENING line and cannot beat the "
                        "CLOSING line by any of ten combination rules. Best closing-line "
                        "Holm-adjusted p is 0.4865.",
        },
        "panel": {
            "n_games": 17731, "n_models": 154, "seasons": "2001-2025",
            "sweep_evaluation_support": sweep["opening"]["n_common"],
            "burn_in": "seasons through 2005 train only; 20 evaluated seasons",
            "target": "y = home margin", "units": "points",
            "unbalanced": "Models enter and exit. At 2025, 39 of 154 were active.",
        },
        "protocol": {
            "validation": "Nested walk-forward. Train on all prior seasons, predict the next. "
                          "Hyperparameters chosen on an inner split (last 3 training seasons) "
                          "by the 1-SE rule, so selection never sees the evaluated season.",
            "anchoring": "Every method is anchored on R0 by Frisch-Waugh, so all nest the "
                         "benchmark and a zero correction returns R0 exactly. Verified by test "
                         "to 1e-8.",
            "inference": "Wild cluster bootstrap-t, Rademacher weights, null imposed by "
                         "centring, clustered by season. B=2000, 25 clusters.",
            "multiplicity": "Holm within the 8-member exploratory family E7-E14, per "
                            "benchmark. E4 and E6 are outside the family (E4 pre-registered, "
                            "E6 a repair).",
            "preregistration": "E6-E14 with named grids and the conservative direction of each "
                               "were committed BEFORE any fitting.",
        },
        "method_catalog": METHODS,
        "hyperparameter_grids": GRIDS,
        "results": {
            b: {
                "benchmark": "opening line" if b == "opening" else "closing line",
                "n_common": sweep[b]["n_common"],
                "mkt_rmse": sweep[b]["mkt_rmse"], "r0_rmse": sweep[b]["r0_rmse"],
                "table": sweep[b]["table"],
                "harvey_newbold_encompassing": {
                    **sweep[b]["harvey_newbold"],
                    "_what": "Joint encompassing: does the line encompass the panel as a SET? "
                             "Five PRE-SPECIFIED directions, not a 154-dim Wald that would "
                             "have no power. Null imposed by centring, season-clustered wild "
                             "bootstrap calibrates it. IN-SAMPLE by construction (the PCA and "
                             "the screen both use the whole panel) -- that is the standard "
                             "framing for an encompassing test, which asks about the "
                             "population, not about out-of-sample deployability.",
                    "_slope_order": ["top20 consensus", "top5 consensus", "PC1", "PC2", "PC3"],
                    "_reading": ("line does NOT encompass the panel"
                                 if sweep[b]["harvey_newbold"]["p"] < 0.05
                                 else "line encompasses the panel"),
                },
                "e6_vs_e5_repair": {
                    **sweep[b]["e6_vs_e5"],
                    "_what": "E6 (ridge) vs E5 (the parent unrestricted combination) on their "
                             "own paired support. E6 was pre-registered as a REPAIR of E5, "
                             "not an exploratory method, so it carries no Holm correction.",
                },
                "parent_run": parent[b],
                "leaderboard_top25": leaderboard(b),
                "_leaderboard_caveat": "Single-model skill, NOT the combination results. "
                                       "Ranked by delta_mse vs the raw line (negative = "
                                       "better). Rows flagged NOT_A_MODEL are market lines "
                                       "and must not be read as forecasting skill. "
                                       "NOTE: once those two are removed, EVERY remaining "
                                       "model is worse than the raw line -- the best "
                                       "(lineespn) by +4.88 MSE. 'The two best forecasters' "
                                       "elsewhere in this file means best AMONG MODELS, not "
                                       "better than the market. The panel only beats the "
                                       "line in combination, never individually.",
            } for b in ("opening", "closing")
        },
        "column_glossary": {
            "d_vs_r0": "mean paired MSE difference vs the recalibrated benchmark; NEGATIVE "
                       "is better",
            "p": "wild cluster bootstrap-t two-sided p, unadjusted",
            "p_holm": "Holm-adjusted within the 8-member exploratory family; null = outside it",
            "frac_seasons": "fraction of the 20 evaluated seasons the method beat R0",
            "mean_abs_corr": "mean |prediction - R0|; how far the method actually moves off "
                             "its own reference. Near zero = the selected hyperparameter "
                             "switched the correction OFF, so the method IS R0.",
            "sign_stab": "KNOWN INERT, see defect 7. Bounded below at 0.50.",
            "rmse_mkt_same_games": "the market RMSE on THIS method games, so a "
                                   "reduced-support method is not compared against a "
                                   "different game set",
            "viable": "yes / NO / none, from the stability gate; 'none' = degenerate",
        },
        "recency_and_cohort": {
            "question": "Does exponentially discounting old market-relative losses, or "
                        "adjusting for entry cohort, improve the screen? Validation was to "
                        "determine the decay rate rather than declaring a structural break.",
            "answer": "No. rho=1.00 (no decay) won 20/20 seasons on both benchmarks. "
                      "Giacomini-Rossi finds no instability. The cohort correction DESTROYS "
                      "signal because the best forecasters are recent entrants.",
            **{b: recency[b] for b in ("opening", "closing")},
        },
        "market_contamination": DECONTAM,
        "akm_bound": {
            "problem": "E14 was the SELECTED method among 8, so its effect is conditional on "
                       "having won a noisy tournament.",
            "approach": "Andrews-Kitagawa-McCloskey is the right framework, but implementing "
                        "it literally needs an 8x8 cluster-robust covariance not persisted by "
                        "the sweep. Bounded instead: the correction is "
                        "E[max_m Z] * se * sqrt(1-rho), and BOTH unknowns (rho, effective m) "
                        "only ever shrink it. The rho=0 corner is a valid worst case.",
            "inputs": {"d_vs_r0": -2.614521, "ci": [-3.595841, -1.583381],
                       "se_conservative": round(se, 4), "naive_z": round(z, 3),
                       "m": 8, "E_max_m_Z": round(e, 4),
                       "se_note": "half-width / 1.96. Real bootstrap-t quantiles at 20 "
                                  "clusters are fatter, implying a SMALLER se and LARGER z, "
                                  "so this is the reading least favourable to the finding."},
            "bound": [{k: round(v, 6) for k, v in r.items()} for r in akm],
            "conclusion": "Worst case over the entire rho range leaves p = 2.4e-4, still "
                          "under the bootstrap 1/2000 floor, and the effect no weaker than "
                          "-1.88. Two of the eight candidates were degenerate on opening "
                          "(E8 |corr|=0.03, E12=0.17) and could not have won, so effective m "
                          "is 6 and the bound tightens to 1.3e-4.",
            "cautions": [
                "The correction REPLACES Holm rather than stacking with it.",
                "Both raw and corrected p sit below the bootstrap floor, so the honest "
                "statement is 'below 1/2000 before and after winner correction'.",
                "AKM real bite is on the POINT ESTIMATE, not the p-value.",
            ],
        },
        "defects_found": [{"defect": a, "detail": b, "consequence": c} for a, b, c in DEFECTS],
        "preregistration_scorecard": {
            "summary": "Eight expectations were committed before fitting. FOUR WERE WRONG.",
            "rows": [{"round": a, "expectation": b, "outcome": c, "detail": d}
                     for a, b, c, d in SCORECARD],
        },
        "known_limitations": LIMITS,
        "open_questions": QUESTIONS,
    }

    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT}  ({kb:.0f} KB)")
    assert kb < 200, "too large to paste"
    # the two numbers most likely to be misquoted
    op = {r["method"]: r for r in doc["results"]["opening"]["table"]}
    cl = {r["method"]: r for r in doc["results"]["closing"]["table"]}
    assert round(op["E14"]["d_vs_r0"], 3) == -2.615, "stale CSR effect"
    assert round(min(r["p_holm"] for r in cl.values()
                     if r["p_holm"] is not None and r["p_holm"] == r["p_holm"]), 4) == 0.4865, \
        "stale closing Holm"
    print("spot checks pass")


if __name__ == "__main__":
    main()
