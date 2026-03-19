"""HackerNews collector using Algolia API."""

from __future__ import annotations

from datetime import datetime

import aiohttp

from ..models import RawSignal
from .base import BaseCollector


class HackerNewsCollector(BaseCollector):
    source_name = "hackernews"
    BASE_URL = "https://hn.algolia.com/api/v1/search"

    async def collect(self) -> list[RawSignal]:
        cfg = self.config.get("sources", {}).get("hackernews", {})
        if not cfg.get("enabled", True):
            return []

        keywords = cfg.get("keywords", ["AI", "LLM"])
        min_score = cfg.get("min_score", 10)
        max_items = cfg.get("max_items", 200)

        signals: list[RawSignal] = []
        seen_urls: set[str] = set()

        async with aiohttp.ClientSession() as session:
            for keyword in keywords:
                if len(signals) >= max_items:
                    break
                params = {
                    "query": keyword,
                    "tags": "story",
                    "numericFilters": f"points>{min_score}",
                    "hitsPerPage": min(50, max_items - len(signals)),
                }
                try:
                    async with session.get(self.BASE_URL, params=params) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                except (aiohttp.ClientError, TimeoutError):
                    continue

                for hit in data.get("hits", []):
                    url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    signals.append(RawSignal.create(
                        source="hackernews",
                        url=url,
                        title=hit.get("title", ""),
                        body=hit.get("story_text") or "",
                        author=hit.get("author", ""),
                        published=datetime.fromisoformat(hit["created_at"].replace("Z", "+00:00"))
                        if hit.get("created_at") else None,
                        meta={
                            "points": hit.get("points", 0),
                            "num_comments": hit.get("num_comments", 0),
                            "hn_id": hit.get("objectID", ""),
                        },
                    ))

        return signals[:max_items]
