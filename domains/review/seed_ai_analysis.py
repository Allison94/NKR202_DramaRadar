"""Seed ai_analysis for Dashboard (dev / local test only).

Writes schema.sql ai_analysis including pr_reply (AI 公關範例).
Dashboard reads PostgreSQL only — this script is not the webpage fallback.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from db.database import engine

ANALYSIS_UPSERT = text(
    '''
    INSERT INTO "ai_analysis" (
        "reviewId", "placeId", "review_text", "review_summary",
        "review_sentiment", "review_score", "owner_text", "owner_summary",
        "owner_sentiment", "owner_score", "pr_reply", "request_json",
        "response_json"
    ) VALUES (
        :review_id, :place_id, :review_text, :review_summary,
        :review_sentiment, :review_score, :owner_text, :owner_summary,
        :owner_sentiment, :owner_score, :pr_reply,
        CAST(:request_json AS JSONB), NULL
    )
    ON CONFLICT ("reviewId") DO UPDATE SET
        "review_score" = EXCLUDED."review_score",
        "owner_score" = EXCLUDED."owner_score",
        "pr_reply" = EXCLUDED."pr_reply",
        "owner_text" = EXCLUDED."owner_text",
        "review_text" = EXCLUDED."review_text"
    '''
)

# Only seed from real review rows already in PostgreSQL (1–2★ fights).
FETCH_DRAMA_REVIEWS = text(
    '''
    SELECT
        r."reviewId",
        r."placeId",
        r."text",
        r."stars",
        COALESCE(r."responseFromOwnerText", '') AS owner_text
    FROM "review" AS r
    INNER JOIN "store" AS s ON s."placeId" = r."placeId"
    WHERE r."stars" <= 2
      AND s."blocked" = FALSE
      AND (s."address" LIKE '%台北市%' OR s."address" LIKE '%臺北市%')
    ORDER BY r."stars" ASC, r."publishedAtDate" DESC
    '''
)


def _pr_reply_for(owner_text: str) -> str:
    base = (
        "非常抱歉造成您不愉快的體驗。"
        "我們已請店長檢視當日服務與出餐狀況，並會持續改善。"
    )
    owner = (owner_text or "").strip()
    if not owner:
        return base
    return base + f"（原老闆回覆可改寫為較合適的公開說明）"


def seed_ai_analysis() -> int:
    now = datetime.now(timezone.utc)
    count = 0
    with engine.begin() as connection:
        reviews = connection.execute(FETCH_DRAMA_REVIEWS).mappings().all()
        for rev in reviews:
            stars = int(rev["stars"] or 0)
            owner_text = str(rev["owner_text"] or "")
            # Higher drama score for 1★
            review_score = 9 if stars <= 1 else 7
            owner_score = 9 if any(
                w in owner_text for w in ("不要來", "不缺", "不爽", "規則", "精準")
            ) else 6
            connection.execute(
                ANALYSIS_UPSERT,
                {
                    "review_id": rev["reviewId"],
                    "place_id": rev["placeId"],
                    "review_text": str(rev["text"] or "")[:2000] or "（無評論）",
                    "review_summary": str(rev["text"] or "")[:200] or "低星客訴",
                    "review_sentiment": "negative",
                    "review_score": review_score,
                    "owner_text": owner_text or "（尚未回覆）",
                    "owner_summary": owner_text[:200] if owner_text else "店家尚未回覆",
                    "owner_sentiment": "negative" if owner_score >= 7 else "neutral",
                    "owner_score": owner_score,
                    "pr_reply": _pr_reply_for(owner_text),
                    "request_json": (
                        f'{{"source":"mock_dev_seed","at":"{now.isoformat()}"}}'
                    ),
                },
            )
            count += 1
    return count


if __name__ == "__main__":
    print(f"已寫入 {seed_ai_analysis()} 筆 ai_analysis（含 pr_reply）。")
