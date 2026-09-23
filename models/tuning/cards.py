"""Markdown model card for one completed run (Release C, C1).

`render_card` is pure: no clock, no I/O, so the same inputs give the same bytes. It
follows the plan §20 sections this release can fill and never states a betting claim:
the market baseline is an untimed, unpriced vendor open and is labeled descriptive.
"""
from __future__ import annotations

from models.tuning.spec import FoldResult, RunSpec

BANNED_TERMS = ("ROI", "CLV", "hit rate", "edge")


def _f(x: float, sign: bool = False) -> str:
    return f"{x:+.3f}" if sign else f"{x:.3f}"


def _params(params: dict) -> str:
    return ", ".join(f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}"
                     for k, v in sorted(params.items()))


def render_card(run_spec: RunSpec, manifest: dict, study_summary: dict,
                outer_results: list[FoldResult], comparisons: dict) -> str:
    rs, st, cmp_ = run_spec, study_summary, comparisons
    fs, ds, acc = rs.feature_set, rs.dataset, rs.acceptance
    lines: list[str] = []
    add = lines.append

    add(f"# Model card: {rs.spec_id} (`{manifest['run_id']}`)")
    add("")
    add("**Status:** research. Forecast accuracy only; this run makes no wagers and states no "
        "betting claim.")
    add(f"**Config hash:** `{manifest['config_hash']}`  ")
    add(f"**Code:** `{manifest['git_sha']}` (dirty worktree: {'yes' if manifest['git_dirty'] else 'no'}); "
        f"code fingerprint `{manifest['code_sha256'][:16]}`; Python {manifest['python']}; "
        + ", ".join(f"{k} {v}" for k, v in sorted(manifest["packages"].items())))
    if rs.notes:
        add("")
        add(f"**Notes:** {rs.notes}")

    add("")
    add("## Purpose, target, and decision time")
    add("")
    add(f"Forecast the full-game `{ds.target}` for `{ds.population}` games. Every forecast is made "
        f"at the `{ds.decision_time}`: the earliest kickoff of the game's week. Source "
        f"`{ds.source}`, snapshot `{ds.snapshot}`, seasons {ds.seasons[0]}–{ds.seasons[-1]}.")

    add("")
    add("## Data sources")
    add("")
    add("| file | sha256 |")
    add("| --- | --- |")
    for s in manifest["sources"]:
        add(f"| `{s['path']}` | `{s['sha256'][:16]}` |")
    if not manifest["sources"]:
        add("| (synthetic, generated from the dataset seed) | |")

    add("")
    add(f"## Features: `{fs.feature_set_id}` v{fs.version}")
    add("")
    add("| feature | version | availability class | status |")
    add("| --- | --- | --- | --- |")
    dropped = manifest["features"]["dropped"]
    for f in fs.features:
        status = f"dropped: {dropped[f.id]}" if f.id in dropped else "used"
        add(f"| `{f.id}` | {f.version} | {f.availability_class} | {status} |")

    add("")
    add("## Validation design")
    add("")
    add(f"Season holdout, grouped by `{rs.folds.group_key}`, embargo {rs.folds.embargo_days} days, "
        f"excluded seasons: {', '.join(map(str, rs.folds.exclude_seasons)) or 'none'}. Inner folds "
        "tune; outer folds evaluate the selected model once each.")
    add("")
    add("| fold | role | train seasons | train rows | test rows | test kickoffs |")
    add("| --- | --- | --- | ---: | ---: | --- |")
    for fold in manifest["folds"]:
        b = fold["bounds"]
        seasons = b["train_seasons"]
        add(f"| {fold['fold_id']} | {fold['role']} | {seasons[0]}–{seasons[-1]} | {b['train_rows']} | "
            f"{b['test_rows']} | {b['test_first_kickoff']} to {b['test_last_kickoff']} |")

    add("")
    add("## Optuna provenance")
    add("")
    sp, pr = st["sampler"], st["pruner"]
    add(f"- Study `{st['study_name']}`, storage `{manifest['storage']}`, search profile "
        f"`{rs.search.profile_id}`, objective mean inner-fold {rs.search.objective.upper()}.")
    add(f"- Sampler: {sp['name']} seed {sp['seed']}, multivariate {sp['multivariate']}, group "
        f"{sp['group']}, {sp['n_startup_trials']} startup trials.")
    add(f"- Pruner: {pr['name']}, {pr['n_startup_trials']} startup trials, {pr['n_warmup_steps']} "
        f"warmup folds, interval {pr['interval_steps']}. Pruning saves time; it is not evidence "
        "that a configuration is bad.")
    kinds = ", ".join(f"{k} {v}" for k, v in sorted(st["failure_kinds"].items())) or "none"
    add(f"- Trials: requested {st['requested']}, completed {st['completed']}, pruned "
        f"{st['pruned']}, failed {st['failed']} (failure kinds: {kinds}).")
    add(f"- Best trial #{st['best']['number']} (objective {_f(st['best']['value'])}); selected "
        f"trial #{st['selected']['number']}: {st['selected']['reason']}.")
    add("")
    add("| trial | objective | parameters |")
    add("| ---: | ---: | --- |")
    for t in st["top"]:
        add(f"| {t['number']} | {_f(t['value'])} | {_params(t['params'])} |")

    add("")
    add("## Selected model")
    add("")
    m = outer_results[0].model if outer_results else None
    if m is not None:
        add(f"`{m.family}`: {_params(m.model_dump(exclude={'family'}, exclude_none=True))}. "
            "Pipeline: median imputer, standard scaler, estimator.")

    add("")
    add("## Outer-fold performance")
    add("")
    add("| fold | games | MAE | RMSE | bias | warnings | artifact sha256 |")
    add("| --- | ---: | ---: | ---: | ---: | --- | --- |")
    for r in outer_results:
        mt = r.metrics
        add(f"| {r.fold_id} | {mt['n']} | {_f(mt['mae'])} | {_f(mt['rmse'])} | {_f(mt['bias'], True)} | "
            f"{'; '.join(r.warnings) or 'none'} | `{r.artifact_sha256}` |")
    mo = cmp_["model"]
    add(f"| pooled | {mo['n']} | {_f(mo['mae'])} | {_f(mo['rmse'])} | {_f(mo['bias'], True)} | | |")

    add("")
    add(f"## Baseline comparisons (pooled outer folds, {cmp_['n_clusters']} season-week clusters)")
    add("")
    add("Differences are model MAE minus baseline MAE on the same games; negative means the model "
        f"is closer to the actual total. Intervals: week-cluster bootstrap, {acc.bootstrap.draws:,} "
        f"draws, seed {acc.bootstrap.seed}. MDE is 2.8 × the bootstrap SE.")
    add("")
    add("| baseline | games | model MAE | baseline MAE | difference | 95% interval | MDE | verdict | note |")
    add("| --- | ---: | ---: | ---: | ---: | --- | ---: | --- | --- |")
    for b in acc.baselines:
        c = cmp_["baselines"].get(b, {"n": 0})
        if not c.get("n"):
            add(f"| {b} | 0 | | | | | | | no games with this baseline |")
            continue
        lo, hi = c["ci95"]
        add(f"| {b} | {c['n']} | {_f(c['model_mae'])} | {_f(c['baseline_mae'])} | {_f(c['diff'], True)} | "
            f"{_f(lo, True)} to {_f(hi, True)} | {_f(c['mde80'])} | {c['verdict']} | {c.get('label', '')} |")
    add("")
    add("By season (difference):")
    add("")
    add("| baseline | " + " | ".join(str(s) for s in sorted(cmp_["by_season"])) + " |")
    add("| --- | " + " | ".join("---:" for _ in cmp_["by_season"]) + " |")
    for b in acc.baselines:
        per = cmp_["baselines"].get(b, {}).get("by_season", {})
        add(f"| {b} | " + " | ".join(_f(per[s], True) if s in per else "" for s in sorted(cmp_["by_season"])) + " |")

    add("")
    add("## Calibration")
    add("")
    cal = cmp_["calibration"]
    add(f"Actual total regressed on the forecast, pooled outer folds: slope {_f(cal['slope'])}, "
        f"intercept {_f(cal['intercept'], True)}. A slope of 1 means forecasts are not "
        f"systematically too spread out or too compressed. Mean residual {_f(mo['bias'], True)}.")

    add("")
    add("## Acceptance gates")
    add("")
    add("| gate | result | detail |")
    add("| --- | --- | --- |")
    for name, g in manifest["gates"].items():
        add(f"| {name} | {'pass' if g['pass'] else 'FAIL'} | {g['detail']} |")

    add("")
    add("## Limitations")
    add("")
    add("- No betting value: the market baseline has no capture time and no price, so it supports "
        "forecast comparison against a labeled vendor number and nothing more.")
    add("- Reproducibility is bit-for-bit only with the same code fingerprint, data hashes, and "
        "library versions recorded above.")
    add("- Linear models on one fixed feature set; no feature search was run.")

    add("")
    add("## Reproduce")
    add("")
    add("```text")
    add(manifest["reproduce"])
    add("```")
    return "\n".join(lines) + "\n"


def render_dist_card(spec, manifest: dict, scores: dict, selective: dict) -> str:
    """Card for a Release D distribution run. Pure, like `render_card`."""
    d, g = spec.distribution, spec.gate
    sel, gate = scores["selected"], scores["gate"]
    lines: list[str] = []
    add = lines.append

    add(f"# Distribution card: {spec.spec_id} (`{manifest['run_id']}`)")
    add("")
    add("**Status:** research. Predictive distributions of the full-game total; no priced "
        "result. Timestamped, priced totals quotes exist for 2026 only, so priced evaluation "
        "belongs to Release E's shadow period.")
    add(f"**Config hash:** `{manifest['config_hash']}`  ")
    add(f"**Point forecasts from:** `{manifest['base_run_id']}` (model "
        f"`{manifest['model']['family']}`, alpha {manifest['model']['alpha']:.4g}"
        + (f", l1_ratio {manifest['model']['l1_ratio']:.4g}" if manifest['model'].get('l1_ratio') is not None else "")
        + ").  ")
    add(f"**Code:** `{manifest['git_sha']}`, fingerprint `{manifest['code_sha256'][:16]}`; "
        + ", ".join(f"{k} {v}" for k, v in sorted(manifest["packages"].items())))
    if spec.notes:
        add("")
        add(f"**Notes:** {spec.notes}")

    add("")
    add("## Method")
    add("")
    add(f"- Candidates: {', '.join(f'`{c}`' for c in d.candidates)}; baseline `{d.baseline}`. "
        f"One table per game over integer totals 0–{d.support_max}, overtime included.")
    add(f"- Residual window: the {d.window_seasons} most recent usable seasons before the test "
        f"season, split early (a team with fewer than {d.early_min_prior_games} prior games) and "
        "primary. Point forecasts are season-ahead and reproduce the base run's outer "
        "predictions exactly.")
    add(f"- Selection: lowest mean CRPS on inner seasons "
        f"{', '.join(map(str, spec.selection_seasons))}. Outer seasons are scored once.")
    add(f"- Gate (declared before scoring): mid-PIT coverage within ±{g.pooled_coverage_tol} "
        f"pooled at {', '.join(f'{lv:.0%}' for lv in d.interval_levels)}; "
        f"{g.season_coverage_level:.0%} coverage within ±{g.season_coverage_tol} every season; "
        f"PIT deciles within ±{g.pit_decile_tol}.")

    add("")
    add("## Selection (inner seasons)")
    add("")
    add("| candidate | mean CRPS |")
    add("| --- | ---: |")
    for c, v in sorted(scores["selection_crps"].items()):
        add(f"| {c}{' (selected)' if c == sel else ''} | {_f(v)} |")

    add("")
    add(f"## Calibration gate: `{sel}` on the outer seasons — {'PASS (go)' if gate['pass'] else 'FAIL (no-go)'}")
    add("")
    add("| check | value | target | result |")
    add("| --- | ---: | --- | --- |")
    for lv, v in gate["pooled_coverage"].items():
        add(f"| coverage {float(lv):.0%}, pooled | {v['value']:.3f} | {v['nominal']:.2f} ± "
            f"{g.pooled_coverage_tol} | {'pass' if v['pass'] else 'FAIL'} |")
    sc = gate["season_coverage"]
    for s, v in sc["by_season"].items():
        add(f"| coverage {sc['level']:.0%}, {s} (n {v['n']}) | {v['value']:.3f} | "
            f"{sc['level']:.2f} ± {g.season_coverage_tol} | {'pass' if v['pass'] else 'FAIL'} |")
    pd_ = gate["pit_deciles"]
    add(f"| PIT deciles, largest deviation | {pd_['max_abs_dev']:.3f} | ≤ {pd_['tolerance']} | "
        f"{'pass' if pd_['pass'] else 'FAIL'} |")
    add("")
    add("PIT decile shares: " + ", ".join(f"{s:.3f}" for s in pd_["shares"]) + ".")

    add("")
    add(f"## Outer seasons, all candidates ({gate['n']} games)")
    add("")
    add("CRPS is in points; lower is better. Differences are candidate minus baseline on the "
        "same games, week-cluster bootstrap, 10,000 draws, seed 20260922.")
    add("")
    add("| candidate | CRPS | vs baseline | 95% interval | 80% width | 80% coverage | PIT max dev | would pass gate |")
    add("| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |")
    for c, v in scores["outer"].items():
        diff = scores["paired_crps_vs_baseline"].get(c)
        cal = v["calibration"]
        delta = _f(diff["diff"], True) if diff else "—"
        interval = f"{_f(diff['ci95'][0], True)} to {_f(diff['ci95'][1], True)}" if diff else ""
        add(f"| {c} | {_f(v['crps'])} | {delta} | {interval} | "
            f"{_f(v['width_80']) if v['width_80'] is not None else ''} | "
            f"{cal['pooled_coverage']['0.8']['value']:.3f} | {cal['pit_deciles']['max_abs_dev']:.3f} | "
            f"{'pass' if cal['pass'] else 'fail'} |")
    add("")
    seasons = sorted({s for v in scores["outer"].values() for s in v["crps_by_season"]})
    add("| candidate | " + " | ".join(str(s) for s in seasons) + " |")
    add("| --- | " + " | ".join("---:" for _ in seasons) + " |")
    for c, v in scores["outer"].items():
        add(f"| {c} | " + " | ".join(_f(v["crps_by_season"][s]) for s in seasons) + " |")

    add("")
    add("## Over the CFBD open label (a forecast of the event, not a price)")
    add("")
    add("The label has no capture time and no price. P(over) is conditional on no push; games "
        "whose total equals an integer label are excluded.")
    add("")
    add("| candidate | games | pushes excluded | Brier | log loss | over rate |")
    add("| --- | ---: | ---: | ---: | ---: | ---: |")
    for c, v in scores["outer"].items():
        o = v["open_label"]
        if o and o["n"]:
            add(f"| {c} | {o['n']} | {o['pushes_excluded']} | {o['brier']:.4f} | {o['log_loss']:.4f} | "
                f"{o['over_rate']:.3f} |")

    if scores.get("coherence"):
        co = scores["coherence"]
        add("")
        add("## Joint model coherence")
        add("")
        add(f"- Overtime: simulated {co['simulated_ot_rate']:.3f} vs observed {co['observed_ot_rate']:.3f}.")
        add(f"- Mean total: table {co['pooled_mean']:.2f} vs observed {co['observed_mean']:.2f}.")
        add(f"- Home-win Brier on the {co['regulation_decided_games']} games decided in regulation: "
            f"{co['home_win_brier_regulation']:.4f} (secondary; the frame does not record the "
            "overtime winner).")

    add("")
    add(f"## Selective prediction (`{sel}`)")
    add("")
    add(f"A fixed Ridge meta-model predicts |residual| from the features and week, trained on the "
        f"window seasons only. Keeping the lowest-score games, mean CRPS by share kept:")
    add("")
    add("| share kept | games | mean CRPS |")
    add("| ---: | ---: | ---: |")
    for p in selective["curve"]:
        add(f"| {p['coverage']:.0%} | {p['n_kept']} | {_f(p['mean_loss'])} |")
    lo, hi = selective["ci95"]
    add("")
    add(f"Area under the curve minus full-coverage risk: {_f(selective['diff'], True)} "
        f"({_f(lo, True)} to {_f(hi, True)}, {selective['n_clusters']} season-week clusters). "
        "Negative means abstaining on high scores lowers the loss on the games kept.")
    if "min_prior_games_rule" in selective:
        r = selective["min_prior_games_rule"]
        add(f"Rule baseline, skip early games: keeps {r['coverage']:.0%}, mean CRPS "
            f"{_f(r['mean_crps'])} vs {_f(selective['full_mean_crps'])} for all games.")

    add("")
    add("## Limitations")
    add("")
    add("- Outer seasons were already used as a holdout by earlier work: descriptive, not new "
        "evidence. 2026 is the untouched season.")
    add("- The base model's hyperparameters were tuned on 2015–2019, so windows that draw on "
        "those seasons may run narrow; per-season coverage shows whether they do.")
    add("- No betting value: nothing here is priced. The betting engine is verified on "
        "hand-computed fixtures only.")

    add("")
    add("## Reproduce")
    add("")
    add("```text")
    add(manifest["reproduce"])
    add("```")
    return "\n".join(lines) + "\n"
