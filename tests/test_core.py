"""Basic tests for core modules."""

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from radar.models import RawSignal, ExtractedSignal, content_hash
from radar.clustering import cluster_signals
from radar.scoring import score_clusters
from radar.balancer import balance_signals


def test_content_hash_deterministic():
    h1 = content_hash("reddit", "https://example.com")
    h2 = content_hash("reddit", "https://example.com")
    assert h1 == h2
    assert len(h1) == 16


def test_content_hash_unique():
    h1 = content_hash("reddit", "https://example.com/1")
    h2 = content_hash("reddit", "https://example.com/2")
    assert h1 != h2


def test_raw_signal_create():
    s = RawSignal.create(
        source="test",
        url="https://example.com",
        title="Test Signal",
        body="Some body",
    )
    assert s.source == "test"
    assert s.url == "https://example.com"
    assert len(s.id) == 16


_DIVERSE_TITLES = [
    ("New quantum computing breakthrough accelerates drug discovery", "Quantum computers solve protein folding"),
    ("Tesla unveils autonomous robotaxi fleet in San Francisco", "Self-driving cars launched commercially by Tesla"),
    ("European Union passes comprehensive AI regulation bill", "EU lawmakers finalize sweeping artificial intelligence rules"),
    ("SpaceX Starship completes first orbital refueling mission", "Orbital refueling demonstrated by SpaceX rocket"),
    ("CRISPR gene therapy cures sickle cell disease in clinical trial", "Gene editing treatment eliminates blood disorder"),
    ("Apple releases Vision Pro spatial computing headset", "Mixed reality headset arrives from Apple"),
    ("OpenAI launches GPT-5 with reasoning capabilities", "Next generation language model released by OpenAI"),
    ("Google DeepMind solves long-standing mathematics conjecture", "AI system proves unsolved math problem"),
    ("Meta open sources new large language model Llama 4", "Facebook parent releases open weight AI model"),
]


def _make_extracted(n: int, category: str = "ecosystem") -> list[ExtractedSignal]:
    signals = []
    for i in range(n):
        title, summary = _DIVERSE_TITLES[i % len(_DIVERSE_TITLES)]
        raw = RawSignal.create(
            source="test", url=f"https://example.com/{category}/{i}",
            title=title, body=summary,
            meta={"points": (i + 1) * 10},
        )
        signals.append(ExtractedSignal(
            signal_id=raw.id,
            title=title,
            summary=summary,
            entities=["OpenAI", "GPT"],
            category=category,
            novelty=0.5 + i * 0.05,
            raw=raw,
        ))
    return signals


def test_clustering_single():
    signals = _make_extracted(1)
    clusters = cluster_signals(signals)
    assert len(clusters) == 1
    assert clusters[0].representative is not None


def test_clustering_multiple():
    signals = _make_extracted(5)
    clusters = cluster_signals(signals, threshold=0.7)
    assert len(clusters) >= 1
    assert all(c.representative is not None for c in clusters)


def test_scoring():
    signals = _make_extracted(5)
    clusters = cluster_signals(signals, threshold=0.3)
    config = {
        "scoring": {
            "weights": {"novelty": 0.3, "impact": 0.25, "relevance": 0.25, "authority": 0.2},
            "core_topics": ["artificial intelligence", "machine learning"],
        }
    }
    scored = score_clusters(clusters, config)
    assert len(scored) > 0
    assert all(0 <= s.composite_score <= 1 for s in scored)
    # Should be sorted by composite score descending
    for i in range(len(scored) - 1):
        assert scored[i].composite_score >= scored[i + 1].composite_score


def test_balancer():
    signals = []
    for cat in ["research", "product", "ecosystem"]:
        signals.extend(_make_extracted(3, category=cat))
    clusters = cluster_signals(signals, threshold=0.3)
    config = {
        "scoring": {
            "weights": {"novelty": 0.3, "impact": 0.25, "relevance": 0.25, "authority": 0.2},
            "core_topics": ["AI"],
        },
        "lanes": {
            "research": {"label": "Research", "min": 1, "max": 3},
            "product": {"label": "Products", "min": 1, "max": 3},
            "ecosystem": {"label": "Ecosystem", "min": 1, "max": 3},
            "events": {"label": "Events", "min": 0, "max": 2},
        },
        "pipeline": {"max_briefing_signals": 10, "min_briefing_signals": 3},
    }
    scored = score_clusters(clusters, config)
    selected = balance_signals(scored, config)
    assert len(selected) >= 3
    assert len(selected) <= 10


if __name__ == "__main__":
    test_content_hash_deterministic()
    test_content_hash_unique()
    test_raw_signal_create()
    test_clustering_single()
    test_clustering_multiple()
    test_scoring()
    test_balancer()
    print("All tests passed!")
