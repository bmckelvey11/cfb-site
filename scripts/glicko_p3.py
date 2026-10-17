"""Glicko P3 bundles (docs/superpowers/specs/2026-10-16-glicko-p3-bundles-design.md).

Each bundle is its own class on top of P1's `GlickoMargin`; with default settings each one
reproduces P1's forecasts exactly (tests/test_glicko_p3.py), and `glicko_ratings.py` is not
touched, so P1's sealed confirmation fingerprint is unchanged.

A. `GlickoFull` -- schedule strength. The within-season filter carries the covariance between
   teams, so a result moves every team linked to the two that played, by how strongly they
   are linked. The offseason keeps P1's variance rule (u^2 += delta^2) and resets every
   cross-team covariance to zero. cross=False is P1's diagonal update.
B. `GlickoStart` -- preseason start. At each offseason
       target = (1 - h) * m + h * hist3
       r      = target + clamp(w + c * rp_z, 0, 1) * (r_old - target)
   m      new_conf=True: the mean final rating of the teams that play the new season in the
          team's new conference (known from the schedule); else P1's target
   hist3  the team's own final ratings over the last three seasons, weights 3:2:1, newest first
   rp_z   z-score among that season's FBS teams of transfer-aware returning production
   Defaults (new_conf=False, h=0, c=0) are P1.
C. `GlickoContext` -- game context, read per game through `run_ctx`:
   home edge  H(s) = H2013 + slope * (s - 2013), with 2020 its own value H2020; a neutral-site
              game within 150 miles of one campus gives that team H(s)/2
   time zone  + tz * (home team's UTC offset - away team's), points per zone, every game
   overtime   an OT game updates on margin 0 (the regulation score); it is still scored on
              its final margin
   noise      observation variance x k for postseason games and FBS-vs-FCS games; the
              forecast SD uses the same multiplier on sigma_pred^2
   Defaults (H2013 = H2020 = P1's 2, slope 0, tz 0, k 1, ot/near off) are P1.
D. `GlickoShrinkX` -- FBS-vs-FCS (docs/superpowers/specs/2026-10-17-glicko-p3d-fcs-design.md).
   A cross-subdivision game's expected margin is (1 - lam) * P1's, in the forecast and in the
   update's innovation; gains and variances are P1's. lam = 0 is P1.
"""
from __future__ import annotations

import json
import math
from collections.abc import MutableMapping
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from scripts.glicko_ratings import FBS, GlickoMargin

HIST_WEIGHTS = (3.0, 2.0, 1.0)   # newest season first
NEAR_MILES = 150.0
EARTH_MILES = 3958.8


# --- A. covariance-carrying filter ---------------------------------------------------

class _ArrayMap(MutableMapping):
    """team -> float stored in a shared array, so _Teams keeps using r[k], u2[k], `k in r`."""

    def __init__(self, owner, attr: str, diag: bool):
        self.o, self.attr, self.diag = owner, attr, diag

    def __getitem__(self, k):
        a, i = getattr(self.o, self.attr), self.o.idx[k]
        return float(a[i, i] if self.diag else a[i])

    def __setitem__(self, k, v):
        i = self.o._slot(k)
        a = getattr(self.o, self.attr)
        if self.diag:
            a[i, i] = v
        else:
            a[i] = v

    def __delitem__(self, k):
        raise TypeError("teams are never removed")

    def __iter__(self):
        return iter(self.o.idx)

    def __len__(self):
        return len(self.o.idx)


class GlickoFull(GlickoMargin):
    def __init__(self, *args, cross: bool = True, **kw):
        self.idx: dict[str, int] = {}
        self.mu, self.P, self.cross = np.zeros(64), np.zeros((64, 64)), cross
        super().__init__(*args, **kw)
        self.r = _ArrayMap(self, "mu", diag=False)
        self.u2 = _ArrayMap(self, "P", diag=True)

    def _slot(self, k: str) -> int:
        if k not in self.idx:
            n = len(self.idx)
            if n == len(self.mu):
                P = np.zeros((2 * n, 2 * n))
                P[:n, :n] = self.P
                self.mu, self.P = np.concatenate([self.mu, np.zeros(n)]), P
            self.idx[k] = n
        return self.idx[k]

    def forecast(self, h, a, neutral, t):
        self._advance(h, t)
        self._advance(a, t)
        i, j = self.idx[h], self.idx[a]
        rd2 = self.P[i, i] + self.P[j, j] - 2.0 * self.P[i, j]
        return self.mu[i] - self.mu[j] + (0.0 if neutral else self.hfa), rd2 + self.sigma2, rd2

    def update(self, h, a, neutral, margin, t):
        mhat, s, _ = self.forecast(h, a, neutral, t)
        e = max(-self.cap, min(self.cap, margin)) - mhat
        i, j, n = self.idx[h], self.idx[a], len(self.idx)
        if not self.cross:
            kh, ka = self.P[i, i] / s, self.P[j, j] / s
            self.mu[i] += kh * e
            self.mu[j] -= ka * e
            self.P[i, i] *= 1.0 - kh
            self.P[j, j] *= 1.0 - ka
            return
        v = self.P[:n, i] - self.P[:n, j]          # cov(every team, home - away)
        self.mu[:n] += v * (e / s)
        self.P[:n, :n] -= np.outer(v, v) / s

    def season_start(self, ended, t):
        super().season_start(ended, t)
        n = len(self.idx)
        d = np.diag(self.P[:n, :n]).copy()
        self.P[:n, :n] = 0.0
        self.P[np.arange(n), np.arange(n)] = d


# --- B. preseason start ----------------------------------------------------------------

class GlickoStart(GlickoMargin):
    """feats = {"new_conf": {season: {team: conf}}, "rp": {season: {team: rp_z}}}."""

    def __init__(self, *args, h: float = 0.0, c: float = 0.0, new_conf: bool = False,
                 feats: dict | None = None, **kw):
        super().__init__(*args, **kw)
        self.h, self.c, self.new_conf, self.feats = h, c, new_conf, feats or {}
        self.hist: dict[str, list[float]] = {}
        self._s, self._m_new = None, {}

    def season_start(self, ended, t):
        self._s = ended + 1
        for k in self.r:
            if self.last.get(k) == ended:
                self.hist.setdefault(k, []).insert(0, self.r[k])
        groups: dict[str, list[float]] = {}
        for k, conf in self.feats.get("new_conf", {}).get(self._s, {}).items():
            if k in self.r and conf is not None:
                groups.setdefault(conf, []).append(self.r[k])
        self._m_new = {c: sum(v) / len(v) for c, v in groups.items()}
        super().season_start(ended, t)

    def _offseason(self, k, t):
        target = self._target(self.div[k], self.conf.get(k))
        if self.new_conf:
            conf = self.feats.get("new_conf", {}).get(self._s, {}).get(k)
            target = self._m_new.get(conf, target)
        hist = self.hist.get(k, [])[:len(HIST_WEIGHTS)]
        if self.h and hist:
            wts = HIST_WEIGHTS[:len(hist)]
            target = (1.0 - self.h) * target + self.h * sum(w * x for w, x in zip(wts, hist)) / sum(wts)
        rp = self.feats.get("rp", {}).get(self._s, {}).get(k, 0.0)
        w = min(1.0, max(0.0, self.w + self.c * rp))
        self.r[k] = target + w * (self.r[k] - target)
        self.u2[k] += self.delta2
        self.tl[k] = t


def new_conferences(games: pd.DataFrame) -> dict[int, dict[str, str]]:
    """{season: {team: conference}} from each team's first game of the season (the schedule)."""
    out: dict[int, dict[str, str]] = {}
    g = games.sort_values(["kickoff", "game_id"])
    for side in ("home", "away"):
        for s, team, conf in zip(g["season"], g[side], g[f"{side}_conf"]):
            out.setdefault(int(s), {}).setdefault(team, conf)
    return out


def _z(d: dict[str, float]) -> dict[str, float]:
    if not d:
        return {}
    v = np.array(list(d.values()), float)
    mu, sd = v.mean(), v.std()
    return {k: (x - mu) / sd for k, x in d.items()} if sd > 0 else {k: 0.0 for k in d}


def transfer_aware_rp(raw: Path, fbs_by_season: dict[int, set[str]]) -> tuple[dict, dict]:
    """({season: {team: rp_z}}, coverage).

    share = (CFBD returning totalPPA + incoming transfers' prior-season PPA) / last season's
    team PPA (sum of CFBD player-season PPA), z-scored among that season's FBS teams.
    A transfer counts when its name and origin match a prior-season player row. CFBD's
    player PPA covers FBS players only, so the spec's half credit for transfers from below
    FBS cannot be applied: those transfers add nothing. Portal files start in 2021, so before
    then the share is CFBD's own returning share.
    """
    out, coverage = {}, {}
    for s, fbs in sorted(fbs_by_season.items()):
        rp_path, ppa_path = raw / f"returning_production_{s}.json", raw / f"ppa_players_season_{s - 1}.json"
        if not rp_path.exists() or not ppa_path.exists():
            continue
        ret = {r["team"]: float(r.get("totalPPA") or 0.0) for r in json.loads(rp_path.read_text())}
        team_ppa: dict[str, float] = {}
        player: dict[tuple[str, str], float] = {}
        for p in json.loads(ppa_path.read_text()):
            v = float(((p.get("totalPPA") or {}).get("all")) or 0.0)
            team_ppa[p["team"]] = team_ppa.get(p["team"], 0.0) + v
            key = (p["name"].strip().lower(), p["team"])
            player[key] = player.get(key, 0.0) + v
        inc: dict[str, float] = {}
        n_in = n_matched = 0
        portal = raw / f"transfer_portal_{s}.json"
        for t in (json.loads(portal.read_text()) if portal.exists() else []):
            if t.get("destination") not in fbs:
                continue
            n_in += 1
            key = (f"{t.get('firstName') or ''} {t.get('lastName') or ''}".strip().lower(), t.get("origin"))
            if key in player:
                n_matched += 1
                inc[t["destination"]] = inc.get(t["destination"], 0.0) + player[key]
        share = {k: (ret.get(k, 0.0) + inc.get(k, 0.0)) / team_ppa[k]
                 for k in fbs if k in ret and team_ppa.get(k, 0.0) > 0}
        out[s] = _z(share)
        coverage[s] = {"teams": len(share), "transfers_into_fbs": n_in, "matched_to_ppa": n_matched}
    return out, coverage


# --- D. FBS-vs-FCS shrink --------------------------------------------------------------

class GlickoShrinkX(GlickoMargin):
    def __init__(self, *args, lam: float = 0.0, **kw):
        super().__init__(*args, **kw)
        self.lam = lam

    def forecast(self, h, a, neutral, t):
        mhat, s, rd2 = super().forecast(h, a, neutral, t)
        if self.div[h] != self.div[a]:
            mhat *= 1.0 - self.lam
        return mhat, s, rd2       # GlickoMargin.update reads this forecast: same shrunk innovation


# --- C. game context -------------------------------------------------------------------

def run_ctx(model, games: pd.DataFrame, ev: list[tuple]) -> pd.DataFrame:
    """glicko_ratings.run, but the model is told which game (row) each call belongs to."""
    home, away = games["home"].tolist(), games["away"].tolist()
    neutral, margin = games["neutral"].tolist(), games["margin"].tolist()
    hdiv, adiv = games["home_div"].tolist(), games["away_div"].tolist()
    n = len(games)
    hconf = games["home_conf"].tolist() if "home_conf" in games.columns else [None] * n
    aconf = games["away_conf"].tolist() if "away_conf" in games.columns else [None] * n
    rows, season = [], None
    for t, kind, s, x in ev:
        if s != season:
            if season is not None:
                model.season_start(season, t)
            season = s
        if kind == 0:
            _, idx = x
            for i in idx:
                model.enter(home[i], hdiv[i], t, hconf[i])
                model.enter(away[i], adiv[i], t, aconf[i])
                model.cur = i
                rows.append((i, *model.forecast(home[i], away[i], neutral[i], t)))
        else:
            model.cur = x
            model.update(home[x], away[x], neutral[x], margin[x], t)
            model.played(home[x], hdiv[x], s, hconf[x])
            model.played(away[x], adiv[x], s, aconf[x])
    return pd.DataFrame(rows, columns=["row", *model.COLS]).set_index("row").sort_index()


class GlickoContext(GlickoMargin):
    """ctx: DataFrame aligned to the games' rows with season, neutral, near (+1 home campus
    within 150 mi of a neutral site, -1 away, 0 neither/both), dz (home - away UTC offset,
    hours), k_game (postseason or FBS-vs-FCS), ot."""

    def __init__(self, *args, ctx: pd.DataFrame | None = None, h2013: float | None = None,
                 slope: float = 0.0, h2020: float | None = None, tz: float = 0.0, k: float = 1.0,
                 ot_tie: bool = False, near: bool = False, **kw):
        super().__init__(*args, **kw)
        self.h2013 = self.hfa if h2013 is None else h2013
        self.h2020 = self.hfa if h2020 is None else h2020
        self.slope, self.tz, self.k, self.ot_tie, self.near = slope, tz, k, ot_tie, near
        self.cur = None
        if ctx is not None:
            self.c_season = ctx["season"].to_numpy(int)
            self.c_neutral = ctx["neutral"].to_numpy(bool)
            self.c_near = ctx["near"].to_numpy(int)
            self.c_dz = ctx["dz"].to_numpy(float)
            self.c_kgame = ctx["k_game"].to_numpy(bool)
            self.c_ot = ctx["ot"].to_numpy(bool)

    def edge(self, i) -> float:
        s = self.c_season[i]
        H = self.h2020 if s == 2020 else self.h2013 + self.slope * (s - 2013)
        if not self.c_neutral[i]:
            e = H
        elif self.near and self.c_near[i]:
            e = 0.5 * H * self.c_near[i]
        else:
            e = 0.0
        return e + self.tz * self.c_dz[i]

    def var_mult(self, i) -> float:
        return self.k if self.c_kgame[i] else 1.0

    def forecast(self, h, a, neutral, t):
        self._advance(h, t)
        self._advance(a, t)
        rd2 = self.u2[h] + self.u2[a]
        i = self.cur
        return self.r[h] - self.r[a] + self.edge(i), rd2 + self.var_mult(i) * self.sigma2, rd2

    def update(self, h, a, neutral, margin, t):
        if self.ot_tie and self.c_ot[self.cur]:
            margin = 0.0
        super().update(h, a, neutral, margin, t)


def _miles(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_MILES * math.asin(math.sqrt(a))


def game_context(raw: Path, games: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Per-game context for GlickoContext from the raw CFBD files (all pregame facts: site,
    campuses, time zones, game type), plus the regulation-tie flag read from line scores."""
    venues = {v["id"]: (v.get("latitude"), v.get("longitude"))
              for v in json.loads((raw / "venues.json").read_text())}
    campus: dict[tuple[int, str], tuple] = {}
    raw_games: dict[int, dict] = {}
    for s in sorted(set(games["season"].astype(int))):
        tp = raw / f"teams_{s}.json"
        for t in (json.loads(tp.read_text()) if tp.exists() else []):
            loc = t.get("location") or {}
            off = None
            if loc.get("timezone"):
                off = datetime(s, 10, 1, 12, tzinfo=ZoneInfo(loc["timezone"])).utcoffset().total_seconds() / 3600
            campus[(s, t["school"])] = (loc.get("latitude"), loc.get("longitude"), off)
        for g in json.loads((raw / f"games_{s}.json").read_text()):
            raw_games[g["id"]] = g
    rows, missing = [], {"campus": 0, "venue": 0, "line_scores": 0}
    for gid, s, h, a, neutral, st, hd, ad in zip(games["game_id"], games["season"], games["home"],
                                                 games["away"], games["neutral"], games["season_type"],
                                                 games["home_div"], games["away_div"]):
        rg = raw_games.get(gid, {})
        ch, ca = campus.get((int(s), h)), campus.get((int(s), a))
        if ch is None or ca is None:
            missing["campus"] += 1
        dz = (ch[2] - ca[2]) if ch and ca and ch[2] is not None and ca[2] is not None else 0.0
        near = 0
        if neutral:
            v = venues.get(rg.get("venueId"))
            if v is None or v[0] is None:
                missing["venue"] += 1
            elif ch and ca and None not in (ch[0], ca[0]):
                dh, da = _miles(v[0], v[1], ch[0], ch[1]), _miles(v[0], v[1], ca[0], ca[1])
                near = (dh <= NEAR_MILES) - (da <= NEAR_MILES)
        hls, als = rg.get("homeLineScores") or [], rg.get("awayLineScores") or []
        if not hls or not als:
            missing["line_scores"] += 1
        rows.append({"season": int(s), "neutral": bool(neutral), "near": int(near), "dz": float(dz),
                     "k_game": st != "regular" or hd != ad, "ot": len(hls) > 4 or len(als) > 4})
    return pd.DataFrame(rows, index=games.index), missing
