"""Reddit collector using public JSON API (no auth)."""

from __future__ import annotations

from datetime import datetime

import aiohttp

from ..models import RawSignal
from .base import BaseCollector


class RedditCollector(BaseCollector):
    source_name = "reddit"

    async def collect(self) -> list[RawSignal]:
        cfg = self.config.get("sources", {}).get("reddit", {})
        if not cfg.get("enabled", True):
            return []

        subreddits = cfg.get("subreddits", ["MachineLearning"])
        min_score = cfg.get("min_score", 20)
        max_items = cfg.get("max_items", 200)

        signals: list[RawSignal] = []
        seen_urls: set[str] = set()
        headers = {"User-Agent": "news-radar/0.1 (AI news aggregator)"}

        async with aiohttp.ClientSession(headers=headers) as session:
            for sub in subreddits:
                if len(signals) >= max_items:
                    break
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=100"
                try:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                except (aiohttp.ClientError, TimeoutError):
                    continue

                for child in data.get("data", {}).get("children", []):
                    post = child.get("data", {})
                    if post.get("score", 0) < min_score:
                        continue

                    post_url = post.get("url", "")
                    if not post_url or post_url in seen_urls:
                        continue
                    seen_urls.add(post_url)

                    signals.append(RawSignal.create(
                        source="reddit",
                        url=post_url,
                        title=post.get("title", ""),
                        body=post.get("selftext", "")[:2000],
                        author=post.get("author", ""),
                        published=datetime.fromtimestamp(post["created_utc"])
                        if post.get("created_utc") else None,
                        meta={
                            "score": post.get("score", 0),
                            "num_comments": post.get("num_comments", 0),
                            "subreddit": sub,
                            "permalink": f"https://reddit.com{post.get('permalink', '')}",
                        },
                    ))

        return signals[:max_items]
