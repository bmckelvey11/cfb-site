"""Release E task 7: the priced replay on a hand-built ledger (no CFB_DATA_ROOT needed).

Three games at one cutoff: a fresh quote the policy takes and wins, a fresh quote it takes
that lands on the number (push), and a quote too old to use.
"""
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from models.tuning.dist_spec import DecisionPolicySpec
from models.tuning.ledger import Ledger
from models.tuning.replay import ReplaySpec, replay
from models.tuning.shadow import ShadowRefused, shadow_dir
from models.tuning.shadow_spec import ShadowSpec

CUT = pd.Timestamp("2026-10-01T23:30:00Z")
KICK = CUT + pd.Timedelta(hours=40)


def _offer(event, side, ticks):
    return {"event_id": event, "book_id": 68, "side": side, "is_live": False,
            "is_alt_market": False,
            "history": [{"updated_at": at.isoformat(), "value": line, "odds": -110,
                         "line_status": "normal"} for at, line in ticks]}


def _world(tmp_path):
    shadow = ShadowSpec(spec_id="t", created_at="x", created_by="t", season=2026,
                        period_weeks=(5,), base_run_id="run-000000000000",
                        dist_run_id="dist-000000000000", window_seasons=(2025,),
                        policy=DecisionPolicySpec(policy_id="p", version=1, kind="min_ev",
                                                  threshold=0.03))
    (tmp_path / "shadow.json").write_text(shadow.model_dump_json(), encoding="utf-8")
    lab = tmp_path / "lab"
    sd = shadow_dir(lab, shadow)
    (sd / "snapshots").mkdir(parents=True)
    pmf = np.zeros((3, 151))
    pmf[0, 70] = pmf[1, 60] = pmf[2, 60] = 1.0
    np.save(sd / "snapshots" / "w05.npy", pmf)
    blob = (sd / "snapshots" / "w05.npy").read_bytes()
    ledger = Ledger(sd / "ledger.sqlite3")
    ledger.append("snapshot", {"snapshot_id": "5:x", "week": 5, "pmf_file": "snapshots/w05.npy",
                               "pmf_sha256": hashlib.sha256(blob).hexdigest()})
    games = {1: (0, 70.0), 2: (1, 50.0), 3: (2, 44.0)}         # game -> (pmf row, final)
    preds = ledger.append_many([("prediction", {
        "snapshot_id": "5:x", "week": 5, "game_id": g, "alias": "challenger", "pmf_row": row,
        "pmf_mean": float(pmf[row] @ np.arange(151)), "decision_ts": CUT.isoformat(),
        "generated_at": (CUT - pd.Timedelta(days=2)).isoformat()}) for g, (row, _) in games.items()])
    ledger.append_many([("score", {
        "game_id": g, "week": 5, "alias": "challenger", "prediction_seq": p.seq,
        "kickoff_final": KICK.isoformat(), "final_total": games[g][1], "artifact_ok": True})
        for p, g in zip(preds, games)])
    quotes = {
        101: [(CUT - pd.Timedelta(hours=1), 55.0), (KICK - pd.Timedelta(hours=1), 57.0)],
        102: [(CUT - pd.Timedelta(hours=2), 50.0)],
        103: [(CUT - pd.Timedelta(hours=48), 52.0)],               # older than 24 h
    }
    (sd / "quotes").mkdir()
    files = {}
    for event, ticks in quotes.items():
        doc = {"68": {"event": {"total": [_offer(event, "over", ticks), _offer(event, "under", ticks)]}}}
        path = sd / "quotes" / f"history_event_{event}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        files[str(event)] = {"game_id": event - 100, "file": f"quotes/{path.name}",
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    ledger.append("quotes_archived", {"week": 5, "files": files})
    spec = ReplaySpec(spec_id="r", created_at="x", created_by="t",
                      shadow_spec=str(tmp_path / "shadow.json"), shadow_id=shadow.shadow_id())
    return spec, lab, ledger, sd


def test_replay_prices_a_win_a_push_and_skips_a_stale_quote(tmp_path):
    spec, lab, ledger, sd = _world(tmp_path)
    with pytest.raises(ShadowRefused, match="no verdict"):
        replay(spec, lab, tmp_path)
    ledger.append("period_verdict", {"go": True})
    out = replay(spec, lab, tmp_path)

    book = pd.read_csv(sd / "replay" / f"{spec.replay_id()}_ledger.csv").set_index("game_id")
    assert book.loc[1, "result"] == "win" and book.loc[1, "line"] == 55.0
    assert book.loc[1, "units"] == pytest.approx(100 / 110)
    assert book.loc[1, "clv_line"] == 2.0                      # closed at 57 on an over at 55
    assert book.loc[2, "result"] == "push" and book.loc[2, "units"] == 0.0
    assert book.loc[3, "action"] == "no_quote"
    assert out["views"]["realized"] == {"bets": 2, "units": pytest.approx(100 / 110),
                                        "wins": 1, "pushes": 1}
    # Only game 1 scores against the market: game 2 landed on the number, game 3 was stale.
    m = out["p_over_vs_market"]
    assert m["n"] == 1 and m["brier_market"] == pytest.approx(0.25)
    assert out["verdict_go"] is True and "trial count 1" in out["framing"]


def test_replay_refuses_a_quote_file_changed_after_archive(tmp_path):
    spec, lab, ledger, sd = _world(tmp_path)
    ledger.append("period_verdict", {"go": True})
    path = sd / "quotes" / "history_event_101.json"
    path.write_text(path.read_text(encoding="utf-8").replace("55.0", "54.5"), encoding="utf-8")
    with pytest.raises(ShadowRefused, match="event 101"):
        replay(spec, lab, tmp_path)
