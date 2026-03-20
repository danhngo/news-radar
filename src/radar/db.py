"""SQLite schema and CRUD operations."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .config import PROJECT_ROOT, get_config
from .models import (
    BriefingMeta,
    ExtractedSignal,
    RawSignal,
    ScoredSignal,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    author TEXT,
    published TEXT,
    collected_at TEXT NOT NULL,
    meta TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS extractions (
    signal_id TEXT PRIMARY KEY REFERENCES signals(id),
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    entities TEXT DEFAULT '[]',
    category TEXT NOT NULL,
    novelty REAL DEFAULT 0.5
);

CREATE TABLE IF NOT EXISTS clusters (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    label TEXT,
    signal_ids TEXT DEFAULT '[]',
    representative_id TEXT
);

CREATE TABLE IF NOT EXISTS scored_signals (
    signal_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    novelty_score REAL,
    impact_score REAL,
    relevance_score REAL,
    authority_score REAL,
    composite_score REAL,
    lane TEXT
);

CREATE TABLE IF NOT EXISTS briefings (
    date TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    total_collected INTEGER,
    total_extracted INTEGER,
    total_clusters INTEGER,
    signals_in_briefing INTEGER,
    file_path TEXT,
    topics TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_signals_source ON signals(source);
CREATE INDEX IF NOT EXISTS idx_signals_collected ON signals(collected_at);
CREATE INDEX IF NOT EXISTS idx_scored_date ON scored_signals(date);
"""


def get_db_path() -> Path:
    cfg = get_config()
    return PROJECT_ROOT / cfg["db_path"]


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.close()


def upsert_signals(signals: list[RawSignal]) -> int:
    conn = get_connection()
    inserted = 0
    for s in signals:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO signals (id, source, url, title, body, author, published, collected_at, meta) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (s.id, s.source, s.url, s.title, s.body, s.author,
                 s.published.isoformat(), s.collected_at.isoformat(),
                 json.dumps(s.meta)),
            )
            if conn.total_changes:
                inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return inserted


def get_unextracted_signals(limit: int = 1000) -> list[RawSignal]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT s.* FROM signals s LEFT JOIN extractions e ON s.id = e.signal_id "
        "WHERE e.signal_id IS NULL ORDER BY s.collected_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [_row_to_signal(r) for r in rows]


def upsert_extractions(extractions: list[ExtractedSignal]) -> int:
    conn = get_connection()
    inserted = 0
    for e in extractions:
        conn.execute(
            "INSERT OR REPLACE INTO extractions (signal_id, title, summary, entities, category, novelty) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (e.signal_id, e.title, e.summary, json.dumps(e.entities), e.category, e.novelty),
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted


def get_extractions_for_date(date: str) -> list[ExtractedSignal]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT e.*, s.url, s.source, s.meta FROM extractions e "
        "JOIN signals s ON e.signal_id = s.id "
        "WHERE date(COALESCE(s.published, s.collected_at)) = ?",
        (date,),
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        raw = RawSignal(
            id=r["signal_id"], source=r["source"], url=r["url"],
            title=r["title"], body="", author="",
            published=datetime.now(), collected_at=datetime.now(),
            meta=json.loads(r["meta"]) if r["meta"] else {},
        )
        results.append(ExtractedSignal(
            signal_id=r["signal_id"],
            title=r["title"],
            summary=r["summary"],
            entities=json.loads(r["entities"]) if r["entities"] else [],
            category=r["category"],
            novelty=r["novelty"],
            raw=raw,
        ))
    return results


def get_extractions_by_ids(signal_ids: set[str]) -> list[ExtractedSignal]:
    """Get extractions for a specific set of signal IDs."""
    if not signal_ids:
        return []
    conn = get_connection()
    placeholders = ",".join("?" for _ in signal_ids)
    rows = conn.execute(
        f"SELECT e.*, s.url, s.source, s.meta FROM extractions e "
        f"JOIN signals s ON e.signal_id = s.id "
        f"WHERE e.signal_id IN ({placeholders})",
        list(signal_ids),
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        raw = RawSignal(
            id=r["signal_id"], source=r["source"], url=r["url"],
            title=r["title"], body="", author="",
            published=datetime.now(), collected_at=datetime.now(),
            meta=json.loads(r["meta"]) if r["meta"] else {},
        )
        results.append(ExtractedSignal(
            signal_id=r["signal_id"],
            title=r["title"],
            summary=r["summary"],
            entities=json.loads(r["entities"]) if r["entities"] else [],
            category=r["category"],
            novelty=r["novelty"],
            raw=raw,
        ))
    return results


def get_recent_extractions(limit: int = 1000) -> list[ExtractedSignal]:
    """Get most recent extractions regardless of date."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT e.*, s.url, s.source, s.meta FROM extractions e "
        "JOIN signals s ON e.signal_id = s.id "
        "ORDER BY s.collected_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        raw = RawSignal(
            id=r["signal_id"], source=r["source"], url=r["url"],
            title=r["title"], body="", author="",
            published=datetime.now(), collected_at=datetime.now(),
            meta=json.loads(r["meta"]) if r["meta"] else {},
        )
        results.append(ExtractedSignal(
            signal_id=r["signal_id"],
            title=r["title"],
            summary=r["summary"],
            entities=json.loads(r["entities"]) if r["entities"] else [],
            category=r["category"],
            novelty=r["novelty"],
            raw=raw,
        ))
    return results


def upsert_scored_signals(date: str, scored: list[ScoredSignal]) -> int:
    conn = get_connection()
    for s in scored:
        conn.execute(
            "INSERT OR REPLACE INTO scored_signals "
            "(signal_id, date, novelty_score, impact_score, relevance_score, authority_score, composite_score, lane) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (s.signal.signal_id, date, s.novelty_score, s.impact_score,
             s.relevance_score, s.authority_score, s.composite_score, s.lane),
        )
    conn.commit()
    conn.close()
    return len(scored)


def upsert_briefing(meta: BriefingMeta) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO briefings "
        "(date, generated_at, total_collected, total_extracted, total_clusters, signals_in_briefing, file_path, topics) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (meta.date, meta.generated_at.isoformat(), meta.total_collected,
         meta.total_extracted, meta.total_clusters, meta.signals_in_briefing,
         meta.file_path, json.dumps(meta.topics)),
    )
    conn.commit()
    conn.close()


def get_briefings() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM briefings ORDER BY date DESC").fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["topics"] = json.loads(d.get("topics") or "[]")
        results.append(d)
    return results


def get_signal_counts_by_source() -> dict[str, int]:
    conn = get_connection()
    rows = conn.execute("SELECT source, COUNT(*) as cnt FROM signals GROUP BY source").fetchall()
    conn.close()
    return {r["source"]: r["cnt"] for r in rows}


def _row_to_signal(row: sqlite3.Row) -> RawSignal:
    return RawSignal(
        id=row["id"],
        source=row["source"],
        url=row["url"],
        title=row["title"],
        body=row["body"] or "",
        author=row["author"] or "",
        published=datetime.fromisoformat(row["published"]) if row["published"] else datetime.now(),
        collected_at=datetime.fromisoformat(row["collected_at"]),
        meta=json.loads(row["meta"]) if row["meta"] else {},
    )
