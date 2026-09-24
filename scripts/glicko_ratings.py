"""Glicko-style margin ratings, with Elo-MOV and Glicko-1 baselines on the same clock.

    M_hat = r_home - r_away + H (1 - neutral),    S = u_home^2 + u_away^2 + sigma^2

Each team carries a mean r (neutral-field points) and a variance u^2. A game's capped
margin moves both teams by their Kalman gains u^2 / S. Inside a season the variance
grows by tau^2 per idle week; each offseason pulls r toward its subdivision's mean
(weight w) and adds delta^2. Win probability is Phi(M_hat / sqrt(S)).

Clock: every game is forecast at its week's cutoff (the week's earliest kickoff) from
games that kicked off strictly before it, and its result updates the state at its own
kickoff -- Release B's rule, stricter than per-game, and close to the open's information.

See docs/superpowers/specs/2026-09-24-glicko-ratings-design.md.
"""
from __future__ import annotations

import math

import pandas as pd

VERSION = "1.0"
FBS, FCS = "fbs", "fcs"
# Picks frozen by the one scoring run (docs/glicko-ratings-2026-09-24.md). The FCS seed m0 is
# not frozen here: glicko_ratings_eval.fcs_seed recomputes it from the 2013 burn-in games.
FROZEN_V1 = {"sigma": 13, "tau": 0.75, "w": 0.9, "delta": 6, "cap": float("inf"),
             "hfa": 2.75, "u0": 14}
# P1 (docs/glicko-pool-2026-09-24.md): adopted variant `pool_conf`, frozen by its one scoring
# run. Superseded v1 as the descriptive/weekly-table base. Its game set is glicko_pool_eval's
# load_pool_games (every completed D-I game, not just games.csv's lined ones), and its FCS
# seed comes from glicko_pool_eval.fcs_seed_pool, run with home_conf/away_conf present so the
# conference-mean offseason target is used.
FROZEN_P1 = {"sigma": 15, "tau": 1.5, "w": 0.7, "delta": 6, "cap": float("inf"),
            "hfa": 2, "u0": 14}
_EPOCH = pd.Timestamp("1970-01-01", tz="UTC")


def to_home_margin(spread: float) -> float:
    """A spread (negative = home favoured) as a home margin (positive = home favoured)."""
    return -spread


# --- clock ----------------------------------------------------------------------

def events(games: pd.DataFrame) -> list[tuple]:
    """Forecast events at week cutoffs and update events at kickoffs, time-ordered.

    `games` needs season, season_type, week, kickoff (UTC). Times are in days. At equal
    times a forecast sorts first, so a game tied at a cutoff never informs that week.
    Forecast: (t, 0, season, ((season, season_type, week), [row positions])).
    Update:   (t, 1, season, row position).
    """
    t = ((games["kickoff"] - _EPOCH).dt.total_seconds() / 86_400.0).tolist()
    season = games["season"].astype(int).tolist()
    keys = list(zip(season, games["season_type"], games["week"].astype(int)))
    groups: dict[tuple, list[int]] = {}
    for i, k in enumerate(keys):
        groups.setdefault(k, []).append(i)
    ev = [(min(t[i] for i in idx), 0, k[0], (k, idx)) for k, idx in groups.items()]
    ev += [(t[i], 1, season[i], i) for i in range(len(t))]
    ev.sort(key=lambda e: (e[0], e[1]))
    return ev


def run(model, games: pd.DataFrame, ev: list[tuple], snaps: list | None = None) -> pd.DataFrame:
    """Replay `ev` through `model`; one forecast row per game, taken at its week's cutoff.

    `games` needs home, away, neutral, margin, home_div, away_div, and optionally home_conf,
    away_conf (pool rung P1 only -- omitting them reproduces v1 exactly). With `snaps` (a
    list), regular-season cutoffs append the state of every rated team (GlickoMargin only).
    """
    home, away = games["home"].tolist(), games["away"].tolist()
    neutral, margin = games["neutral"].tolist(), games["margin"].tolist()
    hdiv, adiv = games["home_div"].tolist(), games["away_div"].tolist()
    n = len(games)
    hconf = games["home_conf"].tolist() if "home_conf" in games.columns else [None] * n
    aconf = games["away_conf"].tolist() if "away_conf" in games.columns else [None] * n
    rows: list[tuple] = []
    season = None
    for t, kind, s, x in ev:
        if s != season:
            if season is not None:
                model.season_start(season, t)
            season = s
        if kind == 0:
            key, idx = x
            for i in idx:
                model.enter(home[i], hdiv[i], t, hconf[i])
                model.enter(away[i], adiv[i], t, aconf[i])
                rows.append((i, *model.forecast(home[i], away[i], neutral[i], t)))
            if snaps is not None and key[1] == "regular":
                snaps += [(key[0], key[2], t, k, *model.state(k)) for k in model.r]
        else:
            model.update(home[x], away[x], neutral[x], margin[x], t)
            model.played(home[x], hdiv[x], s, hconf[x])
            model.played(away[x], adiv[x], s, aconf[x])
    out = pd.DataFrame(rows, columns=["row", *model.COLS]).set_index("row").sort_index()
    return out


# --- models ---------------------------------------------------------------------

class _Teams:
    """Who is rated, their subdivision, and the means new teams enter at.

    A team's `conf` is optional (pool rung P1 only; v1 never passes one). `_target` picks a
    team's conference mean when one has been observed, else its subdivision mean, so passing
    no conference reproduces v1 exactly -- test_glicko_ratings.py pins that.
    """

    def __init__(self, seed: dict[str, float]):
        self.r: dict[str, float] = {}
        self.div: dict[str, str] = {}
        self.conf: dict[str, str | None] = {}
        self.last: dict[str, int] = {}
        self.n: dict[str, int] = {}
        self.mean = dict(seed)
        self.conf_mean: dict[str, float] = {}

    def _target(self, div: str, conf: str | None) -> float:
        if conf is not None and conf in self.conf_mean:
            return self.conf_mean[conf]
        return self.mean[div]

    def enter(self, k: str, div: str, t: float, conf: str | None = None) -> None:
        if k not in self.r:
            self.conf[k] = conf
            self.r[k], self.div[k], self.n[k] = self._target(div, conf), div, 0
            self._new(k, t)

    def played(self, k: str, div: str, season: int, conf: str | None = None) -> None:
        self.div[k], self.last[k] = div, season
        if conf is not None:
            self.conf[k] = conf
        self.n[k] += 1

    def season_start(self, ended: int, t: float) -> None:
        """Means are taken over teams that played in `ended`, before anyone regresses."""
        for c in self.mean:
            vals = [self.r[k] for k in self.r if self.div[k] == c and self.last.get(k) == ended]
            if vals:
                self.mean[c] = sum(vals) / len(vals)
        groups: dict[str, list[float]] = {}
        for k in self.r:
            c = self.conf.get(k)
            if c is not None and self.last.get(k) == ended:
                groups.setdefault(c, []).append(self.r[k])
        for c, vals in groups.items():
            self.conf_mean[c] = sum(vals) / len(vals)
        for k in self.r:
            self.n[k] = 0
            self._offseason(k, t)

    def _new(self, k: str, t: float) -> None:
        pass

    def _offseason(self, k: str, t: float) -> None:
        raise NotImplementedError


class GlickoMargin(_Teams):
    """`glicko_margin_v1`: Gaussian team state updated from capped margins."""

    COLS = ("mhat", "S", "rd2")

    def __init__(self, sigma, tau, w, delta, cap, hfa, u0, m0):
        super().__init__({FBS: 0.0, FCS: m0})
        self.sigma2, self.tau2, self.w, self.delta2 = sigma ** 2, tau ** 2, w, delta ** 2
        self.cap, self.hfa, self.u02 = cap, hfa, u0 ** 2
        self.u2: dict[str, float] = {}
        self.tl: dict[str, float] = {}

    def _new(self, k, t):
        self.u2[k], self.tl[k] = self.u02, t

    def _advance(self, k, t):
        if t > self.tl[k]:
            self.u2[k] += self.tau2 * (t - self.tl[k]) / 7.0
            self.tl[k] = t

    def forecast(self, h, a, neutral, t):
        self._advance(h, t)
        self._advance(a, t)
        rd2 = self.u2[h] + self.u2[a]
        return self.r[h] - self.r[a] + (0.0 if neutral else self.hfa), rd2 + self.sigma2, rd2

    def update(self, h, a, neutral, margin, t):
        mhat, s, _ = self.forecast(h, a, neutral, t)
        e = max(-self.cap, min(self.cap, margin)) - mhat
        kh, ka = self.u2[h] / s, self.u2[a] / s
        self.r[h] += kh * e
        self.r[a] -= ka * e
        self.u2[h] *= 1.0 - kh
        self.u2[a] *= 1.0 - ka

    def _offseason(self, k, t):
        self.r[k] = self.w * self.r[k] + (1.0 - self.w) * self._target(self.div[k], self.conf.get(k))
        self.u2[k] += self.delta2
        self.tl[k] = t

    def state(self, k):
        return self.div[k], self.r[k], math.sqrt(self.u2[k]), self.n[k]


class EloMov(_Teams):
    """`elo_mov`: Elo with a log margin-of-victory multiplier. Points = b x diff, fit later."""

    COLS = ("elo_diff", "elo_p")

    def __init__(self, k, hfa, w, m0):
        super().__init__({FBS: 1500.0, FCS: 1500.0 + 25.0 * m0})
        self.k, self.hfa, self.w = k, hfa, w

    def forecast(self, h, a, neutral, t):
        d = self.r[h] - self.r[a] + (0.0 if neutral else self.hfa)
        return d, 1.0 / (1.0 + 10.0 ** (-d / 400.0))

    def update(self, h, a, neutral, margin, t):
        d, p = self.forecast(h, a, neutral, t)
        o = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        dw = d if margin >= 0 else -d                 # winner minus loser, home edge in
        step = self.k * math.log(abs(margin) + 1.0) * 2.2 / (0.001 * dw + 2.2) * (o - p)
        self.r[h] += step
        self.r[a] -= step

    def _offseason(self, k, t):
        self.r[k] = self.w * self.r[k] + (1.0 - self.w) * self.mean[self.div[k]]


_Q = math.log(10.0) / 400.0
_RD_MAX2 = 350.0 ** 2


def _g(rd2: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * _Q * _Q * rd2 / math.pi ** 2)


class Glicko1(_Teams):
    """`glicko1`: Glickman (1999), one game per rating period, win/loss only."""

    COLS = ("g1_p",)

    def __init__(self, c, delta, hfa, w, m0):
        super().__init__({FBS: 1500.0, FCS: 1500.0 + 25.0 * m0})
        self.c2, self.delta2, self.hfa, self.w = c ** 2, delta ** 2, hfa, w
        self.rd2: dict[str, float] = {}
        self.tl: dict[str, float] = {}

    def _new(self, k, t):
        self.rd2[k], self.tl[k] = _RD_MAX2, t

    def _advance(self, k, t):
        if t > self.tl[k]:
            self.rd2[k] = min(self.rd2[k] + self.c2 * (t - self.tl[k]) / 7.0, _RD_MAX2)
            self.tl[k] = t

    def forecast(self, h, a, neutral, t):
        self._advance(h, t)
        self._advance(a, t)
        d = self.r[h] - self.r[a] + (0.0 if neutral else self.hfa)
        return (1.0 / (1.0 + 10.0 ** (-_g(self.rd2[h] + self.rd2[a]) * d / 400.0)),)

    def update(self, h, a, neutral, margin, t):
        self.forecast(h, a, neutral, t)
        o = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        rh = self.r[h] + (0.0 if neutral else self.hfa)
        ra, rd2h, rd2a = self.r[a], self.rd2[h], self.rd2[a]
        for k, mine, opp, rd2_me, rd2_opp, s in ((h, rh, ra, rd2h, rd2a, o),
                                                 (a, ra, rh, rd2a, rd2h, 1.0 - o)):
            g = _g(rd2_opp)
            e = 1.0 / (1.0 + 10.0 ** (-g * (mine - opp) / 400.0))
            new_rd2 = 1.0 / (1.0 / rd2_me + _Q * _Q * g * g * e * (1.0 - e))
            self.r[k] += _Q * new_rd2 * g * (s - e)
            self.rd2[k] = new_rd2

    def _offseason(self, k, t):
        self.r[k] = self.w * self.r[k] + (1.0 - self.w) * self.mean[self.div[k]]
        self.rd2[k] = min(self.rd2[k] + self.delta2, _RD_MAX2)
        self.tl[k] = t
