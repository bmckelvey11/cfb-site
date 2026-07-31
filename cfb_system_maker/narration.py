from __future__ import annotations

import os
from pathlib import Path

from cfb_system_maker.describe import describe
from cfb_system_maker.models import SearchRun

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_DEFAULT_TIMEOUT = 20.0


class NarrationError(Exception):
    """Raised whenever narration cannot be produced -- missing key, API error, timeout."""


def find_anthropic_key(env_path: str | Path = "env.env") -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]

    path = Path(env_path)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "ANTHROPIC_API_KEY":
                return value.strip()

    raise RuntimeError("ANTHROPIC_API_KEY not found in env or env.env")


def build_prompt(run: SearchRun) -> str:
    lines = [
        "Summarize this college football betting system search run in plain English, "
        "2-4 short sentences. Be neutral and factual -- do not recommend betting real "
        "money or imply guaranteed future performance.",
        "",
        f"Candidates tested: {run.candidates_tested}",
        f"Finalists graded on holdout data: {run.finalists_graded}",
        f"Search params: {run.effective_params}",
        "",
    ]
    if not run.finalists:
        lines.append("No finalist survived holdout grading.")
        return "\n".join(lines)

    lines.append("Finalists (ranked, holdout results):")
    for i, finalist in enumerate(run.finalists, start=1):
        decided = finalist.wins + finalist.losses
        sentences = [row["text"] for row in describe(finalist.system)]
        filters_text = "; ".join(sentences) if sentences else "no filters (all games)"
        lines.append(
            f"{i}. {filters_text} -- holdout record {finalist.wins}-{finalist.losses}-{finalist.pushes} "
            f"({decided} decided), roi={finalist.roi:.4f}, raw_p={finalist.raw_p:.4f}, "
            f"corrected_p={finalist.corrected_p:.4f}, bh_significant={finalist.bh_significant}"
        )
    return "\n".join(lines)


def narrate_run(
    run: SearchRun,
    *,
    client=None,
    api_key: str | None = None,
    model: str = _DEFAULT_MODEL,
    timeout: float = _DEFAULT_TIMEOUT,
) -> str:
    """Exactly one API call. Any failure -- missing key, network, API error -- raises NarrationError."""
    prompt = build_prompt(run)

    if client is None:
        try:
            import anthropic  # noqa: PLC0415

            key = api_key or find_anthropic_key()
            client = anthropic.Anthropic(api_key=key, timeout=timeout)
        except Exception as exc:
            raise NarrationError(f"could not create Anthropic client: {exc}") from exc

    try:
        message = client.messages.create(
            model=model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in message.content if hasattr(block, "text"))
    except Exception as exc:
        raise NarrationError(f"narration call failed: {exc}") from exc

    if not text.strip():
        raise NarrationError("narration returned no text")
    return text
