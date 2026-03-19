"""Lane balancing: guarantee min per lane, fill remaining by score."""

from __future__ import annotations

from .models import ScoredSignal


def balance_signals(
    scored: list[ScoredSignal],
    config: dict,
) -> list[ScoredSignal]:
    """Select final signals with lane balance guarantees."""
    lanes_cfg = config.get("lanes", {})
    pipeline_cfg = config.get("pipeline", {})
    max_total = pipeline_cfg.get("max_briefing_signals", 10)
    min_total = pipeline_cfg.get("min_briefing_signals", 5)

    # Group by lane
    by_lane: dict[str, list[ScoredSignal]] = {}
    for s in scored:
        by_lane.setdefault(s.lane, []).append(s)

    # Sort each lane by composite score
    for lane in by_lane:
        by_lane[lane].sort(key=lambda s: s.composite_score, reverse=True)

    selected: list[ScoredSignal] = []
    remaining: list[ScoredSignal] = []

    # Phase 1: Fill minimums per lane
    for lane_key, lane_cfg in lanes_cfg.items():
        lane_min = lane_cfg.get("min", 0)
        lane_signals = by_lane.get(lane_key, [])
        for s in lane_signals[:lane_min]:
            selected.append(s)
        remaining.extend(lane_signals[lane_min:])

    # Phase 2: Fill remaining slots by composite score, respecting max per lane
    remaining.sort(key=lambda s: s.composite_score, reverse=True)

    lane_counts: dict[str, int] = {}
    for s in selected:
        lane_counts[s.lane] = lane_counts.get(s.lane, 0) + 1

    for s in remaining:
        if len(selected) >= max_total:
            break
        lane_max = lanes_cfg.get(s.lane, {}).get("max", 3)
        current = lane_counts.get(s.lane, 0)
        if current < lane_max:
            selected.append(s)
            lane_counts[s.lane] = current + 1

    # Ensure at least min_total signals
    if len(selected) < min_total:
        already_ids = {s.signal.signal_id for s in selected}
        for s in scored:
            if len(selected) >= min_total:
                break
            if s.signal.signal_id not in already_ids:
                selected.append(s)
                already_ids.add(s.signal.signal_id)

    # Final sort by composite score
    selected.sort(key=lambda s: s.composite_score, reverse=True)
    return selected
