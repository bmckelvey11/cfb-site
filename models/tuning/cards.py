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
