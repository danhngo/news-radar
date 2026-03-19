"""Arxiv collector using Atom API."""

from __future__ import annotations

from datetime import datetime

import aiohttp
import feedparser

from ..models import RawSignal
from .base import BaseCollector


class ArxivCollector(BaseCollector):
    source_name = "arxiv"
    BASE_URL = "http://export.arxiv.org/api/query"

    async def collect(self) -> list[RawSignal]:
        cfg = self.config.get("sources", {}).get("arxiv", {})
        if not cfg.get("enabled", True):
            return []

        categories = cfg.get("categories", ["cs.AI", "cs.CL", "cs.LG"])
        max_items = cfg.get("max_items", 200)

        cat_query = "+OR+".join(f"cat:{c}" for c in categories)
        params = {
            "search_query": cat_query,
            "start": 0,
            "max_results": max_items,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        signals: list[RawSignal] = []
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.BASE_URL, params=params) as resp:
                    if resp.status != 200:
                        return []
                    text = await resp.text()
            except (aiohttp.ClientError, TimeoutError):
                return []

        feed = feedparser.parse(text)
        for entry in feed.entries[:max_items]:
            url = entry.get("link", "")
            authors = ", ".join(a.get("name", "") for a in entry.get("authors", []))

            published = None
            if entry.get("published_parsed"):
                published = datetime(*entry.published_parsed[:6])

            categories_list = [t.get("term", "") for t in entry.get("tags", [])]

            signals.append(RawSignal.create(
                source="arxiv",
                url=url,
                title=entry.get("title", "").replace("\n", " ").strip(),
                body=entry.get("summary", "").replace("\n", " ").strip()[:2000],
                author=authors,
                published=published,
                meta={
                    "arxiv_id": entry.get("id", "").split("/abs/")[-1],
                    "categories": categories_list,
                    "pdf_url": url.replace("/abs/", "/pdf/") if "/abs/" in url else "",
                },
            ))

        return signals
