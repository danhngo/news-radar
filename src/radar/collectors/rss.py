"""Generic RSS/Atom feed collector."""

from __future__ import annotations

from datetime import datetime

import aiohttp
import feedparser

from ..models import RawSignal
from .base import BaseCollector


class RSSCollector(BaseCollector):
    source_name = "rss"

    async def collect(self) -> list[RawSignal]:
        cfg = self.config.get("sources", {}).get("rss", {})
        if not cfg.get("enabled", True):
            return []

        feeds = cfg.get("feeds", [])
        max_items = cfg.get("max_items", 200)

        signals: list[RawSignal] = []

        async with aiohttp.ClientSession() as session:
            for feed_cfg in feeds:
                url = feed_cfg.get("url", "")
                name = feed_cfg.get("name", url)
                if not url:
                    continue
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status != 200:
                            continue
                        text = await resp.text()
                except (aiohttp.ClientError, TimeoutError):
                    continue

                feed = feedparser.parse(text)
                for entry in feed.entries:
                    link = entry.get("link", "")
                    if not link:
                        continue

                    published = None
                    if entry.get("published_parsed"):
                        try:
                            published = datetime(*entry.published_parsed[:6])
                        except (TypeError, ValueError):
                            pass

                    body = entry.get("summary", "") or entry.get("description", "")

                    signals.append(RawSignal.create(
                        source="rss",
                        url=link,
                        title=entry.get("title", ""),
                        body=body[:2000],
                        author=entry.get("author", ""),
                        published=published,
                        meta={"feed_name": name, "feed_url": url},
                    ))

        return signals[:max_items]
