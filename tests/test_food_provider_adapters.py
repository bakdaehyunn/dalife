from __future__ import annotations

import json

from darchivebot.adapters.food.kakao import KakaoFoodApiClient
from darchivebot.adapters.food.naver import NaverBlogApiClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_kakao_adapter_maps_place_documents(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse(
            {
                "documents": [
                    {
                        "id": "123",
                        "place_name": "<b>동네식당</b>",
                        "category_name": "음식점 > 한식",
                        "address_name": "서울 양천구",
                        "road_address_name": "서울 양천구 신정로 1",
                        "phone": "02-123-4567",
                        "place_url": "https://place.map.kakao.com/123",
                        "x": "126.86",
                        "y": "37.52",
                    }
                ]
            }
        )

    monkeypatch.setattr("darchivebot.adapters.food.kakao.urlopen", fake_urlopen)

    places = KakaoFoodApiClient("key").search_places(query="신정동 한식", page=1, sort_mode="accuracy")

    assert places[0].name == "동네식당"
    assert places[0].provider_place_id == "123"
    assert places[0].latitude == 37.52
    assert calls[0][0].get_header("Authorization") == "KakaoAK key"
    assert "category_group_code=FD6" in calls[0][0].full_url


def test_naver_adapter_filters_domains_and_maps_blog_items(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse(
            {
                "items": [
                    {
                        "title": "<b>동네식당</b> 후기",
                        "description": "직접 방문",
                        "bloggername": "작성자",
                        "postdate": "20260820",
                        "link": "https://blog.naver.com/a/1",
                    },
                    {
                        "title": "excluded",
                        "description": "excluded",
                        "link": "https://example.com/a",
                    },
                ]
            }
        )

    monkeypatch.setattr("darchivebot.adapters.food.naver.urlopen", fake_urlopen)

    evidence = NaverBlogApiClient("id", "secret").search_evidence(
        query="신정동 한식 후기",
        page=2,
        sort_mode="date",
    )

    assert len(evidence) == 1
    assert evidence[0].title == "동네식당 후기"
    assert evidence[0].author == "작성자"
    assert calls[0][0].get_header("X-naver-client-id") == "id"
    assert "start=101" in calls[0][0].full_url
    assert "sort=date" in calls[0][0].full_url
