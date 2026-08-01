"""Insert repeatable demo records into PostgreSQL.

Usage inside the dev container:
    uv run python -m domains.store.seed_demo_data
"""

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
        :google_score, :reviews_count, 0, 0, 0, 0, 0, FALSE, FALSE
    )
    ON CONFLICT ("placeId") DO UPDATE SET
        "title" = EXCLUDED."title",
        "categoryName" = EXCLUDED."categoryName",
        "address" = EXCLUDED."address",
        "lat" = EXCLUDED."lat",
        "lng" = EXCLUDED."lng",
        "reviewsCount" = EXCLUDED."reviewsCount",
        "scrapedAt" = EXCLUDED."scrapedAt"
    '''
)

REVIEW_UPSERT = text(
    '''
    INSERT INTO "review" (
        "reviewId", "placeId", "originalLanguage", "text",
        "publishedAtDate", "reviewUrl", "reviewImageUrls", "likesCount",
        "totalScore", "stars", "responseFromOwnerDate",
        "responseFromOwnerText", "scrapedAt", "owner_reply_recheck",
        "owner_reply_recheck_at", "next_check_at"
    ) VALUES (
        :review_id, :place_id, 'zh-TW', :review_text,
        :now, :review_url, NULL, 0, :google_score, 1,
        :now, :owner_reply, :now, FALSE, NULL, NULL
    )
    ON CONFLICT ("reviewId") DO UPDATE SET
        "text" = EXCLUDED."text",
        "responseFromOwnerText" = EXCLUDED."responseFromOwnerText",
        "scrapedAt" = EXCLUDED."scrapedAt"
    '''
)

ANALYSIS_UPSERT = text(
    '''
    INSERT INTO "ai_analysis" (
        "reviewId", "placeId", "review_text", "review_summary",
        "review_sentiment", "review_score", "owner_text", "owner_summary",
        "owner_sentiment", "owner_score", "pr_reply", "request_json",
        "response_json"
    ) VALUES (
        :review_id, :place_id, :review_text, :review_text,
        'negative', :review_score, :owner_reply, :owner_reply,
        :owner_sentiment, :owner_score, NULL, CAST(:request_json AS JSONB), NULL
    )
    ON CONFLICT ("reviewId") DO UPDATE SET
        "review_text" = EXCLUDED."review_text",
        "review_summary" = EXCLUDED."review_summary",
        "review_score" = EXCLUDED."review_score",
        "owner_text" = EXCLUDED."owner_text",
        "owner_summary" = EXCLUDED."owner_summary",
        "owner_score" = EXCLUDED."owner_score"
    '''
)


def seed_demo_data() -> int:
    now = datetime.now(timezone.utc)

    with engine.begin() as connection:
        for row in DEMO_ROWS:
            place_id = row["store_id"]
            review_id = f"{place_id}-review"
            address = f'{row["city"]}{row["district"]}示範路 1 號'
            intensity = float(row["intensity"])
            owner_sentiment = "positive" if intensity < 5 else "negative"

            common = {
                "place_id": place_id,
                "review_id": review_id,
                "title": row["name"],
                "category": row["category"],
                "categories": row["category"],
                "address": address,
                "lat": row["lat"],
                "lng": row["lng"],
                "url": f"https://example.com/{place_id}",
                "review_url": f"https://example.com/{review_id}",
                "scraped_at": now,
                "now": now,
                "google_score": 4.0,
                "reviews_count": row["reviews"],
                "review_text": row["review_text"],
                "owner_reply": row["owner_reply"],
                "review_score": round(intensity * 0.75),
                "owner_score": round(intensity),
                "owner_sentiment": owner_sentiment,
                "request_json": '{"source":"dashboard_demo_seed"}',
            }

            connection.execute(STORE_UPSERT, common)
            connection.execute(REVIEW_UPSERT, common)
            connection.execute(ANALYSIS_UPSERT, common)

    return len(DEMO_ROWS)


if __name__ == "__main__":
    count = seed_demo_data()
    print(f"已寫入或更新 {count} 家 Dashboard 假資料。")
