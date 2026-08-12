"""Review domain database handler."""

from datetime import datetime
from typing import Any

from domains.review.repository import (
    fetch_stores_for_review,
    fetch_place_ids_for_review,
    fetch_reviews_needing_recheck,
    filter_existing_place_ids,
    save_review_batch,
    write_execution_log,
)


def get_stores(limit: int = 50) -> list[dict[str, Any]]:
    return fetch_stores_for_review(limit=limit)


def get_place_ids(limit: int = 50) -> list[str]:
    return fetch_place_ids_for_review(limit=limit)


def get_recheck_reviews(
    limit: int = 100,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    return fetch_reviews_needing_recheck(
        limit=limit,
        now=now,
    )


def get_existing_place_ids(place_ids: list[str]) -> list[str]:
    return filter_existing_place_ids(place_ids)


def save_reviews(
    source_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
) -> tuple[int, int]:
    return save_review_batch(source_rows, review_rows)


def save_execution_log(**kwargs) -> int:
    return write_execution_log(**kwargs)
