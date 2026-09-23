"""The feature catalog and its availability rules (plan §27.5). No pandas, so it imports fast.

`features` re-exports everything here; `screen_features` applies it to a loaded frame.
"""
from __future__ import annotations

from typing import NamedTuple

from models.tuning.spec import AvailabilityClass

ELIGIBLE = "historical_replayable"
REFUSED = {
    "snapshot_dependent": "snapshot_dependent: no snapshot-coverage check exists yet",
    "prospective_only": "prospective_only: shadow/live only, not reconstructible historically",
    "retrospective_descriptive": "retrospective_descriptive: known after kickoff, blocked from prediction",
    "provider_opaque": "provider_opaque: benchmark-only until its timing is audited",
}


class CatalogEntry(NamedTuple):
    version: int
    availability_class: AvailabilityClass
    description: str


CATALOG: dict[str, CatalogEntry] = {
    "rv1_off_home": CatalogEntry(1, "historical_replayable", "ridge_v1 offense O, home team, as of the week cutoff"),
    "rv1_def_home": CatalogEntry(1, "historical_replayable", "ridge_v1 defense D, home team, as of the week cutoff"),
    "rv1_pace_home": CatalogEntry(1, "historical_replayable", "ridge_v1 pace P, home team, as of the week cutoff"),
    "rv1_off_away": CatalogEntry(1, "historical_replayable", "ridge_v1 offense O, away team, as of the week cutoff"),
    "rv1_def_away": CatalogEntry(1, "historical_replayable", "ridge_v1 defense D, away team, as of the week cutoff"),
    "rv1_pace_away": CatalogEntry(1, "historical_replayable", "ridge_v1 pace P, away team, as of the week cutoff"),
    "rv1_total": CatalogEntry(1, "historical_replayable", "forecast_total from the ridge_v1 snapshot"),
    "min_prior_games": CatalogEntry(1, "historical_replayable", "fewer of the two teams' games in the snapshot"),
    "neutral": CatalogEntry(1, "historical_replayable", "neutral-site flag from the schedule, known before the cutoff"),
    "open_total": CatalogEntry(1, "provider_opaque", "Bovada overUnderOpen: no capture time, no price"),
}
