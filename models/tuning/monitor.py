"""Read-only lab monitor (plan §37.2 pages 15-17): shadow period, runs and cards, hypotheses.

    .venv-lab-ui\\Scripts\\python -m streamlit run models/tuning/monitor.py

It never launches, cancels, or edits anything: the CLI (`python -m models.tuning`) does
that. Runs in its own venv so the shadow tick's `.venv` keeps its packages for the period:
    python -m venv .venv-lab-ui && .venv-lab-ui\\Scripts\\pip install -r requirements-lab-ui.txt
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from cfb_paths import PROCESSED, RAW  # noqa: E402
from models.tuning import monitor_data as md  # noqa: E402

LAB = PROCESSED / "tuning"
ALERT = {"error": st.error, "warning": st.warning, "success": st.success, "info": st.info}

st.set_page_config(page_title="CFB Tuning Lab", layout="wide")
page = st.sidebar.radio("Page", ["Shadow", "Runs", "Hypotheses"])
st.sidebar.caption(f"Lab root: `{LAB}`")
st.sidebar.caption("Read-only. Change things with `python -m models.tuning`.")
if st.sidebar.button("Reload"):
    st.rerun()
now = pd.Timestamp.now(tz="UTC")

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
    st.dataframe(v["weeks"], hide_index=True, use_container_width=True)
    st.caption("A game's counted prediction is the last one generated before its kickoff. "
               "Rehearsal weeks never count toward the verdict.")
    if v["aliases"]:
        st.subheader("Aliases")
        st.dataframe(pd.DataFrame(v["aliases"], columns=["alias", "model", "reason"]),
                     hide_index=True, use_container_width=True)
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

elif page == "Runs":
    st.title("Runs")
    jobs = md.jobs(LAB)
    st.subheader("Tuning jobs")
    if len(jobs):
        st.dataframe(jobs, hide_index=True, use_container_width=True)
    else:
        st.caption("None.")
    runs = md.run_dirs(LAB)
    if runs:
        run = st.selectbox("Model card", runs, format_func=lambda p: p.name)
        card = run / "card.md"
        st.markdown(card.read_text(encoding="utf-8") if card.exists() else "_No card._")

else:
    st.title("Hypothesis ledger")
    st.caption("Every hypothesis the lab has tested, nulls included (plan §32.1). "
               "The record wins if it disagrees with this table.")
    h = md.hypotheses()
    status = st.multiselect("Status", sorted(h["status"].unique()), default=sorted(h["status"].unique()))
    st.table(h[h["status"].isin(status)].set_index("id"))
