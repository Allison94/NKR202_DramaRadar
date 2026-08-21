"""寫入「真實 Google placeId」到 store，供 Review Apify 驗收。

demo-* 假 id 無法打 Google Maps Reviews Scraper。
Store domain 若尚未灌真實店家，可用此腳本塞真實台北店 placeId。

Usage:
    uv run python -m domains.review.bootstrap_real_store
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from db.database import engine

# 專案已驗證可抓的真實 placeId（台北）
REAL_TAIPEI_STORES = [
    {
        "placeId": "ChIJi67FDQCrQjQRNnqJst4-2C8",
        "title": "饒咖哩 Rao Curry",
        "categoryName": "咖哩飯",
        "categories": "咖哩飯",
        "address": "台北市大安區和平東路二段18巷",
        "lat": 25.0263,
        "lng": 121.5407,
        "url": (
            "https://www.google.com/maps/place/"
            "?q=place_id:ChIJi67FDQCrQjQRNnqJst4-2C8"
        ),
        "oneStar": 5,
        "twoStar": 8,
        "reviewsCount": 200,
    },
]

UPSERT_STORE = text(
    '''
    INSERT INTO "store" (
        "placeId", "title", "categoryName", "categories", "address",
        "lat", "lng", "url", "imageUrl", "business_status", "scrapedAt",
        "totalScore", "reviewsCount", "oneStar", "twoStar", "threeStar",
        "fourStar", "fiveStar", "blocked", "skip_review_fetch"
    ) VALUES (
        :placeId, :title, :categoryName, :categories, :address,
        :lat, :lng, :url, NULL, 'OPERATIONAL', :scrapedAt,
        4.0, :reviewsCount, :oneStar, :twoStar, 0, 0, 0,
        FALSE, FALSE
    )
    ON CONFLICT ("placeId") DO UPDATE SET
        "title" = EXCLUDED."title",
        "categoryName" = EXCLUDED."categoryName",
        "address" = EXCLUDED."address",
        "lat" = EXCLUDED."lat",
        "lng" = EXCLUDED."lng",
        "oneStar" = EXCLUDED."oneStar",
        "twoStar" = EXCLUDED."twoStar",
        "reviewsCount" = EXCLUDED."reviewsCount",
        "blocked" = FALSE,
        "skip_review_fetch" = FALSE,
        "scrapedAt" = EXCLUDED."scrapedAt"
    '''
)


def bootstrap_real_stores() -> int:
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        for row in REAL_TAIPEI_STORES:
            payload = dict(row)
            payload["scrapedAt"] = now
            connection.execute(UPSERT_STORE, payload)
    return len(REAL_TAIPEI_STORES)


if __name__ == "__main__":
    n = bootstrap_real_stores()
    print(f"[bootstrap] 已寫入 {n} 筆真實 Google placeId 到 store")
    print(
        "接著跑真實 Apify（會花額度）:\n"
        "  uv run python -m domains.review.run_pipeline "
        "--mode manual --place-id ChIJi67FDQCrQjQRNnqJst4-2C8 --max-reviews 5"
    )
