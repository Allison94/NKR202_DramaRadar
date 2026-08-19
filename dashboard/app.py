from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from urllib.parse import urlparse
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


# ============================================================
# Project / data access
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
PAGE_ANALYSIS = "📊 戰況分析"
PAGE_RANKING = "🏆 趣味排行"
PAGE_PR = "🤖 公關救援"
PAGE_REPORT = "🕵️ 匿名爆料"

PAGES = [
    PAGE_MAP,
    PAGE_DUEL,
    PAGE_ANALYSIS,
    PAGE_RANKING,
    PAGE_PR,
    PAGE_REPORT,
]

DISTRICT_PATTERN = re.compile(
    r"(?:台北市|臺北市).*?([\u4e00-\u9fff]{1,4}區)"
)

# 只影響畫面顯示，不改 DB。
DISPLAY_NAME_LIMIT = 26


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
    st.session_state["_next_page"] = page

    if store_id:
        st.session_state["target_store_id"] = str(
            store_id
        )

    st.rerun()


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

    return normalize_review_frame(
        pd.DataFrame(rows)
    )


def refresh_all() -> None:
    st.cache_data.clear()
    st.session_state[
        "last_refresh_at"
    ] = datetime.now(
        timezone.utc
    )
    st.rerun()


# ============================================================
# CSS
# ============================================================

render_html(
    """
    <style>
    :root {
        --bg:#08080a;
        --panel:#141318;
        --panel2:#1b171d;
        --line:rgba(255,255,255,.09);
        --text:#fff8fb;
        --muted:#b5aab1;
        --pink:#ff315d;
        --orange:#ff811b;
        --purple:#c43cff;
        --yellow:#ffc34d;
    }

    .stApp {
        background:
            radial-gradient(
                circle at 12% 0%,
                rgba(255,49,93,.09),
                transparent 24%
            ),
            radial-gradient(
                circle at 90% 8%,
                rgba(196,60,255,.07),
                transparent 22%
            ),
            var(--bg);
        color:var(--text);
    }

    [data-testid="stSidebar"],
    [data-testid="collapsedControl"] {
        display:none !important;
    }

    [data-testid="stHeader"] {
        background:rgba(8,8,10,.90);
        border-bottom:1px solid var(--line);
        backdrop-filter:blur(14px);
    }

    footer {
        display:none !important;
    }

    .block-container {
        max-width:1560px;
        padding-top:1.8rem;
        padding-bottom:3rem;
    }

    h1,h2,h3 {
        color:var(--text) !important;
    }

    .brand-strip {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:16px;
        margin:5px 0 10px;
        padding:12px 15px;
        border:1px solid rgba(255,49,93,.17);
        border-radius:15px;
        background:
            linear-gradient(
                100deg,
                rgba(255,49,93,.06),
                rgba(196,60,255,.035)
            ),
            rgba(18,15,20,.92);
    }

    .brand-name {
        font-size:1.1rem;
        font-weight:950;
        letter-spacing:-.02em;
    }

    .page-title {
        margin:16px 0 2px;
        font-size:clamp(
            1.75rem,
            2.8vw,
            2.35rem
        );
        font-weight:950;
        letter-spacing:-.04em;
    }

    .page-subtitle {
        margin:0 0 14px;
        color:var(--muted);
        font-size:.9rem;
        line-height:1.6;
    }

    div[role="radiogroup"] {
        gap:.45rem;
        padding:.4rem;
        border:1px solid rgba(255,49,93,.14);
        border-radius:14px;
        background:rgba(18,15,20,.78);
    }

    div[role="radiogroup"] label {
        margin:0 !important;
        padding:.42rem .68rem !important;
        border:1px solid transparent;
        border-radius:10px;
        transition:all .15s ease;
    }

    div[role="radiogroup"] label:hover {
        border-color:rgba(255,255,255,.10);
        background:rgba(255,255,255,.04);
    }

    div[role="radiogroup"] label:has(input:checked) {
        border-color:rgba(255,49,93,.28);
        background:linear-gradient(
            90deg,
            rgba(185,32,80,.30),
            rgba(122,36,126,.28)
        );
    }

    .muted {
        color:var(--muted);
        font-size:.82rem;
    }

    .legend {
        display:flex;
        gap:14px;
        flex-wrap:wrap;
        margin:5px 0 10px;
        color:var(--muted);
        font-size:.78rem;
    }

    .map-side-title {
        margin:2px 0 10px;
        font-size:1.25rem;
        font-weight:950;
    }

    .rank-card {
        display:grid;
        grid-template-columns:
            34px
            minmax(0,1fr)
            auto;
        gap:8px;
        align-items:center;
        margin-bottom:7px;
        padding:10px 10px;
        border:1px solid var(--line);
        border-radius:12px;
        background:rgba(21,20,25,.94);
    }

    .rank-no {
        color:#ff8fa7;
        font-weight:950;
    }

    .rank-name {
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
        font-size:.88rem;
        font-weight:850;
    }

    .rank-score {
        color:#ffd17c;
        font-weight:950;
        white-space:nowrap;
    }

    .duel-arena {
        padding:18px;
        border:1px solid rgba(255,49,93,.17);
        border-radius:20px;
        background:
            radial-gradient(
                circle at 50% 0%,
                rgba(255,49,93,.07),
                transparent 38%
            ),
            rgba(20,19,24,.96);
    }

    .duel-store {
        font-size:clamp(
            1.3rem,
            2.2vw,
            1.85rem
        );
        font-weight:950;
        letter-spacing:-.03em;
    }

    .duel-meta {
        margin-top:4px;
        color:var(--muted);
        font-size:.8rem;
    }

    .score-row {
        display:flex;
        gap:7px;
        flex-wrap:wrap;
        margin-top:12px;
    }

    .pill {
        display:inline-block;
        padding:5px 9px;
        border:1px solid rgba(255,255,255,.10);
        border-radius:999px;
        background:rgba(255,255,255,.04);
        color:#eadfe5;
        font-size:.76rem;
        font-weight:850;
    }

    .pill-hot {
        border-color:rgba(255,49,93,.26);
        background:rgba(255,49,93,.08);
        color:#ff9bb2;
    }

    .duel-grid {
        display:grid;
        grid-template-columns:
            1fr
            64px
            1fr;
        gap:12px;
        margin-top:15px;
    }

    .duel-side {
        min-height:220px;
        padding:16px;
        border-radius:15px;
        line-height:1.78;
    }

    .duel-customer {
        border:1px solid rgba(255,49,93,.17);
        background:rgba(255,49,93,.05);
    }

    .duel-owner {
        border:1px solid rgba(255,129,27,.17);
        background:rgba(255,129,27,.05);
    }

    .duel-label {
        margin-bottom:8px;
        font-weight:950;
    }

    .duel-vs {
        display:flex;
        align-items:center;
        justify-content:center;
        color:#ff89a3;
        font-size:1.35rem;
        font-weight:950;
    }

    .ai-summary {
        margin-top:12px;
        padding:13px 14px;
        border:1px solid rgba(196,60,255,.14);
        border-radius:13px;
        background:rgba(196,60,255,.045);
        line-height:1.7;
    }

    .rescue-grid {
        display:grid;
        grid-template-columns:1fr 1fr 1fr;
        gap:12px;
        margin-bottom:14px;
    }

    .rescue-card {
        min-height:205px;
        padding:15px;
        border:1px solid var(--line);
        border-radius:15px;
        background:rgba(20,19,24,.96);
        line-height:1.75;
    }

    .rescue-card.actual {
        border-color:rgba(255,129,27,.18);
    }

    .rescue-card.ai {
        border-color:rgba(196,60,255,.18);
    }

    .rescue-title {
        margin-bottom:8px;
        font-weight:950;
    }

    .big-number {
        font-size:2rem;
        font-weight:950;
        letter-spacing:-.04em;
    }

    .section-rule {
        height:1px;
        margin:18px 0;
        background:var(--line);
    }

    [data-testid="stMetric"] {
        border:1px solid var(--line);
        border-radius:14px;
        padding:11px;
        background:rgba(20,19,24,.94);
    }

    .stButton > button,
    [data-testid="stFormSubmitButton"] button {
        border:1px solid rgba(255,49,93,.30);
        border-radius:11px;
        background:
            linear-gradient(
                90deg,
                #b92050,
                #7a247e
            );
        color:white;
        font-weight:850;
    }

    [data-testid="stLinkButton"] a {
        border-radius:11px;
    }

    iframe[title="streamlit_folium.st_folium"] {
        border:1px solid var(--line);
        border-radius:16px;
        overflow:hidden;
    }

    @media (max-width:900px) {
        .block-container {
            padding-left:.8rem;
            padding-right:.8rem;
        }

        .duel-grid,
        .rescue-grid {
            grid-template-columns:1fr;
        }

        .duel-vs {
            min-height:34px;
        }

        .rank-card {
            grid-template-columns:
                30px
                minmax(0,1fr);
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

    value = max(
        0.0,
        min(float(score), 20.0),
    )

    if value < 7:
        return (
            "#ffc23e",
            "#fff0a4",
            "rgba(255,194,62,.45)",
        )

    if value < 12:
        return (
            "#ff851b",
            "#ffd25d",
            "rgba(255,133,27,.50)",
        )

    if value < 16:
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
) -> DivIcon:
    size = flame_size(score)
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
            );
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
) -> str:
    google_score = to_number(
        row.get("google_score")
    )
    intensity = to_number(
        row.get("intensity")
    )
    store_url = safe_url(
        row.get("store_url")
    )

    badges = []

    if google_score is not None:
        badges.append(
            f"""
            <span style="
                display:inline-block;
                margin-right:5px;
                padding:4px 8px;
                border-radius:999px;
                background:#fff3d4;
                color:#8d6200;
                font-size:12px;
                font-weight:900;
            ">⭐ {google_score:.1f}</span>
            """
        )

    if intensity is not None:
        badges.append(
            f"""
            <span style="
                display:inline-block;
                padding:4px 8px;
                border-radius:999px;
                background:#ffe4eb;
                color:#d71850;
                font-size:12px;
                font-weight:900;
            ">🔥 {intensity:.1f}</span>
            """
        )

    map_link = ""

    if store_url:
        escaped_url = html.escape(
            store_url,
            quote=True,
        )

        map_link = (
            f"""
            <a
                href="{escaped_url}"
                target="_blank"
                style="
                    display:inline-block;
                    margin-top:10px;
                    padding:8px 11px;
                    border-radius:8px;
                    background:#242126;
                    color:white;
                    font-weight:850;
                    text-decoration:none;
                    font-size:12px;
                "
            >Google Maps</a>
            """
        )

    return dedent(
        f"""
        <div style="
            width:290px;
            padding:8px;
            font-family:
                Arial,
                'Microsoft JhengHei',
                sans-serif;
        ">
            <div style="
                font-size:17px;
                font-weight:950;
                color:#241820;
                margin-bottom:7px;
            ">
                {safe_text(
                    display_store_name(
                        row.get("name"),
                        30,
                    )
                )}
            </div>

            <div>
                {''.join(badges)}
            </div>

            <div style="
                margin-top:8px;
                color:#776a71;
                font-size:12px;
                line-height:1.55;
            ">
                📍 {safe_text(
                    row.get("address")
                    or ""
                )}
            </div>

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
        start=1,
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

        render_html(
            f"""
            <div class="rank-card">
                <div class="rank-no">
                    #{number}
                </div>
                <div class="rank-name">
                    {safe_text(
                        row.get(
                            "display_name"
                        )
                        or row.get("name")
                        or ""
                    )}
                </div>
                <div class="rank-score">
                    {safe_text(score_prefix)}
                    {score_text}
                </div>
            </div>
            """
        )

        if clickable:
            if st.button(
                "看這場",
                key=(
                    f"{button_prefix}_"
                    f"{row['store_id']}_"
                    f"{number}"
                ),
                use_container_width=True,
            ):
                go_to(
                    PAGE_DUEL,
                    store_id=str(
                        row["store_id"]
                    ),
                )


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
            f'😡 顧客 {guest_score:.1f}'
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
            f'🏪 店家 {owner_score:.1f}'
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
# PAGE 1 — MAP
# ============================================================

if current_page == PAGE_MAP:
    page_title("🔥 台北吵架地圖")
    render_html(
        '<div class="page-subtitle">'
        '找出低星評論與店家回覆，看看台北今天哪裡最火爆。'
        '</div>'
    )

    if stores.empty:
        st.error(
            database_error
            or "目前沒有可顯示的店家。"
        )

    else:
        # Map = low-star Review + actual owner reply.
        # Reviews waiting for Recheck stay in DB
        # but are not displayed as fight-map cases.
        map_stores = stores[
            stores["owner_replies"]
            .fillna(0)
            > 0
        ].copy()

        if map_stores.empty:
            st.info(
                "目前沒有店家回覆案例。"
            )

        else:
            districts = sorted(
                district
                for district
                in map_stores[
                    "district"
                ].dropna().unique()
                if str(
                    district
                ).strip()
            )

            has_any_ai = bool(
                map_stores[
                    "has_ai"
                ].any()
            )

            filtered = map_stores.copy()

            with st.container(border=True):
                if has_any_ai:
                    search_col, district_col, intensity_col = st.columns(
                        [4.0, 1.35, 1.8]
                    )
                else:
                    search_col, district_col = st.columns(
                        [4.5, 1.5]
                    )

                with search_col:
                    keyword = st.text_input(
                        "搜尋",
                        placeholder=(
                            "店名、地址"
                        ),
                    ).strip()

                with district_col:
                    district_filter = st.selectbox(
                        "行政區",
                        [
                            "全部",
                            *districts,
                        ],
                    )


                if keyword:
                    mask = (
                        filtered[
                            "name"
                        ].str.contains(
                            keyword,
                            case=False,
                            na=False,
                        )
                        | filtered[
                            "address"
                        ].str.contains(
                            keyword,
                            case=False,
                            na=False,
                        )
                    )

                    filtered = filtered[
                        mask
                    ]

                if district_filter != "全部":
                    filtered = filtered[
                        filtered[
                            "district"
                        ]
                        == district_filter
                    ]

                if has_any_ai:
                    with intensity_col:
                        available_scores = pd.to_numeric(
                            filtered[
                                "intensity"
                            ],
                            errors="coerce",
                        ).dropna()

                        if available_scores.empty:
                            st.selectbox(
                                "最低烈度",
                                ["全部"],
                                disabled=True,
                            )
                        else:
                            maximum = max(
                                1.0,
                                float(
                                    available_scores.max()
                                ),
                            )

                            minimum = st.slider(
                                "最低烈度",
                                min_value=0.0,
                                max_value=maximum,
                                value=0.0,
                                step=1.0,
                            )

                            if minimum > 0:
                                filtered = filtered[
                                    filtered[
                                        "intensity"
                                    ].fillna(-1)
                                    >= minimum
                                ]

            map_col, side_col = st.columns(
                [4.0, 1.6],
                gap="large",
            )

            with map_col:
                if filtered.empty:
                    st.warning(
                        "沒有符合條件的案例。"
                    )

                else:
                    center = [
                        float(
                            filtered[
                                "lat"
                            ].mean()
                        ),
                        float(
                            filtered[
                                "lng"
                            ].mean()
                        ),
                    ]

                    drama_map = folium.Map(
                        location=center,
                        zoom_start=12,
                        tiles=None,
                        control_scale=True,
                        prefer_canvas=True,
                    )

                    folium.TileLayer(
                        tiles=(
                            "CartoDB Voyager"
                        ),
                        name="地圖",
                        control=False,
                    ).add_to(
                        drama_map
                    )

                    marker_parent = (
                        drama_map
                    )

                    if len(filtered) > 150:
                        marker_parent = (
                            MarkerCluster(
                                name="店家",
                                overlay=True,
                                control=False,
                            ).add_to(
                                drama_map
                            )
                        )

                    heat_points = []

                    for _, row in filtered.iterrows():
                        score = to_number(
                            row.get(
                                "intensity"
                            )
                        )

                        tooltip = (
                            display_store_name(
                                row.get("name"),
                                28,
                            )
                        )

                        if score is not None:
                            tooltip += (
                                f"｜🔥 "
                                f"{score:.1f}"
                            )

                            heat_points.append(
                                [
                                    float(
                                        row["lat"]
                                    ),
                                    float(
                                        row["lng"]
                                    ),
                                    float(score),
                                ]
                            )

                        Marker(
                            location=[
                                float(
                                    row["lat"]
                                ),
                                float(
                                    row["lng"]
                                ),
                            ],
                            icon=flame_icon(
                                score
                            ),
                            tooltip=tooltip,
                            popup=folium.Popup(
                                map_popup(row),
                                max_width=320,
                            ),
                        ).add_to(
                            marker_parent
                        )

                    if heat_points:
                        HeatMap(
                            heat_points,
                            name="烈度熱區",
                            radius=28,
                            blur=24,
                            min_opacity=.22,
                            show=False,
                        ).add_to(
                            drama_map
                        )

                        folium.LayerControl(
                            collapsed=True
                        ).add_to(
                            drama_map
                        )

                    if len(filtered) > 1:
                        drama_map.fit_bounds(
                            filtered[
                                ["lat", "lng"]
                            ].values.tolist(),
                            padding=(25, 25),
                        )

                    st_folium(
                        drama_map,
                        height=640,
                        use_container_width=True,
                        returned_objects=[],
                        key="main_drama_map",
                    )

            with side_col:
                with st.container(border=True):
                    ai_cases = filtered[
                        filtered[
                            "has_ai"
                        ]
                        & filtered[
                            "intensity"
                        ].notna()
                    ].copy()

                    render_html(
                        '<div class="map-side-title">'
                        '🔥 熱門案例'
                        '</div>'
                    )
                    st.caption(
                        f"目前符合條件 {len(filtered)} 家"
                    )

                    if not ai_cases.empty:
                        intensity_tab, reply_tab = st.tabs(
                            ["🔥 烈度", "💬 回覆"]
                        )

                        with intensity_tab:
                            render_rank_cards(
                                ai_cases,
                                "intensity",
                                "🔥 ",
                                limit=6,
                                clickable=True,
                                button_prefix=(
                                    "map_hot"
                                ),
                            )

                        with reply_tab:
                            render_rank_cards(
                                filtered,
                                "owner_replies",
                                "則 ",
                                limit=7,
                            )

                    else:
                        st.caption(
                            "AI 烈度完成後，這裡會自動出現烈度排行。"
                        )
                        render_rank_cards(
                            filtered,
                            "owner_replies",
                            "則 ",
                            limit=7,
                        )

            st.write("")
            render_html(
                '<div class="map-side-title">'
                '📍 店家概況'
                '</div>'
            )
            st.caption(
                "依照目前搜尋與行政區條件同步更新。"
            )

            overview = filtered.copy()

            if not overview.empty:
                overview["低星評論"] = pd.to_numeric(
                    overview["db_review_count"],
                    errors="coerce",
                ).fillna(0).astype(int)
                overview["店家回覆"] = pd.to_numeric(
                    overview["owner_replies"],
                    errors="coerce",
                ).fillna(0).astype(int)
                overview["回覆率"] = pd.to_numeric(
                    overview["reply_rate"],
                    errors="coerce",
                )
                overview["烈度"] = pd.to_numeric(
                    overview["intensity"],
                    errors="coerce",
                )

                overview = overview[
                    [
                        "display_name",
                        "district",
                        "低星評論",
                        "店家回覆",
                        "回覆率",
                        "烈度",
                    ]
                ].rename(
                    columns={
                        "display_name": "店家",
                        "district": "行政區",
                    }
                )

                if has_any_ai and overview["烈度"].notna().any():
                    overview = overview.sort_values(
                        ["烈度", "店家回覆"],
                        ascending=[False, False],
                        na_position="last",
                    )
                else:
                    overview = overview.sort_values(
                        ["店家回覆", "低星評論"],
                        ascending=[False, False],
                    )

                st.dataframe(
                    overview,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "店家": st.column_config.TextColumn(
                            "店家",
                            width="large",
                        ),
                        "行政區": st.column_config.TextColumn(
                            "行政區",
                            width="small",
                        ),
                        "低星評論": st.column_config.NumberColumn(
                            "低星評論",
                            format="%d",
                        ),
                        "店家回覆": st.column_config.NumberColumn(
                            "店家回覆",
                            format="%d",
                        ),
                        "回覆率": st.column_config.NumberColumn(
                            "回覆率",
                            format="%.0f%%",
                        ),
                        "烈度": st.column_config.NumberColumn(
                            "烈度",
                            format="%.1f",
                        ),
                    },
                    height=min(
                        460,
                        42 + len(overview) * 35,
                    ),
                )
            else:
                st.info("目前沒有符合條件的店家。")


# ============================================================
# PAGE 2 — CLASSIC DUEL
# ============================================================

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
                            max_value=max(
                                1.0,
                                float(
                                    available_intensity.max()
                                ),
                            ),
                            value=0.0,
                            step=1.0,
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
                            "符合案例",
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
    page_title("戰況分析")

    if stores.empty:
        st.info("目前沒有資料。")

    else:
        analyzed = stores[
            stores["has_ai"]
            & stores[
                "intensity"
            ].notna()
        ].copy()

        if analyzed.empty:
            st.info(
                "目前還沒有完成評分的資料。"
            )

        else:
            review_scores = pd.to_numeric(
                analyzed[
                    "review_score"
                ],
                errors="coerce",
            ).dropna()

            owner_scores = pd.to_numeric(
                analyzed[
                    "owner_score"
                ],
                errors="coerce",
            ).dropna()

            intensities = pd.to_numeric(
                analyzed[
                    "intensity"
                ],
                errors="coerce",
            ).dropna()

            stat_1, stat_2, stat_3, stat_4 = st.columns(
                4
            )

            stat_1.metric(
                "已評分店家",
                f"{len(analyzed):,}",
            )

            stat_2.metric(
                "顧客平均火力",
                (
                    f"{review_scores.mean():.1f}"
                    if not review_scores.empty
                    else "—"
                ),
            )

            stat_3.metric(
                "店家平均火力",
                (
                    f"{owner_scores.mean():.1f}"
                    if not owner_scores.empty
                    else "—"
                ),
            )

            stat_4.metric(
                "平均總烈度",
                (
                    f"{intensities.mean():.1f}"
                    if not intensities.empty
                    else "—"
                ),
            )

            st.divider()

            chart_left, chart_right = st.columns(
                2
            )

            with chart_left:
                st.markdown(
                    "### 😡 顧客 vs 店家"
                )

                scatter = analyzed[
                    [
                        "display_name",
                        "review_score",
                        "owner_score",
                        "intensity",
                    ]
                ].dropna(
                    subset=[
                        "review_score",
                        "owner_score",
                    ]
                )

                if not scatter.empty:
                    st.scatter_chart(
                        scatter,
                        x="review_score",
                        y="owner_score",
                        size="intensity",
                        height=370,
                        use_container_width=True,
                    )

            with chart_right:
                st.markdown(
                    "### 📍 行政區烈度"
                )

                district_summary = (
                    analyzed.groupby(
                        "district",
                        as_index=False,
                    )
                    .agg(
                        平均烈度=(
                            "intensity",
                            "mean",
                        ),
                        店家數=(
                            "store_id",
                            "count",
                        ),
                    )
                    .sort_values(
                        "平均烈度",
                        ascending=False,
                    )
                )

                if not district_summary.empty:
                    st.bar_chart(
                        district_summary.set_index(
                            "district"
                        )[
                            ["平均烈度"]
                        ],
                        height=370,
                        use_container_width=True,
                    )

            st.divider()

            sentiment_left, sentiment_right = st.columns(
                2
            )

            with sentiment_left:
                st.markdown(
                    "### 顧客情緒"
                )

                customer_sentiment = (
                    analyzed[
                        "review_sentiment"
                    ]
                    .replace(
                        "",
                        "未標記",
                    )
                    .value_counts()
                    .rename_axis(
                        "sentiment"
                    )
                    .to_frame(
                        "店家數"
                    )
                )

                st.bar_chart(
                    customer_sentiment,
                    height=300,
                    use_container_width=True,
                )

            with sentiment_right:
                st.markdown(
                    "### 店家情緒"
                )

                owner_sentiment = (
                    analyzed[
                        "owner_sentiment"
                    ]
                    .replace(
                        "",
                        "未標記",
                    )
                    .value_counts()
                    .rename_axis(
                        "sentiment"
                    )
                    .to_frame(
                        "店家數"
                    )
                )

                st.bar_chart(
                    owner_sentiment,
                    height=300,
                    use_container_width=True,
                )


# ============================================================
# PAGE 4 — RANKING
# ============================================================

elif current_page == PAGE_RANKING:
    page_title("趣味排行")

    if stores.empty:
        st.info("目前沒有排行資料。")

    else:
        ranking_type = st.radio(
            "排行",
            [
                "🔥 烈度最高",
                "💬 低星評論最多",
                "🏪 回覆率最高",
                "⭐ Google 評分最低",
            ],
            horizontal=True,
            label_visibility="collapsed",
        )

        ranking_source = stores[
            stores[
                "owner_replies"
            ].fillna(0)
            > 0
        ].copy()

        if ranking_type == "🔥 烈度最高":
            ai_ranking = ranking_source[
                ranking_source[
                    "has_ai"
                ]
                & ranking_source[
                    "intensity"
                ].notna()
            ]

            render_rank_cards(
                ai_ranking,
                "intensity",
                "🔥 ",
                limit=15,
                clickable=True,
                button_prefix="ranking_hot",
            )

        elif ranking_type == "💬 低星評論最多":
            render_rank_cards(
                ranking_source,
                "db_review_count",
                "則 ",
                limit=15,
            )

        elif ranking_type == "🏪 回覆率最高":
            valid = ranking_source[
                ranking_source[
                    "db_review_count"
                ].fillna(0)
                > 0
            ]

            render_rank_cards(
                valid,
                "reply_rate",
                "",
                limit=15,
                percent=True,
            )

        else:
            render_rank_cards(
                ranking_source,
                "google_score",
                "⭐ ",
                limit=15,
                ascending=True,
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