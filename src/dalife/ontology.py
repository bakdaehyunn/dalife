from __future__ import annotations

import hashlib
import re


ONTOLOGY_VERSION = "2026-06-08"
GRAPH_EXPORT_VERSION = 1


def interest_id(value: str) -> str:
    return urn("interest", slugify(value or "other-unknown"))


def topic_id(value: str) -> str:
    return urn("topic", slugify(value))


def concept_id(value: str) -> str:
    return urn("concept", slugify(value))


def claim_id(archive_id: str, index: int) -> str:
    return urn("claim", f"{archive_id}-{index}")


def question_id(value: str) -> str:
    return urn("question", stable_hash(value))


def relation_candidate_id(archive_id: str, value: str) -> str:
    return urn("relation-candidate", stable_hash(f"{archive_id}:{value}"))


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:16]


def urn(kind: str, value: str) -> str:
    return f"urn:dalife:{kind}:{value}"


def slugify(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣._/-]+", "-", value.strip().lower())
    return slug.strip("-") or "unknown"

