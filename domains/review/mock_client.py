"""Mock Apify — no token needed."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from domains.store.seed_rows import DEMO_ROWS

MOCK_RUN_ID = "mock-run-0001"
MOCK_DATASET_ID = "mock-dataset-0001"
ACTOR_ID = "mock/compass-google-maps-reviews-scraper"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _stars(intensity: float) -> int:
    if intensity >= 8:
        return 1
    if intensity >= 6:
        return 2
    if intensity >= 4:
        return 3
    return 4


def _review(
    row: dict[str, Any],
    review_id: str,
    text: str,
    owner: str | None,
    stars: int,
    published: datetime,
) -> dict[str, Any]:
    return {
        "reviewId": review_id,
        "placeId": str(row["store_id"]),
        "text": text,
        "stars": stars,
        "totalScore": 4.0,
        "publishedAtDate": _iso(published),
        "reviewUrl": f"https://example.com/reviews/{review_id}",
        "reviewImageUrls": [],
        "likesCount": 2,
        "originalLanguage": "zh-Hant",
        "language": "zh-TW",
        "responseFromOwnerText": owner,
        "responseFromOwnerDate": _iso(published + timedelta(hours=3)) if owner else None,
        "title": row["name"],
        "categoryName": row["category"],
        "address": f"{row['city']}{row['district']}示範路1號",
        "reviewsCount": row["reviews"],
    }


def build_mock_catalog() -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    items: list[dict[str, Any]] = []
    for row in DEMO_ROWS:
        stars = _stars(float(row["intensity"]))
        pid = str(row["store_id"])
        items.extend(
            [
                _review(row, f"{pid}-mock-initial", row["review_text"], row["owner_reply"], stars, now - timedelta(days=14)),
                _review(row, f"{pid}-mock-daily", f"昨天又去了一次，{row['review_text']}", row["owner_reply"], max(1, stars), now - timedelta(days=1)),
                _review(row, f"{pid}-mock-pr-filter", "服務普通。", "非常抱歉讓您有不愉快的用餐體驗，我們會持續改善。", 2, now - timedelta(days=3)),
                _review(row, f"{pid}-mock-positive", "整體還不錯。", None, 5, now - timedelta(days=7)),
            ]
        )
    return items


_CATALOG = build_mock_catalog()


def fetch_mock_reviews(
    place_ids: list[str],
    *,
    max_reviews: int = 100,
    reviews_sort: str = "newest",
    reviews_start_date: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed = set(place_ids)
    items = [item for item in _CATALOG if item["placeId"] in allowed]

    if reviews_start_date:
        start = date.fromisoformat(reviews_start_date)
        items = [
            item
            for item in items
            if datetime.fromisoformat(item["publishedAtDate"].replace("Z", "+00:00")).date() >= start
        ]

    if reviews_sort == "lowestRating":
        items.sort(key=lambda x: (x.get("stars") or 5, x["publishedAtDate"]))
    elif reviews_sort == "highestRating":
        items.sort(key=lambda x: (-(x.get("stars") or 0), x["publishedAtDate"]))
    else:
        items.sort(key=lambda x: x["publishedAtDate"], reverse=True)

    if max_reviews > 0:
        items = items[:max_reviews]

    params = {
        "placeIds": place_ids,
        "maxReviews": max_reviews,
        "reviewsSort": reviews_sort,
        "reviewsStartDate": reviews_start_date,
        "mock": True,
    }
    meta = {
        "run_id": MOCK_RUN_ID,
        "dataset_id": MOCK_DATASET_ID,
        "request": params,
        "item_count": len(items),
        "mock": True,
    }
    return items, meta


def test_mock_connection() -> dict[str, str]:
    return {
        "status": "ok",
        "actor_id": ACTOR_ID,
        "actor_name": "Mock Reviews Scraper",
        "message": f"Mock 模式：{len(_CATALOG)} 筆假資料。",
    }
