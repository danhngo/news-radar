"""Click CLI entrypoint."""

from __future__ import annotations

import asyncio

import click


@click.group()
def cli():
    """AI Intelligence Radar - Daily AI news briefing pipeline."""
    pass


@cli.command()
@click.option("--date", default=None, help="Target date (YYYY-MM-DD). Defaults to today.")
def run(date: str | None):
    """Run the full pipeline: collect → extract → cluster → score → balance → output."""
    from .pipeline import run_pipeline
    asyncio.run(run_pipeline(date))


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
