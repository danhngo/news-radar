"""Signal collectors for various sources."""

from .arxiv import ArxivCollector
from .github import GitHubCollector
from .hackernews import HackerNewsCollector
from .reddit import RedditCollector
from .rss import RSSCollector

__all__ = [
    "ArxivCollector",
    "GitHubCollector",
    "HackerNewsCollector",
    "RedditCollector",
    "RSSCollector",
]
