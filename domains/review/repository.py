"""Review domain DB access — columns match db/schema.sql only.

READ:
- store
- review

WRITE:
- store.skip_review_fetch
- review_source
- review
- execution_log

Does not write ai_analysis / dashboard tables.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from db.database import engine
from domains.review.logging_setup import get_logger


log = get_logger(__name__)


# ============================================================
# Store
# ============================================================

FETCH_ALL_STORES_FOR_REVIEW = text(
    '''
    SELECT
        s."placeId",
        s."oneStar",
        s."twoStar",
        s."reviewsCount",
        s."skip_review_fetch"
    FROM "store" AS s
    WHERE s."blocked" = FALSE
      AND s."skip_review_fetch" = FALSE
    ORDER BY s."reviewsCount" DESC, s."placeId"
    '''
)


FETCH_STORES_FOR_REVIEW_LIMITED = text(
    '''
    SELECT
        s."placeId",
        s."oneStar",
        s."twoStar",
        s."reviewsCount",
        s."skip_review_fetch"
    FROM "store" AS s
    WHERE s."blocked" = FALSE
      AND s."skip_review_fetch" = FALSE
    ORDER BY s."reviewsCount" DESC, s."placeId"
    LIMIT :limit
    '''
)


MARK_STORE_SKIP_REVIEW_FETCH = text(
    '''
    UPDATE "store"
    SET "skip_review_fetch" = TRUE
    WHERE "placeId" IN :place_ids
    '''
).bindparams(
    bindparam("place_ids", expanding=True)
)


# ============================================================
# Owner Reply Recheck
# ============================================================

FETCH_REVIEWS_NEEDING_RECHECK = text(
    '''
    SELECT
        r."reviewId",
        r."placeId",
        r."publishedAtDate",
        r."responseFromOwnerDate",
        r."responseFromOwnerText",
        r."owner_reply_recheck",
        r."owner_reply_recheck_at",
        r."next_check_at"
    FROM "review" AS r
    INNER JOIN "store" AS s
        ON s."placeId" = r."placeId"
    WHERE s."blocked" = FALSE
      AND s."skip_review_fetch" = FALSE
      AND r."owner_reply_recheck" = TRUE
      AND r."next_check_at" IS NOT NULL
      AND r."next_check_at" <= :now
    ORDER BY r."next_check_at", r."placeId", r."reviewId"
    '''
)


UPDATE_REVIEW_RECHECK_STATE = text(
    '''
    UPDATE "review"
    SET
        "owner_reply_recheck" = :owner_reply_recheck,
        "owner_reply_recheck_at" = :owner_reply_recheck_at,
        "next_check_at" = :next_check_at
    WHERE "reviewId" = :review_id
    '''
)


# ============================================================
# execution_log
# ============================================================

INSERT_EXECUTION_LOG = text(
    '''
    INSERT INTO "execution_log" (
        "pipeline",
        "status",
        "items_count",
        "apify_scheduler_id",
        "actor_name",
        "started_at",
        "finished_at",
        "request_json",
        "response_json",
        "error_msg",
        "retry_count"
    ) VALUES (
        :pipeline,
        :status,
        :items_count,
        :apify_scheduler_id,
        :actor_name,
        :started_at,
        :finished_at,
        CAST(:request_json AS JSONB),
        CAST(:response_json AS JSONB),
        :error_msg,
        :retry_count
    )
    RETURNING "id"
    '''
)


# ============================================================
# review_source
# ============================================================

UPSERT_REVIEW_SOURCE = text(
    '''
    INSERT INTO "review_source" (
        "reviewId",
        "placeId",
        "raw_json",
        "scrapedAt"
    ) VALUES (
        :review_id,
        :place_id,
        CAST(:raw_json AS JSONB),
        :scraped_at
    )
    ON CONFLICT ("reviewId") DO UPDATE SET
        "placeId" = EXCLUDED."placeId",
        "raw_json" = EXCLUDED."raw_json",
        "scrapedAt" = EXCLUDED."scrapedAt"
    '''
)


# ============================================================
# review
# ============================================================

UPSERT_REVIEW = text(
    '''
    INSERT INTO "review" (
        "reviewId",
        "placeId",
        "originalLanguage",
        "text",
        "publishedAtDate",
        "reviewUrl",
        "reviewImageUrls",
        "likesCount",
        "totalScore",
        "stars",
        "responseFromOwnerDate",
        "responseFromOwnerText",
        "scrapedAt",
        "owner_reply_recheck",
        "owner_reply_recheck_at",
        "next_check_at"
    ) VALUES (
        :review_id,
        :place_id,
        :original_language,
        :text,
        :published_at_date,
        :review_url,
        :review_image_urls,
        :likes_count,
        :total_score,
        :stars,
        :response_from_owner_date,
        :response_from_owner_text,
        :scraped_at,
        :owner_reply_recheck,
        :owner_reply_recheck_at,
        :next_check_at
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
        "scrapedAt" = EXCLUDED."scrapedAt",
        "owner_reply_recheck" = EXCLUDED."owner_reply_recheck",
        "owner_reply_recheck_at" = EXCLUDED."owner_reply_recheck_at",
        "next_check_at" = EXCLUDED."next_check_at"
    '''
)


def fetch_stores_for_review(
    limit: int | None = None,
    *,
    db_engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """
    READ store rows eligible for Review.

    limit=None:
        正式 Initial / Daily 取得全部符合條件 Store。
        之後由 Airflow DAG 每 50 家拆 Batch。

    limit=N:
        Manual / test only.
    """

    active = db_engine or engine

    with active.connect() as connection:
        if limit is None:
            rows = connection.execute(
                FETCH_ALL_STORES_FOR_REVIEW
            ).mappings().all()
        else:
            safe_limit = max(1, int(limit))

            rows = connection.execute(
                FETCH_STORES_FOR_REVIEW_LIMITED,
                {"limit": safe_limit},
            ).mappings().all()

    result = [
        dict(row)
        for row in rows
    ]

    log.info(
        "fetch_stores_for_review: %s stores "
        "(limit=%s, blocked=FALSE, skip_review_fetch=FALSE)",
        len(result),
        limit,
    )

    return result


def fetch_place_ids_for_review(
    limit: int | None = None,
    *,
    db_engine: Engine | None = None,
) -> list[str]:
    return [
        str(row["placeId"])
        for row in fetch_stores_for_review(
            limit=limit,
            db_engine=db_engine,
        )
        if row.get("placeId")
    ]


def mark_stores_skip_review_fetch(
    place_ids: list[str],
    *,
    db_engine: Engine | None = None,
) -> int:
    """
    >= 80% 制式公關回覆店家：

    UPDATE store
    SET skip_review_fetch = TRUE
    """

    cleaned = sorted(
        {
            str(place_id).strip()
            for place_id in place_ids
            if place_id and str(place_id).strip()
        }
    )

    if not cleaned:
        return 0

    active = db_engine or engine

    with active.begin() as connection:
        result = connection.execute(
            MARK_STORE_SKIP_REVIEW_FETCH,
            {"place_ids": cleaned},
        )

    updated = int(
        result.rowcount or 0
    )

    log.info(
        "mark_stores_skip_review_fetch: %s stores",
        updated,
    )

    return updated


def fetch_reviews_needing_recheck(
    *,
    now: datetime | None = None,
    db_engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """
    取得 next_check_at 已到期的 Review。

    正式 Recheck 不再限制 100 筆。
    """

    active = db_engine or engine
    when = now or datetime.now(timezone.utc)

    with active.connect() as connection:
        rows = connection.execute(
            FETCH_REVIEWS_NEEDING_RECHECK,
            {"now": when},
        ).mappings().all()

    result = [
        dict(row)
        for row in rows
    ]

    log.info(
        "fetch_reviews_needing_recheck: %s rows",
        len(result),
    )

    return result


def update_review_recheck_states(
    rows: list[dict[str, Any]],
    *,
    db_engine: Engine | None = None,
) -> int:
    """
    更新 schema.sql 已存在欄位：

    owner_reply_recheck
    owner_reply_recheck_at
    next_check_at

    使用情境：
    - Recheck 沒抓到該 Review → 今天 + 2 天
    - publishedAtDate 已超過 10 天 → 停止 Recheck
    """

    if not rows:
        return 0

    payload = [
        {
            "review_id": str(row["review_id"]),
            "owner_reply_recheck": bool(
                row["owner_reply_recheck"]
            ),
            "owner_reply_recheck_at": row.get(
                "owner_reply_recheck_at"
            ),
            "next_check_at": row.get(
                "next_check_at"
            ),
        }
        for row in rows
    ]

    active = db_engine or engine

    with active.begin() as connection:
        result = connection.execute(
            UPDATE_REVIEW_RECHECK_STATE,
            payload,
        )

    updated = int(
        result.rowcount or 0
    )

    log.info(
        "update_review_recheck_states: %s rows",
        updated,
    )

    return updated


def filter_existing_place_ids(
    place_ids: list[str],
    *,
    db_engine: Engine | None = None,
) -> list[str]:
    cleaned = [
        str(pid).strip()
        for pid in place_ids
        if pid and str(pid).strip()
    ]

    if not cleaned:
        return []

    active = db_engine or engine

    query = text(
        '''
        SELECT s."placeId"
        FROM "store" AS s
        WHERE s."placeId" IN :place_ids
          AND s."skip_review_fetch" = FALSE
          AND s."blocked" = FALSE
        '''
    ).bindparams(
        bindparam(
            "place_ids",
            expanding=True,
        )
    )

    with active.connect() as connection:
        rows = connection.execute(
            query,
            {"place_ids": cleaned},
        ).mappings().all()

    existing = {
        str(row["placeId"])
        for row in rows
    }

    return [
        pid
        for pid in cleaned
        if pid in existing
    ]


def save_review_batch(
    source_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    *,
    db_engine: Engine | None = None,
) -> tuple[int, int]:
    """WRITE review_source + review."""

    active = db_engine or engine

    source_payload: list[dict[str, Any]] = []

    for row in source_rows:
        raw_json = row["raw_json"]

        if not isinstance(raw_json, str):
            raw_json = json.dumps(
                raw_json,
                ensure_ascii=False,
            )

        source_payload.append(
            {
                "review_id": row["review_id"],
                "place_id": row["place_id"],
                "raw_json": raw_json,
                "scraped_at": row["scraped_at"],
            }
        )

    with active.begin() as connection:
        if source_payload:
            connection.execute(
                UPSERT_REVIEW_SOURCE,
                source_payload,
            )

        if review_rows:
            connection.execute(
                UPSERT_REVIEW,
                review_rows,
            )

    log.info(
        "save_review_batch: review_source=%s review=%s",
        len(source_payload),
        len(review_rows),
    )

    return (
        len(source_payload),
        len(review_rows),
    )


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
    """WRITE execution_log."""

    active = db_engine or engine

    payload = {
        "pipeline": pipeline,
        "status": status,
        "items_count": items_count,
        "apify_scheduler_id": apify_scheduler_id,
        "actor_name": actor_name,
        "started_at": started_at,
        "finished_at": finished_at,
        "request_json": json.dumps(
            request_json or {},
            ensure_ascii=False,
        ),
        "response_json": json.dumps(
            response_json or {},
            ensure_ascii=False,
        ),
        "error_msg": error_msg,
        "retry_count": retry_count,
    }

    with active.begin() as connection:
        row_id = connection.execute(
            INSERT_EXECUTION_LOG,
            payload,
        ).scalar_one()

    log.info(
        "execution_log id=%s pipeline=%s "
        "status=%s items=%s error=%s",
        row_id,
        pipeline,
        status,
        items_count,
        error_msg,
    )

    return int(row_id)


def clear_all_store_and_review_data(
    *,
    db_engine: Engine | None = None,
) -> dict[str, int]:
    """
    Test helper only.

    Delete demo/test rows:
    ai_analysis → review → review_source → store_source → store
    """

    active = db_engine or engine

    counts: dict[str, int] = {}

    statements = [
        (
            "ai_analysis",
            'DELETE FROM "ai_analysis"',
        ),
        (
            "review",
            'DELETE FROM "review"',
        ),
        (
            "review_source",
            'DELETE FROM "review_source"',
        ),
        (
            "store_source",
            'DELETE FROM "store_source"',
        ),
        (
            "store",
            'DELETE FROM "store"',
        ),
    ]

    with active.begin() as connection:
        for name, sql in statements:
            result = connection.execute(
                text(sql)
            )

            counts[name] = int(
                result.rowcount or 0
            )

    log.warning(
        "cleared DB tables: %s",
        counts,
    )

    return counts