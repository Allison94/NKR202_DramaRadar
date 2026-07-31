"""PostgreSQL queries used by the store dashboard domain.

This module only reads database records.  Presentation defaults and demo-data
fallbacks belong in ``service.py``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from db.database import engine


DASHBOARD_QUERY = text(
    '''
    WITH review_rollup AS (
        SELECT
            r."placeId",
            COUNT(*)::int AS review_rows,
            COUNT(r."responseFromOwnerText")::int AS owner_reply_rows,
            (ARRAY_AGG(
                r."text"
                ORDER BY
                    CASE
                        WHEN r."responseFromOwnerText" IS NOT NULL
                         AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
                        THEN 0 ELSE 1
                    END,
                    r."stars" ASC,
                    r."publishedAtDate" DESC
            ))[1] AS latest_review_text,
            (ARRAY_AGG(
                r."responseFromOwnerText"
                ORDER BY
                    CASE
                        WHEN r."responseFromOwnerText" IS NOT NULL
                         AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
                        THEN 0 ELSE 1
                    END,
                    r."stars" ASC,
                    r."publishedAtDate" DESC
            ) FILTER (WHERE r."responseFromOwnerText" IS NOT NULL))[1]
                AS latest_owner_reply,
            (ARRAY_AGG(
                r."stars"
                ORDER BY
                    CASE
                        WHEN r."responseFromOwnerText" IS NOT NULL
                         AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
                        THEN 0 ELSE 1
                    END,
                    r."stars" ASC,
                    r."publishedAtDate" DESC
            ))[1] AS drama_stars
        FROM "review" AS r
        GROUP BY r."placeId"
    ),
    analysis_rollup AS (
        SELECT
            a."placeId",
            ROUND(AVG(a."review_score")::numeric, 2) AS review_score,
            ROUND(AVG(a."owner_score")::numeric, 2) AS owner_score,
            (ARRAY_AGG(a."review_summary"))[1] AS review_summary,
            (ARRAY_AGG(a."owner_summary"))[1] AS owner_summary,
            (ARRAY_AGG(a."review_sentiment"))[1] AS review_sentiment,
            (ARRAY_AGG(a."owner_sentiment"))[1] AS owner_sentiment
        FROM "ai_analysis" AS a
        GROUP BY a."placeId"
    )
    SELECT
        s."placeId" AS store_id,
        s."title" AS name,
        s."categoryName" AS category,
        s."address" AS address,
        s."lat" AS lat,
        s."lng" AS lng,
        s."totalScore" AS google_score,
        s."reviewsCount" AS reviews,
        COALESCE(rr.owner_reply_rows, 0) AS owner_replies,
        COALESCE(rr.latest_review_text, ar.review_summary, '尚無評論內容')
            AS review_text,
        COALESCE(rr.latest_owner_reply, ar.owner_summary, '店家尚未回覆')
            AS owner_reply,
        COALESCE(rr.drama_stars, 0) AS drama_stars,
        COALESCE(ar.review_score, 0) AS review_score,
        COALESCE(ar.owner_score, 0) AS owner_score,
        COALESCE(ar.review_sentiment, '') AS review_sentiment,
        COALESCE(ar.owner_sentiment, '') AS owner_sentiment
    FROM "store" AS s
    LEFT JOIN review_rollup AS rr
        ON rr."placeId" = s."placeId"
    LEFT JOIN analysis_rollup AS ar
        ON ar."placeId" = s."placeId"
    WHERE s."blocked" = FALSE
      AND s."lat" BETWEEN 24.7 AND 25.35
      AND s."lng" BETWEEN 121.2 AND 122.1
    ORDER BY
        GREATEST(COALESCE(ar.owner_score, 0), COALESCE(ar.review_score, 0)) DESC,
        s."reviewsCount" DESC
    LIMIT :limit
    '''
)


def fetch_dashboard_rows(
    limit: int = 300,
    *,
    db_engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """Return dashboard-ready raw rows from PostgreSQL."""

    safe_limit = max(1, min(int(limit), 2_000))
    active_engine = db_engine or engine

    with active_engine.connect() as connection:
        result = connection.execute(DASHBOARD_QUERY, {"limit": safe_limit})
        return [dict(row) for row in result.mappings().all()]


def database_is_available(*, db_engine: Engine | None = None) -> bool:
    """Cheap health check used by scripts and debugging tools."""

    active_engine = db_engine or engine

    with active_engine.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1


REVIEW_STAR_QUERY = text(
    '''
    SELECT
        r."stars" AS stars,
        COUNT(*)::int AS review_count
    FROM "review" AS r
    INNER JOIN "store" AS s ON s."placeId" = r."placeId"
    WHERE s."blocked" = FALSE
    GROUP BY r."stars"
    ORDER BY r."stars"
    '''
)


INTENSITY_RANKING_QUERY = text(
    '''
    WITH review_rollup AS (
        SELECT
            r."placeId",
            COUNT(r."responseFromOwnerText")::int AS owner_reply_rows
        FROM "review" AS r
        GROUP BY r."placeId"
    ),
    analysis_rollup AS (
        SELECT
            a."placeId",
            ROUND(AVG(GREATEST(a."review_score", a."owner_score"))::numeric, 2)
                AS max_score
        FROM "ai_analysis" AS a
        GROUP BY a."placeId"
    )
    SELECT
        s."title" AS name,
        COALESCE(ar.max_score, 0) AS intensity,
        s."reviewsCount" AS reviews,
        COALESCE(rr.owner_reply_rows, 0) AS owner_replies
    FROM "store" AS s
    LEFT JOIN review_rollup AS rr ON rr."placeId" = s."placeId"
    LEFT JOIN analysis_rollup AS ar ON ar."placeId" = s."placeId"
    WHERE s."blocked" = FALSE
    ORDER BY intensity DESC, s."reviewsCount" DESC
    LIMIT :limit
    '''
)


def fetch_review_star_distribution(
    *,
    db_engine: Engine | None = None,
) -> list[dict[str, Any]]:
    active_engine = db_engine or engine
    with active_engine.connect() as connection:
        rows = connection.execute(REVIEW_STAR_QUERY).mappings().all()
    return [dict(row) for row in rows]


def fetch_store_intensity_ranking(
    limit: int = 10,
    *,
    db_engine: Engine | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 50))
    active_engine = db_engine or engine
    with active_engine.connect() as connection:
        rows = connection.execute(
            INTENSITY_RANKING_QUERY,
            {"limit": safe_limit},
        ).mappings().all()
    return [dict(row) for row in rows]
