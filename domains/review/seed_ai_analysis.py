"""Seed ai_analysis for Dashboard intensity (dev mock)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from db.database import engine
from domains.store.service import DEMO_ROWS

ANALYSIS_UPSERT = text(
    '''
    INSERT INTO "ai_analysis" (
        "reviewId", "placeId", "review_text", "review_summary",
        "review_sentiment", "review_score", "owner_text", "owner_summary",
        "owner_sentiment", "owner_score", "pr_reply", "request_json",
        "response_json"
    ) VALUES (
        :review_id, :place_id, :review_text, :review_text,
        :review_sentiment, :review_score, :owner_reply, :owner_reply,
        :owner_sentiment, :owner_score, NULL,
        CAST(:request_json AS JSONB), NULL
    )
    ON CONFLICT ("reviewId") DO UPDATE SET
        "review_score" = EXCLUDED."review_score",
        "owner_score" = EXCLUDED."owner_score"
    '''
)


def seed_ai_analysis() -> int:
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        for row in DEMO_ROWS:
            intensity = float(row["intensity"])
            connection.execute(
                ANALYSIS_UPSERT,
                {
                    "review_id": f"{row['store_id']}-mock-initial",
                    "place_id": row["store_id"],
                    "review_text": row["review_text"],
                    "owner_reply": row["owner_reply"],
                    "review_sentiment": "negative" if intensity >= 5 else "neutral",
                    "review_score": round(intensity * 0.75),
                    "owner_sentiment": "negative" if intensity >= 5 else "positive",
                    "owner_score": round(intensity),
                    "request_json": f'{{"source":"mock_dev_seed","at":"{now.isoformat()}"}}',
                },
            )
    return len(DEMO_ROWS)


if __name__ == "__main__":
    print(f"已寫入 {seed_ai_analysis()} 筆 ai_analysis。")
