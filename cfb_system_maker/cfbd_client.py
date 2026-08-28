from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def fetch_games_and_lines(
    seasons: list[int],
    *,
    season_type: str = "both",
    provider: str | None = None,
    token: str | None = None,
) -> dict[int, dict[str, list[dict[str, Any]]]]:
    cfbd = _load_cfbd_module()
    access_token = token or find_cfbd_token()
    configuration = cfbd.Configuration(access_token=access_token)

    results: dict[int, dict[str, list[dict[str, Any]]]] = {}
    with cfbd.ApiClient(configuration) as api_client:
        games_api = cfbd.GamesApi(api_client)
        betting_api = cfbd.BettingApi(api_client)
        for season in seasons:
            games = games_api.get_games(year=season, season_type=season_type)
            lines = betting_api.get_lines(year=season, season_type=season_type, provider=provider)
            results[season] = {
                "games": [_to_dict(game) for game in games],
                "lines": [_to_dict(line) for line in lines],
            }
    return results


def find_cfbd_token(env_path: str | Path = "env.env") -> str:
    for key in ("CFBD_API_KEY", "CFBD-API", "BEARER_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]

    path = Path(env_path)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in {"CFBD_API_KEY", "CFBD-API", "BEARER_TOKEN"}:
                return value.strip()

    raise RuntimeError("CFBD API token not found in env or env.env")


def _load_cfbd_module():
    repo_client = Path(__file__).resolve().parents[1] / "cfbd-python"
    if repo_client.exists():
        sys.path.insert(0, str(repo_client))

    import cfbd  # noqa: PLC0415

    return cfbd


def _to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "dict"):
        return model.dict(by_alias=True)
    if hasattr(model, "model_dump"):
        return model.model_dump(by_alias=True)
    if isinstance(model, dict):
        return model
    return dict(model)

