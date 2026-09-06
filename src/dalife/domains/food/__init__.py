"""Food recommendation domain boundary."""

from dalife.domains.food.collection import persist_food_collection_plan
from dalife.domains.food.collection_plan import (
    FoodCollectionArea,
    FoodCollectionFacet,
    FoodCollectionPlan,
    FoodCollectionQuery,
    build_food_collection_plan,
)
from dalife.domains.food.collection_runner import (
    CollectedEvidence,
    CollectedPlace,
    FoodCollectionRun,
    FoodCollectionRunItem,
    FoodCollectionRunner,
    KakaoFoodCollectionPort,
    NaverFoodCollectionPort,
    diversify_due_queries,
)
from dalife.domains.food.feedback import (
    FOOD_FEEDBACK_CHOICES,
    FoodFeedback,
    FoodFeedbackAction,
    record_food_feedback,
)
from dalife.domains.food.history_importer import (
    MomukHistoryImportReport,
    build_momuk_history_refresh_plan,
    import_momuk_history,
)
from dalife.domains.food.local_recommendations import (
    LocalFoodRecommendation,
    feedback_signals,
    normalize_area_name,
    recommend_local_food,
)
from dalife.domains.food.models import (
    EvidenceTier,
    FoodEvidence,
    FoodPlace,
    FoodParsedRequest,
    FoodRecommendationContext,
)
from dalife.domains.food.parser import looks_like_food_request, parse_food_request
from dalife.domains.food.ranking import PlaceRanker, RankedFoodPlace
from dalife.domains.food.recommendations import persist_food_recommendation_session

__all__ = [
    "EvidenceTier",
    "FoodCollectionArea",
    "FoodCollectionFacet",
    "FoodCollectionPlan",
    "FoodCollectionQuery",
    "FoodCollectionRun",
    "FoodCollectionRunItem",
    "FoodCollectionRunner",
    "FoodEvidence",
    "FOOD_FEEDBACK_CHOICES",
    "FoodFeedback",
    "FoodFeedbackAction",
    "FoodPlace",
    "FoodParsedRequest",
    "FoodRecommendationContext",
    "LocalFoodRecommendation",
    "MomukHistoryImportReport",
    "CollectedEvidence",
    "CollectedPlace",
    "KakaoFoodCollectionPort",
    "NaverFoodCollectionPort",
    "diversify_due_queries",
    "PlaceRanker",
    "RankedFoodPlace",
    "build_food_collection_plan",
    "build_momuk_history_refresh_plan",
    "feedback_signals",
    "import_momuk_history",
    "looks_like_food_request",
    "parse_food_request",
    "persist_food_collection_plan",
    "persist_food_recommendation_session",
    "record_food_feedback",
    "normalize_area_name",
    "recommend_local_food",
]
