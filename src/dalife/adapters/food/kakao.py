from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dalife.domains.food.collection_runner import CollectedPlace
from dalife.domains.food.evidence_scoring import clean_html, normalize_match_text


class KakaoNotConfigured(RuntimeError):
    pass


class KakaoFoodApiClient:
    def __init__(self, api_key: str, *, timeout_seconds: int = 20) -> None:
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search_places(self, *, query: str, page: int, sort_mode: str) -> list[CollectedPlace]:
        if not self.configured:
            raise KakaoNotConfigured("KAKAO_REST_API_KEY is not configured")
        params: dict[str, str | int] = {
            "query": query,
            "page": max(1, min(page, 45)),
            "size": 15,
            "category_group_code": "CE7" if _is_cafe_query(query) else "FD6",
        }
        url = "https://dapi.kakao.com/v2/local/search/keyword.json?" + urlencode(params)
        request = Request(url, method="GET")
        request.add_header("Authorization", f"KakaoAK {self.api_key}")
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        documents = payload.get("documents", []) if isinstance(payload, dict) else []
        if not isinstance(documents, list):
            raise ValueError("Kakao response documents must be a list")
        return [place for item in documents if isinstance(item, dict) if (place := _place_from_document(item))]


def _place_from_document(document: dict[str, Any]) -> CollectedPlace | None:
    name = clean_html(str(document.get("place_name") or ""))
    provider_place_id = str(document.get("id") or "").strip()
    if not name or not provider_place_id:
        return None
    return CollectedPlace(
        provider_place_id=provider_place_id,
        name=name,
        normalized_name=normalize_match_text(name),
        category=clean_html(str(document.get("category_name") or "")),
        address=clean_html(str(document.get("address_name") or "")),
        road_address=clean_html(str(document.get("road_address_name") or "")),
        phone=clean_html(str(document.get("phone") or "")),
        map_url=str(document.get("place_url") or "").strip(),
        latitude=_optional_float(document.get("y")),
        longitude=_optional_float(document.get("x")),
        raw=document,
    )


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _is_cafe_query(query: str) -> bool:
    return any(term in query for term in ("카페", "커피", "디저트", "베이커리"))
