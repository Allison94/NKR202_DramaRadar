"""PostgreSQL queries for Dashboard — columns match db/schema.sql.

Tables used (see db/schema.sql):
  READ "store"        → placeId, title, categoryName, address, lat, lng, …
  READ "review"       → placeId, text, stars, responseFromOwnerText, …
  READ "ai_analysis"  → placeId, review_score, owner_score, summaries, …

Scope: Taipei City only (address contains 台北市 / 臺北市).
This is the ONLY SQL entrypoint the Dashboard uses for store/map data.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from db.database import engine


TAIPEI_ADDRESS_FILTER = '''
      AND (
            s."address" LIKE '%台北市%'
         OR s."address" LIKE '%臺北市%'
      )
'''


DASHBOARD_QUERY = text(
    f'''
    WITH review_rollup AS (
        SELECT
            r."placeId",
            COUNT(*)::int AS review_rows,
            COUNT(r."responseFromOwnerText")::int AS owner_reply_rows,
            -- Prefer 1–2★ drama fights, not polite 4★ fluff
            (ARRAY_AGG(
                r."text"
                ORDER BY
                    r."stars" ASC,
                    CASE
                        WHEN r."responseFromOwnerText" IS NOT NULL
                         AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
                        THEN 0 ELSE 1
                    END,
                    r."publishedAtDate" DESC
            ))[1] AS latest_review_text,
            (ARRAY_AGG(
                r."responseFromOwnerText"
                ORDER BY
                    r."stars" ASC,
                    r."publishedAtDate" DESC
            ) FILTER (
                WHERE r."responseFromOwnerText" IS NOT NULL
                  AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
            ))[1] AS latest_owner_reply,
            (ARRAY_AGG(
                r."stars"
                ORDER BY r."stars" ASC, r."publishedAtDate" DESC
            ))[1] AS drama_stars,
            (ARRAY_AGG(
                r."reviewUrl"
                ORDER BY r."stars" ASC, r."publishedAtDate" DESC
            ))[1] AS latest_review_url
        FROM "review" AS r
        WHERE r."stars" <= 2
        GROUP BY r."placeId"
    ),
    analysis_rollup AS (
        SELECT
            a."placeId",
            ROUND(AVG(a."review_score")::numeric, 2) AS review_score,
            ROUND(AVG(a."owner_score")::numeric, 2) AS owner_score,
            ROUND(
                MAX(a."owner_score") FILTER (
                    WHERE a."owner_score" > 0
                )::numeric,
                2
            ) AS max_owner_score,
            (ARRAY_AGG(
                a."review_summary"
                ORDER BY GREATEST(a."review_score", a."owner_score") DESC
            ))[1] AS review_summary,
            (ARRAY_AGG(
                a."owner_summary"
                ORDER BY GREATEST(a."review_score", a."owner_score") DESC
            ))[1] AS owner_summary,
            (ARRAY_AGG(
                a."review_sentiment"
                ORDER BY a."review_score" DESC
            ))[1] AS review_sentiment,
            (ARRAY_AGG(
                a."owner_sentiment"
                ORDER BY a."owner_score" DESC
            ))[1] AS owner_sentiment,
            -- AI 公關回覆教學：schema.sql ai_analysis.pr_reply
            (ARRAY_AGG(
                a."pr_reply"
                ORDER BY GREATEST(a."review_score", a."owner_score") DESC
            ) FILTER (
                WHERE a."pr_reply" IS NOT NULL
                  AND LENGTH(TRIM(a."pr_reply")) > 0
            ))[1] AS pr_reply
        FROM "ai_analysis" AS a
        GROUP BY a."placeId"
    )
    SELECT
        s."placeId" AS store_id,
        s."title" AS name,
        s."categoryName" AS category,
        s."address" AS address,
        s."url" AS store_url,
        s."lat" AS lat,
        s."lng" AS lng,
        s."totalScore" AS google_score,
        s."reviewsCount" AS reviews,
        COALESCE(rr.review_rows, 0) AS db_review_count,
        COALESCE(rr.owner_reply_rows, 0) AS owner_replies,
        COALESCE(rr.latest_review_text, ar.review_summary, '尚無低星吵架評論')
            AS review_text,
        COALESCE(rr.latest_owner_reply, ar.owner_summary, '店家尚未回覆')
            AS owner_reply,
        COALESCE(ar.pr_reply, '') AS pr_reply,
        COALESCE(rr.latest_review_url, '') AS review_url,
        COALESCE(rr.drama_stars, 0) AS drama_stars,
        COALESCE(ar.review_score, 0) AS review_score,
        COALESCE(ar.owner_score, 0) AS owner_score,
        ar.max_owner_score AS max_owner_score,
        COALESCE(ar.review_sentiment, '') AS review_sentiment,
        COALESCE(ar.owner_sentiment, '') AS owner_sentiment
    FROM "store" AS s
    INNER JOIN review_rollup AS rr
        ON rr."placeId" = s."placeId"
    LEFT JOIN analysis_rollup AS ar
        ON ar."placeId" = s."placeId"
    WHERE s."blocked" = FALSE
    {TAIPEI_ADDRESS_FILTER}
      AND rr.review_rows > 0
    ORDER BY
        GREATEST(COALESCE(ar.owner_score, 0), COALESCE(ar.review_score, 0)) DESC,
        rr.review_rows DESC,
        s."reviewsCount" DESC
    LIMIT :limit
    '''
)

# schema.sql ai_analysis.pr_reply — for 公關回覆教室
FETCH_PR_REPLY_EXAMPLES = text(
    f'''
    SELECT
        s."title" AS store_name,
        s."placeId" AS place_id,
        r."reviewId" AS review_id,
        r."text" AS review_text,
        r."responseFromOwnerText" AS owner_reply,
        r."reviewUrl" AS review_url,
        a."pr_reply" AS pr_reply,
        a."review_score" AS guest_score,
        a."owner_score" AS owner_score
    FROM "ai_analysis" AS a
    INNER JOIN "review" AS r ON r."reviewId" = a."reviewId"
    INNER JOIN "store" AS s ON s."placeId" = a."placeId"
    WHERE s."blocked" = FALSE
    {TAIPEI_ADDRESS_FILTER}
      AND a."pr_reply" IS NOT NULL
      AND LENGTH(TRIM(a."pr_reply")) > 0
      AND r."stars" <= 2
    ORDER BY GREATEST(a."review_score", a."owner_score") DESC
    LIMIT :limit
    '''
)

# schema.sql "review" + "ai_analysis" — one store, many reviews
FETCH_STORE_REVIEWS = text(
    '''
    SELECT
        r."reviewId" AS review_id,
        r."placeId" AS place_id,
        r."text" AS review_text,
        r."stars" AS stars,
        r."reviewUrl" AS review_url,
        r."publishedAtDate" AS published_at,
        r."likesCount" AS likes_count,
        r."responseFromOwnerText" AS owner_reply,
        r."responseFromOwnerDate" AS owner_reply_date,
        COALESCE(a."review_score", 0) AS guest_score,
        COALESCE(a."owner_score", 0) AS owner_score,
        COALESCE(a."review_sentiment", '') AS guest_sentiment,
        COALESCE(a."owner_sentiment", '') AS owner_sentiment,
        COALESCE(a."review_summary", '') AS guest_summary,
        COALESCE(a."owner_summary", '') AS owner_summary,
        COALESCE(a."pr_reply", '') AS pr_reply
    FROM "review" AS r
    LEFT JOIN "ai_analysis" AS a
        ON a."reviewId" = r."reviewId"
    WHERE r."placeId" = :place_id
      AND r."stars" <= 2
    ORDER BY r."stars" ASC, r."publishedAtDate" DESC NULLS LAST
    LIMIT :limit
    '''
)


def fetch_dashboard_rows(
    limit: int = 300,
    *,
    db_engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """READ store + review + ai_analysis (schema.sql) for Taipei City dashboard."""

    safe_limit = max(1, min(int(limit), 2_000))
    active_engine = db_engine or engine

    with active_engine.connect() as connection:
        result = connection.execute(DASHBOARD_QUERY, {"limit": safe_limit})
        return [dict(row) for row in result.mappings().all()]


def fetch_store_reviews(
    place_id: str,
    *,
    limit: int = 50,
    db_engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """READ all reviews for one store from schema.sql review (+ ai_analysis)."""

    if not place_id or not str(place_id).strip():
        return []

    safe_limit = max(1, min(int(limit), 200))
    active_engine = db_engine or engine

    with active_engine.connect() as connection:
        rows = connection.execute(
            FETCH_STORE_REVIEWS,
            {"place_id": str(place_id).strip(), "limit": safe_limit},
        ).mappings().all()
    return [dict(row) for row in rows]


def fetch_pr_reply_examples(
    limit: int = 20,
    *,
    db_engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """READ ai_analysis.pr_reply rows that already have AI 公關範例."""

    safe_limit = max(1, min(int(limit), 100))
    active_engine = db_engine or engine
    with active_engine.connect() as connection:
        rows = connection.execute(
            FETCH_PR_REPLY_EXAMPLES,
            {"limit": safe_limit},
        ).mappings().all()
    return [dict(row) for row in rows]


def database_is_available(*, db_engine: Engine | None = None) -> bool:
    """Cheap health check used by scripts and debugging tools."""

    active_engine = db_engine or engine

    with active_engine.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1


REVIEW_STAR_QUERY = text(
    f'''
    SELECT
        r."stars" AS stars,
        COUNT(*)::int AS review_count
    FROM "review" AS r
    INNER JOIN "store" AS s ON s."placeId" = r."placeId"
    WHERE s."blocked" = FALSE
    {TAIPEI_ADDRESS_FILTER}
    GROUP BY r."stars"
    ORDER BY r."stars"
    '''
)


INTENSITY_RANKING_QUERY = text(
    f'''
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
    {TAIPEI_ADDRESS_FILTER}
    ORDER BY intensity DESC, s."reviewsCount" DESC
    LIMIT :limit
    '''
)


def fetch_review_star_distribution(
    *,
    db_engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """READ review.stars counts for Taipei City stores."""

    active_engine = db_engine or engine
    with active_engine.connect() as connection:
        rows = connection.execute(REVIEW_STAR_QUERY).mappings().all()
    return [dict(row) for row in rows]


def fetch_store_intensity_ranking(
    limit: int = 10,
    *,
    db_engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """READ store intensity ranking for Taipei City."""

    safe_limit = max(1, min(int(limit), 50))
    active_engine = db_engine or engine
    with active_engine.connect() as connection:
        rows = connection.execute(
            INTENSITY_RANKING_QUERY,
            {"limit": safe_limit},
        ).mappings().all()
    return [dict(row) for row in rows]
