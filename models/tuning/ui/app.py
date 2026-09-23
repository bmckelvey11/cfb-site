"""The tuning lab GUI (plan §5 and §37): build and launch runs, follow them, read results.

    .venv-lab-ui\\Scripts\\python -m streamlit run models/tuning/ui/app.py

Pages: Shadow (read-only), New run (plan §5 pages 01-06), Jobs (07), Runs (08-09),
Hypotheses (10). Every check a spec must pass lives in `models.tuning.ui.api`, run in the
main `.venv`, so the GUI cannot skip one; a launch re-validates the exact file it starts.
Set CFB_LAB_ROOT to point the whole GUI at a scratch lab. Runs in its own venv so the
shadow tick's `.venv` keeps its packages:
    python -m venv .venv-lab-ui && .venv-lab-ui\\Scripts\\pip install -r requirements-lab-ui.txt
"""
from __future__ import annotations

import difflib
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from cfb_paths import RAW  # noqa: E402
from models.tuning.ui import actions  # noqa: E402
from models.tuning.ui import data as md  # noqa: E402

# `streamlit run app.py -- --lab-root DIR` (or CFB_LAB_ROOT) points the GUI at a scratch lab.
LAB = (Path(sys.argv[sys.argv.index("--lab-root") + 1]) if "--lab-root" in sys.argv
       else md.lab_root())
SPECS = REPO / "models" / "tuning" / "specs"
ALERT = {"error": st.error, "warning": st.warning, "success": st.success, "info": st.info}
IN_FLIGHT = ("queued", "claimed", "running", "retry_wait", "cancellation_requested")

st.set_page_config(page_title="CFB Tuning Lab", layout="wide")
page = st.sidebar.radio("Page", ["Shadow", "New run", "Jobs", "Runs", "Hypotheses"])
st.sidebar.caption(f"Lab root: `{LAB}`" + ("  \n**scratch lab**" if "--lab-root" in sys.argv
                                            or os.environ.get("CFB_LAB_ROOT") else ""))
st.sidebar.caption("Shadow and Hypotheses are read-only. Freeze, tick, alias, and replay "
                   "stay in the CLI.")
if st.sidebar.button("Reload"):
    st.rerun()
now = pd.Timestamp.now(tz="UTC")


@st.cache_data(ttl=600)
def lab_catalog(root: str) -> dict:
    return actions.api(Path(root), "catalog")


def templates() -> dict[str, Path]:
    out = {}
    for p in sorted(SPECS.glob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        if {"dataset", "folds", "search"} <= set(doc):
            out[f"spec: {p.stem}"] = p
    for p in md.run_dirs(LAB):
        if (p / "run_spec.json").exists():
            out[f"run: {p.name}"] = p / "run_spec.json"
    return out


def pretty(doc: dict) -> list[str]:
    return json.dumps(doc, indent=1, sort_keys=True).splitlines()


if page == "Shadow":
    shadows = sorted(p for p in (LAB / "shadow").glob("shadow-*") if (p / "ledger.sqlite3").exists())
    if not shadows:
        st.info("No shadow period is armed.")
        st.stop()
    sd = st.selectbox("Shadow period", shadows, format_func=lambda p: p.name)
    v = md.shadow_view(sd, RAW, now)
    st.title(f"Shadow {v['shadow_id']}")
    for level, text in v["alerts"] or [("success", "Nothing needs you right now.")]:
        ALERT[level](text)
    c1, c2, c3 = st.columns(3)
    hours = v["last_tick_hours"]
    c1.metric("Last tick", "never" if hours is None else f"{hours:.0f} h ago", v["last_tick"],
              delta_color="off")
    c2.metric("Ledger chain", "ok" if v["chain_ok"] else "FAILS", v["chain"], delta_color="off")
    c3.metric("Records", sum(v["counts"].values()))
    st.subheader("Weeks")
    st.dataframe(v["weeks"], hide_index=True, width="stretch")
    st.caption("A game's counted prediction is the last one generated before its kickoff. "
               "Rehearsal weeks never count toward the verdict.")
    if v["aliases"]:
        st.subheader("Aliases")
        st.dataframe(pd.DataFrame(v["aliases"], columns=["alias", "model", "reason"]),
                     hide_index=True, width="stretch")
    st.subheader("Priced replay")
    if not v["replays"]:
        st.caption("Not run yet. It runs after the period verdict (`python -m models.tuning replay`).")
    for path in v["replays"]:
        out = json.loads(path.read_text(encoding="utf-8"))
        with st.expander(path.stem, expanded=True):
            st.warning(out["framing"])
            st.json({k: out[k] for k in ("weeks", "games_priced", "views", "units_per_bet",
                                         "clv_line", "clv_close_unknown", "actionable",
                                         "p_over_vs_market")}, expanded=False)
            st.dataframe(pd.DataFrame(out["sensitivity"]), hide_index=True)
    with st.expander("status.md (written by the tick)"):
        st.markdown(v["status_md"])

elif page == "New run":
    st.title("New run")
    st.caption("Start from a template, edit, Validate, then Launch. Only options the lab "
               "implements are offered; everything else is fixed and shown as such.")
    cat = lab_catalog(str(LAB))
    tpls = templates()
    tpl = st.selectbox("Template", list(tpls))
    t = json.loads(tpls[tpl].read_text(encoding="utf-8"))
    feats = {f["id"]: f for f in cat["features"]}
    seasons = cat["seasons"]
    with st.form(f"spec:{tpl}"):
        st.subheader("01 Dataset and task")
        c1, c2, c3 = st.columns(3)
        source = c1.selectbox("Source", ["cfb_release_b", "synthetic_v1"],
                              index=["cfb_release_b", "synthetic_v1"].index(t["dataset"]["source"]))
        snapshot = c2.selectbox("Snapshot (cfb_release_b)", cat["snapshots"])
        seed = c3.number_input("Seed (synthetic_v1)", value=int(t["dataset"].get("synthetic_seed") or 0))
        ds_seasons = st.multiselect("Seasons loaded", seasons,
                                    default=[s for s in t["dataset"]["seasons"] if s in seasons])
        st.caption("Target: full-game total. Decision time: each week's cutoff. Population: FBS "
                   f"vs FBS, week 2+. {cat['sealed']} is sealed and not offered.")

        st.subheader("02 Features")
        chosen = st.multiselect(
            "Features, in column order", list(feats),
            default=[f["id"] for f in t["feature_set"]["features"] if f["id"] in feats],
            format_func=lambda i: i if feats[i]["eligible"] else f"{i} (blocked)")
        st.dataframe(pd.DataFrame(cat["features"])[["id", "availability_class", "eligible",
                                                    "description"]], hide_index=True, width="stretch")
        c1, c2 = st.columns(2)
        fs_id = c1.text_input("Feature set id", t["feature_set"]["feature_set_id"])
        fs_version = c2.number_input("Feature set version", min_value=1,
                                     value=int(t["feature_set"]["version"]))

        st.subheader("03 Opponent adjustment and priors")
        st.info("Fixed by the Release B snapshot: `ridge_v1` ratings, λ 40 (points per "
                "possession) and 8 (pace), season to date, no priors. Changing them takes a new "
                "snapshot, not a setting. Drifting (Kalman) ratings were tested and lost "
                "(Hypotheses: F1).")

        st.subheader("04 Validation design")
        f = t["folds"]
        c1, c2, c3, c4 = st.columns(4)
        inner = c1.multiselect("Inner test seasons (tuning)", seasons, default=f["inner_test_seasons"])
        outer = c2.multiselect("Outer test seasons (evaluated once)", seasons,
                               default=f["outer_test_seasons"])
        exclude = c3.multiselect("Excluded seasons", seasons, default=f.get("exclude_seasons", []))
        embargo = c4.number_input("Embargo days", min_value=0, value=int(f.get("embargo_days", 0)))

        st.subheader("05 Model and search space")
        s = t["search"]
        profile = st.selectbox("Search profile", list(cat["profiles"]))
        st.caption("Families and ranges: " + "; ".join(
            f"{fam} " + ", ".join(f"{p} {lo:g}–{hi:g}{' (log)' if log else ''}"
                                  for p, (lo, hi, log) in ps.items())
            for fam, ps in cat["profiles"][profile].items()))
        c1, c2, c3, c4 = st.columns(4)
        n_trials = c1.number_input("Trials", min_value=1, value=int(s["n_trials"]))
        objective = c2.selectbox("Objective", ["mae", "rmse"], index=["mae", "rmse"].index(s.get("objective", "mae")))
        max_retry = c3.number_input("Max retries", min_value=0, value=int(s.get("max_retry", 2)))
        sp, pr = s.get("sampler", {}), s.get("pruner", {})
        sampler_startup = c4.number_input("TPE startup trials", min_value=0,
                                          value=int(sp.get("n_startup_trials", 20)))
        c1, c2, c3, c4 = st.columns(4)
        multivariate = c1.checkbox("TPE multivariate", value=sp.get("multivariate", True))
        group = c2.checkbox("TPE group", value=sp.get("group", True))
        pruner_startup = c3.number_input("Pruner startup trials", min_value=0,
                                         value=int(pr.get("n_startup_trials", 20)))
        warmup = c4.number_input("Pruner warmup folds", min_value=1, value=int(pr.get("n_warmup_steps", 2)))

        st.subheader("Acceptance and seeds")
        a, sd_ = t["acceptance"], t.get("seeds", {})
        c1, c2, c3 = st.columns(3)
        baselines = c1.multiselect("Baselines", cat["baselines"], default=a["baselines"])
        bias_tol = c2.number_input("Bias tolerance (points)", min_value=0.01,
                                   value=float(a.get("bias_tolerance", 1.0)))
        max_features = c3.number_input("Max features", min_value=1, value=int(a.get("max_features", 20)))
        c1, c2, c3 = st.columns(3)
        seed_split = c1.number_input("Split seed", value=int(sd_.get("split", 0)))
        seed_model = c2.number_input("Model seed", value=int(sd_.get("model", 0)))
        seed_sampler = c3.number_input("Sampler seed", value=int(sd_.get("sampler", 42)))

        st.subheader("Identity")
        c1, c2 = st.columns(2)
        spec_id = c1.text_input("Spec id", t["spec_id"])
        created_by = c2.text_input("Created by", t.get("created_by", "mckel"))
        notes = st.text_area("Notes (for the card; not hashed)", t.get("notes", ""))
        submitted = st.form_submit_button("Validate", type="primary")

    if submitted:
        dataset = {"source": source, "snapshot": snapshot, "seasons": ds_seasons}
        if source == "synthetic_v1":
            dataset["synthetic_seed"] = int(seed)
        doc = {
            "schema_version": 1, "spec_id": spec_id, "created_at": now.isoformat(timespec="seconds"),
            "created_by": created_by, "notes": notes, "dataset": dataset,
            "feature_set": {"feature_set_id": fs_id, "version": int(fs_version), "features": [
                {"id": i, "version": feats[i]["version"],
                 "availability_class": feats[i]["availability_class"]} for i in chosen]},
            "folds": {"inner_test_seasons": inner, "outer_test_seasons": outer,
                      "exclude_seasons": exclude, "embargo_days": int(embargo)},
            "search": {"profile_id": profile, "n_trials": int(n_trials), "objective": objective,
                       "sampler": {"n_startup_trials": int(sampler_startup),
                                   "multivariate": multivariate, "group": group},
                       "pruner": {"n_startup_trials": int(pruner_startup), "n_warmup_steps": int(warmup)},
                       "max_retry": int(max_retry)},
            "acceptance": {"baselines": baselines, "bias_tolerance": float(bias_tol),
                           "max_features": int(max_features)},
            "seeds": {"split": int(seed_split), "model": int(seed_model), "sampler": int(seed_sampler)},
        }
        draft = actions.write_draft(LAB, doc)
        st.session_state["validated"] = {"template": tpl, "draft": str(draft), "doc": doc,
                                         "res": actions.api(LAB, "validate", "--spec", str(draft))}

    val = st.session_state.get("validated")
    if val and val["template"] == tpl:
        res = val["res"]
        st.subheader("06 Review and launch")
        for e in res["errors"]:
            st.error(e)
        for w in res["warnings"]:
            st.warning(w)
        if res["ok"]:
            ln = res["launch"]
            st.success(f"Valid. Config `{res['config_hash'][:12]}` launches **{ln['run_id']}**"
                       + (f" (replicate {ln['replicate']})" if ln["replicate"] else ""))
            for s_ in ln["skipped"]:
                st.info(f"Skipping {s_['run_id']}: {s_['state']}"
                        + ("" if s_["same_code"] else ", on different code") + ".")
        with st.expander("Diff against the template"):
            diff = list(difflib.unified_diff(pretty(t), pretty(val["doc"]), "template", "draft",
                                             lineterm="", n=1))
            st.code("\n".join(diff) or "(no changes)", language="diff")
        if res["canonical"]:
            with st.expander("Canonical spec (what the config hash covers)"):
                st.code(res["canonical"], language="json")
        if res["ok"]:
            h = res["holdout"]
            done = ln["existing_state"] == "completed"
            inner_s = sorted(val["doc"]["folds"]["inner_test_seasons"])
            if val["doc"]["dataset"]["source"] == "synthetic_v1":
                st.markdown(f"**Synthetic data:** tunes on {inner_s}, evaluates on {h['outer']}. "
                            "No real season is consumed.")
            else:
                st.markdown(
                    f"**This run tunes on inner seasons {inner_s} and evaluates once on outer "
                    f"seasons {h['outer']}.** {h['prior_trials']} trials were already requested on "
                    "these outer seasons in the lab"
                    + (f", and {h['used_outside_lab']} served earlier releases" if h["used_outside_lab"] else "")
                    + ". This adds to that count; nothing about it can be undone.")
            ok = st.checkbox(f"I understand; launch {ln['run_id']}", disabled=done,
                             key=f"confirm:{val['draft']}")
            if done:
                st.caption("Already completed on this code: open it on the Runs page.")
            if st.button("Launch", type="primary", disabled=not ok or done):
                try:
                    run_id, log = actions.launch(LAB, Path(val["draft"]), ln["replicate"])
                    st.success(f"Launched {run_id}. Follow it on the Jobs page (log: `{log}`).")
                    del st.session_state["validated"]
                except actions.Refused as e:
                    st.error(f"Not launched: {e}")

elif page == "Jobs":
    st.title("Jobs")
    jobs = md.jobs(LAB)
    if not len(jobs):
        st.caption("No jobs yet.")
        st.stop()
    st.dataframe(jobs, hide_index=True, width="stretch")
    run_id = st.selectbox("Job", jobs["run_id"])
    state = jobs.set_index("run_id").at[run_id, "state"]
    tr = md.trials(LAB, run_id)
    c1, c2, c3 = st.columns(3)
    c1.metric("State", state)
    c2.metric("Trials complete / started",
              f"{int((tr['state'] == 'COMPLETE').sum()) if len(tr) else 0} / {len(tr)}")
    best = tr.loc[tr["state"] == "COMPLETE", "objective"].min() if len(tr) else None
    c3.metric("Best objective", "—" if best is None or pd.isna(best) else f"{best:.3f}")
    if len(tr):
        done = tr[tr["state"] == "COMPLETE"].set_index("number")["objective"]
        if len(done):
            st.line_chart(done.cummin().rename("best so far"))
        st.dataframe(tr, hide_index=True, width="stretch")
    tail = md.log_tail(LAB, run_id)
    if tail:
        with st.expander("Worker log (last 40 lines)", expanded=state in IN_FLIGHT):
            st.code(tail)
    if state in IN_FLIGHT:
        st.subheader("Cancel")
        sure = st.checkbox(f"Yes, cancel {run_id}. Completed trials are kept; the run stops "
                           "between folds.")
        if st.button("Request cancel", disabled=not sure):
            st.info(actions.cancel(LAB, run_id))

elif page == "Runs":
    st.title("Runs")
    runs = md.run_dirs(LAB)
    if not runs:
        st.caption("No published runs.")
        st.stop()
    run = st.selectbox("Run", runs, format_func=lambda p: p.name)
    tabs = st.tabs(["Card", "Trials", "Comparisons", "Spec"])
    card = run / "card.md"
    tabs[0].markdown(card.read_text(encoding="utf-8") if card.exists() else "_No card._")
    if (run / "trials.csv").exists():
        tabs[1].dataframe(pd.read_csv(run / "trials.csv"), hide_index=True, width="stretch")
    else:
        tabs[1].caption("No trials file (a distribution run has none).")
    for name in ("comparisons.json", "scores.json"):
        if (run / name).exists():
            tabs[2].json(json.loads((run / name).read_text(encoding="utf-8")), expanded=1)
    for name in ("run_spec.json", "dist_spec.json"):
        if (run / name).exists():
            tabs[3].code((run / name).read_text(encoding="utf-8"), language="json")

else:
    st.title("Hypothesis ledger")
    st.caption("Every hypothesis the lab has tested, nulls included (plan §32.1). "
               "The record wins if it disagrees with this table.")
    h = md.hypotheses()
    status = st.multiselect("Status", sorted(h["status"].unique()), default=sorted(h["status"].unique()))
    st.table(h[h["status"].isin(status)].set_index("id"))
