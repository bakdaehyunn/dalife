from __future__ import annotations

import re
from datetime import date, datetime
from html import unescape


VISIT_REVIEW_WORDS = ("방문", "다녀왔", "먹고", "주문", "웨이팅", "내돈내산")
OPEN_STATUS_WORDS = ("24시", "새벽", "늦게", "영업시간", "라스트오더", "심야", "야간")
AD_WORDS = ("협찬", "제공받아", "체험단", "원고료", "광고")
ROUNDUP_WORDS = ("best", "총정리", "모음", "리스트")
GENERIC_NAME_TOKENS = {"본점", "지점", "직영점", "역점", "점"}


def clean_html(text: str) -> str:
    value = unescape(text or "")
    value = re.sub(r"</?b>", "", value)
    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_match_text(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", text).lower()


def blog_text_matches_name(place_name: str, evidence_text: str) -> bool:
    name = normalize_match_text(place_name)
    evidence = normalize_match_text(evidence_text)
    if not name or not evidence:
        return False
    if len(name) <= 2:
        pattern = re.compile(
            rf"(?<![0-9A-Za-z가-힣]){re.escape(place_name.strip())}(?![0-9A-Za-z가-힣])"
        )
        return bool(pattern.search(evidence_text))
    if name in evidence:
        return True
    tokens = []
    for raw_token in re.split(r"[\s,/()]+", place_name):
        token = normalize_match_text(raw_token)
        if token.endswith("점") and len(token) <= 4:
            continue
        if len(token) >= 3 and token not in GENERIC_NAME_TOKENS:
            tokens.append(token)
    if not tokens:
        return False
    matched = [token for token in tokens if token in evidence]
    return tokens[0] in matched or len(matched) >= 2


def score_blog_evidence(
    *,
    title: str,
    snippet: str,
    published_at: str,
    area: str,
    query_text: str,
    today: date | None = None,
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    today = today or date.today()
    text = f"{title} {snippet}"
    lowered = text.lower()
    score = 0
    signals: list[str] = []
    penalties: list[str] = []

    age_days = _post_age_days(published_at, today)
    if age_days is None:
        penalties.append("date_unknown")
    elif age_days <= 90:
        score += 5
        signals.append("recent_90d")
    elif age_days <= 180:
        score += 4
        signals.append("recent_180d")
    elif age_days <= 365:
        score += 3
        signals.append("recent_1y")
    elif age_days <= 730:
        score += 1
        signals.append("recent_2y")
    else:
        penalties.append("old_post")

    area_terms = _meaningful_terms(area)
    if area_terms and not any(term in normalize_match_text(text) for term in area_terms):
        score -= 4
        penalties.append(f"area_missing:{area.strip()}")

    keyword_score = 0
    for keyword in _meaningful_terms(query_text):
        if keyword in normalize_match_text(title):
            keyword_score += 2
            signals.append(f"title_match:{keyword}")
        elif keyword in normalize_match_text(snippet):
            keyword_score += 1
            signals.append(f"summary_match:{keyword}")
    score += min(8, keyword_score)

    visit_words = [word for word in VISIT_REVIEW_WORDS if word in text]
    score += min(4, len(visit_words))
    signals.extend(f"visit:{word}" for word in visit_words)
    open_words = [word for word in OPEN_STATUS_WORDS if word in text]
    score += min(4, len(open_words))
    signals.extend(f"open_hint:{word}" for word in open_words)

    ad_words = [word for word in AD_WORDS if word in text]
    if ad_words:
        score -= min(8, 3 + len(ad_words))
        penalties.extend(f"ad_like:{word}" for word in ad_words)
    roundup_words = [word for word in ROUNDUP_WORDS if word in lowered]
    if roundup_words and not visit_words:
        score -= 3
        penalties.extend(f"roundup:{word}" for word in roundup_words)
    return score, tuple(signals), tuple(penalties)


def normalized_evidence_score(score: int) -> float:
    return round(max(0.0, min(1.0, (score + 4) / 20)), 4)


def _meaningful_terms(value: str) -> tuple[str, ...]:
    generic = {"맛집", "후기", "추천", "방문", "식당"}
    terms = []
    for token in re.split(r"[\s,/()]+", value):
        normalized = normalize_match_text(token)
        if len(normalized) >= 2 and normalized not in generic and normalized not in terms:
            terms.append(normalized)
    return tuple(terms)


def _post_age_days(value: str, today: date) -> int | None:
    compact = re.sub(r"[^0-9]", "", value or "")
    if len(compact) != 8:
        return None
    try:
        published = datetime.strptime(compact, "%Y%m%d").date()
    except ValueError:
        return None
    return max(0, (today - published).days)
