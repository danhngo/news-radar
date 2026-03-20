"""Data models for the radar pipeline."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime


def content_hash(source: str, url: str) -> str:
    """Generate a deterministic content-hash ID for dedup."""
    return hashlib.sha256(f"{source}:{url}".encode()).hexdigest()[:16]


@dataclass
class RawSignal:
    id: str
    source: str
    url: str
    title: str
    body: str
    author: str
    published: datetime
    collected_at: datetime
    meta: dict = field(default_factory=dict)

    @classmethod
    def create(cls, source: str, url: str, title: str, body: str = "",
               author: str = "", published: datetime | None = None,
               meta: dict | None = None) -> RawSignal:
        return cls(
            id=content_hash(source, url),
            source=source,
            url=url,
            title=title,
            body=body,
            author=author,
            published=published or datetime.now(),
            collected_at=datetime.now(),
            meta=meta or {},
        )


@dataclass
class ExtractedSignal:
    signal_id: str
    title: str
    summary: str
    entities: list[str]
    category: str  # research / product / ecosystem / events
    novelty: float  # 0.0 - 1.0
    raw: RawSignal | None = None


@dataclass
class Cluster:
    id: int
    label: str
    signals: list[ExtractedSignal]
    representative: ExtractedSignal | None = None


@dataclass
class ScoredSignal:
    signal: ExtractedSignal
    novelty_score: float
    impact_score: float
    relevance_score: float
    authority_score: float
    composite_score: float
    lane: str


@dataclass
class BriefingMeta:
    date: str
    generated_at: datetime
    total_collected: int
    total_extracted: int
    total_clusters: int
    signals_in_briefing: int
    file_path: str
    topics: list[str] = field(default_factory=list)
