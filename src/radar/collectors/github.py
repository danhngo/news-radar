"""GitHub collector using search API."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import aiohttp

from ..models import RawSignal
from .base import BaseCollector


class GitHubCollector(BaseCollector):
    source_name = "github"
    BASE_URL = "https://api.github.com/search/repositories"

    async def collect(self) -> list[RawSignal]:
        cfg = self.config.get("sources", {}).get("github", {})
        if not cfg.get("enabled", True):
            return []

        query = cfg.get("query", "AI OR LLM")
        min_stars = cfg.get("min_stars", 50)
        max_items = cfg.get("max_items", 200)

        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        q = f"{query} pushed:>{since} stars:>={min_stars}"

        headers = {"Accept": "application/vnd.github.v3+json"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"

        signals: list[RawSignal] = []
        page = 1
        per_page = min(100, max_items)

        async with aiohttp.ClientSession(headers=headers) as session:
            while len(signals) < max_items:
                params = {
                    "q": q,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": per_page,
                    "page": page,
                }
                try:
                    async with session.get(self.BASE_URL, params=params) as resp:
                        if resp.status != 200:
                            break
                        data = await resp.json()
                except (aiohttp.ClientError, TimeoutError):
                    break

                items = data.get("items", [])
                if not items:
                    break

                for repo in items:
                    signals.append(RawSignal.create(
                        source="github",
                        url=repo.get("html_url", ""),
                        title=f"{repo.get('full_name', '')}: {repo.get('description', '') or ''}",
                        body=repo.get("description", "") or "",
                        author=repo.get("owner", {}).get("login", ""),
                        published=datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
                        if repo.get("pushed_at") else None,
                        meta={
                            "stars": repo.get("stargazers_count", 0),
                            "forks": repo.get("forks_count", 0),
                            "language": repo.get("language", ""),
                            "topics": repo.get("topics", []),
                        },
                    ))

                page += 1
                if len(items) < per_page:
                    break

        return signals[:max_items]
