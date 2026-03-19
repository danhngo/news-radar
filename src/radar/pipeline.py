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


async def run_extract(config: dict) -> int:
    """Stage 2: Extract structured info from unprocessed signals."""
    signals = db.get_unextracted_signals(limit=1000)
    if not signals:
        click.echo("  No unextracted signals found")
        return 0

    batch_size = config.get("pipeline", {}).get("batch_size", 15)
    max_concurrent = config.get("pipeline", {}).get("max_concurrent_extractions", 5)

    click.echo(f"  Extracting {len(signals)} signals (batch_size={batch_size}, concurrency={max_concurrent})")
    extracted = await extract_batch(signals, batch_size=batch_size, max_concurrent=max_concurrent)
    count = db.upsert_extractions(extracted)
    return count


async def run_pipeline(date: str | None = None) -> None:
    """Run the full pipeline."""
    config = get_config()
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    db.init_db()

    click.echo(f"\n=== AI Intelligence Radar — {target_date} ===\n")

    # Stage 1: Collect
    click.echo("[1/6] Collecting signals...")
    signals = await run_collect(config)
    total_collected = len(signals)
    inserted = db.upsert_signals(signals)
    click.echo(f"  Total: {total_collected} collected, {inserted} new\n")

    # Stage 2: Extract
    click.echo("[2/6] Extracting signals...")
    total_extracted = await run_extract(config)
    click.echo(f"  Extracted: {total_extracted}\n")

    # Stage 3: Cluster
    click.echo("[3/6] Clustering signals...")
    extractions = db.get_extractions_for_date(target_date)
    if not extractions:
        click.echo("  No extractions for today. Using all recent extractions.")
        extractions = db.get_extractions_for_date(target_date)

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
        meta = generate_briefing(target_date, selected, stats)
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
        count = await run_extract(config)
        click.echo(f"Done: {count} extracted")

    elif stage == "cluster":
        click.echo("Running: cluster")
        extractions = db.get_extractions_for_date(target_date)
        threshold = config.get("pipeline", {}).get("clustering_threshold", 0.7)
        clusters = cluster_signals(extractions, threshold=threshold)
        click.echo(f"Done: {len(clusters)} clusters from {len(extractions)} signals")

    elif stage == "score":
        click.echo("Running: score")
        extractions = db.get_extractions_for_date(target_date)
        threshold = config.get("pipeline", {}).get("clustering_threshold", 0.7)
        clusters = cluster_signals(extractions, threshold=threshold)
        scored = score_clusters(clusters, config)
        click.echo(f"Done: {len(scored)} scored signals")

    elif stage == "balance":
        click.echo("Running: balance (includes score)")
        extractions = db.get_extractions_for_date(target_date)
        threshold = config.get("pipeline", {}).get("clustering_threshold", 0.7)
        clusters = cluster_signals(extractions, threshold=threshold)
        scored = score_clusters(clusters, config)
        selected = balance_signals(scored, config)
        click.echo(f"Done: {len(selected)} selected from {len(scored)} scored")

    elif stage == "output":
        click.echo("Running: output (includes score+balance)")
        extractions = db.get_extractions_for_date(target_date)
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
