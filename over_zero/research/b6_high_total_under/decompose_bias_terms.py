import sys, numpy as np
from pathlib import Path
REPO = Path("C:/Users/mckel/dev/over-zero")
sys.path.insert(0, str(REPO/"v1"))
sys.path.insert(0, str(REPO/"research/b6_high_total_under"))
from censoring_bias import fit_pipeline, implied_team_points, _team_censor_bias, censoring_bias
from test_high_total_under import load_with_season

sp, to, fav, dog, season = load_with_season()
tt = fav+dog; keep = (tt-to)!=0
sp,to,fav,dog,season = (a[keep] for a in (sp,to,fav,dog,season))
over = ((fav+dog-to)>0).astype(float)
fit = fit_pipeline(sp,to,fav,dog)
dog_est, fav_est = implied_team_points(sp,to)
sd, sf = fit.tobit_dog.sigma, fit.tobit_fav.sigma
bdog = _team_censor_bias(dog_est, sd); bfav = _team_censor_bias(fav_est, sf)
_, btot = censoring_bias(dog_est, fav_est, sd, sf)
print(f"N={sp.size}  sigma_dog={sd:.2f} sigma_fav={sf:.2f}")
print(f"bias_dog: mean={bdog.mean():.4f} max={bdog.max():.3f}")
print(f"bias_fav: mean={bfav.mean():.4f} max={bfav.max():.3f}")
print(f"share of biasTotals from dog term: {bdog.sum()/btot.sum()*100:.2f}%")
print(f"corr(biasTotals, dog_est)  = {np.corrcoef(btot,dog_est)[0,1]:+.4f}")
print(f"corr(biasTotals, bias_dog) = {np.corrcoef(btot,bdog)[0,1]:+.4f}")
print(f"corr(biasTotals, spread)   = {np.corrcoef(btot,sp)[0,1]:+.4f}")
print(f"corr(biasTotals, total)    = {np.corrcoef(btot,to)[0,1]:+.4f}")
print(f"\ndog_est quantiles: {np.percentile(dog_est,[1,25,50,75,99]).round(2)}")
print(f"fav_est quantiles: {np.percentile(fav_est,[1,25,50,75,99]).round(2)}")
print(f"fav_est/sigma_fav min = {(fav_est/sf).min():.2f} (sigmas from 0)")

# Is dog_est alone as good a bet-selector as biasTotals?
print("\n[bet the over] biasTotals>1.75 vs dog_est-threshold matched on N")
sel = btot>1.75; n=int(sel.sum())
print(f"  biasTotals>1.75 : N={n} over%={over[sel].mean()*100:.2f}%")
cut = np.sort(dog_est)[n-1]
sel2 = dog_est<=cut
print(f"  dog_est<={cut:.2f}   : N={int(sel2.sum())} over%={over[sel2].mean()*100:.2f}%")
print(f"  overlap: {int((sel&sel2).sum())}/{n} = {(sel&sel2).sum()/n*100:.1f}%")
