"""Seed store rows from dashboard DEMO_ROWS (Review pipeline prerequisite)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from db.database import engine
from domains.store.seed_rows import DEMO_ROWS


STORE_UPSERT = text(
    '''
    INSERT INTO "store" (
        "placeId", "title", "categoryName", "categories", "address",
        "lat", "lng", "url", "imageUrl", "business_status", "scrapedAt",
        "totalScore", "reviewsCount", "oneStar", "twoStar", "threeStar",
        "fourStar", "fiveStar", "blocked", "skip_review_fetch"
    ) VALUES (
        :place_id, :title, :category, :categories, :address,
        :lat, :lng, :url, NULL, 'OPERATIONAL', :scraped_at,
        :google_score, :reviews_count, :one_star, :two_star, :three_star,
        :four_star, :five_star, FALSE, FALSE
    )
    ON CONFLICT ("placeId") DO UPDATE SET
        "title" = EXCLUDED."title",
        "categoryName" = EXCLUDED."categoryName",
        "address" = EXCLUDED."address",
        "lat" = EXCLUDED."lat",
        "lng" = EXCLUDED."lng",
        "reviewsCount" = EXCLUDED."reviewsCount",
        "oneStar" = EXCLUDED."oneStar",
        "twoStar" = EXCLUDED."twoStar",
        "scrapedAt" = EXCLUDED."scrapedAt"
    '''
)


def seed_stores() -> int:
    """WRITE schema.sql store — Taipei City only (address contains 台北市)."""

    now = datetime.now(timezone.utc)
    taipei_rows = [
        row for row in DEMO_ROWS if str(row.get("city", "")).replace("臺", "台") == "台北市"
    ]
    if not taipei_rows:
        raise RuntimeError("DEMO_ROWS 沒有台北市店家，無法 seed store。")

    with engine.begin() as connection:
        for row in taipei_rows:
            reviews_count = int(row["reviews"])
            intensity = float(row["intensity"])
            one_star = max(3, reviews_count // 25)
            two_star = max(5, reviews_count // 18)
            if intensity >= 8:
                one_star = max(one_star, 12)
                two_star = max(two_star, 18)

            payload = {
                "place_id": row["store_id"],
                "title": row["name"],
                "category": row["category"],
                "categories": row["category"],
                "address": f'台北市{row["district"]}示範路 1 號',
                "lat": row["lat"],
                "lng": row["lng"],
                "url": f"https://example.com/{row['store_id']}",
                "scraped_at": now,
                "google_score": 4.0,
                "reviews_count": reviews_count,
                "one_star": one_star,
                "two_star": two_star,
                "three_star": max(10, reviews_count // 10),
                "four_star": max(20, reviews_count // 4),
                "five_star": max(30, reviews_count // 2),
            }
            connection.execute(STORE_UPSERT, payload)

    return len(taipei_rows)


if __name__ == "__main__":
    count = seed_stores()
    print(f"已寫入 {count} 家 store（Review pipeline 用）。")
