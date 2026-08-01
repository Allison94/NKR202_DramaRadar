"""PostgreSQL read/write for Review domain — columns match db/schema.sql.

Tables used (see db/schema.sql):
  READ  "store"          → placeId, oneStar, twoStar, reviewsCount, address
  WRITE "review_source"  → reviewId, placeId, raw_json, scrapedAt
  WRITE "review"         → reviewId, placeId, originalLanguage, text, …
  WRITE "execution_log"  → pipeline run audit

Scope: Taipei City only (address contains 台北市 / 臺北市).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from db.database import engine


# schema.sql "store" — only Taipei City rows for review fetch
FETCH_STORES_FOR_REVIEW = text(
    '''
    SELECT
        s."placeId",
        s."oneStar",
        s."twoStar",
        s."reviewsCount",
        s."address"
    FROM "store" AS s
    WHERE s."blocked" = FALSE
      AND s."skip_review_fetch" = FALSE
      AND (
            s."address" LIKE '%台北市%'
         OR s."address" LIKE '%臺北市%'
      )
    ORDER BY s."reviewsCount" DESC, s."placeId"
    LIMIT :limit
    '''
)

# schema.sql "execution_log"
INSERT_EXECUTION_LOG = text(
    '''
    INSERT INTO "execution_log" (
        "pipeline", "status", "items_count", "apify_scheduler_id",
        "actor_name", "started_at", "finished_at",
        "request_json", "response_json", "error_msg", "retry_count"
    ) VALUES (
        :pipeline, :status, :items_count, :apify_scheduler_id,
        :actor_name, :started_at, :finished_at,
        CAST(:request_json AS JSONB), CAST(:response_json AS JSONB),
        :error_msg, :retry_count
    )
    RETURNING "id"
    '''
)

# schema.sql "review_source"
UPSERT_REVIEW_SOURCE = text(
    '''
    INSERT INTO "review_source" (
        "reviewId", "placeId", "raw_json", "scrapedAt"
    ) VALUES (
        :review_id, :place_id, CAST(:raw_json AS JSONB), :scraped_at
    )
    ON CONFLICT ("reviewId") DO UPDATE SET
        "placeId" = EXCLUDED."placeId",
        "raw_json" = EXCLUDED."raw_json",
        "scrapedAt" = EXCLUDED."scrapedAt"
    '''
)

# schema.sql "review"
UPSERT_REVIEW = text(
    '''
    INSERT INTO "review" (
        "reviewId", "placeId", "originalLanguage", "text",
        "publishedAtDate", "reviewUrl", "reviewImageUrls", "likesCount",
        "totalScore", "stars", "responseFromOwnerDate",
        "responseFromOwnerText", "scrapedAt", "owner_reply_recheck",
        "owner_reply_recheck_at", "next_check_at"
    ) VALUES (
        :review_id, :place_id, :original_language, :text,
        :published_at_date, :review_url, :review_image_urls, :likes_count,
        :total_score, :stars, :response_from_owner_date,
        :response_from_owner_text, :scraped_at, :owner_reply_recheck,
        :owner_reply_recheck_at, :next_check_at
    )
    ON CONFLICT ("reviewId") DO UPDATE SET
        "placeId" = EXCLUDED."placeId",
        "originalLanguage" = EXCLUDED."originalLanguage",
        "text" = EXCLUDED."text",
        "publishedAtDate" = EXCLUDED."publishedAtDate",
        "reviewUrl" = EXCLUDED."reviewUrl",
        "reviewImageUrls" = EXCLUDED."reviewImageUrls",
        "likesCount" = EXCLUDED."likesCount",
        "totalScore" = EXCLUDED."totalScore",
        "stars" = EXCLUDED."stars",
        "responseFromOwnerDate" = EXCLUDED."responseFromOwnerDate",
        "responseFromOwnerText" = EXCLUDED."responseFromOwnerText",
        "scrapedAt" = EXCLUDED."scrapedAt"
    '''
)


def fetch_stores_for_review(
    limit: int = 20,
    *,
    db_engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """READ store (schema.sql) — Taipei City placeIds for Apify / mock fetch."""

    safe_limit = max(1, min(int(limit), 500))
    active_engine = db_engine or engine

    with active_engine.connect() as connection:
        rows = connection.execute(
            FETCH_STORES_FOR_REVIEW,
            {"limit": safe_limit},
        ).mappings().all()

    return [dict(row) for row in rows]


def fetch_place_ids_for_review(
    limit: int = 20,
    *,
    db_engine: Engine | None = None,
) -> list[str]:
    stores = fetch_stores_for_review(limit=limit, db_engine=db_engine)
    return [str(row["placeId"]) for row in stores if row.get("placeId")]


def filter_existing_place_ids(
    place_ids: list[str],
    *,
    db_engine: Engine | None = None,
) -> list[str]:
    cleaned = [pid.strip() for pid in place_ids if pid and str(pid).strip()]
    if not cleaned:
        return []

    active_engine = db_engine or engine
    query = text(
        '''
        SELECT s."placeId"
        FROM "store" AS s
        WHERE s."placeId" IN :place_ids
        '''
    ).bindparams(bindparam("place_ids", expanding=True))

    with active_engine.connect() as connection:
        rows = connection.execute(query, {"place_ids": cleaned}).mappings().all()

    existing = {str(row["placeId"]) for row in rows}
    return [pid for pid in cleaned if pid in existing]


def save_review_batch(
    source_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    *,
    db_engine: Engine | None = None,
) -> tuple[int, int]:
    """WRITE review_source + review (schema.sql)."""

    active_engine = db_engine or engine
    source_payload = []

    for row in source_rows:
        raw_json = row["raw_json"]
        if not isinstance(raw_json, str):
            raw_json = json.dumps(raw_json, ensure_ascii=False)

        source_payload.append(
            {
                "review_id": row["review_id"],
                "place_id": row["place_id"],
                "raw_json": raw_json,
                "scraped_at": row["scraped_at"],
            }
        )

    with active_engine.begin() as connection:
        if source_payload:
            connection.execute(UPSERT_REVIEW_SOURCE, source_payload)
        if review_rows:
            connection.execute(UPSERT_REVIEW, review_rows)

    return len(source_payload), len(review_rows)


def write_execution_log(
    *,
    pipeline: str,
    status: str,
    items_count: int = 0,
    apify_scheduler_id: str | None = None,
    actor_name: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    request_json: dict[str, Any] | None = None,
    response_json: dict[str, Any] | None = None,
    error_msg: str | None = None,
    retry_count: int = 0,
    db_engine: Engine | None = None,
) -> int:
    """WRITE execution_log (schema.sql)."""

    active_engine = db_engine or engine
    payload = {
        "pipeline": pipeline,
        "status": status,
        "items_count": items_count,
        "apify_scheduler_id": apify_scheduler_id,
        "actor_name": actor_name,
        "started_at": started_at,
        "finished_at": finished_at,
        "request_json": json.dumps(request_json or {}, ensure_ascii=False),
        "response_json": json.dumps(response_json or {}, ensure_ascii=False),
        "error_msg": error_msg,
        "retry_count": retry_count,
    }

    with active_engine.begin() as connection:
        row_id = connection.execute(INSERT_EXECUTION_LOG, payload).scalar_one()

    return int(row_id)
