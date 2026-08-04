"""用指令把測試假資料寫進 PostgreSQL（不是讀 JSON 當畫面資料）。

Usage（Dev Container / app container）:

    uv run python -m domains.store.seed_demo_data

會寫入：store / review / ai_analysis
Dashboard 只從 DB 讀，不會靜默用這份資料當 fallback。
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy import bindparam, text

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
        :google_score, :reviews_count, :one_star, :two_star, 0, 0, 0,
        FALSE, FALSE
    )
    ON CONFLICT ("placeId") DO UPDATE SET
        "title" = EXCLUDED."title",
        "categoryName" = EXCLUDED."categoryName",
        "address" = EXCLUDED."address",
        "lat" = EXCLUDED."lat",
        "lng" = EXCLUDED."lng",
        "url" = EXCLUDED."url",
        "reviewsCount" = EXCLUDED."reviewsCount",
        "oneStar" = EXCLUDED."oneStar",
        "twoStar" = EXCLUDED."twoStar",
        "scrapedAt" = EXCLUDED."scrapedAt",
        "blocked" = FALSE,
        "skip_review_fetch" = FALSE
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
        :now, :review_url, NULL, 0, :google_score, :stars,
        :now, :owner_reply, :now, FALSE, NULL, NULL
    )
    ON CONFLICT ("reviewId") DO UPDATE SET
        "text" = EXCLUDED."text",
        "stars" = EXCLUDED."stars",
        "reviewUrl" = EXCLUDED."reviewUrl",
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
        :owner_sentiment, :owner_score, :pr_reply,
        CAST(:request_json AS JSONB), NULL
    )
    ON CONFLICT ("reviewId") DO UPDATE SET
        "review_text" = EXCLUDED."review_text",
        "review_summary" = EXCLUDED."review_summary",
        "review_score" = EXCLUDED."review_score",
        "owner_text" = EXCLUDED."owner_text",
        "owner_summary" = EXCLUDED."owner_summary",
        "owner_score" = EXCLUDED."owner_score",
        "pr_reply" = EXCLUDED."pr_reply"
    '''
)

COUNT_SQL = text(
    '''
    SELECT
        (SELECT COUNT(*) FROM "store") AS stores,
        (SELECT COUNT(*) FROM "review") AS reviews,
        (SELECT COUNT(*) FROM "ai_analysis") AS analyses
    '''
)


def seed_demo_data() -> dict[str, int]:
    """把 DEMO_ROWS 用 SQL upsert 進 PostgreSQL。

    每店評論則數依 seed_rows.reviews 長度（可不同）。
    UI「只留一個原始網址」與此無關。
    """

    now = datetime.now(timezone.utc)
    review_count = 0
    place_ids = [str(row["store_id"]) for row in DEMO_ROWS]

    with engine.begin() as connection:
        # 清掉這批 demo 店舊評論，避免則數殘留
        if place_ids:
            for table in ("ai_analysis", "review", "review_source"):
                connection.execute(
                    text(
                        f'''
                        DELETE FROM "{table}"
                        WHERE "placeId" IN :place_ids
                        '''
                    ).bindparams(bindparam("place_ids", expanding=True)),
                    {"place_ids": place_ids},
                )

        for row in DEMO_ROWS:
            place_id = str(row["store_id"])
            address = f'{row["city"]}{row["district"]}示範路 1 號'
            intensity = float(row["intensity"])
            owner_sentiment = "positive" if intensity < 5 else "negative"
            pr_reply = str(row.get("pr_reply") or "").strip() or None
            reviews = list(row.get("reviews") or [])
            if not reviews:
                raise ValueError(f"{place_id} 缺少 reviews 列表")

            one_star = sum(1 for item in reviews if int(item.get("stars") or 0) == 1)
            two_star = sum(1 for item in reviews if int(item.get("stars") or 0) == 2)

            connection.execute(
                STORE_UPSERT,
                {
                    "place_id": place_id,
                    "title": row["name"],
                    "category": row["category"],
                    "categories": row["category"],
                    "address": address,
                    "lat": row["lat"],
                    "lng": row["lng"],
                    "url": f"https://maps.google.com/?q={place_id}",
                    "scraped_at": now,
                    "google_score": 1.5,
                    "reviews_count": len(reviews),
                    "one_star": one_star,
                    "two_star": two_star,
                },
            )

            for index, review in enumerate(reviews, start=1):
                stars = int(review.get("stars") or 1)
                review_id = f"{place_id}-review-{index}"
                payload = {
                    "place_id": place_id,
                    "review_id": review_id,
                    "review_url": (
                        f"https://maps.google.com/maps/reviews?rid={review_id}"
                    ),
                    "now": now,
                    "google_score": float(stars),
                    "stars": stars,
                    "review_text": review["text"],
                    "owner_reply": review["owner_reply"],
                    "review_score": round(intensity * 0.75),
                    "owner_score": round(intensity),
                    "owner_sentiment": owner_sentiment,
                    "pr_reply": pr_reply,
                    "request_json": '{"source":"seed_demo_data"}',
                }
                connection.execute(REVIEW_UPSERT, payload)
                connection.execute(ANALYSIS_UPSERT, payload)
                review_count += 1

        counts = connection.execute(COUNT_SQL).mappings().one()

    return {
        "seeded_stores": len(DEMO_ROWS),
        "seeded_reviews": review_count,
        "db_stores": int(counts["stores"]),
        "db_reviews": int(counts["reviews"]),
        "db_analyses": int(counts["analyses"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="產生測試假資料並寫入 PostgreSQL（非 JSON 畫面假資料）",
    )
    parser.parse_args()
    result = seed_demo_data()
    print("[seed] 已寫入 PostgreSQL（非 JSON）")
    print(
        f"  本次 upsert：{result['seeded_stores']} 店 / "
        f"{result['seeded_reviews']} 則評論"
    )
    print(
        f"  資料庫現況：store={result['db_stores']} "
        f"review={result['db_reviews']} "
        f"ai_analysis={result['db_analyses']}"
    )
    print("  畫面請重新整理 http://localhost:8501")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
