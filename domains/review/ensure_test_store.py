"""Ensure the sample Google placeId exists in store so Review FK inserts succeed.

Usage:
    uv run python -m domains.review.ensure_test_store
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from db.database import engine
from domains.review.service import DEFAULT_TEST_PLACE_ID


UPSERT_STORE = text(
    '''
    INSERT INTO "store" (
        "placeId", "title", "categoryName", "categories", "address",
        "lat", "lng", "url", "imageUrl", "business_status", "scrapedAt",
        "totalScore", "reviewsCount", "oneStar", "twoStar", "threeStar",
        "fourStar", "fiveStar", "blocked", "skip_review_fetch"
    ) VALUES (
        :place_id, :title, :category, :categories, :address,
        :lat, :lng, :url, NULL, 'OPERATIONAL', :scraped_at,
        :google_score, :reviews_count, 0, 0, 0, 0, 0, FALSE, FALSE
    )
    ON CONFLICT ("placeId") DO UPDATE SET
        "title" = EXCLUDED."title",
        "scrapedAt" = EXCLUDED."scrapedAt"
    '''
)


def ensure_test_store(place_id: str = DEFAULT_TEST_PLACE_ID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "place_id": place_id,
        "title": "饒咖哩 日式咖哩專賣店",
        "category": "日式咖哩餐廳",
        "categories": "日式咖哩餐廳",
        "address": "台北市南港區玉成街14-14號",
        "lat": 25.0505127,
        "lng": 121.5809709,
        "url": (
            "https://www.google.com/maps/search/?api=1"
            f"&query_place_id={place_id}"
        ),
        "scraped_at": now,
        "google_score": 4.5,
        "reviews_count": 133,
    }

    with engine.begin() as connection:
        connection.execute(UPSERT_STORE, payload)

    return place_id


if __name__ == "__main__":
    pid = ensure_test_store()
    print(f"已確保 store 內有測試 placeId: {pid}")
