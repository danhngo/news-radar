"""Click CLI entrypoint."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import click


def _parse_date_range(date: str | None, date_from: str | None, date_to: str | None) -> list[str]:
    """Parse date options into a list of date strings."""
    if date:
        return [date]
    if date_from or date_to:
        start = datetime.strptime(date_from, "%Y-%m-%d") if date_from else datetime.now()
        end = datetime.strptime(date_to, "%Y-%m-%d") if date_to else datetime.now()
        if start > end:
            start, end = end, start
        dates = []
        current = start
        while current <= end:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        return dates
    return [datetime.now().strftime("%Y-%m-%d")]


@click.group()
def cli():
    """AI Intelligence Radar - Daily AI news briefing pipeline."""
    pass


@cli.command()
@click.option("--date", default=None, help="Single target date (YYYY-MM-DD).")
@click.option("--date-from", default=None, help="Start date for range (YYYY-MM-DD).")
@click.option("--date-to", default=None, help="End date for range (YYYY-MM-DD).")
@click.option("--topics", default=None, help="Comma-separated favorite topics to boost in scoring (e.g. 'AI agents,RAG,multimodal').")
def run(date: str | None, date_from: str | None, date_to: str | None, topics: str | None):
    """Run the full pipeline: collect → extract → cluster → score → balance → output."""
    from .pipeline import run_pipeline
    topic_list = [t.strip() for t in topics.split(",") if t.strip()] if topics else None
    dates = _parse_date_range(date, date_from, date_to)
    if len(dates) > 1:
        click.echo(f"Running pipeline for {len(dates)} days: {dates[0]} → {dates[-1]}\n")
    for d in dates:
        asyncio.run(run_pipeline(d, extra_topics=topic_list))


@cli.command("run-stage")
@click.argument("stage", type=click.Choice(["collect", "extract", "cluster", "score", "balance", "output"]))
@click.option("--date", default=None, help="Target date (YYYY-MM-DD). Defaults to today.")
def run_stage(stage: str, date: str | None):
    """Run a single pipeline stage."""
    from .pipeline import run_stage as _run_stage
    asyncio.run(_run_stage(stage, date))


@cli.command()
@click.option("--host", default=None, help="Host to bind to.")
@click.option("--port", default=None, type=int, help="Port to bind to.")
def web(host: str | None, port: int | None):
    """Start the web dashboard."""
    import uvicorn
    from .config import get_config

    cfg = get_config()
    web_cfg = cfg.get("web", {})
    uvicorn.run(
        "radar.web.app:app",
        host=host or web_cfg.get("host", "0.0.0.0"),
        port=port or web_cfg.get("port", 8080),
        reload=False,
    )


if __name__ == "__main__":
    cli()
