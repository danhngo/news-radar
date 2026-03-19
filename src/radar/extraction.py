"""Signal extraction using Claude CLI (batch, semaphore)."""

from __future__ import annotations

import asyncio
import json
import re
import subprocess

from .models import ExtractedSignal, RawSignal


EXTRACTION_PROMPT = """You are an AI news analyst. Given the following batch of signals, extract structured information for each.

For each signal, return a JSON object with:
- "signal_id": the provided ID
- "title": cleaned, concise title
- "summary": 1-2 sentence summary of significance
- "entities": list of key entities (companies, models, people, technologies)
- "category": one of "research", "product", "ecosystem", "startup", "events"
- "novelty": float 0.0-1.0 (how novel/surprising is this?)

Return a JSON array of objects. Only output valid JSON, no other text.

SIGNALS:
{signals_text}"""


async def extract_batch(
    signals: list[RawSignal],
    batch_size: int = 15,
    max_concurrent: int = 5,
) -> list[ExtractedSignal]:
    """Extract structured info from signals using Claude CLI in batches."""
    semaphore = asyncio.Semaphore(max_concurrent)
    batches = [signals[i:i + batch_size] for i in range(0, len(signals), batch_size)]

    tasks = [_extract_one_batch(batch, semaphore) for batch in batches]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    extracted: list[ExtractedSignal] = []
    for result in results:
        if isinstance(result, list):
            extracted.extend(result)
    return extracted


async def _extract_one_batch(
    batch: list[RawSignal],
    semaphore: asyncio.Semaphore,
) -> list[ExtractedSignal]:
    async with semaphore:
        signals_text = "\n---\n".join(
            f"ID: {s.id}\nSource: {s.source}\nTitle: {s.title}\nBody: {s.body[:500]}\nURL: {s.url}"
            for s in batch
        )
        prompt = EXTRACTION_PROMPT.format(signals_text=signals_text)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _call_claude, prompt)

        return _parse_extraction_response(result, {s.id: s for s in batch})


def _call_claude(prompt: str) -> str:
    """Call Claude CLI via subprocess."""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "haiku", "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return ""
        # Parse the JSON output from Claude CLI
        try:
            output = json.loads(result.stdout)
            # Claude CLI JSON format returns result in a "result" field
            if isinstance(output, dict) and "result" in output:
                return output["result"]
            return result.stdout
        except json.JSONDecodeError:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _parse_extraction_response(
    response: str, signal_map: dict[str, RawSignal]
) -> list[ExtractedSignal]:
    """Parse Claude's JSON response into ExtractedSignal objects."""
    if not response:
        return _fallback_extraction(signal_map)

    # Try to extract JSON from response (handle markdown fences)
    json_str = response.strip()
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", json_str, re.DOTALL)
    if fence_match:
        json_str = fence_match.group(1).strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # Try to find array in response
        array_match = re.search(r"\[.*\]", json_str, re.DOTALL)
        if array_match:
            try:
                data = json.loads(array_match.group())
            except json.JSONDecodeError:
                return _fallback_extraction(signal_map)
        else:
            return _fallback_extraction(signal_map)

    if not isinstance(data, list):
        data = [data]

    results: list[ExtractedSignal] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        sid = item.get("signal_id", "")
        raw = signal_map.get(sid)
        category = item.get("category", "ecosystem")
        if category not in ("research", "product", "ecosystem", "startup", "events"):
            category = "ecosystem"

        results.append(ExtractedSignal(
            signal_id=sid,
            title=item.get("title", raw.title if raw else ""),
            summary=item.get("summary", ""),
            entities=item.get("entities", []),
            category=category,
            novelty=max(0.0, min(1.0, float(item.get("novelty", 0.5)))),
            raw=raw,
        ))

    return results


def _fallback_extraction(signal_map: dict[str, RawSignal]) -> list[ExtractedSignal]:
    """Fallback: create basic extractions from raw signals when Claude fails."""
    results: list[ExtractedSignal] = []
    for sid, raw in signal_map.items():
        # Guess category from source
        category = "ecosystem"
        if raw.source == "arxiv":
            category = "research"
        elif raw.source == "github":
            category = "product"

        results.append(ExtractedSignal(
            signal_id=sid,
            title=raw.title,
            summary=raw.body[:200] if raw.body else raw.title,
            entities=[],
            category=category,
            novelty=0.5,
            raw=raw,
        ))
    return results
