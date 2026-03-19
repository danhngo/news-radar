"""4 sub-scores + weighted composite scoring."""

from __future__ import annotations

import math

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Cluster, ExtractedSignal, ScoredSignal


def score_clusters(
    clusters: list[Cluster],
    config: dict,
) -> list[ScoredSignal]:
    """Score representative signals from each cluster."""
    if not clusters:
        return []

    weights = config.get("scoring", {}).get("weights", {})
    w_novelty = weights.get("novelty", 0.30)
    w_impact = weights.get("impact", 0.25)
    w_relevance = weights.get("relevance", 0.25)
    w_authority = weights.get("authority", 0.20)

    core_topics = config.get("scoring", {}).get("core_topics", [])

    reps = [c.representative for c in clusters if c.representative]
    if not reps:
        return []

    # Pre-compute relevance via TF-IDF similarity to core topics
    relevance_scores = _compute_relevance(reps, core_topics)

    scored: list[ScoredSignal] = []
    for i, signal in enumerate(reps):
        novelty = signal.novelty
        impact = _compute_impact(signal)
        relevance = relevance_scores[i]
        authority = _compute_authority(signal)

        composite = (
            w_novelty * novelty
            + w_impact * impact
            + w_relevance * relevance
            + w_authority * authority
        )

        scored.append(ScoredSignal(
            signal=signal,
            novelty_score=novelty,
            impact_score=impact,
            relevance_score=relevance,
            authority_score=authority,
            composite_score=composite,
            lane=signal.category,
        ))

    # Sort by composite score descending
    scored.sort(key=lambda s: s.composite_score, reverse=True)
    return scored


def _compute_impact(signal: ExtractedSignal) -> float:
    """Compute impact score from engagement metrics."""
    if signal.raw is None:
        return 0.5

    meta = signal.raw.meta
    points = meta.get("points", 0) + meta.get("score", 0) + meta.get("stars", 0)
    comments = meta.get("num_comments", 0) + meta.get("forks", 0)

    # Log-scale normalization
    engagement = points + comments * 2
    if engagement <= 0:
        return 0.2
    # Normalize: log(engagement) / log(max_expected)
    return min(1.0, math.log1p(engagement) / math.log1p(10000))


def _compute_relevance(
    signals: list[ExtractedSignal], core_topics: list[str]
) -> list[float]:
    """Compute relevance to core AI topics using TF-IDF cosine similarity."""
    if not core_topics or not signals:
        return [0.5] * len(signals)

    signal_texts = [f"{s.title} {s.summary}" for s in signals]
    topic_text = " ".join(core_topics)

    all_texts = signal_texts + [topic_text]
    vectorizer = TfidfVectorizer(max_features=3000, stop_words="english")
    tfidf = vectorizer.fit_transform(all_texts)

    # Cosine similarity of each signal vs topic vector
    topic_vec = tfidf[-1:]
    signal_vecs = tfidf[:-1]
    sims = cosine_similarity(signal_vecs, topic_vec).flatten()

    return [float(s) for s in sims]


def _compute_authority(signal: ExtractedSignal) -> float:
    """Compute authority score based on source reputation."""
    source_weights = {
        "arxiv": 0.9,
        "github": 0.7,
        "hackernews": 0.6,
        "reddit": 0.5,
        "rss": 0.8,  # Curated blogs
    }
    if signal.raw is None:
        return 0.5
    return source_weights.get(signal.raw.source, 0.5)
