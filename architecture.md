# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                      CLI (Click)                        │
│              radar run / run-stage / web                 │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                 Pipeline Orchestrator                    │
│            (pipeline.py — 6-stage flow)                  │
└──┬──────┬──────┬──────┬──────┬──────┬───────────────────┘
   │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼
 Collect Extract Cluster Score Balance Output
```

## Data Flow

```
Sources (11)          RawSignal          ExtractedSignal
  HackerNews ──┐        │                    │
  Reddit ──────┤        │  Claude CLI        │  TF-IDF
  Arxiv ───────┤──▶  signals  ──▶  extractions  ──▶  clusters
  GitHub ──────┤      table          table           │
  RSS (x7) ────┘                                     │
                                                     ▼
                    briefings/       ScoredSignal   Cluster
                    2026-03-19.md  ◀── balanced ◀── representatives
                         │              │
                         ▼              ▼
                    Web Dashboard   scored_signals
                    (FastAPI)         table
```

## Stage Details

### 1. Collect (async)

All collectors inherit from `BaseCollector` and implement `async collect() -> list[RawSignal]`.

- Collectors run concurrently via `asyncio.gather`
- Each source is rate-limited by its own API constraints
- Signals get content-hash IDs (`sha256(source:url)[:16]`) for natural dedup
- `INSERT OR IGNORE` prevents duplicate storage

### 2. Extract (Claude CLI)

- Signals batched in groups of 15 per Claude call
- `asyncio.Semaphore(5)` limits concurrent subprocess calls
- Claude CLI invoked as: `claude -p <prompt> --model haiku --output-format json`
- JSON response parsed with fallback for markdown fences
- If Claude fails, fallback extraction uses source heuristics (arxiv→research, github→product)

### 3. Cluster (TF-IDF)

- `TfidfVectorizer` on `title + summary` text
- `AgglomerativeClustering` with cosine distance, threshold 0.7
- Each cluster picks a representative by highest engagement score
- Reduces ~1000 signals to ~100-300 unique stories

### 4. Score

Four sub-scores, each normalized to [0, 1]:

| Score | Method | Weight |
|-------|--------|--------|
| Novelty | From Claude extraction | 0.30 |
| Impact | log-scale engagement metrics | 0.25 |
| Relevance | TF-IDF cosine sim to core AI topics | 0.25 |
| Authority | Source reputation lookup | 0.20 |

Composite = weighted sum of sub-scores.

### 5. Balance

Lane-based selection algorithm:

1. **Phase 1**: Fill each lane's minimum quota (top-N by composite)
2. **Phase 2**: Fill remaining slots globally by composite score, respecting lane max
3. **Phase 3**: If below `min_briefing_signals`, backfill from overall top scores

### 6. Output

- Jinja2 template generates Markdown grouped by lane
- File saved to `briefings/{date}.md`
- Metadata persisted to `briefings` SQLite table

## Storage Schema

```sql
signals          -- Raw collected data (id, source, url, title, body, meta)
extractions      -- Claude-extracted structured data (signal_id, summary, entities, category, novelty)
clusters         -- Cluster membership (date, signal_ids, representative_id)
scored_signals   -- Final scores per signal per date
briefings        -- Briefing metadata (date, file_path, stats)
```

All tables use `INSERT OR REPLACE` / `INSERT OR IGNORE` for idempotent reruns.

## Web Dashboard

```
GET /                → List all briefings + source stats
GET /briefing/{date} → Render briefing markdown as HTML
```

- FastAPI + Jinja2 templates
- Dark theme (CSS custom properties)
- Markdown rendered via `markdown` library with tables + fenced code extensions

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Claude CLI via subprocess | No API key needed, uses existing Claude Code auth |
| TF-IDF over sentence-transformers | Avoids torch dependency (~2GB), sufficient for dedup |
| Batch extraction (15/call) | ~67 Claude calls for 1000 signals, balances throughput vs context |
| Content-hash IDs | Deterministic dedup without UUID coordination |
| Async collect, sync process | Collectors are I/O-bound, processing is CPU-bound |
| SQLite WAL mode | Safe concurrent reads during web serving |
| Lane balancing | Guarantees topical diversity in briefings |
