"""Run GPA extraction on a single candidate under multiple LLM models.

Usage::

    uv run python scripts/compare_gpa_extraction.py \\
        --transcript /tmp/transcript_xxx.md \\
        --models google/gemini-3-flash-preview anthropic/claude-sonnet-4.6

Prints the structured ``GpaExtraction`` from each model side by side so
mismatches are obvious. Used to diagnose extractor failures before
deciding whether the fix is "swap model" or "fix prompt".
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

from agentic_admission.agents.gpa_extractor import extract_gpa


async def _run_one(
    transcript_text: str,
    model: str,
    *,
    base_url: str,
    api_key: str,
) -> dict[str, object]:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
        try:
            extraction = await extract_gpa(
                transcript_text, model=model, base_url=base_url, client=client,
            )
        except Exception as exc:  # noqa: BLE001 — diagnostic script, surface anything
            return {"error": f"{type(exc).__name__}: {exc}"}
    return json.loads(extraction.model_dump_json())


async def _run_all(
    transcript_text: str,
    models: list[str],
    *,
    base_url: str,
    api_key: str,
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for model in models:
        print(f"=== {model} ===", file=sys.stderr, flush=True)
        results[model] = await _run_one(
            transcript_text, model, base_url=base_url, api_key=api_key,
        )
    return results


def _print_side_by_side(results: dict[str, dict[str, object]]) -> None:
    """Print a flat key-by-key table comparing the models."""
    keys = sorted({k for r in results.values() for k in r})
    width = max((len(m) for m in results), default=10)
    header = "field".ljust(28) + "  " + "  ".join(m.ljust(width) for m in results)
    print(header)
    print("-" * len(header))
    for key in keys:
        row = key.ljust(28) + "  " + "  ".join(
            f"{results[m].get(key, '—')!s:<{width}}" for m in results
        )
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transcript",
        type=Path,
        required=True,
        help="Path to the candidate's concatenated transcript markdown.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        required=True,
        help="OpenRouter model IDs to test (e.g. google/gemini-3-flash-preview).",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MODEL_BASE_URL", "https://openrouter.ai/api/v1"),
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPENROUTER_API_KEY", ""),
    )
    args = parser.parse_args()

    transcript_text = args.transcript.read_text(encoding="utf-8")

    results = asyncio.run(
        _run_all(
            transcript_text,
            args.models,
            base_url=args.base_url,
            api_key=args.api_key,
        ),
    )

    print()
    _print_side_by_side(results)
    print()
    print("=== full JSON ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
