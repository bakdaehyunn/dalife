from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FoodCollectionFacet(StrEnum):
    BROAD_DISCOVERY = "broad_discovery"
    CUISINE = "cuisine"
    OCCASION = "occasion"
    EVIDENCE_REFRESH = "evidence_refresh"
    EXPLORATION = "exploration"


@dataclass(frozen=True)
class FoodCollectionArea:
    name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class FoodCollectionQuery:
    provider: str
    query_text: str
    area: str
    facet: FoodCollectionFacet
    sort_mode: str = ""
    page: int = 1
    quota_cost: int = 1


@dataclass(frozen=True)
class FoodCollectionPlan:
    daily_quota_limit: int
    queries: tuple[FoodCollectionQuery, ...]

    @property
    def quota_cost(self) -> int:
        return sum(query.quota_cost for query in self.queries)


DEFAULT_CUISINES = (
    "한식",
    "고기",
    "해산물",
    "일식",
    "중식",
    "양식",
    "분식",
    "카페",
)

DEFAULT_OCCASIONS = (
    "혼밥",
    "점심",
    "저녁",
    "술자리",
    "데이트",
    "가족외식",
)

DEFAULT_EXPLORATION_TERMS = (
    "신상",
    "로컬맛집",
    "웨이팅",
    "가성비",
    "예약",
)


def build_food_collection_plan(
    *,
    areas: list[FoodCollectionArea],
    daily_quota_limit: int,
    cuisines: tuple[str, ...] = DEFAULT_CUISINES,
    occasions: tuple[str, ...] = DEFAULT_OCCASIONS,
    exploration_terms: tuple[str, ...] = DEFAULT_EXPLORATION_TERMS,
) -> FoodCollectionPlan:
    if daily_quota_limit < 1:
        return FoodCollectionPlan(daily_quota_limit=daily_quota_limit, queries=())

    queries: list[FoodCollectionQuery] = []
    seen: set[tuple[str, str, str, str, int]] = set()

    def add(query: FoodCollectionQuery) -> None:
        key = (query.provider, query.area, query.query_text, query.sort_mode, query.page)
        if key in seen:
            return
        next_cost = sum(item.quota_cost for item in queries) + query.quota_cost
        if next_cost > daily_quota_limit:
            return
        seen.add(key)
        queries.append(query)

    for area in areas:
        area_terms = (area.name, *area.aliases)
        for term in area_terms:
            add(
                FoodCollectionQuery(
                    provider="kakao_local",
                    query_text=f"{term} 맛집",
                    area=area.name,
                    facet=FoodCollectionFacet.BROAD_DISCOVERY,
                    sort_mode="accuracy",
                )
            )
            add(
                FoodCollectionQuery(
                    provider="naver_blog",
                    query_text=f"{term} 맛집 후기",
                    area=area.name,
                    facet=FoodCollectionFacet.BROAD_DISCOVERY,
                    sort_mode="sim",
                )
            )

        for cuisine in cuisines:
            add(
                FoodCollectionQuery(
                    provider="kakao_local",
                    query_text=f"{area.name} {cuisine}",
                    area=area.name,
                    facet=FoodCollectionFacet.CUISINE,
                    sort_mode="accuracy",
                )
            )
            add(
                FoodCollectionQuery(
                    provider="naver_blog",
                    query_text=f"{area.name} {cuisine} 후기",
                    area=area.name,
                    facet=FoodCollectionFacet.EVIDENCE_REFRESH,
                    sort_mode="date",
                )
            )

        for occasion in occasions:
            add(
                FoodCollectionQuery(
                    provider="naver_blog",
                    query_text=f"{area.name} {occasion} 맛집",
                    area=area.name,
                    facet=FoodCollectionFacet.OCCASION,
                    sort_mode="sim",
                )
            )

        for term in exploration_terms:
            add(
                FoodCollectionQuery(
                    provider="naver_blog",
                    query_text=f"{area.name} {term} 맛집",
                    area=area.name,
                    facet=FoodCollectionFacet.EXPLORATION,
                    sort_mode="date",
                )
            )

    return FoodCollectionPlan(daily_quota_limit=daily_quota_limit, queries=tuple(queries))
