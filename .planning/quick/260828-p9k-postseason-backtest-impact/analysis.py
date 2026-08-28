"""Build step for 260828-p9k. Implements ANALYSIS-PLAN.md exactly."""
import sys, json, math
from dataclasses import replace
sys.path.insert(0, r"C:\Users\mckel\dev\cfb-site")
sys.path.insert(0, r"C:\Users\mckel\.claude\skills\econometrics")
from cfb_system_maker.storage import load_processed_games, list_examples, load_example_system
from cfb_system_maker.backtest import run_backtest
from toolkit.multiplicity import benjamini_hochberg

BREAK_EVEN = 0.5238
games = load_processed_games("data")
fm = {int(k): v for k, v in json.loads(
    open("data/processed/features.json", encoding="utf-8").read())["games"].items()}

def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (c-h, c+h)

def one_sided_p(k, n, p0=BREAK_EVEN):
    """Upper-tail: is the hit rate above break-even? Normal approx, n>=100 here."""
    if n == 0: return None
    se = math.sqrt(p0*(1-p0)/n)
    z = (k/n - p0) / se
    return 0.5 * math.erfc(z / math.sqrt(2))

rows, pvals = [], []
for name in list_examples():
    base = load_example_system(name).system
    res = {}
    for label, s in (("all", base),
                     ("regular", replace(base, season_types={"regular"})),
                     ("postseason", replace(base, season_types={"postseason"}))):
        r = run_backtest(games, s, feature_map=fm)
        decided = r.wins + r.losses
        hr = r.wins / decided if decided else float("nan")
        lo, hi = wilson(r.wins, decided)
        res[label] = dict(n=r.bets, decided=decided, wins=r.wins, hr=hr, lo=lo, hi=hi,
                          roi=r.roi, clusters=r.stats.cluster_count if r.stats else 0)
    shift = res["all"]["hr"] - res["regular"]["hr"]
    p_post = one_sided_p(res["postseason"]["wins"], res["postseason"]["decided"])
    rows.append((name, res, shift, p_post))
    pvals.append(p_post)

print(f"{'system':<28}{'sample':<11}{'n':>6}{'hit%':>8}{'95% Wilson':>18}{'ROI%':>8}")
print("-"*80)
for name, res, shift, p_post in rows:
    for label in ("all", "regular", "postseason"):
        d = res[label]
        ci = f"[{d['lo']*100:5.1f},{d['hi']*100:5.1f}]" if d["lo"] is not None else "     n/a     "
        print(f"{name if label=='all' else '':<28}{label:<11}{d['decided']:>6}{d['hr']*100:>8.2f}{ci:>18}{d['roi']*100:>8.2f}")
    print(f"{'':<28}{'-> shift (all - regular)':<11} {shift*100:+.3f} pp")
    print()

print("="*80)
print("Estimand (B): postseason vs break-even 52.38%, one-sided upper tail")
print(f"{'system':<28}{'n':>6}{'hit%':>8}{'raw p':>9}{'BH q':>9}  verdict")
print("-"*80)
qs = benjamini_hochberg(pvals, alpha=0.05)
qvals = qs["p_adjusted"]
for (name, res, shift, p_post), q in zip(rows, qvals):
    d = res["postseason"]
    q = float(q)
    print(f"{name:<28}{d['decided']:>6}{d['hr']*100:>8.2f}{p_post:>9.3f}{q:>9.3f}  "
          f"{'reject H0' if q < 0.05 else 'no evidence (underpowered)'}")
