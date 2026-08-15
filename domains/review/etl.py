"""Apify JSON → schema.sql review_source / review rows."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from domains.review.config import (
    RECHECK_AFTER_DAYS,
    RECHECK_MAX_AGE_DAYS,
)
from domains.review.filters import (
    dedupe_raw_items,
    should_write_business_review,
    validate_raw_item,
)
from domains.review.logging_setup import get_logger


log = get_logger(__name__)




def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _image_urls_to_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, list):
        urls = [str(item) for item in value if item]
        return json.dumps(urls, ensure_ascii=False) if urls else None
    return str(value)


def build_owner_recheck_state(
    owner_reply_text: object,
    *,
    published_at: datetime,
    now: datetime,
    is_recheck: bool = False,
) -> tuple[bool, datetime | None, datetime | None]:
    """Return owner_reply_recheck / owner_reply_recheck_at / next_check_at."""

    text = "" if owner_reply_text is None else str(owner_reply_text).strip()
    recheck_at = now if is_recheck else None

    if text:
        return False, recheck_at, None

    recheck_deadline = published_at + timedelta(days=RECHECK_MAX_AGE_DAYS)
    if now > recheck_deadline:
        return False, recheck_at, None

    return True, recheck_at, now + timedelta(days=RECHECK_AFTER_DAYS)


def transform_raw_review(
    raw: dict[str, Any],
    *,
    scraped_at: datetime | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    ok, reason = validate_raw_item(raw)
    if not ok:
        return None, None, reason

    review_id = str(raw["reviewId"])
    place_id = str(raw["placeId"])
    now = scraped_at or _utcnow()

    published_at = _as_datetime(raw.get("publishedAtDate")) or now
    owner_reply_date = _as_datetime(raw.get("responseFromOwnerDate"))
    owner_reply_text = raw.get("responseFromOwnerText")

    text = raw.get("text")
    if text is None:
        text = ""

    original_language = (
        raw.get("originalLanguage")
        or raw.get("language")
        or "unknown"
    )
    review_url = raw.get("reviewUrl") or ""
    stars = _as_int(raw.get("stars"), default=0)
    total_score = _as_float(raw.get("totalScore"), default=float(stars))

    (
        owner_reply_recheck,
        owner_reply_recheck_at,
        next_check_at,
    ) = build_owner_recheck_state(
        owner_reply_text,
        published_at=published_at,
        now=now,
        is_recheck=False,
    )

    source_row = {
        "review_id": review_id,
        "place_id": place_id,
        "raw_json": raw,
        "scraped_at": now,
    }

    review_row = {
        "review_id": review_id,
        "place_id": place_id,
        "original_language": str(original_language),
        "text": str(text),
        "published_at_date": published_at,
        "review_url": str(review_url),
        "review_image_urls": _image_urls_to_text(raw.get("reviewImageUrls")),
        "likes_count": _as_int(raw.get("likesCount"), default=0),
        "total_score": total_score,
        "stars": stars,
        "response_from_owner_date": owner_reply_date,
        "response_from_owner_text": owner_reply_text,
        "scraped_at": now,
        "owner_reply_recheck": owner_reply_recheck,
        "owner_reply_recheck_at": owner_reply_recheck_at,
        "next_check_at": next_check_at,
    }

    write_ok, skip_reason = should_write_business_review(review_row)
    if not write_ok:
        return source_row, None, skip_reason

    return source_row, review_row, skip_reason


def transform_raw_reviews(
    raw_items: list[dict[str, Any]],
    *,
    scraped_at: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Only 1★/2★ are written to review_source/review."""

    deduped, dedupe_skipped = dedupe_raw_items(raw_items)

    source_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    generic_pr_place_ids: set[str] = set()

    stats: dict[str, Any] = {
        "raw_count": len(raw_items),
        "dedupe_skipped": dedupe_skipped,
        "invalid_skipped": 0,
        "non_low_star_skipped": 0,
        "filter_skipped": 0,
        "source_count": 0,
        "review_count": 0,
        "generic_pr_store_count": 0,
        "generic_pr_place_ids": [],
    }

    now = scraped_at or _utcnow()

    for item in deduped:
        valid, _ = validate_raw_item(item)
        if not valid:
            stats["invalid_skipped"] += 1
            continue

        stars = _as_int(item.get("stars"), default=0)
        if stars not in (1, 2):
            stats["non_low_star_skipped"] += 1
            log.debug(
                "skip non-low-star reviewId=%s stars=%s",
                item.get("reviewId"),
                stars,
            )
            continue

        source_row, review_row, reason = transform_raw_review(
            item,
            scraped_at=now,
        )

        if source_row is None:
            stats["invalid_skipped"] += 1
            continue

        source_rows.append(source_row)

        if reason == "generic_pr_reply":
            place_id = item.get("placeId")
            if place_id:
                generic_pr_place_ids.add(str(place_id))

        if review_row is None:
            stats["filter_skipped"] += 1
            log.debug(
                "business skip reviewId=%s reason=%s",
                item.get("reviewId"),
                reason,
            )
            continue

        review_rows.append(review_row)

    stats["source_count"] = len(source_rows)
    stats["review_count"] = len(review_rows)
    stats["generic_pr_place_ids"] = sorted(generic_pr_place_ids)
    stats["generic_pr_store_count"] = len(generic_pr_place_ids)
    stats["skipped"] = (
        stats["dedupe_skipped"]
        + stats["invalid_skipped"]
        + stats["non_low_star_skipped"]
        + stats["filter_skipped"]
    )

    log.info("ETL stats: %s", stats)
    return source_rows, review_rows, stats