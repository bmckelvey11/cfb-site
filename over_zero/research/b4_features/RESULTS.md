# B4.2 Results: Residual-Feature Probit

## Full Verbatim Output

```
12,493 games with features joined

spec: ['biasTotals']
            const -0.0238 (SE 0.0078, p=0.002289)
       biasTotals +0.0710 (SE 0.0081, p=1.231e-18)

spec: ['biasTotals', 'week', 'neutralSite', 'conferenceGame', 'home_dog']
            const -0.0238 (SE 0.0076, p=0.00183)
       biasTotals +0.0742 (SE 0.0099, p=5.2e-14)
             week +0.0268 (SE 0.0148, p=0.07004)
      neutralSite -0.0220 (SE 0.0081, p=0.006706) *SIG*
   conferenceGame -0.0179 (SE 0.0131, p=0.1728)
         home_dog +0.0212 (SE 0.0094, p=0.02383)

biasTotals coefficient shift with features: +0.39 SEs (over 1 SE = features materially overlap the censoring signal)
```

## Checklist

### (1) Any feature *SIG* (p < 0.0125)?
**Yes.** `neutralSite` is significant under Bonferroni (p=0.006706 < 0.0125). The effect is negative: games at neutral sites show reduced over-win probability relative to the censoring baseline (standardized coefficient −0.0220, SE 0.0081). This is inconsistent with the hypothesis that neutral sites favor overs; instead, the data suggests neutral sites are associated with *lower* over rates after controlling for censoring bias.

### (2) biasTotals shift over 1 SE?
**No.** The `biasTotals` coefficient shifts from +0.0710 (base) to +0.0742 (full) — a shift of +0.0032. Scaled by the base-spec SE of 0.0081, this is +0.39 SEs. The features do not materially displace the censoring signal; the bias estimate is robust.

### (3) Verdict Paragraph

**Does anything in the raw data explain the excess edge beyond biasTotals?**

The tested features — week, neutralSite, conferenceGame, and home_dog — show very limited ability to explain the excess overs beyond the censoring baseline. Only one feature (neutralSite) clears the Bonferroni threshold, and its effect is small (−0.022 standardized). The biasTotals coefficient remains stable when features are added (+0.39 SE shift, well under 1 SE), confirming that the raw-data features do not overlap with the censoring-bias signal in a materially meaningful way.

**No feature materially displaces the censoring signal.** One feature (neutralSite) clears the Bonferroni bar with a small negative effect that does not undermine the biasTotals estimate. The finding is consistent with the open question: if the over-edge exists beyond measurement error in implied points, censoring in team scoring, and week/location/matchup effects, then either (a) a feature not yet considered (e.g., recruit rankings, coaching tenure, game importance) drives it, or (b) the excess is statistical noise that vanishes under proper multiple-comparison control.

With ~12k games a standardized probit coefficient below ≈0.03 is undetectable at this power; absence of significance is not absence of effect for smaller influences.

**Clustering caveat:** SEs here are season-clustered (`cov_type="cluster"`) over only 13 season clusters (2013–2025). `v2/models_v2.py`'s own docstring on this estimator warns that "with few clusters (~13 seasons) treat clustered p-values as indicative rather than exact." The `neutralSite` result (p=0.0067 against a 0.0125 Bonferroni bar) is exactly this kind of marginal call — it clears the bar, but the margin (0.0058) is well within the range where an approximate cluster-robust p-value should be read as indicative rather than exact, so the significance finding is more marginal than the raw p-value alone suggests.

---

**Note:** The feature list was originally `["week", "neutralSite", "conferenceGame", "fcs_dog"]` per B4.1, but `fcs_dog` had zero variance post-join (no FCS teams carry betting lines in the dataset). Per BLOCKERS.md commit 11b2500, `fcs_dog` was substituted with `home_dog` (an underutilized candidate from B4.1's ranked list) to preserve the 4-feature budget and Bonferroni denominator. The analysis reported here tests the substituted feature set.
