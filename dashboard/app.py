from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from urllib.parse import quote, urlparse
import html
import random
import re
import sys

import folium
import pandas as pd
import streamlit as st
from folium import DivIcon, Marker
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
from sqlalchemy import bindparam, text as sql_text



# ============================================================
# Project / data access
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import engine as db_engine

# 沿用既有 Store Repository 作為 Dashboard SQL 入口。
# 只 READ，不改 schema、不 INSERT / UPDATE Store、Review、AI。
from domains.store.repository import (
    fetch_dashboard_rows,
    fetch_store_reviews,
)


# ============================================================
# App config
# ============================================================

st.set_page_config(
    page_title="Drama Radar｜台北吵架地圖",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
SPLASH_IMAGE = ASSETS_DIR / "splash.png"

PAGE_MAP = "🗺️ 吵架地圖"
PAGE_DUEL = "💬 經典對決"
PAGE_ANALYSIS = "📊 全站分析"
PAGE_RANKING = "🏆 吵架名人堂"
PAGE_PR = "🤖 公關救援"
PAGE_REPORT = "🕵️ 匿名爆料"

PAGES = [
    PAGE_MAP,
    PAGE_RANKING,
    PAGE_ANALYSIS,
]

DISTRICT_PATTERN = re.compile(
    r"(?:台北市|臺北市).*?([\u4e00-\u9fff]{1,4}區)"
)

# 只影響畫面顯示，不改 DB。
DISPLAY_NAME_LIMIT = 26
REVIEW_PAGE_SIZE = 100


# ============================================================
# Navigation state
# ============================================================

if "_next_page" in st.session_state:
    st.session_state["main_nav"] = st.session_state.pop(
        "_next_page"
    )

if "main_nav" not in st.session_state:
    st.session_state["main_nav"] = PAGE_MAP


def go_to(
    page: str,
    *,
    store_id: str | None = None,
) -> None:
    # 經典對決 / 公關救援已整合進店家詳情，舊按鈕也導回地圖。
    if page in {PAGE_DUEL, PAGE_PR}:
        page = PAGE_MAP

    st.session_state["_next_page"] = page

    if store_id:
        store_id = str(store_id)
        st.session_state["target_store_id"] = store_id
        st.session_state["selected_store_id"] = store_id
        st.session_state["map_store_detail_selector"] = store_id

    st.rerun()


# 地圖 popup 的「查看全部評論」用 query params 回到同一個 Streamlit app。
query_store_id = str(
    st.query_params.get("store_id", "")
    or ""
).strip()

if (
    query_store_id
    and st.session_state.get("_consumed_store_id") != query_store_id
):
    st.session_state["selected_store_id"] = query_store_id
    st.session_state["target_store_id"] = query_store_id
    st.session_state["map_store_detail_selector"] = query_store_id
    st.session_state["main_nav"] = PAGE_MAP
    st.session_state["_consumed_store_id"] = query_store_id


# ============================================================
# Generic helpers
# ============================================================

def render_html(content: str) -> None:
    st.html(dedent(content).strip())


def safe_text(value: object) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def safe_url(value: object) -> str:
    text = str(value or "").strip()

    if not text:
        return ""

    try:
        parsed = urlparse(text)
    except ValueError:
        return ""

    if parsed.scheme not in {"http", "https"}:
        return ""

    return text


def to_number(value: object) -> float | None:
    number = pd.to_numeric(
        pd.Series([value]),
        errors="coerce",
    ).iloc[0]

    if pd.isna(number):
        return None

    return float(number)


def district_from_address(address: object) -> str:
    text = str(address or "")
    match = DISTRICT_PATTERN.search(text)

    return (
        match.group(1)
        if match
        else "未辨識行政區"
    )


def display_store_name(
    value: object,
    limit: int = DISPLAY_NAME_LIMIT,
) -> str:
    """
    UI-only shortening.
    Never changes store.title in PostgreSQL.
    """

    text = str(value or "").strip()

    if len(text) <= limit:
        return text

    separators = [
        "｜",
        "|",
        " 好吃",
        " 人氣",
        " 熱門",
        " 特色",
        " 上班族",
        " 外送",
    ]

    candidate = text

    for separator in separators:
        if separator in candidate:
            candidate = candidate.split(
                separator,
                1,
            )[0].strip()

    if candidate and len(candidate) <= limit:
        return candidate

    return text[:limit].rstrip() + "…"


def has_ai_store(row: pd.Series) -> bool:
    """
    Existing repository COALESCEs missing AI values to 0 / ''.
    This only detects whether real AI fields are present.
    """

    review_score = (
        to_number(row.get("review_score"))
        or 0.0
    )
    owner_score = (
        to_number(row.get("owner_score"))
        or 0.0
    )

    return any(
        [
            review_score > 0,
            owner_score > 0,
            bool(
                str(
                    row.get(
                        "review_sentiment"
                    )
                    or ""
                ).strip()
            ),
            bool(
                str(
                    row.get(
                        "owner_sentiment"
                    )
                    or ""
                ).strip()
            ),
            bool(
                str(
                    row.get("pr_reply")
                    or ""
                ).strip()
            ),
        ]
    )


def store_intensity(
    row: pd.Series,
) -> float | None:
    """
    Team rule:
    (review_score + owner_score) / 2.
    No AI -> no fake score.
    """

    if not has_ai_store(row):
        return None

    review_score = to_number(
        row.get("review_score")
    )
    owner_score = to_number(
        row.get("owner_score")
    )

    if (
        review_score is None
        or owner_score is None
    ):
        return None

    return (
        float(review_score)
        + float(owner_score)
    ) / 2


def has_ai_review(row: pd.Series) -> bool:
    guest_score = (
        to_number(row.get("guest_score"))
        or 0.0
    )
    owner_score = (
        to_number(row.get("owner_score"))
        or 0.0
    )

    return any(
        [
            guest_score > 0,
            owner_score > 0,
            bool(
                str(
                    row.get(
                        "guest_sentiment"
                    )
                    or ""
                ).strip()
            ),
            bool(
                str(
                    row.get(
                        "owner_sentiment"
                    )
                    or ""
                ).strip()
            ),
            bool(
                str(
                    row.get("pr_reply")
                    or ""
                ).strip()
            ),
        ]
    )


def review_intensity(
    row: pd.Series,
) -> float | None:
    if not has_ai_review(row):
        return None

    guest_score = to_number(
        row.get("guest_score")
    )
    owner_score = to_number(
        row.get("owner_score")
    )

    if (
        guest_score is None
        or owner_score is None
    ):
        return None

    return (
        float(guest_score)
        + float(owner_score)
    ) / 2


def truncate_text(
    value: object,
    limit: int = 190,
) -> str:
    text = str(value or "").strip()

    if len(text) <= limit:
        return text

    return text[:limit].rstrip() + "…"


# ============================================================
# Data loading / normalization
# ============================================================

def normalize_store_frame(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    result = frame.copy()

    if result.empty:
        return result

    text_columns = [
        "store_id",
        "name",
        "category",
        "address",
        "store_url",
        "review_text",
        "owner_reply",
        "pr_reply",
        "review_url",
        "review_sentiment",
        "owner_sentiment",
    ]

    for column in text_columns:
        if column not in result.columns:
            result[column] = ""

        result[column] = (
            result[column]
            .fillna("")
            .astype(str)
        )

    numeric_columns = [
        "lat",
        "lng",
        "google_score",
        "reviews",
        "db_review_count",
        "owner_replies",
        "drama_stars",
        "review_score",
        "owner_score",
    ]

    for column in numeric_columns:
        if column not in result.columns:
            result[column] = pd.NA

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    result["district"] = (
        result["address"]
        .apply(district_from_address)
    )

    result["display_name"] = (
        result["name"]
        .apply(display_store_name)
    )

    result["has_ai"] = result.apply(
        has_ai_store,
        axis=1,
    )

    result["intensity"] = result.apply(
        store_intensity,
        axis=1,
    )

    review_count = (
        result["db_review_count"]
        .fillna(0)
    )
    owner_count = (
        result["owner_replies"]
        .fillna(0)
    )

    result["reply_rate"] = 0.0

    valid = review_count > 0

    result.loc[
        valid,
        "reply_rate",
    ] = (
        owner_count[valid]
        / review_count[valid]
        * 100
    )

    # Schema lat/lng defaults to 0.
    # 0,0 is not a valid Taipei marker.
    result = result.dropna(
        subset=["lat", "lng"]
    )

    result = result[
        result["lat"].between(
            24.8,
            25.3,
        )
        & result["lng"].between(
            121.2,
            122.0,
        )
    ].copy()

    return result.reset_index(
        drop=True
    )


def normalize_review_frame(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    result = frame.copy()

    if result.empty:
        return result

    numeric_columns = [
        "stars",
        "likes_count",
        "guest_score",
        "owner_score",
    ]

    for column in numeric_columns:
        if column not in result.columns:
            result[column] = pd.NA

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    text_columns = [
        "review_id",
        "place_id",
        "review_text",
        "review_url",
        "owner_reply",
        "guest_sentiment",
        "owner_sentiment",
        "guest_summary",
        "owner_summary",
        "pr_reply",
    ]

    for column in text_columns:
        if column not in result.columns:
            result[column] = ""

        result[column] = (
            result[column]
            .fillna("")
            .astype(str)
        )

    result["has_owner_reply"] = (
        result["owner_reply"]
        .str.strip()
        .ne("")
    )

    result["has_ai"] = result.apply(
        has_ai_review,
        axis=1,
    )

    result["intensity"] = result.apply(
        review_intensity,
        axis=1,
    )

    return result


@st.cache_data(
    ttl=300,
    show_spinner="載入地圖中…",
)
def load_store_data() -> pd.DataFrame:
    rows = fetch_dashboard_rows(
        limit=2000
    )

    return normalize_store_frame(
        pd.DataFrame(rows)
    )


@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_store_reviews(
    place_id: str,
) -> pd.DataFrame:
    rows = fetch_store_reviews(
        str(place_id),
        limit=200,
    )

    frame = normalize_review_frame(
        pd.DataFrame(rows)
    )

    if frame.empty:
        return frame

    # Dashboard 的「吵架案例」定義：
    # 1–2★ 且店家真的有回覆。沒回覆的不進入前台案例。
    return frame[
        frame["has_owner_reply"]
    ].reset_index(drop=True)


# Dashboard-only READ queries. 其他 domain / schema 完全不修改。
# 首頁瀏覽全部「1–2★ + 店家有回覆」案例，因此不能受 fetch_store_reviews(limit<=200) 限制。

@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_map_review_previews(
    place_ids: tuple[str, ...],
) -> pd.DataFrame:
    # 每家店抓 1 筆一致的 review + owner reply，供地圖 popup 預覽。
    if not place_ids:
        return pd.DataFrame()

    preview_sql = sql_text(
        r'''
        SELECT DISTINCT ON (r."placeId")
            r."placeId" AS place_id,
            r."reviewId" AS review_id,
            r."text" AS review_text,
            r."stars" AS stars,
            r."publishedAtDate" AS published_at,
            r."responseFromOwnerText" AS owner_reply,
            r."reviewUrl" AS review_url,
            a."review_score" AS guest_score,
            a."owner_score" AS owner_score,
            a."review_summary" AS guest_summary,
            a."owner_summary" AS owner_summary
        FROM "review" AS r
        LEFT JOIN "ai_analysis" AS a
            ON a."reviewId" = r."reviewId"
        WHERE r."placeId" IN :place_ids
          AND r."stars" <= 2
          AND r."responseFromOwnerText" IS NOT NULL
          AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
          AND r."responseFromOwnerText" IS NOT NULL
          AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
        ORDER BY
            r."placeId",
            CASE
                WHEN r."responseFromOwnerText" IS NOT NULL
                 AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
                THEN 0 ELSE 1
            END,
            r."stars" ASC,
            r."publishedAtDate" DESC NULLS LAST
        '''
    ).bindparams(
        bindparam("place_ids", expanding=True)
    )

    with db_engine.connect() as connection:
        rows = connection.execute(
            preview_sql,
            {"place_ids": list(place_ids)},
        ).mappings().all()

    frame = pd.DataFrame(
        [dict(row) for row in rows]
    )

    if frame.empty:
        return frame

    return normalize_review_frame(frame)


@st.cache_data(
    ttl=300,
    show_spinner="正在載入吵架評論…",
)
def load_all_review_page(
    place_ids: tuple[str, ...],
    page: int,
    page_size: int = REVIEW_PAGE_SIZE,
) -> tuple[pd.DataFrame, int]:
    # 讀取符合目前地圖篩選、且店家有回覆的 1–2 星案例，每頁固定 100 筆。
    if not place_ids:
        return pd.DataFrame(), 0

    safe_page = max(1, int(page))
    safe_page_size = max(1, min(int(page_size), REVIEW_PAGE_SIZE))
    offset = (safe_page - 1) * safe_page_size

    count_sql = sql_text(
        r'''
        SELECT COUNT(*)::int
        FROM "review" AS r
        WHERE r."placeId" IN :place_ids
          AND r."stars" <= 2
        '''
    ).bindparams(
        bindparam("place_ids", expanding=True)
    )

    page_sql = sql_text(
        r'''
        SELECT
            r."reviewId" AS review_id,
            r."placeId" AS place_id,
            s."title" AS store_name,
            s."address" AS address,
            s."url" AS store_url,
            r."text" AS review_text,
            r."stars" AS stars,
            r."reviewUrl" AS review_url,
            r."publishedAtDate" AS published_at,
            r."likesCount" AS likes_count,
            r."responseFromOwnerText" AS owner_reply,
            a."review_score" AS guest_score,
            a."owner_score" AS owner_score,
            a."review_sentiment" AS guest_sentiment,
            a."owner_sentiment" AS owner_sentiment,
            a."review_summary" AS guest_summary,
            a."owner_summary" AS owner_summary,
            a."pr_reply" AS pr_reply
        FROM "review" AS r
        INNER JOIN "store" AS s
            ON s."placeId" = r."placeId"
        LEFT JOIN "ai_analysis" AS a
            ON a."reviewId" = r."reviewId"
        WHERE r."placeId" IN :place_ids
          AND r."stars" <= 2
          AND r."responseFromOwnerText" IS NOT NULL
          AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
        ORDER BY
            r."publishedAtDate" DESC NULLS LAST,
            r."reviewId"
        LIMIT :page_size
        OFFSET :offset
        '''
    ).bindparams(
        bindparam("place_ids", expanding=True)
    )

    params = {
        "place_ids": list(place_ids),
        "page_size": safe_page_size,
        "offset": offset,
    }

    with db_engine.connect() as connection:
        total = int(
            connection.execute(
                count_sql,
                {"place_ids": list(place_ids)},
            ).scalar()
            or 0
        )
        rows = connection.execute(
            page_sql,
            params,
        ).mappings().all()

    raw_frame = pd.DataFrame(
        [dict(row) for row in rows]
    )

    if raw_frame.empty:
        return raw_frame, total

    extra_columns = raw_frame[
        ["store_name", "address", "store_url"]
    ].copy()

    frame = normalize_review_frame(
        raw_frame
    )

    for column in [
        "store_name",
        "address",
        "store_url",
    ]:
        frame[column] = (
            extra_columns[column]
            .fillna("")
            .astype(str)
            .values
        )

    return frame, total

@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_store_rating_summary(
    place_id: str,
) -> dict[str, object]:
    """READ store rating distribution for a Google-Maps-like summary UI."""
    query = sql_text(
        r'''
        SELECT
            s."placeId" AS place_id,
            s."title" AS store_name,
            s."categoryName" AS category,
            s."address" AS address,
            s."url" AS store_url,
            s."totalScore" AS google_score,
            s."reviewsCount" AS reviews_count,
            s."oneStar" AS one_star,
            s."twoStar" AS two_star,
            s."threeStar" AS three_star,
            s."fourStar" AS four_star,
            s."fiveStar" AS five_star
        FROM "store" AS s
        WHERE s."placeId" = :place_id
          AND s."blocked" = FALSE
        LIMIT 1
        '''
    )

    with db_engine.connect() as connection:
        row = connection.execute(
            query,
            {"place_id": str(place_id)},
        ).mappings().first()

    return dict(row) if row else {}


@st.cache_data(
    ttl=300,
    show_spinner="正在載入店家評論…",
)
def load_store_review_page(
    place_id: str,
    page: int,
    filter_key: str,
    sort_key: str,
    page_size: int = REVIEW_PAGE_SIZE,
) -> tuple[pd.DataFrame, int]:
    """READ all 1–2★ reviews for one store with server-side pagination."""
    safe_page = max(1, int(page))
    safe_page_size = max(1, min(int(page_size), REVIEW_PAGE_SIZE))
    offset = (safe_page - 1) * safe_page_size

    # 所有店家詳情評論都必須先符合「店家有回覆」。
    # 再在這批有效吵架案例上做 AI / 星等篩選。
    filter_sql = {
        "全部": "",
        "AI 已分析": 'AND a."reviewId" IS NOT NULL',
        "1 星": 'AND r."stars" = 1',
        "2 星": 'AND r."stars" = 2',
    }.get(filter_key, "")

    order_sql = {
        "最新": 'r."publishedAtDate" DESC NULLS LAST, r."reviewId"',
        "最激烈": '''
            CASE
                WHEN a."review_score" IS NOT NULL
                 AND a."owner_score" IS NOT NULL
                THEN (a."review_score" + a."owner_score") / 2.0
                ELSE -1
            END DESC,
            r."publishedAtDate" DESC NULLS LAST,
            r."reviewId"
        ''',
        "最多讚": '''
            r."likesCount" DESC NULLS LAST,
            r."publishedAtDate" DESC NULLS LAST,
            r."reviewId"
        ''',
        "最舊": 'r."publishedAtDate" ASC NULLS LAST, r."reviewId"',
    }.get(
        sort_key,
        'r."publishedAtDate" DESC NULLS LAST, r."reviewId"',
    )

    count_sql = sql_text(
        f'''
        SELECT COUNT(*)::int
        FROM "review" AS r
        LEFT JOIN "ai_analysis" AS a
            ON a."reviewId" = r."reviewId"
        WHERE r."placeId" = :place_id
          AND r."stars" <= 2
          AND r."responseFromOwnerText" IS NOT NULL
          AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
          {filter_sql}
        '''
    )

    page_sql = sql_text(
        f'''
        SELECT
            r."reviewId" AS review_id,
            r."placeId" AS place_id,
            s."title" AS store_name,
            s."address" AS address,
            s."url" AS store_url,
            r."text" AS review_text,
            r."stars" AS stars,
            r."reviewUrl" AS review_url,
            r."publishedAtDate" AS published_at,
            r."likesCount" AS likes_count,
            r."responseFromOwnerText" AS owner_reply,
            a."review_score" AS guest_score,
            a."owner_score" AS owner_score,
            a."review_sentiment" AS guest_sentiment,
            a."owner_sentiment" AS owner_sentiment,
            a."review_summary" AS guest_summary,
            a."owner_summary" AS owner_summary,
            a."pr_reply" AS pr_reply
        FROM "review" AS r
        INNER JOIN "store" AS s
            ON s."placeId" = r."placeId"
        LEFT JOIN "ai_analysis" AS a
            ON a."reviewId" = r."reviewId"
        WHERE r."placeId" = :place_id
          AND r."stars" <= 2
          AND r."responseFromOwnerText" IS NOT NULL
          AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
          {filter_sql}
        ORDER BY {order_sql}
        LIMIT :page_size
        OFFSET :offset
        '''
    )

    with db_engine.connect() as connection:
        total = int(
            connection.execute(
                count_sql,
                {"place_id": str(place_id)},
            ).scalar()
            or 0
        )
        rows = connection.execute(
            page_sql,
            {
                "place_id": str(place_id),
                "page_size": safe_page_size,
                "offset": offset,
            },
        ).mappings().all()

    raw = pd.DataFrame([dict(row) for row in rows])
    if raw.empty:
        return raw, total

    extras = raw[["store_name", "address", "store_url"]].copy()
    frame = normalize_review_frame(raw)
    for column in ["store_name", "address", "store_url"]:
        frame[column] = extras[column].fillna("").astype(str).values

    return frame, total


@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_store_classic_reviews(
    place_id: str,
    limit: int = 20,
) -> pd.DataFrame:
    """READ the most intense AI-analyzed owner-reply cases for one store."""
    query = sql_text(
        r'''
        SELECT
            r."reviewId" AS review_id,
            r."placeId" AS place_id,
            r."text" AS review_text,
            r."stars" AS stars,
            r."reviewUrl" AS review_url,
            r."publishedAtDate" AS published_at,
            r."likesCount" AS likes_count,
            r."responseFromOwnerText" AS owner_reply,
            a."review_score" AS guest_score,
            a."owner_score" AS owner_score,
            a."review_sentiment" AS guest_sentiment,
            a."owner_sentiment" AS owner_sentiment,
            a."review_summary" AS guest_summary,
            a."owner_summary" AS owner_summary,
            a."pr_reply" AS pr_reply
        FROM "review" AS r
        INNER JOIN "ai_analysis" AS a
            ON a."reviewId" = r."reviewId"
        WHERE r."placeId" = :place_id
          AND r."stars" <= 2
          AND r."responseFromOwnerText" IS NOT NULL
          AND LENGTH(TRIM(r."responseFromOwnerText")) > 0
          AND a."review_score" IS NOT NULL
          AND a."owner_score" IS NOT NULL
        ORDER BY
            (a."review_score" + a."owner_score") / 2.0 DESC,
            r."publishedAtDate" DESC NULLS LAST
        LIMIT :limit
        '''
    )

    with db_engine.connect() as connection:
        rows = connection.execute(
            query,
            {
                "place_id": str(place_id),
                "limit": max(1, min(int(limit), 100)),
            },
        ).mappings().all()

    return normalize_review_frame(
        pd.DataFrame([dict(row) for row in rows])
    )


@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_store_ai_rows(
    place_id: str,
) -> pd.DataFrame:
    """READ all AI rows for store-level analysis. No writes."""
    query = sql_text(
        r'''
        SELECT
            a."review_score" AS guest_score,
            a."owner_score" AS owner_score,
            a."review_sentiment" AS guest_sentiment,
            a."owner_sentiment" AS owner_sentiment
        FROM "ai_analysis" AS a
        WHERE a."placeId" = :place_id
        ORDER BY a."reviewId"
        '''
    )

    with db_engine.connect() as connection:
        rows = connection.execute(
            query,
            {"place_id": str(place_id)},
        ).mappings().all()

    return pd.DataFrame([dict(row) for row in rows])


def refresh_all() -> None:
    st.cache_data.clear()
    st.session_state[
        "last_refresh_at"
    ] = datetime.now(
        timezone.utc
    )
    st.rerun()


# ============================================================
# CSS — white / readable website style
# ============================================================

render_html(
    """
    <style>
    :root {
        --bg:#ffffff;
        --panel:#ffffff;
        --panel2:#fff8f6;
        --line:#e6e7eb;
        --text:#18181b;
        --muted:#686b73;
        --pink:#e9255c;
        --orange:#f97316;
        --purple:#8b3fd6;
        --yellow:#f5a623;
        --soft-pink:#fff1f4;
        --soft-orange:#fff7ed;
        --soft-purple:#faf5ff;
    }

    html, body {
        font-size:17px;
    }

    .stApp,
    [data-testid="stAppViewContainer"] {
        background:#ffffff !important;
        color:var(--text) !important;
    }

    [data-testid="stSidebar"],
    [data-testid="collapsedControl"] {
        display:none !important;
    }

    [data-testid="stHeader"] {
        background:rgba(255,255,255,.96) !important;
        border-bottom:1px solid var(--line);
        backdrop-filter:blur(14px);
    }

    footer {
        display:none !important;
    }

    .block-container {
        max-width:1560px;
        padding-top:1.35rem;
        padding-bottom:4rem;
    }

    h1,h2,h3,h4,h5,h6,
    p, label,
    [data-testid="stMarkdownContainer"],
    [data-testid="stCaptionContainer"] {
        color:var(--text) !important;
    }

    [data-testid="stMarkdownContainer"] p {
        font-size:1.02rem;
        line-height:1.75;
    }

    [data-testid="stCaptionContainer"] {
        font-size:.93rem;
        color:var(--muted) !important;
    }

    .brand-strip {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:16px;
        margin:5px 0 10px;
        padding:14px 16px;
        border:1px solid #f1d5dc;
        border-radius:15px;
        background:#fff8fa;
    }

    .brand-name {
        font-size:1.15rem;
        font-weight:950;
        letter-spacing:-.02em;
    }

    .page-title {
        margin:18px 0 3px;
        font-size:clamp(2rem,3vw,2.65rem);
        font-weight:950;
        letter-spacing:-.04em;
        color:#141414;
    }

    .page-subtitle {
        margin:0 0 18px;
        color:var(--muted);
        font-size:1.05rem;
        line-height:1.7;
    }

    div[role="radiogroup"] {
        gap:.5rem;
        padding:.48rem;
        border:1px solid var(--line);
        border-radius:14px;
        background:#ffffff;
        box-shadow:0 2px 12px rgba(20,20,20,.04);
    }

    div[role="radiogroup"] label {
        margin:0 !important;
        padding:.52rem .78rem !important;
        border:1px solid transparent;
        border-radius:10px;
        transition:all .15s ease;
        color:#242428 !important;
        font-size:.98rem !important;
        font-weight:750 !important;
    }

    div[role="radiogroup"] label:hover {
        border-color:#f3c8d3;
        background:#fff7f9;
    }

    div[role="radiogroup"] label:has(input:checked) {
        border-color:#ef9fb4;
        background:#fff0f4;
        color:#b81f4b !important;
    }

    [data-baseweb="input"] > div,
    [data-baseweb="select"] > div,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        background:#ffffff !important;
        color:#171717 !important;
        border-color:#dadce1 !important;
    }

    [data-baseweb="select"] span,
    [data-baseweb="select"] div {
        color:#171717 !important;
    }

    [data-testid="stSelectbox"] label,
    [data-testid="stTextInput"] label,
    [data-testid="stSlider"] label,
    [data-testid="stNumberInput"] label {
        font-size:1rem !important;
        font-weight:800 !important;
        color:#28282c !important;
    }

    .muted {
        color:var(--muted);
        font-size:.92rem;
    }

    .legend {
        display:flex;
        gap:14px;
        flex-wrap:wrap;
        margin:5px 0 10px;
        color:var(--muted);
        font-size:.9rem;
    }

    .map-side-title {
        margin:4px 0 12px;
        font-size:1.4rem;
        font-weight:950;
        color:#19191d;
    }

    .rank-card {
        display:grid;
        grid-template-columns:38px minmax(0,1fr) auto;
        gap:9px;
        align-items:center;
        margin-bottom:9px;
        padding:13px 12px;
        border:1px solid var(--line);
        border-radius:12px;
        background:#ffffff;
        box-shadow:0 2px 10px rgba(20,20,20,.035);
    }

    .rank-no {
        color:#d72555;
        font-weight:950;
    }

    .rank-name {
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
        font-size:1rem;
        font-weight:850;
        color:#202024;
    }

    .rank-score {
        color:#c85b00;
        font-weight:950;
        white-space:nowrap;
    }

    .duel-arena {
        padding:22px;
        border:1px solid #efc9d2;
        border-radius:20px;
        background:#ffffff;
        box-shadow:0 6px 24px rgba(20,20,20,.055);
    }

    .duel-store {
        font-size:clamp(1.55rem,2.3vw,2.05rem);
        font-weight:950;
        letter-spacing:-.03em;
        color:#18181b;
    }

    .duel-meta {
        margin-top:6px;
        color:var(--muted);
        font-size:.95rem;
    }

    .score-row {
        display:flex;
        gap:8px;
        flex-wrap:wrap;
        margin-top:14px;
    }

    .pill {
        display:inline-block;
        padding:6px 10px;
        border:1px solid #dedfe3;
        border-radius:999px;
        background:#fafafa;
        color:#333338;
        font-size:.9rem;
        font-weight:850;
    }

    .pill-hot {
        border-color:#efb0bf;
        background:#fff0f4;
        color:#c82250;
    }

    .duel-grid {
        display:grid;
        grid-template-columns:1fr 70px 1fr;
        gap:14px;
        margin-top:18px;
    }

    .duel-side {
        min-height:220px;
        padding:20px;
        border-radius:15px;
        line-height:1.85;
        font-size:1.04rem;
        color:#222226;
    }

    .duel-customer {
        border:1px solid #f2c9d3;
        background:var(--soft-pink);
    }

    .duel-owner {
        border:1px solid #fed7aa;
        background:var(--soft-orange);
    }

    .duel-label {
        margin-bottom:9px;
        font-size:1.08rem;
        font-weight:950;
    }

    .duel-vs {
        display:flex;
        align-items:center;
        justify-content:center;
        color:#d52a59;
        font-size:1.4rem;
        font-weight:950;
    }

    .ai-summary {
        margin-top:14px;
        padding:15px 16px;
        border:1px solid #e6d1f7;
        border-radius:13px;
        background:var(--soft-purple);
        color:#29232f;
        line-height:1.75;
        font-size:1rem;
    }

    .rescue-grid {
        display:grid;
        grid-template-columns:1fr 1fr 1fr;
        gap:12px;
        margin-bottom:14px;
    }

    .rescue-card {
        min-height:205px;
        padding:17px;
        border:1px solid var(--line);
        border-radius:15px;
        background:#ffffff;
        color:#222226;
        line-height:1.78;
        font-size:1rem;
    }

    .rescue-card.actual {
        border-color:#fed7aa;
        background:#fffaf5;
    }

    .rescue-card.ai {
        border-color:#e6d1f7;
        background:#fcf8ff;
    }

    .rescue-title {
        margin-bottom:8px;
        font-weight:950;
    }

    .big-number {
        font-size:2.1rem;
        font-weight:950;
        letter-spacing:-.04em;
    }

    .section-rule {
        height:1px;
        margin:22px 0;
        background:var(--line);
    }


    [data-testid="stVerticalBlockBorderWrapper"] {
        background:#ffffff !important;
        border-color:#e3e4e8 !important;
    }

    [data-baseweb="tab-list"] {
        background:#ffffff !important;
    }

    [data-baseweb="tab"] {
        color:#26262b !important;
        font-size:.96rem !important;
        font-weight:800 !important;
    }

    [data-baseweb="tab"][aria-selected="true"] {
        color:#c82150 !important;
    }

    [data-testid="stMetric"] {
        border:1px solid var(--line);
        border-radius:14px;
        padding:13px;
        background:#ffffff;
        box-shadow:0 2px 10px rgba(20,20,20,.035);
    }

    [data-testid="stMetric"] label,
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color:#18181b !important;
    }

    .stButton > button,
    [data-testid="stFormSubmitButton"] button {
        border:1px solid #d8295a;
        border-radius:11px;
        background:linear-gradient(90deg,#e32c5d,#c82175);
        color:white !important;
        font-weight:850;
        min-height:42px;
        font-size:.98rem;
    }

    .stButton > button:hover,
    [data-testid="stFormSubmitButton"] button:hover {
        border-color:#b91c4c;
        background:linear-gradient(90deg,#d92556,#b91c68);
    }

    [data-testid="stLinkButton"] a {
        border-radius:11px;
        font-weight:800;
    }

    iframe[title="streamlit_folium.st_folium"] {
        border:1px solid var(--line);
        border-radius:16px;
        overflow:hidden;
        box-shadow:0 5px 22px rgba(20,20,20,.06);
    }

    .review-feed-head {
        display:flex;
        align-items:flex-end;
        justify-content:space-between;
        gap:18px;
        margin:30px 0 13px;
        padding-top:14px;
        border-top:1px solid var(--line);
    }

    .review-feed-title {
        font-size:1.75rem;
        font-weight:950;
        color:#17171b;
    }

    .review-feed-subtitle {
        margin-top:3px;
        color:var(--muted);
        font-size:1rem;
    }

    .review-card {
        margin-bottom:14px;
        padding:19px 20px;
        border:1px solid #e1e2e6;
        border-radius:16px;
        background:#ffffff;
        box-shadow:0 3px 16px rgba(20,20,20,.045);
    }

    .review-store {
        font-size:1.22rem;
        font-weight:950;
        color:#19191d;
        margin-bottom:4px;
    }

    .review-meta {
        color:#72757d;
        font-size:.92rem;
        margin-bottom:12px;
    }

    .review-badges {
        display:flex;
        gap:7px;
        flex-wrap:wrap;
        margin-bottom:12px;
    }

    .review-badge {
        display:inline-block;
        padding:4px 9px;
        border-radius:999px;
        background:#f5f5f6;
        border:1px solid #e3e3e5;
        color:#39393e;
        font-size:.86rem;
        font-weight:850;
    }

    .review-badge.hot {
        background:#fff0f4;
        border-color:#f0b8c5;
        color:#c5224f;
    }

    .review-dialogue {
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:13px;
    }

    .review-side {
        padding:15px 16px;
        border-radius:13px;
        font-size:1.03rem;
        line-height:1.8;
        white-space:normal;
        overflow-wrap:anywhere;
        color:#222226;
    }

    .review-side.customer {
        background:#fff4f6;
        border:1px solid #f3cbd4;
    }

    .review-side.owner {
        background:#fff8ef;
        border:1px solid #fedbb2;
    }

    .review-side-title {
        margin-bottom:7px;
        font-size:1.02rem;
        font-weight:950;
    }

    /* Google-Maps-inspired store detail / review browsing */
    .gm-store-shell {
        margin-top:26px;
        border:1px solid #e0e3e7;
        border-radius:20px;
        background:#fff;
        box-shadow:0 5px 24px rgba(32,33,36,.07);
        overflow:hidden;
    }

    .gm-store-head {
        padding:24px 26px 20px;
        border-bottom:1px solid #eceff1;
        background:#fff;
    }

    .gm-store-name {
        font-size:clamp(1.8rem,3vw,2.45rem);
        line-height:1.25;
        font-weight:950;
        letter-spacing:-.035em;
        color:#202124;
    }

    .gm-store-address {
        margin-top:8px;
        color:#5f6368;
        font-size:1rem;
        line-height:1.6;
    }

    .gm-rating-grid {
        display:grid;
        grid-template-columns:170px minmax(260px,520px) 1fr;
        gap:28px;
        align-items:center;
        margin-top:18px;
    }

    .gm-rating-number {
        font-size:4rem;
        line-height:1;
        font-weight:500;
        letter-spacing:-.06em;
        color:#202124;
    }

    .gm-stars {
        margin-top:8px;
        color:#f9ab00;
        font-size:1.25rem;
        letter-spacing:2px;
    }

    .gm-rating-count {
        margin-top:5px;
        color:#5f6368;
        font-size:.95rem;
    }

    .gm-star-row {
        display:grid;
        grid-template-columns:18px 1fr 54px;
        gap:9px;
        align-items:center;
        margin:5px 0;
        color:#5f6368;
        font-size:.9rem;
    }

    .gm-star-track {
        height:9px;
        border-radius:999px;
        background:#eceff1;
        overflow:hidden;
    }

    .gm-star-fill {
        height:100%;
        border-radius:999px;
        background:#f9ab00;
    }

    .gm-chip-line {
        display:flex;
        gap:8px;
        flex-wrap:wrap;
        margin-top:16px;
    }

    .gm-chip {
        display:inline-flex;
        align-items:center;
        min-height:36px;
        padding:7px 12px;
        border:1px solid #dadce0;
        border-radius:999px;
        background:#fff;
        color:#3c4043;
        font-size:.92rem;
        font-weight:750;
    }

    .gm-chip.hot {
        border-color:#f3b4c4;
        background:#fff1f5;
        color:#bd2350;
    }

    .gm-section-title {
        margin:26px 0 5px;
        font-size:1.55rem;
        font-weight:950;
        color:#202124;
    }

    .gm-section-subtitle {
        margin-bottom:14px;
        color:#5f6368;
        font-size:.98rem;
    }

    .gm-review-card {
        margin:0 0 14px;
        padding:20px 22px;
        border:1px solid #e3e6ea;
        border-radius:16px;
        background:#fff;
        box-shadow:0 2px 9px rgba(32,33,36,.035);
    }

    .gm-review-top {
        display:flex;
        justify-content:space-between;
        gap:12px;
        align-items:flex-start;
    }

    .gm-review-source {
        font-size:1rem;
        font-weight:900;
        color:#202124;
    }

    .gm-review-date {
        color:#70757a;
        font-size:.9rem;
        white-space:nowrap;
    }

    .gm-review-stars {
        margin-top:8px;
        color:#f9ab00;
        font-size:1.08rem;
        letter-spacing:1px;
    }

    .gm-review-text {
        margin-top:12px;
        color:#202124;
        font-size:1.04rem;
        line-height:1.78;
        white-space:normal;
    }

    .gm-owner-box {
        margin-top:14px;
        padding:14px 15px;
        border-left:4px solid #f4a261;
        border-radius:0 10px 10px 0;
        background:#fff8ef;
        color:#3c4043;
        font-size:.98rem;
        line-height:1.72;
    }

    .gm-owner-label {
        margin-bottom:5px;
        color:#9a4c00;
        font-weight:900;
    }

    .gm-ai-line {
        display:flex;
        gap:7px;
        flex-wrap:wrap;
        margin-top:12px;
    }

    .gm-ai-badge {
        padding:5px 9px;
        border-radius:999px;
        background:#f5f3ff;
        color:#6d35a8;
        font-size:.84rem;
        font-weight:850;
    }

    .gm-empty-reply {
        margin-top:12px;
        color:#80868b;
        font-size:.93rem;
    }

    .gm-toolbar-note {
        color:#5f6368;
        font-size:.92rem;
        margin:4px 0 12px;
    }

    .rank-main { min-width:0; }
    .rank-detail-link {
        display:inline-block; margin-top:4px; color:#1a73e8;
        text-decoration:none; font-size:.78rem; font-weight:850;
    }
    .rank-detail-link:hover { text-decoration:underline; }

    .gm-store-shell { scroll-margin-top:88px; }
    .gm-store-head.compact { padding:20px 22px; }
    .gm-quick-grid {
        display:grid; grid-template-columns:repeat(4,minmax(140px,1fr));
        gap:10px; margin-top:16px;
    }
    .gm-quick-stat {
        padding:12px 14px; border:1px solid #e1e4e8;
        border-radius:14px; background:#fff;
    }
    .gm-quick-label { color:#70757a; font-size:.82rem; font-weight:800; }
    .gm-quick-value { margin-top:3px; color:#202124; font-size:1.18rem; font-weight:950; }
    .gm-quick-value.hot { color:#d81b50; }

    div[data-baseweb="tab-list"] {
        position:sticky; top:58px; z-index:30; padding-top:7px;
        background:rgba(255,255,255,.98); border-bottom:1px solid #eceff1;
    }

    .gm-pr-box {
        margin-top:12px; padding:13px 15px; border:1px solid #ddd1f2;
        border-radius:12px; background:#faf7ff; color:#3f2c53;
        font-size:.96rem; line-height:1.72;
    }
    .gm-pr-label { margin-bottom:5px; color:#6f3aa6; font-weight:950; }
    .gm-review-actions { margin-top:12px; }
    .gm-review-link {
        display:inline-block; padding:7px 11px; border:1px solid #dadce0;
        border-radius:9px; background:#fff; color:#1a73e8;
        text-decoration:none; font-size:.88rem; font-weight:850;
    }

    .podium-wrap {
        display:grid; grid-template-columns:1fr 1.08fr 1fr; gap:14px;
        align-items:end; margin:22px 0 28px;
    }
    .podium-slot {
        position:relative; display:flex; min-height:205px; flex-direction:column;
        justify-content:flex-end; padding:18px 16px 0; border:1px solid #e3e6ea;
        border-radius:20px 20px 8px 8px; background:#fff;
        box-shadow:0 8px 24px rgba(32,33,36,.08); color:#202124;
        text-decoration:none; overflow:hidden; transition:.15s ease;
    }
    .podium-slot:hover { transform:translateY(-4px); box-shadow:0 12px 28px rgba(32,33,36,.13); }
    .podium-slot.p1 { min-height:255px; border-color:#f3d16a; background:linear-gradient(180deg,#fffdf5 0%,#fff 56%); }
    .podium-slot.p2 { min-height:220px; background:linear-gradient(180deg,#f9fafb 0%,#fff 58%); }
    .podium-slot.p3 { min-height:195px; background:linear-gradient(180deg,#fff9f2 0%,#fff 58%); }
    .podium-medal { font-size:2rem; line-height:1; }
    .podium-rank { margin-top:8px; color:#70757a; font-size:.82rem; font-weight:850; }
    .podium-name { margin-top:5px; font-size:1.05rem; font-weight:950; line-height:1.35; }
    .podium-score { margin:7px 0 14px; color:#d81b50; font-size:1.2rem; font-weight:950; }
    .podium-base { display:flex; height:52px; align-items:center; justify-content:center; margin:0 -16px; background:#f5f6f8; font-size:1.5rem; font-weight:950; color:#5f6368; }
    .podium-slot.p1 .podium-base { height:76px; background:#fff1b8; color:#8b6500; }
    .podium-slot.p2 .podium-base { height:60px; background:#eceff1; }
    .podium-slot.p3 .podium-base { height:48px; background:#f5dfcc; color:#8a542e; }


    /* ========================================================
       V6 — Google-Maps-like split explorer
       ======================================================== */
    .explorer-hint {
        margin:0 0 10px;
        color:#5f6368;
        font-size:.92rem;
        line-height:1.55;
    }

    .explorer-store-head {
        padding:2px 2px 12px;
        border-bottom:1px solid #eceff1;
        margin-bottom:12px;
    }

    .explorer-store-name {
        color:#202124;
        font-size:1.55rem;
        font-weight:950;
        line-height:1.25;
        letter-spacing:-.025em;
    }

    .explorer-store-address {
        margin-top:5px;
        color:#70757a;
        font-size:.86rem;
        line-height:1.55;
    }

    .explorer-chip-row {
        display:flex;
        flex-wrap:wrap;
        gap:7px;
        margin-top:11px;
    }

    .explorer-chip {
        display:inline-flex;
        align-items:center;
        min-height:30px;
        padding:5px 9px;
        border:1px solid #e1e4e8;
        border-radius:999px;
        background:#fff;
        color:#34363a;
        font-size:.78rem;
        font-weight:850;
    }

    .explorer-chip.hot {
        border-color:#ffc2d1;
        background:#fff1f5;
        color:#c81e4f;
    }

    .explorer-panel-title {
        margin:10px 0 3px;
        color:#202124;
        font-size:1.02rem;
        font-weight:950;
    }

    .explorer-panel-subtitle {
        margin:0 0 10px;
        color:#70757a;
        font-size:.82rem;
        line-height:1.55;
    }

    .explorer-page-info {
        text-align:center;
        color:#5f6368;
        font-size:.86rem;
        font-weight:850;
        padding-top:8px;
    }

    /* Detail panel lives beside map; browsers with a recent Streamlit
       get an independent scroll area through st.container(height=...). */
    .gm-review-card {
        padding:14px 14px;
        margin-bottom:11px;
    }

    .gm-review-text {
        font-size:.98rem;
        line-height:1.75;
    }

    .gm-owner-box,
    .gm-pr-box {
        font-size:.92rem;
        line-height:1.68;
    }

    iframe[title="streamlit_folium.st_folium"] {
        min-height:720px;
    }

    @media (max-width:900px) {
        .block-container {
            padding-left:.8rem;
            padding-right:.8rem;
        }

        .duel-grid,
        .rescue-grid,
        .review-dialogue,
        .gm-rating-grid,
        .gm-quick-grid,
        .podium-wrap {
            grid-template-columns:1fr;
        }

        .podium-slot,
        .podium-slot.p1,
        .podium-slot.p2,
        .podium-slot.p3 {
            min-height:auto;
        }

        .gm-store-head {
            padding:18px;
        }

        .gm-rating-number {
            font-size:3.1rem;
        }

        .duel-vs {
            min-height:34px;
        }

        .rank-card {
            grid-template-columns:30px minmax(0,1fr);
        }

        .rank-score {
            grid-column:2;
        }
    }
    </style>
    """
)


# ============================================================
# Header
# ============================================================

if SPLASH_IMAGE.exists():
    _, image_column, _ = st.columns(
        [3.25, 3.5, 3.25]
    )

    with image_column:
        st.image(
            str(SPLASH_IMAGE),
            use_container_width=True,
        )

nav_column, refresh_column = st.columns(
    [8, 1.25]
)

with nav_column:
    current_page = st.radio(
        "功能",
        PAGES,
        horizontal=True,
        label_visibility="collapsed",
        key="main_nav",
    )

with refresh_column:
    st.button(
        "↻ 重新整理",
        use_container_width=True,
        on_click=refresh_all,
    )


# ============================================================
# Load store data
# ============================================================

try:
    stores = load_store_data()
    database_error = ""
except Exception as exc:
    stores = pd.DataFrame()
    database_error = str(exc)


def page_title(title: str) -> None:
    render_html(
        f'<div class="page-title">'
        f'{safe_text(title)}'
        f'</div>'
    )


# ============================================================
# Map visual helpers
# ============================================================

def flame_size(
    score: float | None,
) -> int:
    if score is None:
        return 32

    value = max(
        0.0,
        min(float(score), 10.0),
    )

    return int(
        30
        + (value / 10.0) * 38
    )


def flame_colors(
    score: float | None,
) -> tuple[str, str, str]:
    if score is None:
        return (
            "#6f6970",
            "#b9afb7",
            "rgba(180,170,178,.22)",
        )

    value = max(
        0.0,
        min(float(score), 10.0),
    )

    if value < 3:
        return (
            "#ffc23e",
            "#fff0a4",
            "rgba(255,194,62,.45)",
        )

    if value < 5:
        return (
            "#ff851b",
            "#ffd25d",
            "rgba(255,133,27,.50)",
        )

    if value < 7:
        return (
            "#ff4638",
            "#ffad3d",
            "rgba(255,70,56,.62)",
        )

    return (
        "#e60046",
        "#ff7138",
        "rgba(230,0,70,.82)",
    )



def flame_icon(
    score: float | None,
    *,
    selected: bool = False,
) -> DivIcon:
    size = flame_size(score)
    if selected:
        size = int(size * 1.22)
    outer, inner, glow = flame_colors(
        score
    )

    score_html = ""

    if score is not None:
        score_html = (
            f"""
            <div style="
                position:absolute;
                left:50%;
                bottom:0;
                transform:translateX(-50%);
                min-width:28px;
                padding:1px 5px;
                border-radius:999px;
                background:rgba(16,12,16,.95);
                border:1px solid rgba(255,255,255,.25);
                color:white;
                font:800 10px/14px Arial;
                text-align:center;
            ">{score:.0f}</div>
            """
        )

    icon_html = dedent(
        f"""
        <div style="
            position:relative;
            width:{size}px;
            height:{size + 17}px;
            filter:drop-shadow(
                0 0
                {max(4, size // 7)}px
                {glow}
            ){" drop-shadow(0 0 8px rgba(216,27,80,.75))" if selected else ""};
        ">
            <svg
                width="{size}"
                height="{size}"
                viewBox="0 0 64 64"
            >
                <path
                    d="M34 3
                       C37 13 31 17 38 25
                       C41 20 45 16 45 10
                       C55 21 60 31 57 43
                       C54 55 45 62 32 62
                       C18 62 8 53 7 41
                       C6 31 12 23 20 17
                       C19 26 24 29 27 23
                       C31 16 27 10 34 3 Z"
                    fill="{outer}"
                />
                <path
                    d="M33 28
                       C38 34 43 38 42 46
                       C41 54 36 58 30 58
                       C23 58 18 53 19 46
                       C20 40 25 37 28 32
                       C29 37 32 39 34 36
                       C36 33 34 30 33 28 Z"
                    fill="{inner}"
                />
            </svg>
            {score_html}
        </div>
        """
    ).strip()

    return DivIcon(
        html=icon_html,
        icon_size=(
            size,
            size + 17,
        ),
        icon_anchor=(
            size // 2,
            size + 8,
        ),
        popup_anchor=(
            0,
            -size,
        ),
        class_name=(
            "drama-flame-icon"
        ),
    )


def map_popup(
    row: pd.Series,
    preview: pd.Series | None = None,
) -> str:
    google_score = to_number(
        row.get("google_score")
    )
    store_intensity_value = to_number(
        row.get("intensity")
    )
    store_url = safe_url(
        row.get("store_url")
    )

    preview = (
        preview
        if preview is not None
        else pd.Series(dtype=object)
    )

    review_text = str(
        preview.get("review_text")
        or row.get("review_text")
        or ""
    ).strip()
    owner_reply = str(
        preview.get("owner_reply")
        or ""
    ).strip()
    stars = to_number(
        preview.get("stars")
    )
    guest_score = to_number(
        preview.get("guest_score")
    )
    owner_score = to_number(
        preview.get("owner_score")
    )

    case_intensity = None
    if (
        guest_score is not None
        and owner_score is not None
    ):
        case_intensity = (
            float(guest_score)
            + float(owner_score)
        ) / 2

    badges = []

    if google_score is not None:
        badges.append(
            f'<span style="display:inline-block;margin:0 6px 6px 0;'
            f'padding:5px 9px;border-radius:999px;background:#fff3d4;'
            f'color:#8d6200;font-size:13px;font-weight:900;">'
            f'⭐ Google {google_score:.1f}</span>'
        )

    if store_intensity_value is not None:
        badges.append(
            f'<span style="display:inline-block;margin:0 6px 6px 0;'
            f'padding:5px 9px;border-radius:999px;background:#ffe4eb;'
            f'color:#d71850;font-size:13px;font-weight:900;">'
            f'🔥 平均烈度 {store_intensity_value:.1f}</span>'
        )

    if stars is not None:
        badges.append(
            f'<span style="display:inline-block;margin:0 6px 6px 0;'
            f'padding:5px 9px;border-radius:999px;background:#f2f2f3;'
            f'color:#333;font-size:13px;font-weight:900;">'
            f'⭐ {int(stars)} 星評論</span>'
        )

    if case_intensity is not None:
        badges.append(
            f'<span style="display:inline-block;margin:0 6px 6px 0;'
            f'padding:5px 9px;border-radius:999px;background:#fff0f4;'
            f'color:#c6204d;font-size:13px;font-weight:900;">'
            f'⚔️ 本場 {case_intensity:.1f}</span>'
        )

    detail_link = ""
    store_id = str(row.get("store_id") or "").strip()
    if store_id:
        detail_href = (
            "?store_id=" + quote(store_id, safe="") + "#store-detail-start"
        )
        detail_link = (
            f'<a href="{detail_href}" target="_top" '
            f'style="display:inline-block;margin:12px 8px 0 0;padding:10px 13px;'
            f'border-radius:9px;background:#1a73e8;color:white;'
            f'font-weight:900;text-decoration:none;font-size:14px;">'
            f'查看這間店吵架內容</a>'
        )

    map_link = ""

    if store_url:
        escaped_url = html.escape(
            store_url,
            quote=True,
        )
        map_link = (
            f'<a href="{escaped_url}" target="_blank" '
            f'style="display:inline-block;margin-top:12px;padding:9px 12px;'
            f'border-radius:8px;background:#242126;color:white;'
            f'font-weight:850;text-decoration:none;font-size:13px;">'
            f'Google Maps</a>'
        )

    review_html = safe_text(
        truncate_text(
            review_text,
            280,
        )
        or "目前沒有評論文字"
    ).replace(
        "\\n",
        "<br>",
    )

    owner_html = safe_text(
        truncate_text(
            owner_reply,
            260,
        )
        or "店家尚未回覆"
    ).replace(
        "\\n",
        "<br>",
    )

    return dedent(
        f"""
        <div style="
            width:420px;
            max-width:420px;
            padding:10px 11px 12px;
            font-family:Arial,'Microsoft JhengHei',sans-serif;
            color:#1f1f22;
        ">
            <div style="
                font-size:20px;
                font-weight:950;
                color:#20191e;
                margin-bottom:8px;
                line-height:1.35;
            ">
                {safe_text(
                    display_store_name(
                        row.get("name"),
                        36,
                    )
                )}
            </div>

            <div>{''.join(badges)}</div>

            <div style="
                margin-top:8px;
                color:#6d666b;
                font-size:13px;
                line-height:1.55;
            ">
                📍 {safe_text(
                    row.get("address")
                    or ""
                )}
            </div>

            <div style="
                margin-top:13px;
                padding:12px 13px;
                border:1px solid #f0ccd5;
                border-radius:11px;
                background:#fff4f6;
                font-size:14px;
                line-height:1.7;
            ">
                <div style="
                    font-weight:950;
                    margin-bottom:5px;
                    color:#b82048;
                ">
                    😡 顧客評論
                </div>
                {review_html}
            </div>

            <div style="
                margin-top:9px;
                padding:12px 13px;
                border:1px solid #fed8ad;
                border-radius:11px;
                background:#fff8ef;
                font-size:14px;
                line-height:1.7;
            ">
                <div style="
                    font-weight:950;
                    margin-bottom:5px;
                    color:#ad5500;
                ">
                    🏪 店家回覆
                </div>
                {owner_html}
            </div>

            <div style="
                margin-top:9px;
                color:#787078;
                font-size:12px;
            ">
                點「查看這間店吵架內容」直接進入店家評論、經典對決與分析。
            </div>

            {detail_link}
            {map_link}
        </div>
        """
    ).strip()


# ============================================================
# Reusable rank UI
# ============================================================

def render_rank_cards(
    frame: pd.DataFrame,
    score_column: str,
    score_prefix: str,
    *,
    limit: int = 8,
    ascending: bool = False,
    percent: bool = False,
    clickable: bool = False,
    button_prefix: str = "rank",
    start_rank: int = 1,
) -> None:
    if (
        frame.empty
        or score_column not in frame.columns
    ):
        st.info("目前沒有資料。")
        return

    ranked = frame.copy()

    ranked[score_column] = pd.to_numeric(
        ranked[score_column],
        errors="coerce",
    )

    ranked = ranked.dropna(
        subset=[score_column]
    )

    if ranked.empty:
        st.info("目前沒有資料。")
        return

    ranked = ranked.sort_values(
        [
            score_column,
            "db_review_count",
        ],
        ascending=[
            ascending,
            False,
        ],
    ).head(limit)

    for number, (_, row) in enumerate(
        ranked.iterrows(),
        start=start_rank,
    ):
        score = float(
            row[score_column]
        )

        if percent:
            score_text = f"{score:.0f}%"
        elif score_column in {
            "db_review_count",
            "owner_replies",
        }:
            score_text = f"{score:.0f}"
        else:
            score_text = f"{score:.1f}"

        store_name = safe_text(
            row.get("display_name")
            or row.get("name")
            or ""
        )
        action_html = ""
        if clickable:
            detail_href = (
                "?store_id="
                + quote(str(row["store_id"]), safe="")
                + "#store-detail-start"
            )
            action_html = (
                f'<a class="rank-detail-link" href="{detail_href}" '
                f'target="_top">查看店家</a>'
            )

        render_html(
            f"""
            <div class="rank-card">
                <div class="rank-no">#{number}</div>
                <div class="rank-main">
                    <div class="rank-name">{store_name}</div>
                    {action_html}
                </div>
                <div class="rank-score">
                    {safe_text(score_prefix)}{score_text}
                </div>
            </div>
            """
        )


def render_podium(
    frame: pd.DataFrame,
    score_column: str,
    score_prefix: str,
    *,
    ascending: bool = False,
    percent: bool = False,
) -> pd.DataFrame:
    """前三名用頒獎台顯示，並回傳排序後完整 DataFrame。"""
    if frame.empty or score_column not in frame.columns:
        st.info("目前沒有排行資料。")
        return pd.DataFrame()

    ranked = frame.copy()
    ranked[score_column] = pd.to_numeric(ranked[score_column], errors="coerce")
    ranked = ranked.dropna(subset=[score_column])
    if ranked.empty:
        st.info("目前沒有排行資料。")
        return ranked

    ranked = ranked.sort_values(
        [score_column, "db_review_count"],
        ascending=[ascending, False],
    ).reset_index(drop=True)

    top = ranked.head(3).copy()

    def _score_text(row: pd.Series) -> str:
        score = float(row[score_column])
        if percent:
            value = f"{score:.0f}%"
        elif score_column in {"db_review_count", "owner_replies"}:
            value = f"{score:.0f}"
        else:
            value = f"{score:.1f}"
        return f"{safe_text(score_prefix)}{value}"

    cards = {}
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for pos in [1, 2, 3]:
        if len(top) < pos:
            cards[pos] = '<div class="podium-slot empty"></div>'
            continue
        row = top.iloc[pos - 1]
        name = safe_text(row.get("display_name") or row.get("name") or "")
        href = (
            "?store_id="
            + quote(str(row["store_id"]), safe="")
            + "#store-detail-start"
        )
        cards[pos] = f"""
        <a class="podium-slot p{pos}" href="{href}" target="_top">
            <div class="podium-medal">{medals[pos]}</div>
            <div class="podium-rank">第 {pos} 名</div>
            <div class="podium-name">{name}</div>
            <div class="podium-score">{_score_text(row)}</div>
            <div class="podium-base"><span>{pos}</span></div>
        </a>
        """

    render_html(
        f"""
        <div class="podium-wrap">
            {cards[2]}
            {cards[1]}
            {cards[3]}
        </div>
        """
    )
    return ranked


# ============================================================
# Reusable duel UI
# ============================================================

def render_duel(
    store_row: pd.Series,
    review_row: pd.Series,
) -> None:
    stars = to_number(
        review_row.get("stars")
    )
    guest_score = to_number(
        review_row.get("guest_score")
    )
    owner_score = to_number(
        review_row.get("owner_score")
    )
    intensity = to_number(
        review_row.get("intensity")
    )

    pills = []

    if stars is not None:
        pills.append(
            f'<span class="pill">'
            f'⭐ {int(stars)} 星'
            f'</span>'
        )

    if intensity is not None:
        pills.append(
            f'<span class="pill pill-hot">'
            f'🔥 總烈度 {intensity:.1f}'
            f'</span>'
        )

    if (
        guest_score is not None
        and bool(
            review_row.get("has_ai")
        )
    ):
        pills.append(
            f'<span class="pill">'
            f'😡 顧客 {guest_score:.0f}'
            f'</span>'
        )

    if (
        owner_score is not None
        and bool(
            review_row.get("has_ai")
        )
    ):
        pills.append(
            f'<span class="pill">'
            f'🏪 店家 {owner_score:.0f}'
            f'</span>'
        )

    published_at = (
        review_row.get(
            "published_at"
        )
    )

    date_text = ""

    if pd.notna(published_at):
        date_text = str(
            published_at
        )[:10]

    guest_summary = safe_text(
        review_row.get(
            "guest_summary"
        )
        or ""
    )
    owner_summary = safe_text(
        review_row.get(
            "owner_summary"
        )
        or ""
    )

    summary_html = ""

    if guest_summary or owner_summary:
        summary_html = (
            f"""
            <div class="ai-summary">
                <b>🧠 AI 懶人包</b>
                <br>
                顧客：{guest_summary or "—"}
                <br>
                店家：{owner_summary or "—"}
            </div>
            """
        )

    render_html(
        f"""
        <div class="duel-arena">
            <div class="duel-store">
                {safe_text(
                    store_row.get(
                        "display_name"
                    )
                    or display_store_name(
                        store_row.get("name")
                    )
                )}
            </div>

            <div class="duel-meta">
                {safe_text(
                    store_row.get(
                        "district"
                    )
                    or ""
                )}
                {
                    "｜" + safe_text(date_text)
                    if date_text
                    else ""
                }
            </div>

            <div class="score-row">
                {''.join(pills)}
            </div>

            <div class="duel-grid">
                <div class="
                    duel-side
                    duel-customer
                ">
                    <div class="duel-label">
                        😡 顧客
                    </div>

                    {safe_text(
                        review_row.get(
                            "review_text"
                        )
                        or ""
                    )}
                </div>

                <div class="duel-vs">
                    VS
                </div>

                <div class="
                    duel-side
                    duel-owner
                ">
                    <div class="duel-label">
                        🏪 店家
                    </div>

                    {safe_text(
                        review_row.get(
                            "owner_reply"
                        )
                        or ""
                    )}
                </div>
            </div>

            {summary_html}
        </div>
        """
    )


# ============================================================
# Reusable review feed UI
# ============================================================

def render_review_feed_card(
    review: pd.Series,
) -> None:
    stars = to_number(
        review.get("stars")
    )
    guest_score = to_number(
        review.get("guest_score")
    )
    owner_score = to_number(
        review.get("owner_score")
    )
    intensity = to_number(
        review.get("intensity")
    )

    published_at = review.get(
        "published_at"
    )
    date_text = ""

    if pd.notna(published_at):
        date_text = str(
            published_at
        )[:10]

    badges = []

    if stars is not None:
        badges.append(
            f'<span class="review-badge">'
            f'⭐ {int(stars)} 星'
            f'</span>'
        )

    if intensity is not None:
        badges.append(
            f'<span class="review-badge hot">'
            f'🔥 本場烈度 {intensity:.1f}'
            f'</span>'
        )

    if (
        guest_score is not None
        and bool(
            review.get("has_ai")
        )
    ):
        badges.append(
            f'<span class="review-badge">'
            f'😡 顧客 {guest_score:.0f}'
            f'</span>'
        )

    if (
        owner_score is not None
        and bool(
            review.get("has_ai")
        )
    ):
        badges.append(
            f'<span class="review-badge">'
            f'🏪 店家 {owner_score:.0f}'
            f'</span>'
        )

    customer = safe_text(
        review.get("review_text")
        or "（沒有評論文字）"
    ).replace(
        "\n",
        "<br>",
    )

    owner = safe_text(
        review.get("owner_reply")
        or "（店家尚未回覆）"
    ).replace(
        "\n",
        "<br>",
    )

    store_name = safe_text(
        display_store_name(
            review.get("store_name"),
            42,
        )
    )

    address = safe_text(
        review.get("address")
        or ""
    )

    render_html(
        f"""
        <div class="review-card">
            <div class="review-store">
                {store_name}
            </div>

            <div class="review-meta">
                {safe_text(date_text)}
                {
                    "｜"
                    if date_text and address
                    else ""
                }
                {address}
            </div>

            <div class="review-badges">
                {''.join(badges)}
            </div>

            <div class="review-dialogue">
                <div class="
                    review-side
                    customer
                ">
                    <div class="review-side-title">
                        😡 顧客
                    </div>
                    {customer}
                </div>

                <div class="
                    review-side
                    owner
                ">
                    <div class="review-side-title">
                        🏪 店家
                    </div>
                    {owner}
                </div>
            </div>
        </div>
        """
    )

    review_url = safe_url(
        review.get("review_url")
    )
    store_url = safe_url(
        review.get("store_url")
    )

    links = []

    if review_url:
        links.append(
            '<a href="'
            + html.escape(
                review_url,
                quote=True,
            )
            + '" target="_blank" '
            + 'style="display:inline-block;margin:0 8px 12px 0;'
            + 'padding:7px 11px;border:1px solid #d9dbe0;border-radius:9px;'
            + 'color:#29292d;text-decoration:none;font-size:14px;font-weight:800;'
            + 'background:#fff;">原始 Review</a>'
        )

    if store_url:
        links.append(
            '<a href="'
            + html.escape(
                store_url,
                quote=True,
            )
            + '" target="_blank" '
            + 'style="display:inline-block;margin:0 8px 12px 0;'
            + 'padding:7px 11px;border:1px solid #d9dbe0;border-radius:9px;'
            + 'color:#29292d;text-decoration:none;font-size:14px;font-weight:800;'
            + 'background:#fff;">Google Maps</a>'
        )

    if links:
        render_html(
            '<div>'
            + ''.join(links)
            + '</div>'
        )

# ============================================================
# Google-Maps-like review UI
# ============================================================

def render_google_review_card(
    review: pd.Series,
) -> None:
    stars = to_number(review.get("stars"))
    likes = to_number(review.get("likes_count"))
    guest_score = to_number(review.get("guest_score"))
    owner_score = to_number(review.get("owner_score"))
    intensity = to_number(review.get("intensity"))

    published_at = review.get("published_at")
    date_text = ""
    if pd.notna(published_at):
        date_text = str(published_at)[:10]

    star_text = "★" * int(stars or 0)
    star_text += "☆" * max(0, 5 - int(stars or 0))

    review_html = safe_text(
        review.get("review_text")
        or "（沒有評論文字）"
    ).replace("\n", "<br>")

    owner_reply = str(
        review.get("owner_reply")
        or ""
    ).strip()
    owner_html = safe_text(owner_reply).replace("\n", "<br>")

    ai_badges = []
    if intensity is not None:
        ai_badges.append(
            f'<span class="gm-ai-badge">🔥 本場烈度 {intensity:.1f}</span>'
        )
    if guest_score is not None and bool(review.get("has_ai")):
        ai_badges.append(
            f'<span class="gm-ai-badge">😡 顧客 {guest_score:.0f}</span>'
        )
    if owner_score is not None and bool(review.get("has_ai")):
        ai_badges.append(
            f'<span class="gm-ai-badge">🏪 店家 {owner_score:.0f}</span>'
        )
    if likes is not None and likes > 0:
        ai_badges.append(
            f'<span class="gm-ai-badge">👍 {int(likes)}</span>'
        )

    if owner_reply:
        owner_section = (
            '<div class="gm-owner-box">'
            '<div class="gm-owner-label">🏪 店家回覆</div>'
            + owner_html
            + '</div>'
        )
    else:
        owner_section = ""

    pr_reply = str(review.get("pr_reply") or "").strip()
    pr_section = ""
    if pr_reply:
        pr_section = (
            '<div class="gm-pr-box">'
            '<div class="gm-pr-label">🤖 AI 公關建議</div>'
            + safe_text(pr_reply).replace("\n", "<br>")
            + '</div>'
        )

    review_url = safe_url(review.get("review_url"))
    review_link = ""
    if review_url:
        review_link = (
            '<div class="gm-review-actions">'
            '<a class="gm-review-link" href="'
            + html.escape(review_url, quote=True)
            + '" target="_blank">查看原始 Google Review</a>'
            '</div>'
        )

    render_html(
        f"""
        <div class="gm-review-card">
            <div class="gm-review-top">
                <div>
                    <div class="gm-review-source">Google 低星評論</div>
                    <div class="gm-review-stars">{star_text}</div>
                </div>
                <div class="gm-review-date">{safe_text(date_text)}</div>
            </div>

            <div class="gm-review-text">{review_html}</div>
            {owner_section}

            <div class="gm-ai-line">
                {''.join(ai_badges)}
            </div>

            {pr_section}
            {review_link}
        </div>
        """
    )


def render_clean_horizontal_bar(
    frame: pd.DataFrame,
    *,
    category: str,
    value: str,
    title: str,
    value_format: str = ".1f",
    height: int = 230,
) -> None:
    """白底、中文欄名、直接標數值的簡潔橫條圖。"""
    if frame.empty:
        st.info("目前沒有可顯示的資料。")
        return

    data = frame[[category, value]].dropna().to_dict("records")
    if not data:
        st.info("目前沒有可顯示的資料。")
        return

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "background": "white",
        "title": {
            "text": title,
            "anchor": "start",
            "fontSize": 18,
            "fontWeight": "bold",
            "color": "#202124",
        },
        "data": {"values": data},
        "mark": {
            "type": "bar",
            "cornerRadiusEnd": 6,
            "color": "#7cb9e8",
        },
        "encoding": {
            "y": {
                "field": category,
                "type": "nominal",
                "sort": "-x",
                "title": None,
                "axis": {
                    "labelFontSize": 14,
                    "labelLimit": 180,
                    "labelColor": "#5f6368",
                    "domainColor": "#dadce0",
                },
            },
            "x": {
                "field": value,
                "type": "quantitative",
                "title": None,
                "axis": {
                    "labelFontSize": 12,
                    "labelColor": "#5f6368",
                    "grid": True,
                    "gridColor": "#eef0f2",
                    "domainColor": "#dadce0",
                },
            },
            "tooltip": [
                {"field": category, "type": "nominal", "title": "項目"},
                {"field": value, "type": "quantitative", "title": "分數", "format": value_format},
            ],
        },
        "height": height,
        "config": {
            "view": {"stroke": None},
            "axis": {"titleColor": "#5f6368"},
        },
    }
    st.vega_lite_chart(spec, use_container_width=True)


def render_sentiment_comparison(
    frame: pd.DataFrame,
    *,
    title: str = "情緒分布",
    height: int = 280,
) -> None:
    if frame.empty:
        st.info("目前沒有情緒資料。")
        return

    data = frame[["角色", "情緒", "筆數"]].dropna().to_dict("records")
    if not data:
        st.info("目前沒有情緒資料。")
        return

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "background": "white",
        "title": {
            "text": title,
            "anchor": "start",
            "fontSize": 18,
            "fontWeight": "bold",
            "color": "#202124",
        },
        "data": {"values": data},
        "mark": {"type": "bar", "cornerRadiusEnd": 5},
        "encoding": {
            "y": {
                "field": "情緒",
                "type": "nominal",
                "title": None,
                "axis": {
                    "labelFontSize": 13,
                    "labelLimit": 180,
                    "labelColor": "#5f6368",
                    "domainColor": "#dadce0",
                },
            },
            "x": {
                "field": "筆數",
                "type": "quantitative",
                "title": "筆數",
                "axis": {
                    "labelFontSize": 12,
                    "labelColor": "#5f6368",
                    "grid": True,
                    "gridColor": "#eef0f2",
                    "domainColor": "#dadce0",
                },
            },
            "yOffset": {"field": "角色"},
            "color": {
                "field": "角色",
                "type": "nominal",
                "title": None,
                "scale": {
                    "domain": ["顧客", "店家"],
                    "range": ["#e91e63", "#fb8c00"],
                },
                "legend": {
                    "orient": "top",
                    "labelColor": "#5f6368",
                    "labelFontSize": 13,
                },
            },
            "tooltip": [
                {"field": "角色", "type": "nominal"},
                {"field": "情緒", "type": "nominal"},
                {"field": "筆數", "type": "quantitative"},
            ],
        },
        "height": height,
        "config": {"view": {"stroke": None}},
    }
    st.vega_lite_chart(spec, use_container_width=True)


# ============================================================
# PAGE 1 — MAP
# ============================================================

if current_page == PAGE_MAP:
    page_title("🔥 台北吵架地圖")
    render_html(
        '<div class="page-subtitle">'
        '點地圖火焰就直接在右側看店家吵架內容，不用再跳頁或往下找。'
        '</div>'
    )

    if stores.empty:
        st.error(
            database_error
            or "目前沒有可顯示的店家。"
        )

    else:
        # 前台只顯示 1–2★ 且店家有真實回覆的吵架案例。
        map_stores = stores[
            stores["owner_replies"].fillna(0) > 0
        ].copy()

        if map_stores.empty:
            st.info("目前沒有符合『低星評論 + 店家回覆』的案例。")

        else:
            districts = sorted(
                district
                for district
                in map_stores["district"].dropna().unique()
                if str(district).strip()
            )

            filter_search, filter_district, filter_intensity = st.columns(
                [3.8, 1.35, 1.7],
                vertical_alignment="bottom",
            )

            with filter_search:
                keyword = st.text_input(
                    "搜尋",
                    placeholder="搜尋店名或地址",
                    key="v6_map_keyword",
                ).strip()

            with filter_district:
                district_filter = st.selectbox(
                    "行政區",
                    ["全部", *districts],
                    key="v6_map_district",
                )

            with filter_intensity:
                intensity_filter = st.selectbox(
                    "最低烈度",
                    ["全部", "3+", "5+", "7+", "9+"],
                    key="v7_map_intensity",
                )
                minimum = {
                    "全部": 0.0,
                    "3+": 3.0,
                    "5+": 5.0,
                    "7+": 7.0,
                    "9+": 9.0,
                }[intensity_filter]

            filtered = map_stores.copy()

            if keyword:
                keyword_mask = (
                    filtered["name"].str.contains(
                        keyword,
                        case=False,
                        na=False,
                    )
                    | filtered["address"].str.contains(
                        keyword,
                        case=False,
                        na=False,
                    )
                )
                filtered = filtered[keyword_mask]

            if district_filter != "全部":
                filtered = filtered[
                    filtered["district"] == district_filter
                ]

            if minimum > 0:
                filtered = filtered[
                    filtered["intensity"].fillna(-1) >= minimum
                ]

            render_html(
                '<div class="explorer-hint">'
                f'目前 {len(filtered)} 家｜點 🔥 直接切換右側店家內容。'
                '</div>'
            )

            if filtered.empty:
                st.warning("沒有符合目前篩選條件的店家。")

            else:
                filtered = filtered.reset_index(drop=True)
                filtered_ids = filtered["store_id"].astype(str).tolist()

                # 預設店家：先沿用使用者剛選過的；否則用最高烈度案例。
                selected_store_id = str(
                    st.session_state.get("selected_store_id", "")
                    or ""
                )

                if selected_store_id not in filtered_ids:
                    ai_candidates = filtered[
                        filtered["intensity"].notna()
                    ].sort_values(
                        ["intensity", "owner_replies"],
                        ascending=[False, False],
                    )
                    if not ai_candidates.empty:
                        selected_store_id = str(
                            ai_candidates.iloc[0]["store_id"]
                        )
                    else:
                        selected_store_id = str(
                            filtered.sort_values(
                                "owner_replies",
                                ascending=False,
                            ).iloc[0]["store_id"]
                        )
                    st.session_state["selected_store_id"] = selected_store_id

                map_col, detail_col = st.columns(
                    [1.62, 1.0],
                    gap="large",
                )

                # ----------------------------------------------------
                # LEFT — map. Marker click is the store selector.
                # ----------------------------------------------------
                with map_col:
                    center = [
                        float(filtered["lat"].mean()),
                        float(filtered["lng"].mean()),
                    ]

                    drama_map = folium.Map(
                        location=center,
                        zoom_start=12,
                        tiles=None,
                        control_scale=True,
                        prefer_canvas=True,
                    )

                    folium.TileLayer(
                        tiles="CartoDB Voyager",
                        name="地圖",
                        control=False,
                    ).add_to(drama_map)

                    marker_parent = drama_map
                    if len(filtered) > 150:
                        marker_parent = MarkerCluster(
                            name="店家",
                            overlay=True,
                            control=False,
                        ).add_to(drama_map)

                    heat_points = []

                    for _, row in filtered.iterrows():
                        score = to_number(row.get("intensity"))
                        case_count = int(
                            to_number(row.get("owner_replies"))
                            or 0
                        )
                        tooltip = (
                            f"{display_store_name(row.get('name'), 30)}"
                            f"｜🔥 {score:.1f}" if score is not None
                            else f"{display_store_name(row.get('name'), 30)}"
                        )
                        tooltip += f"｜{case_count} 則"

                        if score is not None:
                            heat_points.append(
                                [
                                    float(row["lat"]),
                                    float(row["lng"]),
                                    float(score),
                                ]
                            )

                        Marker(
                            location=[
                                float(row["lat"]),
                                float(row["lng"]),
                            ],
                            icon=flame_icon(score, selected=str(row.get("store_id")) == str(selected_store_id)),
                            tooltip=tooltip,
                        ).add_to(marker_parent)

                    if heat_points:
                        HeatMap(
                            heat_points,
                            name="烈度熱區",
                            radius=28,
                            blur=24,
                            min_opacity=.22,
                            show=False,
                        ).add_to(drama_map)

                        folium.LayerControl(
                            collapsed=True
                        ).add_to(drama_map)

                    if len(filtered) > 1:
                        drama_map.fit_bounds(
                            filtered[["lat", "lng"]].values.tolist(),
                            padding=(25, 25),
                        )

                    map_state = st_folium(
                        drama_map,
                        height=720,
                        use_container_width=True,
                        returned_objects=["last_object_clicked"],
                        key="main_drama_map_v6",
                    )

                    clicked = (
                        map_state.get("last_object_clicked")
                        if isinstance(map_state, dict)
                        else None
                    )

                    if (
                        isinstance(clicked, dict)
                        and clicked.get("lat") is not None
                        and clicked.get("lng") is not None
                    ):
                        click_lat = float(clicked["lat"])
                        click_lng = float(clicked["lng"])

                        distances = (
                            (filtered["lat"].astype(float) - click_lat) ** 2
                            + (filtered["lng"].astype(float) - click_lng) ** 2
                        )
                        nearest_index = distances.idxmin()
                        clicked_store_id = str(
                            filtered.loc[nearest_index, "store_id"]
                        )

                        if clicked_store_id != selected_store_id:
                            st.session_state["selected_store_id"] = clicked_store_id
                            st.session_state["target_store_id"] = clicked_store_id
                            st.rerun()

                # ----------------------------------------------------
                # RIGHT — one store, all useful content in one panel.
                # ----------------------------------------------------
                with detail_col:
                    try:
                        detail_container = st.container(
                            height=720,
                            border=True,
                        )
                    except TypeError:
                        # Compatibility with older Streamlit versions.
                        detail_container = st.container(border=True)

                    with detail_container:
                        selected_store = filtered[
                            filtered["store_id"].astype(str)
                            == str(selected_store_id)
                        ].iloc[0]

                        rating = load_store_rating_summary(
                            selected_store_id
                        )
                        google_score = to_number(
                            rating.get("google_score")
                            if rating
                            else selected_store.get("google_score")
                        )
                        reviews_count = int(
                            to_number(
                                rating.get("reviews_count")
                                if rating
                                else selected_store.get("reviews")
                            )
                            or 0
                        )
                        case_count = int(
                            to_number(selected_store.get("owner_replies"))
                            or 0
                        )
                        avg_intensity = to_number(
                            selected_store.get("intensity")
                        )

                        google_text = (
                            f"{google_score:.1f}"
                            if google_score is not None
                            else "—"
                        )
                        intensity_text = (
                            f"{avg_intensity:.1f}"
                            if avg_intensity is not None
                            else "—"
                        )

                        render_html(
                            f'''
                            <div class="explorer-store-head">
                                <div style="font-size:.82rem;font-weight:900;color:#d81b50;margin-bottom:5px;">🔥 你正在查看</div>
                                <div class="explorer-store-name">
                                    {safe_text(selected_store.get("name") or "")}
                                </div>
                                <div class="explorer-store-address">
                                    📍 {safe_text(selected_store.get("district") or "")}
                                </div>
                                <div class="explorer-chip-row">
                                    <span class="explorer-chip">⭐ {google_text}</span>
                                    <span class="explorer-chip">💬 {case_count:,} 場</span>
                                    <span class="explorer-chip hot">🔥 {intensity_text}</span>
                                </div>
                            </div>
                            '''
                        )

                        featured = load_store_classic_reviews(
                            selected_store_id,
                            limit=1,
                        )
                        if not featured.empty:
                            featured_review = featured.iloc[0]
                            featured_intensity = to_number(
                                featured_review.get("intensity")
                            )
                            feature_badge = (
                                f"🔥 本場 {featured_intensity:.1f}"
                                if featured_intensity is not None
                                else "🔥 精選案例"
                            )
                            render_html(
                                '<div style="margin:8px 0 12px;padding:13px 14px;border:1px solid #f0d6de;border-radius:14px;background:#fff9fb;">'
                                '<div style="font-weight:950;font-size:1rem;margin-bottom:6px;">🔥 這間店最精彩的一場</div>'
                                f'<div style="font-size:.86rem;color:#d81b50;font-weight:900;margin-bottom:7px;">{safe_text(feature_badge)}</div>'
                                '<div style="font-size:.91rem;line-height:1.55;"><b>😡 顧客：</b>'
                                + safe_text(truncate_text(featured_review.get("review_text"), 92))
                                + '</div>'
                                '<div style="margin-top:6px;font-size:.91rem;line-height:1.55;"><b>🏪 店家：</b>'
                                + safe_text(truncate_text(featured_review.get("owner_reply"), 92))
                                + '</div>'
                                '</div>'
                            )

                        store_url = safe_url(
                            selected_store.get("store_url")
                        )
                        if store_url:
                            st.link_button(
                                "Google Maps",
                                store_url,
                                use_container_width=True,
                            )

                        review_tab, classic_tab, analysis_tab = st.tabs(
                            [
                                "💬 全部案例",
                                "🔥 經典對決",
                                "📊 分析",
                            ]
                        )

                        # --------------------------------------------
                        # TAB 1 — all owner-reply low-star cases
                        # --------------------------------------------
                        with review_tab:
                            render_html(
                                '<div class="explorer-panel-title">全部吵架案例</div>'
                                '<div class="explorer-panel-subtitle">'
                                '只顯示 1–2 星且店家有回覆；每頁 100 筆。'
                                '</div>'
                            )

                            review_filter = st.radio(
                                "篩選",
                                ["全部", "AI 已分析", "1 星", "2 星"],
                                horizontal=True,
                                key=f"v6_filter_{selected_store_id}",
                            )
                            review_sort = st.selectbox(
                                "排序",
                                ["最新", "最激烈", "最多讚", "最舊"],
                                key=f"v6_sort_{selected_store_id}",
                            )

                            page_key = (
                                f"v6_page_{selected_store_id}_"
                                f"{review_filter}_{review_sort}"
                            )
                            current_page_no = int(
                                st.session_state.get(page_key, 1)
                            )

                            review_page, total_reviews = load_store_review_page(
                                selected_store_id,
                                current_page_no,
                                review_filter,
                                review_sort,
                                REVIEW_PAGE_SIZE,
                            )

                            total_pages = max(
                                1,
                                (
                                    total_reviews
                                    + REVIEW_PAGE_SIZE
                                    - 1
                                ) // REVIEW_PAGE_SIZE,
                            )

                            if current_page_no > total_pages:
                                current_page_no = total_pages
                                st.session_state[page_key] = total_pages
                                review_page, total_reviews = load_store_review_page(
                                    selected_store_id,
                                    current_page_no,
                                    review_filter,
                                    review_sort,
                                    REVIEW_PAGE_SIZE,
                                )

                            prev_col, info_col, next_col = st.columns(
                                [1.0, 1.4, 1.0],
                                vertical_alignment="center",
                            )

                            with prev_col:
                                if st.button(
                                    "← 上一頁",
                                    key=f"v6_prev_{page_key}",
                                    disabled=current_page_no <= 1,
                                    use_container_width=True,
                                ):
                                    st.session_state[page_key] = current_page_no - 1
                                    st.rerun()

                            with info_col:
                                render_html(
                                    '<div class="explorer-page-info">'
                                    f'第 {current_page_no} / {total_pages} 頁<br>'
                                    f'共 {total_reviews:,} 則'
                                    '</div>'
                                )

                            with next_col:
                                if st.button(
                                    "下一頁 →",
                                    key=f"v6_next_{page_key}",
                                    disabled=current_page_no >= total_pages,
                                    use_container_width=True,
                                ):
                                    st.session_state[page_key] = current_page_no + 1
                                    st.rerun()

                            if review_page.empty:
                                st.info("目前沒有符合條件的案例。")
                            else:
                                for _, review in review_page.iterrows():
                                    render_google_review_card(review)

                            if total_pages > 1:
                                bottom_prev, bottom_info, bottom_next = st.columns(
                                    [1.0, 1.4, 1.0],
                                    vertical_alignment="center",
                                )
                                with bottom_prev:
                                    if st.button(
                                        "← 上一頁 ",
                                        key=f"v6_prev_bottom_{page_key}",
                                        disabled=current_page_no <= 1,
                                        use_container_width=True,
                                    ):
                                        st.session_state[page_key] = current_page_no - 1
                                        st.rerun()
                                with bottom_info:
                                    render_html(
                                        '<div class="explorer-page-info">'
                                        f'{current_page_no} / {total_pages}'
                                        '</div>'
                                    )
                                with bottom_next:
                                    if st.button(
                                        "下一頁 → ",
                                        key=f"v6_next_bottom_{page_key}",
                                        disabled=current_page_no >= total_pages,
                                        use_container_width=True,
                                    ):
                                        st.session_state[page_key] = current_page_no + 1
                                        st.rerun()

                        # --------------------------------------------
                        # TAB 2 — strongest AI-scored cases
                        # --------------------------------------------
                        with classic_tab:
                            render_html(
                                '<div class="explorer-panel-title">🔥 最精彩對決</div>'
                                '<div class="explorer-panel-subtitle">'
                                '依本場烈度排序，只顯示已有 AI 評分的真實案例。'
                                '</div>'
                            )

                            classics = load_store_classic_reviews(
                                selected_store_id,
                                limit=20,
                            )

                            if classics.empty:
                                st.info("這家店目前還沒有完成 AI 評分的對決。")
                            else:
                                for number, (_, review) in enumerate(
                                    classics.iterrows(),
                                    start=1,
                                ):
                                    intensity = to_number(
                                        review.get("intensity")
                                    )
                                    title = f"#{number}"
                                    if intensity is not None:
                                        title += f"　🔥 {intensity:.1f}"
                                    st.markdown(f"**{title}**")
                                    render_google_review_card(review)

                        # --------------------------------------------
                        # TAB 3 — store analysis, no extra page needed
                        # --------------------------------------------
                        with analysis_tab:
                            render_html(
                                '<div class="explorer-panel-title">📊 店家分析</div>'
                                '<div class="explorer-panel-subtitle">'
                                '快速看這間店的顧客火力、店家火力與情緒，不塞工程圖表。'
                                '</div>'
                            )

                            ai_rows = load_store_ai_rows(
                                selected_store_id
                            )

                            if ai_rows.empty:
                                st.info("這家店目前沒有 AI 分析資料。")
                            else:
                                ai_rows["guest_score"] = pd.to_numeric(
                                    ai_rows["guest_score"], errors="coerce"
                                )
                                ai_rows["owner_score"] = pd.to_numeric(
                                    ai_rows["owner_score"], errors="coerce"
                                )
                                ai_rows["intensity"] = (
                                    ai_rows["guest_score"]
                                    + ai_rows["owner_score"]
                                ) / 2

                                guest_avg = ai_rows["guest_score"].mean()
                                owner_avg = ai_rows["owner_score"].mean()
                                intensity_avg = ai_rows["intensity"].mean()

                                m1, m2, m3 = st.columns(3)
                                m1.metric("😡 顧客平均火力", f"{guest_avg:.1f}")
                                m2.metric("🏪 店家平均火力", f"{owner_avg:.1f}")
                                m3.metric("🔥 平均烈度", f"{intensity_avg:.1f}")

                                score_frame = pd.DataFrame(
                                    {
                                        "角色": ["顧客", "店家"],
                                        "平均火力": [guest_avg, owner_avg],
                                    }
                                )
                                render_clean_horizontal_bar(
                                    score_frame,
                                    category="角色",
                                    value="平均火力",
                                    title="顧客 vs 店家，誰比較火？",
                                    height=150,
                                )

                                sentiment_parts = []
                                for column, role in [
                                    ("guest_sentiment", "顧客"),
                                    ("owner_sentiment", "店家"),
                                ]:
                                    if column in ai_rows.columns:
                                        counts = (
                                            ai_rows[column]
                                            .fillna("")
                                            .replace("", "未標記")
                                            .value_counts()
                                            .rename_axis("情緒")
                                            .reset_index(name="筆數")
                                        )
                                        counts["角色"] = role
                                        sentiment_parts.append(counts)

                                if sentiment_parts:
                                    sentiment_frame = pd.concat(
                                        sentiment_parts,
                                        ignore_index=True,
                                    )
                                    render_sentiment_comparison(
                                        sentiment_frame,
                                        title="顧客 / 店家情緒分布",
                                        height=230,
                                    )

elif current_page == PAGE_DUEL:
    page_title("經典對決")

    if stores.empty:
        st.info("目前沒有資料。")

    else:
        # Classic Duel only shows AI-analyzed stores.
        duel_stores = stores[
            stores["has_ai"]
            & stores[
                "intensity"
            ].notna()
            & (
                stores[
                    "owner_replies"
                ].fillna(0)
                > 0
            )
        ].copy()

        if duel_stores.empty:
            st.info(
                "目前還沒有完成評分的對決。"
            )

        else:
            duel_stores = duel_stores.sort_values(
                "intensity",
                ascending=False,
            )

            store_ids = (
                duel_stores[
                    "store_id"
                ]
                .astype(str)
                .tolist()
            )

            target_store_id = str(
                st.session_state.get(
                    "target_store_id",
                    "",
                )
            )

            default_index = 0

            if (
                target_store_id
                in store_ids
            ):
                default_index = (
                    store_ids.index(
                        target_store_id
                    )
                )

            selector_col, random_col = st.columns(
                [5, 1]
            )

            with selector_col:
                selected_store_id = st.selectbox(
                    "選擇店家",
                    store_ids,
                    index=default_index,
                    format_func=lambda store_id: (
                        duel_stores.loc[
                            duel_stores[
                                "store_id"
                            ].astype(str)
                            == str(store_id),
                            "display_name",
                        ].iloc[0]
                    ),
                    key="duel_store_selector",
                )

            with random_col:
                st.write("")
                st.write("")

                if st.button(
                    "🎲 換一間",
                    use_container_width=True,
                ):
                    selected_store_id = (
                        random.choice(
                            store_ids
                        )
                    )
                    st.session_state[
                        "target_store_id"
                    ] = selected_store_id
                    st.rerun()

            selected_store = (
                duel_stores[
                    duel_stores[
                        "store_id"
                    ].astype(str)
                    == str(
                        selected_store_id
                    )
                ].iloc[0]
            )

            reviews = load_store_reviews(
                str(
                    selected_store_id
                )
            )

            analyzed_reviews = (
                reviews[
                    reviews[
                        "has_ai"
                    ]
                    & reviews[
                        "has_owner_reply"
                    ]
                    & reviews[
                        "intensity"
                    ].notna()
                ].copy()
                if not reviews.empty
                else pd.DataFrame()
            )

            if analyzed_reviews.empty:
                st.info(
                    "這家店目前沒有完成評分的對決。"
                )

            else:
                analyzed_reviews = analyzed_reviews.sort_values(
                    [
                        "intensity",
                        "published_at",
                    ],
                    ascending=[
                        False,
                        False,
                    ],
                    na_position="last",
                ).reset_index(
                    drop=True
                )

                available_intensity = pd.to_numeric(
                    analyzed_reviews[
                        "intensity"
                    ],
                    errors="coerce",
                ).dropna()

                if not available_intensity.empty:
                    filter_col, count_col = st.columns(
                        [4, 1]
                    )

                    with filter_col:
                        minimum = st.slider(
                            "最低烈度",
                            min_value=0.0,
                            max_value=10.0,
                            value=0.0,
                            step=0.5,
                            key=(
                                "duel_min_intensity"
                            ),
                        )

                    analyzed_reviews = analyzed_reviews[
                        analyzed_reviews[
                            "intensity"
                        ]
                        >= minimum
                    ].reset_index(
                        drop=True
                    )

                    with count_col:
                        st.metric(
                            "此店可用案例",
                            len(
                                analyzed_reviews
                            ),
                        )

                if analyzed_reviews.empty:
                    st.warning(
                        "沒有符合烈度條件的案例。"
                    )

                else:
                    case_options = list(
                        range(
                            len(
                                analyzed_reviews
                            )
                        )
                    )

                    selected_case_index = st.selectbox(
                        "選擇這場對決",
                        case_options,
                        format_func=lambda index: (
                            f"#{index + 1}"
                            f"｜🔥 "
                            f"{float(analyzed_reviews.iloc[index]['intensity']):.1f}"
                            f"｜"
                            f"{int(analyzed_reviews.iloc[index]['stars'])}★"
                            f"｜"
                            f"{str(analyzed_reviews.iloc[index]['published_at'])[:10]}"
                        ),
                        key=(
                            f"duel_case_"
                            f"{selected_store_id}"
                        ),
                    )

                    selected_review = (
                        analyzed_reviews.iloc[
                            int(
                                selected_case_index
                            )
                        ]
                    )

                    render_duel(
                        selected_store,
                        selected_review,
                    )

                    st.write("")

                    action_1, action_2, action_3 = st.columns(
                        [1.1, 1.1, 4]
                    )

                    review_url = safe_url(
                        selected_review.get(
                            "review_url"
                        )
                    )
                    store_url = safe_url(
                        selected_store.get(
                            "store_url"
                        )
                    )

                    with action_1:
                        if review_url:
                            st.link_button(
                                "原始 Review",
                                review_url,
                                use_container_width=True,
                            )

                    with action_2:
                        if store_url:
                            st.link_button(
                                "Google Maps",
                                store_url,
                                use_container_width=True,
                            )

                    pr_reply = str(
                        selected_review.get(
                            "pr_reply"
                        )
                        or ""
                    ).strip()

                    if pr_reply:
                        st.divider()

                        st.markdown(
                            "### 🤖 公關救援"
                        )

                        st.info(pr_reply)


# ============================================================
# PAGE 3 — ANALYSIS
# ============================================================

elif current_page == PAGE_ANALYSIS:
    page_title("📊 全站分析")
    render_html(
        '<div class="page-subtitle">'
        '把台北目前已完成 AI 評分的吵架案例整理成幾個一眼能懂的指標。'
        '</div>'
    )

    if stores.empty:
        st.info("目前沒有資料。")
    else:
        analyzed = stores[
            stores["has_ai"]
            & stores["intensity"].notna()
        ].copy()

        if analyzed.empty:
            st.info("目前還沒有完成評分的資料。")
        else:
            review_scores = pd.to_numeric(
                analyzed["review_score"], errors="coerce"
            ).dropna()
            owner_scores = pd.to_numeric(
                analyzed["owner_score"], errors="coerce"
            ).dropna()
            intensities = pd.to_numeric(
                analyzed["intensity"], errors="coerce"
            ).dropna()

            stat_1, stat_2, stat_3, stat_4 = st.columns(4)
            stat_1.metric("已評分店家", f"{len(analyzed):,}")
            stat_2.metric(
                "😡 顧客平均火力",
                f"{review_scores.mean():.1f}" if not review_scores.empty else "—",
            )
            stat_3.metric(
                "🏪 店家平均火力",
                f"{owner_scores.mean():.1f}" if not owner_scores.empty else "—",
            )
            stat_4.metric(
                "🔥 平均烈度",
                f"{intensities.mean():.1f}" if not intensities.empty else "—",
            )

            st.write("")
            left, right = st.columns(2, gap="large")

            with left:
                firepower = pd.DataFrame(
                    {
                        "角色": ["顧客", "店家"],
                        "平均火力": [
                            review_scores.mean() if not review_scores.empty else 0,
                            owner_scores.mean() if not owner_scores.empty else 0,
                        ],
                    }
                )
                render_clean_horizontal_bar(
                    firepower,
                    category="角色",
                    value="平均火力",
                    title="😡 顧客 vs 店家平均火力",
                    height=180,
                )

            with right:
                district_summary = (
                    analyzed.groupby("district", as_index=False)
                    .agg(
                        平均烈度=("intensity", "mean"),
                        店家數=("store_id", "count"),
                    )
                    .sort_values(
                        ["平均烈度", "店家數"],
                        ascending=[False, False],
                    )
                    .head(10)
                )
                render_clean_horizontal_bar(
                    district_summary,
                    category="district",
                    value="平均烈度",
                    title="📍 行政區平均烈度 Top 10",
                    height=280,
                )

            sentiment_parts = []
            for column, role in [
                ("review_sentiment", "顧客"),
                ("owner_sentiment", "店家"),
            ]:
                if column in analyzed.columns:
                    counts = (
                        analyzed[column]
                        .fillna("")
                        .replace("", "未標記")
                        .value_counts()
                        .rename_axis("情緒")
                        .reset_index(name="筆數")
                    )
                    counts["角色"] = role
                    sentiment_parts.append(counts)

            if sentiment_parts:
                sentiment_frame = pd.concat(
                    sentiment_parts,
                    ignore_index=True,
                )
                render_sentiment_comparison(
                    sentiment_frame,
                    title="🙂 全站情緒分布",
                    height=260,
                )


# ============================================================
# PAGE 4 — RANKING
# ============================================================

elif current_page == PAGE_RANKING:
    page_title("🏆 吵架名人堂")
    render_html(
        '<div class="page-subtitle">'
        '前三名直接上頒獎台；點店家就回到地圖查看真實吵架內容。'
        '</div>'
    )

    if stores.empty:
        st.info("目前沒有排行資料。")
    else:
        ranking_type = st.radio(
            "排行",
            [
                "🔥 最火店家",
                "🏪 最嗆店家",
                "😡 最怒顧客",
                "💬 戰役最多",
                "⭐ Google 最低分",
            ],
            horizontal=True,
            label_visibility="collapsed",
        )

        ranking_source = stores[
            stores["owner_replies"].fillna(0) > 0
        ].copy()

        if ranking_type == "🔥 最火店家":
            source = ranking_source[
                ranking_source["has_ai"]
                & ranking_source["intensity"].notna()
            ]
            score_column, prefix, ascending = "intensity", "🔥 ", False

        elif ranking_type == "🏪 最嗆店家":
            source = ranking_source[
                ranking_source["has_ai"]
                & ranking_source["owner_score"].notna()
            ]
            score_column, prefix, ascending = "owner_score", "🏪 ", False

        elif ranking_type == "😡 最怒顧客":
            source = ranking_source[
                ranking_source["has_ai"]
                & ranking_source["review_score"].notna()
            ]
            score_column, prefix, ascending = "review_score", "😡 ", False

        elif ranking_type == "💬 戰役最多":
            source = ranking_source
            score_column, prefix, ascending = "owner_replies", "場 ", False

        else:
            source = ranking_source.dropna(subset=["google_score"])
            score_column, prefix, ascending = "google_score", "⭐ ", True

        ranked = render_podium(
            source,
            score_column,
            prefix,
            ascending=ascending,
        )

        if len(ranked) > 3:
            render_html('<div class="gm-section-title">第 4 名以後</div>')
            render_rank_cards(
                ranked.iloc[3:],
                score_column,
                prefix,
                limit=12,
                ascending=ascending,
                clickable=True,
                start_rank=4,
            )


# ============================================================
# PAGE 5 — PR RESCUE
# ============================================================

elif current_page == PAGE_PR:
    page_title("公關救援")

    if stores.empty:
        st.info("目前沒有資料。")

    else:
        ai_store_options = stores[
            stores["has_ai"]
        ].copy()

        if ai_store_options.empty:
            st.info(
                "目前還沒有公關救援案例。"
            )

        else:
            ai_store_options = ai_store_options.sort_values(
                "intensity",
                ascending=False,
            )

            candidate_ids = (
                ai_store_options[
                    "store_id"
                ]
                .astype(str)
                .tolist()
            )

            selected_pr_store = st.selectbox(
                "選擇店家",
                candidate_ids,
                format_func=lambda store_id: (
                    ai_store_options.loc[
                        ai_store_options[
                            "store_id"
                        ].astype(str)
                        == str(store_id),
                        "display_name",
                    ].iloc[0]
                ),
                key="pr_store",
            )

            selected_store = (
                ai_store_options[
                    ai_store_options[
                        "store_id"
                    ].astype(str)
                    == str(
                        selected_pr_store
                    )
                ].iloc[0]
            )

            reviews = load_store_reviews(
                str(
                    selected_pr_store
                )
            )

            pr_reviews = (
                reviews[
                    reviews[
                        "pr_reply"
                    ].str.strip().ne("")
                    & reviews[
                        "has_owner_reply"
                    ]
                ].copy()
                if not reviews.empty
                else pd.DataFrame()
            )

            if pr_reviews.empty:
                st.info(
                    "這家店目前沒有公關救援案例。"
                )

            else:
                pr_reviews = pr_reviews.sort_values(
                    "intensity",
                    ascending=False,
                    na_position="last",
                ).reset_index(
                    drop=True
                )

                case_index = st.selectbox(
                    "選擇案例",
                    list(
                        range(
                            len(pr_reviews)
                        )
                    ),
                    format_func=lambda index: (
                        f"#{index + 1}"
                        f"｜"
                        f"{int(pr_reviews.iloc[index]['stars'])}★"
                        + (
                            f"｜🔥 "
                            f"{float(pr_reviews.iloc[index]['intensity']):.1f}"
                            if pd.notna(
                                pr_reviews.iloc[index][
                                    "intensity"
                                ]
                            )
                            else ""
                        )
                    ),
                    key="pr_case",
                )

                case = pr_reviews.iloc[
                    int(case_index)
                ]

                render_html(
                    f"""
                    <div class="rescue-grid">
                        <div class="rescue-card">
                            <div class="rescue-title">
                                😡 顧客原文
                            </div>
                            {safe_text(
                                case.get(
                                    "review_text"
                                )
                                or ""
                            )}
                        </div>

                        <div class="
                            rescue-card
                            actual
                        ">
                            <div class="rescue-title">
                                🏪 店家原回覆
                            </div>
                            {safe_text(
                                case.get(
                                    "owner_reply"
                                )
                                or ""
                            )}
                        </div>

                        <div class="
                            rescue-card
                            ai
                        ">
                            <div class="rescue-title">
                                🤖 AI 建議
                            </div>
                            {safe_text(
                                case.get(
                                    "pr_reply"
                                )
                                or ""
                            )}
                        </div>
                    </div>
                    """
                )

                review_url = safe_url(
                    case.get("review_url")
                )
                store_url = safe_url(
                    selected_store.get(
                        "store_url"
                    )
                )

                link_1, link_2, _ = st.columns(
                    [1, 1, 4]
                )

                with link_1:
                    if review_url:
                        st.link_button(
                            "原始 Review",
                            review_url,
                            use_container_width=True,
                        )

                with link_2:
                    if store_url:
                        st.link_button(
                            "Google Maps",
                            store_url,
                            use_container_width=True,
                        )


# ============================================================
# PAGE 6 — REPORT PROTOTYPE
# ============================================================

elif current_page == PAGE_REPORT:
    page_title("匿名爆料")

    if "report_drafts" not in st.session_state:
        st.session_state[
            "report_drafts"
        ] = []

    form_col, draft_col = st.columns(
        [1.35, .85],
        gap="large",
    )

    with form_col:
        with st.form(
            "report_form",
            clear_on_submit=True,
        ):
            left, right = st.columns(
                2
            )

            with left:
                report_store = st.text_input(
                    "店家名稱 *"
                )

                report_location = st.text_input(
                    "地點"
                )

            with right:
                report_tag = st.text_input(
                    "事件標籤",
                    placeholder=(
                        "排隊、態度、價格…"
                    ),
                )

                evidence_url = st.text_input(
                    "公開證據網址"
                )

            report_text = st.text_area(
                "爆料內容 *",
                height=190,
            )

            submitted = st.form_submit_button(
                "暫存匿名草稿",
                use_container_width=True,
            )

            if submitted:
                if (
                    not report_store.strip()
                    or not report_text.strip()
                ):
                    st.warning(
                        "請填寫店家名稱與內容。"
                    )

                else:
                    st.session_state[
                        "report_drafts"
                    ].append(
                        {
                            "store": (
                                report_store.strip()
                            ),
                            "location": (
                                report_location.strip()
                            ),
                            "tag": (
                                report_tag.strip()
                            ),
                            "text": (
                                report_text.strip()
                            ),
                            "url": (
                                evidence_url.strip()
                            ),
                        }
                    )

                    st.success(
                        "已暫存於本次頁面。"
                    )

    with draft_col:
        drafts = st.session_state[
            "report_drafts"
        ]

        st.markdown(
            f"### 草稿箱（{len(drafts)}）"
        )

        if not drafts:
            st.caption(
                "目前沒有草稿。"
            )

        for index, draft in enumerate(
            drafts,
            start=1,
        ):
            with st.expander(
                f"#{index} "
                f"{draft['store']}"
            ):
                if draft["tag"]:
                    st.caption(
                        f"#{draft['tag']}"
                    )

                if draft["location"]:
                    st.caption(
                        draft["location"]
                    )

                st.write(
                    draft["text"]
                )

                url = safe_url(
                    draft["url"]
                )

                if url:
                    st.link_button(
                        "公開證據",
                        url,
                    )