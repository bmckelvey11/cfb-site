"""Tests for turning a weekly_slate.py snapshot into a fillable bet sheet."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ledgers.build_slate_sheet import COLUMNS, SOURCE, build


def _slate_row(**overrides):
    row = {"road": "Furman", "home": "Tennessee", "side": "Tennessee", "side_line": -49.5,
           "side_odds": -115.0, "side_book": "DraftKings", "edge": 5.2, "kick_et": "Sat 7PM"}
    row.update(overrides)
    return row


def test_a_game_with_a_pick_becomes_one_spread_row():
    slate = pd.DataFrame([_slate_row()])
    out = build(slate, pd.Timestamp("2026-09-18T12:00", tz="America/New_York"))
    assert len(out) == 1
    row = out.iloc[0]
    assert (row.away, row.home, row.market) == ("Furman", "Tennessee", "spread")
    assert (row.side, row.line, row.odds) == ("Tennessee", -49.5, -115.0)
    assert row.book == "DraftKings" and row.source == SOURCE
    assert row.notes == "edge 5.2"
    assert row.bet == "" and row.stake == ""


def test_a_flat_game_is_dropped():
    slate = pd.DataFrame([_slate_row(side="", side_line=np.nan, side_odds=np.nan,
                                      side_book="", edge=0.1)])
    out = build(slate, pd.Timestamp("2026-09-18T12:00", tz="America/New_York"))
    assert out.empty


def test_missing_kick_et_and_edge_become_blank_not_nan():
    slate = pd.DataFrame([_slate_row(kick_et=np.nan, edge=np.nan)])
    out = build(slate, pd.Timestamp("2026-09-18T12:00", tz="America/New_York"))
    row = out.iloc[0]
    assert row.kick_et == "" and row.notes == ""


def test_output_column_order_is_fixed():
    slate = pd.DataFrame([_slate_row()])
    out = build(slate, pd.Timestamp("2026-09-18T12:00", tz="America/New_York"))
    assert list(out.columns) == COLUMNS
