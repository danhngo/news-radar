"""Pipeline orchestrator: collect → extract → cluster → score → balance → output."""

from __future__ import annotations

import asyncio
from datetime import datetime

import click

from . import db
from .balancer import balance_signals
from .clustering import cluster_signals
from .collectors import (
    ArxivCollector,
    GitHubCollector,
    HackerNewsCollector,
    RedditCollector,
    RSSCollector,
)
from .config import get_config
from .extraction import extract_batch
from .models import RawSignal
from .output import generate_briefing
from .scoring import score_clusters


def _get_extractions(date: str) -> list:
    """Get extractions for a date, falling back to recent if none match."""
    extractions = db.get_extractions_for_date(date)
    if not extractions:
        extractions = db.get_recent_extractions(limit=1000)
    return extractions


COLLECTOR_CLASSES = [
    HackerNewsCollector,
    RedditCollector,
    ArxivCollector,
    GitHubCollector,
    RSSCollector,
]


async def run_collect(config: dict) -> list[RawSignal]:
    """Stage 1: Collect raw signals from all sources."""
    collectors = [cls(config) for cls in COLLECTOR_CLASSES]
    tasks = [c.collect() for c in collectors]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_signals: list[RawSignal] = []
    for i, result in enumerate(results):
        name = collectors[i].source_name
        if isinstance(result, Exception):
            click.echo(f"  [{name}] Error: {result}")
        else:
            click.echo(f"  [{name}] Collected {len(result)} signals")
            all_signals.extend(result)

    return all_signals


async def run_extract(config: dict, signal_ids: set[str] | None = None) -> tuple[int, list[ExtractedSignal]]:
    """Stage 2: Extract structured info from unprocessed signals."""
    signals = db.get_unextracted_signals(limit=1000)
    if not signals:
        click.echo("  No unextracted signals found")
        # Return existing extractions for the collected signal IDs
        if signal_ids:
            return 0, db.get_extractions_by_ids(signal_ids)
        return 0, []

    batch_size = config.get("pipeline", {}).get("batch_size", 15)
    max_concurrent = config.get("pipeline", {}).get("max_concurrent_extractions", 5)

    click.echo(f"  Extracting {len(signals)} signals (batch_size={batch_size}, concurrency={max_concurrent})")
    extracted = await extract_batch(signals, batch_size=batch_size, max_concurrent=max_concurrent)
    db.upsert_extractions(extracted)

    # Return extractions matching the collected signal IDs
    if signal_ids:
        all_extracted = db.get_extractions_by_ids(signal_ids)
    else:
        all_extracted = extracted
    return len(extracted), all_extracted


async def run_pipeline(date: str | None = None, extra_topics: list[str] | None = None) -> None:
    """Run the full pipeline."""
    config = get_config()

    # Merge extra topics into scoring config
    if extra_topics:
        scoring = config.setdefault("scoring", {})
        core = scoring.setdefault("core_topics", [])
        for t in extra_topics:
            if t.lower() not in [c.lower() for c in core]:
                core.append(t)
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    db.init_db()

    click.echo(f"\n=== AI Intelligence Radar — {target_date} ===\n")
    if extra_topics:
        click.echo(f"  Boosted topics: {', '.join(extra_topics)}\n")

    # Stage 1: Collect
    click.echo("[1/6] Collecting signals...")
    signals = await run_collect(config)
    total_collected = len(signals)
    inserted = db.upsert_signals(signals)
    collected_ids = {s.id for s in signals}
    click.echo(f"  Total: {total_collected} collected, {inserted} new\n")

    # Stage 2: Extract
    click.echo("[2/6] Extracting signals...")
    total_extracted, extractions = await run_extract(config, signal_ids=collected_ids)
    click.echo(f"  Extracted: {total_extracted} new, {len(extractions)} total for this run\n")

    # Stage 3: Cluster
    click.echo("[3/6] Clustering signals...")

    threshold = config.get("pipeline", {}).get("clustering_threshold", 0.7)
    clusters = cluster_signals(extractions, threshold=threshold)
    total_clusters = len(clusters)
    click.echo(f"  Clusters: {total_clusters} (from {len(extractions)} signals)\n")

    # Stage 4: Score
    click.echo("[4/6] Scoring signals...")
    scored = score_clusters(clusters, config)
    click.echo(f"  Scored: {len(scored)} representative signals\n")

    # Stage 5: Balance
    click.echo("[5/6] Balancing lanes...")
    selected = balance_signals(scored, config)
    click.echo(f"  Selected: {len(selected)} signals for briefing\n")

    # Stage 6: Output
    click.echo("[6/6] Generating briefing...")
    stats = {
        "total_collected": total_collected,
        "total_extracted": total_extracted,
        "total_clusters": total_clusters,
    }
    if selected:
        all_topics = config.get("scoring", {}).get("core_topics", [])
        meta = generate_briefing(target_date, selected, stats, topics=all_topics)
        db.upsert_briefing(meta)
        db.upsert_scored_signals(target_date, selected)
        click.echo(f"  Briefing saved: {meta.file_path}\n")
    else:
        click.echo("  No signals to include in briefing.\n")

    click.echo("=== Pipeline complete ===\n")


async def run_stage(stage: str, date: str | None = None) -> None:
    """Run a single pipeline stage."""
    config = get_config()
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    db.init_db()

    if stage == "collect":
        click.echo("Running: collect")
        signals = await run_collect(config)
        inserted = db.upsert_signals(signals)
        click.echo(f"Done: {len(signals)} collected, {inserted} new")

    elif stage == "extract":
        click.echo("Running: extract")
        count, _ = await run_extract(config)
        click.echo(f"Done: {count} extracted")

    elif stage == "cluster":
        click.echo("Running: cluster")
        extractions = _get_extractions(target_date)
        threshold = config.get("pipeline", {}).get("clustering_threshold", 0.7)
        clusters = cluster_signals(extractions, threshold=threshold)
        click.echo(f"Done: {len(clusters)} clusters from {len(extractions)} signals")

    elif stage == "score":
        click.echo("Running: score")
        extractions = _get_extractions(target_date)
        threshold = config.get("pipeline", {}).get("clustering_threshold", 0.7)
        clusters = cluster_signals(extractions, threshold=threshold)
        scored = score_clusters(clusters, config)
        click.echo(f"Done: {len(scored)} scored signals")

    elif stage == "balance":
        click.echo("Running: balance (includes score)")
        extractions = _get_extractions(target_date)
        threshold = config.get("pipeline", {}).get("clustering_threshold", 0.7)
        clusters = cluster_signals(extractions, threshold=threshold)
        scored = score_clusters(clusters, config)
        selected = balance_signals(scored, config)
        click.echo(f"Done: {len(selected)} selected from {len(scored)} scored")

    elif stage == "output":
        click.echo("Running: output (includes score+balance)")
        extractions = _get_extractions(target_date)
        threshold = config.get("pipeline", {}).get("clustering_threshold", 0.7)
        clusters = cluster_signals(extractions, threshold=threshold)
        scored = score_clusters(clusters, config)
        selected = balance_signals(scored, config)
        if selected:
            meta = generate_briefing(target_date, selected, {
                "total_collected": 0, "total_extracted": len(extractions),
                "total_clusters": len(clusters),
            })
            db.upsert_briefing(meta)
            click.echo(f"Done: briefing saved to {meta.file_path}")
        else:
            click.echo("No signals to output")
    else:
        click.echo(f"Unknown stage: {stage}. Use: collect, extract, cluster, score, balance, output")
