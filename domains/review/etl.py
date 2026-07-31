"""Transform Apify Google Maps Reviews JSON into schema-aligned rows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from domains.review.filters import (
    dedupe_raw_items,
    should_write_business_review,
    validate_raw_item,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    text = str(value).strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


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
        if not urls:
            return None
        return json.dumps(urls, ensure_ascii=False)

    return str(value)


def transform_raw_review(
    raw: dict[str, Any],
    *,
    scraped_at: datetime | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    """Map one Apify item to (review_source row, review row, skip_reason)."""

    ok, reason = validate_raw_item(raw)
    if not ok:
        return None, None, reason

    review_id = str(raw["reviewId"])
    place_id = str(raw["placeId"])
    now = scraped_at or _utcnow()
    published_at = _as_datetime(raw.get("publishedAtDate")) or now
    owner_reply_date = _as_datetime(raw.get("responseFromOwnerDate"))

    text = raw.get("text")
    if text is None:
        text = ""

    original_language = raw.get("originalLanguage") or raw.get("language") or "unknown"
    review_url = raw.get("reviewUrl") or ""
    stars = _as_int(raw.get("stars"), default=0)
    total_score = _as_float(raw.get("totalScore"), default=float(stars))

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
        "response_from_owner_text": raw.get("responseFromOwnerText"),
        "scraped_at": now,
        "owner_reply_recheck": False,
        "owner_reply_recheck_at": None,
        "next_check_at": None,
    }

    write_ok, skip_reason = should_write_business_review(review_row)
    if not write_ok:
        return source_row, None, skip_reason

    return source_row, review_row, "ok"


def transform_raw_reviews(
    raw_items: list[dict[str, Any]],
    *,
    scraped_at: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Transform many Apify items.

    Raw always -> review_source when valid.
    Business -> review only when filters pass.
    """

    deduped, dedupe_skipped = dedupe_raw_items(raw_items)
    source_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    stats = {
        "raw_count": len(raw_items),
        "dedupe_skipped": dedupe_skipped,
        "invalid_skipped": 0,
        "filter_skipped": 0,
        "source_count": 0,
        "review_count": 0,
    }
    now = scraped_at or _utcnow()

    for item in deduped:
        source_row, review_row, reason = transform_raw_review(item, scraped_at=now)
        if source_row is None:
            stats["invalid_skipped"] += 1
            continue

        source_rows.append(source_row)
        if review_row is None:
            stats["filter_skipped"] += 1
            continue

        review_rows.append(review_row)

    stats["source_count"] = len(source_rows)
    stats["review_count"] = len(review_rows)
    stats["skipped"] = (
        stats["dedupe_skipped"]
        + stats["invalid_skipped"]
        + stats["filter_skipped"]
    )
    return source_rows, review_rows, stats
