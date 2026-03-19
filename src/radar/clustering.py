"""TF-IDF + Agglomerative Clustering for signal dedup."""

from __future__ import annotations

from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from .models import Cluster, ExtractedSignal


def cluster_signals(
    signals: list[ExtractedSignal],
    threshold: float = 0.7,
) -> list[Cluster]:
    """Cluster signals by TF-IDF similarity and return deduplicated clusters."""
    if not signals:
        return []

    if len(signals) == 1:
        return [Cluster(id=0, label=signals[0].title, signals=signals, representative=signals[0])]

    # Build TF-IDF matrix from title + summary
    texts = [f"{s.title} {s.summary}" for s in signals]
    vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(texts)

    # Agglomerative clustering with cosine distance
    # distance_threshold = 1 - similarity_threshold
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1 - threshold,
        metric="cosine",
        linkage="average",
    )
    labels = clustering.fit_predict(tfidf_matrix.toarray())

    # Group signals by cluster label
    cluster_map: dict[int, list[ExtractedSignal]] = {}
    for signal, label in zip(signals, labels):
        cluster_map.setdefault(label, []).append(signal)

    # Build cluster objects, pick representative (highest engagement or first)
    clusters: list[Cluster] = []
    for cid, cluster_signals_list in cluster_map.items():
        rep = _pick_representative(cluster_signals_list)
        clusters.append(Cluster(
            id=cid,
            label=rep.title,
            signals=cluster_signals_list,
            representative=rep,
        ))

    return clusters


def _pick_representative(signals: list[ExtractedSignal]) -> ExtractedSignal:
    """Pick the best signal from a cluster based on engagement metrics."""
    def score_key(s: ExtractedSignal) -> float:
        if s.raw is None:
            return 0.0
        meta = s.raw.meta
        return (
            meta.get("points", 0)
            + meta.get("score", 0)
            + meta.get("stars", 0)
            + meta.get("num_comments", 0) * 0.5
        )
    return max(signals, key=score_key)
