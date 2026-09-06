from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from dalife.domains.food.collection_runner import CollectedEvidence
from dalife.domains.food.evidence_scoring import clean_html


class NaverNotConfigured(RuntimeError):
    pass


class NaverBlogApiClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        allowed_domains: tuple[str, ...] = ("blog.naver.com",),
        timeout_seconds: int = 20,
    ) -> None:
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.allowed_domains = tuple(domain.lower() for domain in allowed_domains)
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def search_evidence(self, *, query: str, page: int, sort_mode: str) -> list[CollectedEvidence]:
        if not self.configured:
            raise NaverNotConfigured("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET are not configured")
        start = min(1000, max(1, ((max(1, page) - 1) * 100) + 1))
        params = {
            "query": query,
            "display": 100,
            "start": start,
            "sort": "date" if sort_mode == "date" else "sim",
        }
        url = "https://openapi.naver.com/v1/search/blog.json?" + urlencode(params)
        request = Request(url, method="GET")
        request.add_header("X-Naver-Client-Id", self.client_id)
        request.add_header("X-Naver-Client-Secret", self.client_secret)
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        items = payload.get("items", []) if isinstance(payload, dict) else []
        if not isinstance(items, list):
            raise ValueError("Naver response items must be a list")
        evidence = []
        for item in items:
            if not isinstance(item, dict):
                continue
            url = str(item.get("link") or "").strip()
            if not url or not self._allowed_url(url):
                continue
            evidence.append(
                CollectedEvidence(
                    external_id=str(item.get("postdate") or "") + ":" + url,
                    url=url,
                    title=clean_html(str(item.get("title") or "")),
                    snippet=clean_html(str(item.get("description") or "")),
                    author=clean_html(str(item.get("bloggername") or "")),
                    published_at=str(item.get("postdate") or "").strip(),
                    raw=item,
                )
            )
        return evidence

    def _allowed_url(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(host == domain or host.endswith("." + domain) for domain in self.allowed_domains)
