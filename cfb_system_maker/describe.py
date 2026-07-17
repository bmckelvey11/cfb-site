from __future__ import annotations

from collections import OrderedDict

from cfb_system_maker.features import FEATURE_BY_KEY
from cfb_system_maker.models import FeatureFilter, SystemFilter

_PERSPECTIVE_PREFIX: dict[str, str] = {
    "home": "Home",
    "away": "Away",
    "bet_side": "Bet-side",
    "opponent": "Opponent",
    "either": "Either team's",
}


def _fmt_num(value: float) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric)


def _range_sentence(minimum: float | None, maximum: float | None, *, noun: str, key: str) -> dict[str, object] | None:
    if minimum is None and maximum is None:
        return None
    if minimum is not None and maximum is not None and minimum == maximum:
        text = f"the {noun} is exactly {_fmt_num(minimum)}"
    elif minimum is not None and maximum is not None:
        text = f"the {noun} is between {_fmt_num(minimum)} and {_fmt_num(maximum)}"
    elif minimum is not None:
        text = f"the {noun} is at least {_fmt_num(minimum)}"
    else:
        text = f"the {noun} is at most {_fmt_num(maximum)}"
    return {"text": text, "key": key}


def _labeled_range_sentence(
    minimum: float | None,
    maximum: float | None,
    *,
    label: str,
    key: str,
) -> dict[str, object] | None:
    if minimum is None and maximum is None:
        return None
    if minimum is not None and maximum is not None and minimum == maximum:
        text = f"{label} is exactly {_fmt_num(minimum)}"
    elif minimum is not None and maximum is not None:
        text = f"{label} is between {_fmt_num(minimum)} and {_fmt_num(maximum)}"
    elif minimum is not None:
        text = f"{label} is at least {_fmt_num(minimum)}"
    else:
        text = f"{label} is at most {_fmt_num(maximum)}"
    return {"text": text, "key": key}


def _feature_group_sentence(filts: list[FeatureFilter]) -> dict[str, object] | None:
    key = filts[0].key
    perspective = filts[0].perspective
    feature = FEATURE_BY_KEY.get(key)
    if feature is None:
        return {"text": f'Unknown filter "{key}" is unavailable', "key": f"ff:{key}"}

    if feature.team_scoped and perspective in _PERSPECTIVE_PREFIX:
        label = f"{_PERSPECTIVE_PREFIX[perspective]} {feature.label}"
    else:
        label = feature.label

    if feature.control == "numeric":
        gte = next((float(filt.value) for filt in filts if filt.op == "gte"), None)
        lte = next((float(filt.value) for filt in filts if filt.op == "lte"), None)
        return _labeled_range_sentence(gte, lte, label=label, key=f"ff:{key}")

    # Bool / categorical: one sentence per filter (existing wording)
    for filt in filts:
        text: str | None = None
        if filt.op == "eq" and feature.control == "bool":
            text = f"{label} is {'Yes' if filt.value else 'No'}"
        elif filt.op == "eq" and feature.control == "categorical":
            text = f"{label} is {filt.value}"
        elif filt.op == "in" and feature.control == "categorical":
            text = f"{label} is one of {', '.join(filt.value)}"
        if text is not None:
            return {"text": text, "key": f"ff:{key}"}
    return None


def describe(system: SystemFilter) -> list[dict[str, object]]:
    sentences: list[dict[str, object]] = []

    if system.bet_type == "spread":
        if system.favorite:
            sentences.append({"text": "the team is a favorite", "key": "favorite"})
        if system.underdog:
            sentences.append({"text": "the team is an underdog", "key": "underdog"})

    if system.home:
        sentences.append({"text": "home games only", "key": "home"})
    if system.away:
        sentences.append({"text": "away games only", "key": "away"})

    if system.bet_type == "spread":
        spread_sentence = _range_sentence(system.min_spread, system.max_spread, noun="spread", key="spread_range")
        if spread_sentence is not None:
            sentences.append(spread_sentence)

    total_sentence = _range_sentence(system.min_total, system.max_total, noun="total", key="total_range")
    if total_sentence is not None:
        sentences.append(total_sentence)

    for values, noun, key in (
        (system.seasons, "season", "seasons"),
        (system.weeks, "week", "weeks"),
        (system.teams, "team", "teams"),
        (system.conferences, "conference", "conferences"),
        (system.providers, "provider", "providers"),
    ):
        if values:
            joined = ", ".join(str(v) for v in sorted(values))
            sentences.append({"text": f"the {noun} is {joined}", "key": key})

    groups: OrderedDict[tuple[str, str], list[FeatureFilter]] = OrderedDict()
    for filt in system.feature_filters:
        groups.setdefault((filt.key, filt.perspective), []).append(filt)

    for filts in groups.values():
        sentence = _feature_group_sentence(filts)
        if sentence is not None:
            sentences.append(sentence)

    return sentences
