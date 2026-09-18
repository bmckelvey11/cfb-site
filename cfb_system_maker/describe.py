from __future__ import annotations

from collections import OrderedDict

from cfb_system_maker.features import FEATURE_BY_KEY, format_kickoff_hour
from cfb_system_maker.models import FeatureFilter, SystemFilter

PERSPECTIVE_PREFIX: dict[str, str] = {
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
    fmt=_fmt_num,
) -> dict[str, object] | None:
    if minimum is None and maximum is None:
        return None
    if minimum is not None and maximum is not None and minimum == maximum:
        text = f"{label} is exactly {fmt(minimum)}"
    elif minimum is not None and maximum is not None:
        text = f"{label} is between {fmt(minimum)} and {fmt(maximum)}"
    elif minimum is not None:
        text = f"{label} is at least {fmt(minimum)}"
    else:
        text = f"{label} is at most {fmt(maximum)}"
    return {"text": text, "key": key}


def group_is_renderable(filts: list[FeatureFilter], control: str) -> bool:
    """True only if the WHOLE group matches a shape the hand-written branches
    can round-trip. Partial coverage (e.g. one renderable filter alongside an
    uncovered one, or two filters that would each render but collide, like
    eq=True + eq=False) must fall back — never drop a sibling filter silently.
    """
    if control == "numeric":
        ops = [filt.op for filt in filts]
        return all(op in ("gte", "lte") for op in ops) and len(ops) == len(set(ops))
    if control == "bool":
        return len(filts) == 1 and filts[0].op in ("eq", "not_eq")
    if control == "categorical":
        return len(filts) == 1 and filts[0].op in ("eq", "not_eq", "in", "not_in")
    return False


def _feature_group_sentence(filts: list[FeatureFilter]) -> dict[str, object] | None:
    key = filts[0].key
    perspective = filts[0].perspective
    feature = FEATURE_BY_KEY.get(key)
    # Sentence key carries the perspective so each (key, perspective) group gets
    # its own Edit/Remove: a system can constrain the bet-side team and its
    # opponent on the SAME stat, and those must be independently removable.
    # "single" stays bare for backward compatibility with existing links.
    sentence_key = f"ff:{key}"
    if feature is None:
        return {"text": f'Unknown filter "{key}" is unavailable', "key": sentence_key}
    # Only team-scoped features can carry more than one perspective group, so
    # only they need a per-perspective sentence key. Everything else keeps the
    # bare "ff:{key}" it has always had.
    if feature.team_scoped and perspective != "single":
        sentence_key = f"ff:{key}@{perspective}"

    if feature.team_scoped and perspective in PERSPECTIVE_PREFIX:
        label = f"{PERSPECTIVE_PREFIX[perspective]} {feature.label}"
    else:
        label = feature.label

    if group_is_renderable(filts, feature.control):
        if feature.control == "numeric":
            gte = next((float(filt.value) for filt in filts if filt.op == "gte"), None)
            lte = next((float(filt.value) for filt in filts if filt.op == "lte"), None)
            fmt = format_kickoff_hour if feature.key == "kickoff_hour" else _fmt_num
            return _labeled_range_sentence(gte, lte, label=label, key=sentence_key, fmt=fmt)
        filt = filts[0]
        if filt.op == "eq" and feature.control == "bool":
            text = f"{label} is {'Yes' if filt.value else 'No'}"
        elif filt.op == "not_eq" and feature.control == "bool":
            text = f"{label} is not {'Yes' if filt.value else 'No'}"
        elif filt.op == "eq" and feature.control == "categorical":
            text = f"{label} is {filt.value}"
        elif filt.op == "not_eq" and feature.control == "categorical":
            text = f"{label} is not {filt.value}"
        elif filt.op == "not_in" and feature.control == "categorical":
            text = f"{label} is not one of {', '.join(filt.value)}"
        else:  # op == "in" and feature.control == "categorical"
            text = f"{label} is one of {', '.join(filt.value)}"
        return {"text": text, "key": sentence_key}

    # Fallback: the group doesn't match a shape the branches above can
    # round-trip (uncovered op/control combo, or multiple filters that would
    # each individually render but can't be coalesced into one sentence
    # without dropping one). Deliberately distinct wording (never blends in)
    # and joins every filter's value so nothing in the group vanishes.
    values = ", ".join(repr(filt.value) for filt in filts)
    return {"text": f"{label} filter applied (value: {values})", "key": sentence_key}


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

    for values, noun, key in (
        (system.exclude_seasons, "season", "exclude_seasons"),
        (system.exclude_weeks, "week", "exclude_weeks"),
        (system.exclude_teams, "team", "exclude_teams"),
        (system.exclude_conferences, "conference", "exclude_conferences"),
        (system.exclude_providers, "provider", "exclude_providers"),
    ):
        if values:
            joined = ", ".join(str(v) for v in sorted(values))
            sentences.append({"text": f"the {noun} is not {joined}", "key": key})

    groups: OrderedDict[tuple[str, str], list[FeatureFilter]] = OrderedDict()
    for filt in system.feature_filters:
        groups.setdefault((filt.key, filt.perspective), []).append(filt)

    for filts in groups.values():
        sentence = _feature_group_sentence(filts)
        if sentence is not None:
            sentences.append(sentence)

    return sentences
