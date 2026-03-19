# AI Intelligence Radar

Daily AI/ML/LLM news intelligence pipeline. Collects ~1000 signals from multiple sources, processes them through a 6-stage pipeline, and delivers a clean daily briefing of top signals via Markdown files and a web dashboard.

## Quick Start

```bash
# Install dependencies
uv sync

# Run full pipeline
uv run radar run

# Run for a specific date
uv run radar run --date 2026-03-19

# Run a single stage
uv run radar run-stage collect

# Start web dashboard
uv run radar web
```

## Pipeline

```
collect → extract → cluster → score → balance → output
```

1. **Collect** — Async fetching from 11 sources across 5 collector types
2. **Extract** — Claude CLI (haiku) batch extraction: title, summary, entities, category, novelty
3. **Cluster** — TF-IDF + Agglomerative Clustering to deduplicate similar signals
4. **Score** — 4 sub-scores (novelty, impact, relevance, authority) → weighted composite
5. **Balance** — Lane-based selection with min/max guarantees per category
6. **Output** — Markdown briefing generation + SQLite persistence

## Sources

| Collector | Sources | API |
|-----------|---------|-----|
| HackerNews | AI/ML keyword search | Algolia API |
| Reddit | MachineLearning, artificial, LocalLLaMA, singularity | Public JSON API |
| Arxiv | cs.AI, cs.CL, cs.LG, cs.CV | Atom API |
| GitHub | Trending AI/ML repos | Search API |
| RSS (x7) | Google AI, OpenAI, DeepMind, Meta AI, Hugging Face, MIT Tech Review, BAIR | feedparser |

## Output Lanes

| Lane | Label | Min–Max |
|------|-------|---------|
| research | Research & Papers | 1–3 |
| product | Products & Launches | 1–3 |
| ecosystem | Industry & Ecosystem | 1–3 |
| startup | Startups & Funding | 1–3 |
| events | Events & Community | 0–2 |

## Configuration

- `config.yaml` — sources, scoring weights, lane config, web settings
- `.env` — optional overrides (`GITHUB_TOKEN`, `RADAR_DB_PATH`, `RADAR_BRIEFINGS_DIR`)

## Tech Stack

- **Python 3.11+** with `uv`
- **Claude CLI** (`claude -p`) for LLM extraction (haiku, batched)
- **SQLite** for storage
- **scikit-learn** TF-IDF + AgglomerativeClustering
- **FastAPI + Jinja2** for web dashboard
- **aiohttp** for async collection
- **feedparser** for RSS/Atom

## Project Structure

```
src/radar/
├── cli.py              # Click CLI (run, run-stage, web)
├── config.py           # YAML config loader
├── db.py               # SQLite schema + CRUD
├── models.py           # Dataclasses
├── pipeline.py         # 6-stage orchestrator
├── collectors/         # hackernews, reddit, arxiv, github, rss
├── extraction.py       # Claude CLI batch integration
├── clustering.py       # TF-IDF + agglomerative
├── scoring.py          # 4 sub-scores + composite
├── balancer.py         # Lane balancing
├── output.py           # Markdown briefing generator
└── web/                # FastAPI dashboard
```
