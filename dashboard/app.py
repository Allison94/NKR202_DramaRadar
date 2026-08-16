from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from urllib.parse import quote, urlparse
import html
import re
import sys

import folium
import pandas as pd
import streamlit as st
from folium import DivIcon, Marker
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium


# ============================================================
# Project path / existing project data access
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 沿用組內既有 Dashboard SQL 入口。
# 本檔只 READ，不新增欄位、不修改 schema、不寫 Store / Review / AI。
from domains.store.repository import (
    fetch_dashboard_rows,
    fetch_store_reviews,
)


# ============================================================
# Streamlit config
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
PAGE_CLASSIC = "💬 經典對決"
PAGE_ANALYSIS = "📊 戰況分析"
PAGE_RANKING = "🏆 趣味排行"
PAGE_PR = "🤖 公關救援"
PAGE_REPORT = "🕵️ 匿名爆料"

PAGE_OPTIONS = [
    PAGE_MAP,
    PAGE_CLASSIC,
    PAGE_ANALYSIS,
    PAGE_RANKING,
    PAGE_PR,
    PAGE_REPORT,
]

DISTRICT_PATTERN = re.compile(
    r"(?:台北市|臺北市).*?([\u4e00-\u9fff]{1,4}區)"
)


# ============================================================
# Helpers
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

    return text if parsed.scheme in {"http", "https"} else ""


def to_number(value: object) -> float | None:
    parsed = pd.to_numeric(
        pd.Series([value]),
        errors="coerce",
    ).iloc[0]

    if pd.isna(parsed):
        return None

    return float(parsed)


def district_from_address(address: object) -> str:
    text = str(address or "")
    match = DISTRICT_PATTERN.search(text)
    return match.group(1) if match else "未辨識行政區"


def short_store_name(value: object, limit: int = 24) -> str:
    """UI-only shortening; database title is never changed."""
    text = str(value or "").strip()

    if len(text) <= limit:
        return text

    return text[:limit].rstrip() + "…"


def format_case_label(
    review: pd.Series,
    index: int,
) -> str:
    stars = to_number(review.get("stars"))
    intensity = to_number(review.get("intensity"))
    published_at = review.get("published_at")

    parts = [f"案例 {index}"]

    if stars is not None:
        parts.append(f"{int(stars)}★")

    if pd.notna(published_at):
        parts.append(str(published_at)[:10])

    if intensity is not None:
        parts.append(f"🔥 {intensity:.1f}")

    return "｜".join(parts)


def row_has_ai(row: pd.Series) -> bool:
    """
    domains/store/repository.py 目前會把 AI score 缺值 COALESCE 成 0。
    因此用 score / sentiment / pr_reply 綜合判斷是否已有正式 AI 結果。
    """

    review_score = to_number(row.get("review_score")) or 0.0
    owner_score = to_number(row.get("owner_score")) or 0.0

    return any(
        [
            review_score > 0,
            owner_score > 0,
            bool(str(row.get("review_sentiment") or "").strip()),
            bool(str(row.get("owner_sentiment") or "").strip()),
            bool(str(row.get("pr_reply") or "").strip()),
        ]
    )


def official_intensity(row: pd.Series) -> float | None:
    """
    組長既定烈度：
    review_score + owner_score

    沒有正式 AI 結果就回傳 None，不從星等、文字自行補分。
    """

    if not row_has_ai(row):
        return None

    review_score = to_number(row.get("review_score"))
    owner_score = to_number(row.get("owner_score"))

    if review_score is None or owner_score is None:
        return None

    return float(review_score) + float(owner_score)


def normalize_store_frame(frame: pd.DataFrame) -> pd.DataFrame:
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
        result[column] = result[column].fillna("").astype(str)

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

    result["district"] = result["address"].apply(district_from_address)
    result["has_ai"] = result.apply(row_has_ai, axis=1)
    result["intensity"] = result.apply(official_intensity, axis=1)

    result["has_representative_reply"] = (
        result["owner_reply"].str.strip().ne("")
        & result["owner_reply"].str.strip().ne("店家尚未回覆")
    )

    review_count = result["db_review_count"].fillna(0)
    owner_count = result["owner_replies"].fillna(0)

    result["reply_rate"] = 0.0
    valid = review_count > 0
    result.loc[valid, "reply_rate"] = (
        owner_count[valid]
        / review_count[valid]
        * 100
    )

    # schema 的 lat/lng default 是 0，但 Dashboard 不把 0/0 當成真實台北座標。
    result = result.dropna(subset=["lat", "lng"])
    result = result[
        result["lat"].between(24.8, 25.3)
        & result["lng"].between(121.2, 122.0)
    ].copy()

    return result.reset_index(drop=True)


def normalize_review_frame(frame: pd.DataFrame) -> pd.DataFrame:
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
        if column in result.columns:
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
        result[column] = result[column].fillna("").astype(str)

    result["has_ai"] = result.apply(
        lambda row: any(
            [
                (to_number(row.get("guest_score")) or 0) > 0,
                (to_number(row.get("owner_score")) or 0) > 0,
                bool(str(row.get("guest_sentiment") or "").strip()),
                bool(str(row.get("owner_sentiment") or "").strip()),
                bool(str(row.get("pr_reply") or "").strip()),
            ]
        ),
        axis=1,
    )

    result["intensity"] = result.apply(
        lambda row: (
            (to_number(row.get("guest_score")) or 0)
            + (to_number(row.get("owner_score")) or 0)
            if bool(row.get("has_ai"))
            else None
        ),
        axis=1,
    )

    result["has_owner_reply"] = (
        result["owner_reply"].str.strip().ne("")
    )

    return result


@st.cache_data(ttl=300, show_spinner="正在讀取資料…")
def load_store_data() -> pd.DataFrame:
    # 沿用現有 Store repository；不修改它。
    rows = fetch_dashboard_rows(limit=2000)
    return normalize_store_frame(pd.DataFrame(rows))


@st.cache_data(ttl=300, show_spinner=False)
def load_reviews(place_id: str) -> pd.DataFrame:
    rows = fetch_store_reviews(
        place_id,
        limit=200,
    )
    return normalize_review_frame(pd.DataFrame(rows))


def refresh_dashboard() -> None:
    st.cache_data.clear()
    st.session_state["last_refresh_utc"] = datetime.now(timezone.utc)
    st.rerun()


# ============================================================
# CSS
# ============================================================

render_html(
    """
    <style>
    :root {
        --bg:#09090b;
        --panel:rgba(24,24,29,.93);
        --panel2:rgba(35,29,39,.92);
        --border:rgba(255,255,255,.09);
        --text:#fff8fb;
        --muted:#b9acb3;
        --pink:#ff315d;
        --orange:#ff811b;
        --purple:#c13cff;
        --yellow:#f7ba38;
    }

    .stApp {
        background:
            radial-gradient(circle at 10% 0%, rgba(255,49,93,.08), transparent 26%),
            radial-gradient(circle at 90% 8%, rgba(193,60,255,.07), transparent 24%),
            var(--bg);
        color:var(--text);
    }

    [data-testid="stSidebar"],
    [data-testid="collapsedControl"] {
        display:none !important;
    }

    [data-testid="stHeader"] {
        background:rgba(9,9,11,.88);
        border-bottom:1px solid var(--border);
        backdrop-filter:blur(14px);
    }

    footer { display:none !important; }

    .block-container {
        max-width:1580px;
        padding-top:3.4rem;
        padding-bottom:3rem;
    }

    h1,h2,h3 { color:var(--text) !important; }

    .page-title {
        margin-top:8px;
        font-size:clamp(1.55rem,2.5vw,2.05rem);
        font-weight:950;
        letter-spacing:-.03em;
    }

    .small-muted {
        color:var(--muted);
        font-size:.82rem;
    }

    .legend {
        display:flex;
        flex-wrap:wrap;
        gap:14px;
        margin:5px 0 10px;
        color:var(--muted);
        font-size:.78rem;
    }

    [data-testid="stMetric"] {
        border:1px solid var(--border);
        border-radius:15px;
        padding:12px;
        background:var(--panel);
    }

    .rank-row {
        display:grid;
        grid-template-columns:38px minmax(0,1fr) auto;
        gap:9px;
        align-items:center;
        margin-bottom:8px;
        padding:10px 11px;
        border:1px solid var(--border);
        border-radius:12px;
        background:var(--panel);
    }

    .rank-no {
        color:#ff9ab0;
        font-weight:950;
    }

    .rank-name {
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
        font-weight:850;
    }

    .rank-score {
        color:#ffd082;
        font-weight:950;
    }

    .battle-card {
        margin-bottom:13px;
        padding:16px;
        border:1px solid rgba(255,49,93,.16);
        border-radius:17px;
        background:var(--panel);
    }

    .battle-head {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        margin-bottom:10px;
    }

    .battle-name {
        font-size:1.05rem;
        font-weight:950;
    }

    .battle-score {
        color:#ff9eb3;
        font-weight:950;
    }

    .battle-grid {
        display:grid;
        grid-template-columns:1fr 46px 1fr;
        gap:9px;
        align-items:stretch;
    }

    .battle-side {
        padding:11px 12px;
        border-radius:12px;
        line-height:1.65;
        font-size:.88rem;
    }

    .battle-customer {
        background:rgba(255,49,93,.05);
        border:1px solid rgba(255,49,93,.14);
    }

    .battle-owner {
        background:rgba(255,129,27,.05);
        border:1px solid rgba(255,129,27,.14);
    }

    .battle-vs {
        display:flex;
        align-items:center;
        justify-content:center;
        font-weight:950;
        color:#ff93aa;
    }

    .ai-card {
        margin-top:9px;
        padding:11px 12px;
        border-radius:12px;
        border:1px solid rgba(193,60,255,.14);
        background:rgba(193,60,255,.05);
        line-height:1.65;
        font-size:.87rem;
    }

    .pill {
        display:inline-block;
        margin:2px 5px 2px 0;
        padding:4px 8px;
        border:1px solid rgba(255,255,255,.10);
        border-radius:999px;
        background:rgba(255,255,255,.045);
        color:#e8dde3;
        font-size:.74rem;
        font-weight:800;
    }

    .pill-hot {
        border-color:rgba(255,49,93,.26);
        background:rgba(255,49,93,.08);
        color:#ff9bb1;
    }

    .duel-stage {
        padding: 18px;
        border: 1px solid rgba(255,49,93,.18);
        border-radius: 20px;
        background:
            radial-gradient(circle at 50% 0%, rgba(255,49,93,.07), transparent 38%),
            var(--panel);
    }

    .duel-store {
        font-size: clamp(1.2rem, 2vw, 1.65rem);
        font-weight: 950;
        letter-spacing: -.02em;
    }

    .duel-meta {
        margin-top: 4px;
        color: var(--muted);
        font-size: .8rem;
    }

    .duel-scoreline {
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
        margin-top: 12px;
    }

    .duel-grid {
        display: grid;
        grid-template-columns: 1fr 58px 1fr;
        gap: 12px;
        margin-top: 14px;
        align-items: stretch;
    }

    .duel-side {
        min-height: 210px;
        padding: 16px;
        border-radius: 15px;
        line-height: 1.78;
    }

    .duel-customer {
        border: 1px solid rgba(255,49,93,.18);
        background: rgba(255,49,93,.055);
    }

    .duel-owner {
        border: 1px solid rgba(255,129,27,.18);
        background: rgba(255,129,27,.055);
    }

    .duel-label {
        margin-bottom: 8px;
        font-size: 1rem;
        font-weight: 950;
    }

    .duel-vs {
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ff8aa4;
        font-size: 1.35rem;
        font-weight: 950;
    }

    .duel-ai {
        margin-top: 12px;
        padding: 13px 14px;
        border-radius: 13px;
        border: 1px solid rgba(193,60,255,.15);
        background: rgba(193,60,255,.05);
        line-height: 1.7;
    }

    .preview-badge {
        display: inline-block;
        margin-bottom: 10px;
        padding: 5px 9px;
        border: 1px solid rgba(255,255,255,.10);
        border-radius: 999px;
        color: var(--muted);
        background: rgba(255,255,255,.035);
        font-size: .75rem;
        font-weight: 800;
    }

    .note-box {
        padding:14px 15px;
        border:1px dashed rgba(255,255,255,.14);
        border-radius:13px;
        background:rgba(255,255,255,.025);
        color:var(--muted);
        line-height:1.7;
    }

    .stButton > button,
    [data-testid="stFormSubmitButton"] button {
        border:1px solid rgba(255,49,93,.32);
        border-radius:11px;
        background:linear-gradient(90deg,#ac204c,#7d247f);
        color:white;
        font-weight:850;
    }


    /* 首頁地圖優先：減少主視覺與導覽之間的空白 */
    [data-testid="stImage"] {
        margin-bottom: .15rem;
    }

    iframe[title="streamlit_folium.st_folium"] {
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,.08);
        overflow: hidden;
    }

    @media (max-width:800px) {
        .block-container {
            padding-left:.8rem;
            padding-right:.8rem;
            padding-top:3.4rem;
        }

        .battle-grid,
        .duel-grid {
            grid-template-columns:1fr;
        }

        .battle-vs,
        .duel-vs {
            min-height:30px;
        }

        .rank-row {
            grid-template-columns:32px minmax(0,1fr);
        }

        .rank-score {
            grid-column:2;
        }
    }
    </style>
    """
)


# ============================================================
# Data
# ============================================================

try:
    df = load_store_data()
    db_error = ""
except Exception as exc:
    df = pd.DataFrame()
    db_error = str(exc)

if "last_refresh_utc" not in st.session_state:
    st.session_state["last_refresh_utc"] = datetime.now(timezone.utc)


# ============================================================
# Header / navigation
# ============================================================

# 主視覺縮小，首頁第一屏就能看到地圖。
if SPLASH_IMAGE.exists():
    _, image_col, _ = st.columns([2.2, 5.6, 2.2])
    with image_col:
        st.image(
            str(SPLASH_IMAGE),
            use_container_width=True,
        )

# Folium popup 可直接導向「經典對決」並帶入店家。
requested_page = str(st.query_params.get("page", "") or "")
requested_store = str(st.query_params.get("store", "") or "")

if requested_page == "classic":
    st.session_state["dashboard_page_v8"] = PAGE_CLASSIC

nav_col, refresh_col = st.columns([6, 1])

with nav_col:
    current_page = st.radio(
        "功能",
        PAGE_OPTIONS,
        horizontal=True,
        label_visibility="collapsed",
        key="dashboard_page_v8",
    )

with refresh_col:
    st.button(
        "↻ 重新整理",
        use_container_width=True,
        on_click=refresh_dashboard,
    )


def page_title(title: str) -> None:
    render_html(
        f'<div class="page-title">{safe_text(title)}</div>'
    )


# ============================================================
# Shared rendering
# ============================================================

def render_rank(
    frame: pd.DataFrame,
    score_col: str,
    label: str,
    *,
    limit: int = 8,
    ascending: bool = False,
    percentage: bool = False,
) -> None:
    if frame.empty or score_col not in frame.columns:
        st.info("目前沒有資料。")
        return

    ranked = frame.copy()
    ranked[score_col] = pd.to_numeric(
        ranked[score_col],
        errors="coerce",
    )
    ranked = ranked.dropna(subset=[score_col])

    if ranked.empty:
        st.info("目前沒有資料。")
        return

    ranked = ranked.sort_values(
        [score_col, "db_review_count"],
        ascending=[ascending, False],
    ).head(limit)

    rows = []

    for rank, (_, row) in enumerate(
        ranked.iterrows(),
        start=1,
    ):
        score = float(row[score_col])

        if percentage:
            score_text = f"{score:.0f}%"
        elif score_col in {"db_review_count", "owner_replies"}:
            score_text = f"{score:.0f}"
        else:
            score_text = f"{score:.1f}"

        rows.append(
            f"""
            <div class="rank-row">
                <div class="rank-no">#{rank}</div>
                <div class="rank-name">{safe_text(row.get("name") or "")}</div>
                <div class="rank-score">{safe_text(label)} {score_text}</div>
            </div>
            """
        )

    render_html("".join(rows))


def flame_size(score: float | None) -> int:
    if score is None:
        return 31

    value = max(0.0, min(float(score), 20.0))
    return int(30 + (value / 20.0) * 35)


def flame_colors(score: float | None) -> tuple[str, str, str]:
    if score is None:
        return "#746d73", "#bbb2b9", "rgba(180,170,178,.22)"

    value = max(0.0, min(float(score), 20.0))

    if value < 7:
        return "#f7ba38", "#fff0a5", "rgba(247,186,56,.45)"
    if value < 12:
        return "#ff811b", "#ffd05b", "rgba(255,129,27,.50)"
    if value < 16:
        return "#ff4338", "#ffad3d", "rgba(255,67,56,.62)"

    return "#e00043", "#ff7138", "rgba(224,0,67,.84)"


def make_flame_icon(score: float | None) -> DivIcon:
    size = flame_size(score)
    outer, inner, glow = flame_colors(score)

    score_html = (
        f"""
        <div style="
            position:absolute;left:50%;bottom:0;transform:translateX(-50%);
            min-width:28px;padding:1px 5px;border-radius:999px;
            background:rgba(18,13,18,.94);
            border:1px solid rgba(255,255,255,.25);
            color:white;font:800 10px/14px Arial;text-align:center;
        ">{score:.0f}</div>
        """
        if score is not None
        else ""
    )

    icon_html = dedent(
        f"""
        <div style="
            position:relative;width:{size}px;height:{size + 17}px;
            filter:drop-shadow(0 0 {max(4, size // 7)}px {glow});
        ">
            <svg width="{size}" height="{size}" viewBox="0 0 64 64">
                <path d="M34 3 C37 13 31 17 38 25
                         C41 20 45 16 45 10
                         C55 21 60 31 57 43
                         C54 55 45 62 32 62
                         C18 62 8 53 7 41
                         C6 31 12 23 20 17
                         C19 26 24 29 27 23
                         C31 16 27 10 34 3 Z"
                      fill="{outer}" />
                <path d="M33 28 C38 34 43 38 42 46
                         C41 54 36 58 30 58
                         C23 58 18 53 19 46
                         C20 40 25 37 28 32
                         C29 37 32 39 34 36
                         C36 33 34 30 33 28 Z"
                      fill="{inner}" />
            </svg>
            {score_html}
        </div>
        """
    ).strip()

    return DivIcon(
        html=icon_html,
        icon_size=(size, size + 17),
        icon_anchor=(size // 2, size + 8),
        popup_anchor=(0, -size),
        class_name="drama-flame-div-icon",
    )


def map_popup(row: pd.Series) -> str:
    store_url = safe_url(row.get("store_url"))

    google_score = to_number(row.get("google_score"))
    intensity = to_number(row.get("intensity"))
    review_count = int(
        to_number(row.get("db_review_count")) or 0
    )
    owner_reply_count = int(
        to_number(row.get("owner_replies")) or 0
    )

    badge_html = ""

    if google_score is not None:
        badge_html += (
            f'<span style="display:inline-block;margin-right:5px;padding:4px 8px;'
            f'border-radius:999px;background:#fff4d8;color:#946400;'
            f'font-size:12px;font-weight:900;">⭐ {google_score:.1f}</span>'
        )

    if intensity is not None:
        badge_html += (
            f'<span style="display:inline-block;padding:4px 8px;border-radius:999px;'
            f'background:#ffe7ed;color:#d71952;font-size:12px;font-weight:900;">'
            f'🔥 {intensity:.1f}</span>'
        )

    place_id = str(row.get("store_id") or "").strip()
    detail_html = ""

    if place_id:
        detail_url = f"?page=classic&store={quote(place_id)}"
        detail_html = (
            f'<a href="{detail_url}" target="_top" '
            'style="display:inline-block;margin-top:11px;margin-right:6px;'
            'padding:8px 12px;border-radius:8px;background:#c82455;'
            'color:white;font-weight:800;text-decoration:none;font-size:12px;">'
            '查看案例</a>'
        )

    map_html = ""

    if store_url:
        escaped = html.escape(
            store_url,
            quote=True,
        )
        map_html = (
            f'<a href="{escaped}" target="_blank" '
            'style="display:inline-block;margin-top:11px;padding:8px 12px;'
            'border-radius:8px;background:#242126;color:white;font-weight:800;'
            'text-decoration:none;font-size:12px;">Google Maps</a>'
        )

    return dedent(
        f"""
        <div style="width:300px;padding:8px;font-family:Arial,'Microsoft JhengHei',sans-serif;">
            <div style="font-size:17px;font-weight:900;color:#241820;margin-bottom:6px;">
                {safe_text(short_store_name(row.get("name"), 28))}
            </div>

            <div style="margin-bottom:8px;">{badge_html}</div>

            <div style="margin:7px 0;color:#74666e;font-size:12px;line-height:1.55;">
                📍 {safe_text(row.get("address") or "")}
            </div>

            <div style="display:flex;gap:7px;margin-top:9px;">
                <div style="flex:1;padding:8px;border-radius:8px;background:#fff7f8;
                            color:#41363c;font-size:12px;">
                    <b>{review_count}</b><br>1★ / 2★ 評論
                </div>
                <div style="flex:1;padding:8px;border-radius:8px;background:#fff7ed;
                            color:#41363c;font-size:12px;">
                    <b>{owner_reply_count}</b><br>店家回覆
                </div>
            </div>

            {detail_html}
            {map_html}
        </div>
        """
    ).strip()


def render_battle_card(
    store_name: str,
    review: pd.Series,
    *,
    show_ai: bool = True,
) -> None:
    intensity = to_number(review.get("intensity"))
    stars = to_number(review.get("stars"))

    score_html = ""

    if stars is not None:
        score_html += (
            f'<span class="pill">⭐ {int(stars)} 星</span>'
        )

    if intensity is not None:
        score_html += (
            f'<span class="pill pill-hot">🔥 {intensity:.1f}/20</span>'
        )

    ai_html = ""

    if show_ai:
        guest_summary = safe_text(
            review.get("guest_summary") or ""
        )
        owner_summary = safe_text(
            review.get("owner_summary") or ""
        )

        if guest_summary or owner_summary:
            ai_html = (
                '<div class="ai-card">'
                '<b>AI 摘要</b><br>'
                f'顧客：{guest_summary or "—"}<br>'
                f'店家：{owner_summary or "—"}'
                '</div>'
            )

    render_html(
        f"""
        <div class="battle-card">
            <div class="battle-head">
                <div class="battle-name">{safe_text(store_name)}</div>
                <div>{score_html}</div>
            </div>

            <div class="battle-grid">
                <div class="battle-side battle-customer">
                    <b>😡 顧客</b><br>
                    {safe_text(review.get("review_text") or "") or "（沒有評論內容）"}
                </div>

                <div class="battle-vs">VS</div>

                <div class="battle-side battle-owner">
                    <b>🏪 店家</b><br>
                    {safe_text(review.get("owner_reply") or "") or "（店家尚未回覆）"}
                </div>
            </div>

            {ai_html}
        </div>
        """
    )


def render_featured_duel(
    store_row: pd.Series,
    review: pd.Series,
    *,
    preview_mode: bool,
) -> None:
    stars = to_number(review.get("stars"))
    guest_score = to_number(review.get("guest_score"))
    owner_score = to_number(review.get("owner_score"))
    intensity = to_number(review.get("intensity"))

    pills: list[str] = []

    if stars is not None:
        pills.append(
            f'<span class="pill">⭐ {int(stars)} 星</span>'
        )

    if intensity is not None:
        pills.append(
            f'<span class="pill pill-hot">🔥 烈度 {intensity:.1f}</span>'
        )

    if guest_score is not None and bool(review.get("has_ai")):
        pills.append(
            f'<span class="pill">😡 顧客 {guest_score:.1f}</span>'
        )

    if owner_score is not None and bool(review.get("has_ai")):
        pills.append(
            f'<span class="pill">🏪 店家 {owner_score:.1f}</span>'
        )

    guest_summary = safe_text(
        review.get("guest_summary") or ""
    )
    owner_summary = safe_text(
        review.get("owner_summary") or ""
    )
    pr_reply = safe_text(
        review.get("pr_reply") or ""
    )

    ai_summary_html = ""

    if guest_summary or owner_summary:
        ai_summary_html = (
            '<div class="duel-ai">'
            '<b>🧠 AI 摘要</b><br>'
            f'顧客：{guest_summary or "—"}<br>'
            f'店家：{owner_summary or "—"}'
            '</div>'
        )

    preview_html = (
        '<span class="preview-badge">回覆案例預覽</span>'
        if preview_mode
        else ""
    )

    render_html(
        f"""
        {preview_html}

        <div class="duel-stage">
            <div class="duel-store">
                {safe_text(short_store_name(store_row.get("name"), 34))}
            </div>

            <div class="duel-meta">
                {safe_text(store_row.get("district") or "")}
                &nbsp;｜&nbsp;
                {safe_text(str(review.get("published_at") or "")[:10])}
            </div>

            <div class="duel-scoreline">
                {''.join(pills)}
            </div>

            <div class="duel-grid">
                <div class="duel-side duel-customer">
                    <div class="duel-label">😡 顧客</div>
                    {safe_text(review.get("review_text") or "") or "（沒有評論內容）"}
                </div>

                <div class="duel-vs">VS</div>

                <div class="duel-side duel-owner">
                    <div class="duel-label">🏪 店家</div>
                    {safe_text(review.get("owner_reply") or "") or "（店家尚未回覆）"}
                </div>
            </div>

            {ai_summary_html}
        </div>
        """
    )

    if pr_reply:
        with st.expander("🤖 公關救援"):
            st.write(pr_reply)


# ============================================================
# PAGE: Map — default homepage
# ============================================================

if current_page == PAGE_MAP:
    page_title("吵架地圖")

    if df.empty:
        st.error(
            db_error
            or "目前沒有可顯示的台北市低星評論店家。"
        )
    else:
        # 吵架地圖只展示「至少有一則店家回覆」的店。
        # 沒回覆的 Review 仍留在 DB 做 Recheck，但不當成地圖案例。
        map_df = df[
            df["owner_replies"].fillna(0) > 0
        ].copy()

        if map_df.empty:
            st.info("目前沒有可顯示的店家回覆案例。")
        else:
            district_values = sorted(
                value
                for value in map_df["district"].dropna().unique().tolist()
                if str(value).strip()
            )

            has_any_ai = bool(map_df["has_ai"].any())

            if has_any_ai:
                search_col, district_col, intensity_col = st.columns(
                    [3.0, 1.3, 2.0]
                )
            else:
                search_col, district_col = st.columns(
                    [4.5, 1.5]
                )

            with search_col:
                keyword = st.text_input(
                    "搜尋",
                    placeholder="店名、地址",
                ).strip()

            with district_col:
                district = st.selectbox(
                    "行政區",
                    ["全部", *district_values],
                )

            filtered = map_df.copy()

            if keyword:
                mask = (
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
                filtered = filtered[mask]

            if district != "全部":
                filtered = filtered[
                    filtered["district"] == district
                ]

            if has_any_ai:
                intensity_values = pd.to_numeric(
                    filtered["intensity"],
                    errors="coerce",
                ).dropna()

                with intensity_col:
                    if intensity_values.empty:
                        st.selectbox(
                            "最低烈度",
                            ["全部"],
                            disabled=True,
                        )
                    else:
                        actual_max = max(
                            1.0,
                            float(intensity_values.max()),
                        )

                        minimum_intensity = st.slider(
                            "最低烈度",
                            min_value=0.0,
                            max_value=actual_max,
                            value=0.0,
                            step=1.0,
                        )

                        if minimum_intensity > 0:
                            filtered = filtered[
                                filtered["intensity"].fillna(-1)
                                >= minimum_intensity
                            ]

            render_html(
                """
                <div class="legend">
                    <span>🔥 灰焰：待評分</span>
                    <span>🔥 彩焰：已有烈度</span>
                </div>
                """
            )

            map_col, side_col = st.columns(
                [4.85, 1.15],
                gap="large",
            )

            with map_col:
                if filtered.empty:
                    st.warning("目前沒有符合條件的店家。")
                else:
                    center = [
                        float(filtered["lat"].mean()),
                        float(filtered["lng"].mean()),
                    ]

                    drama_map = folium.Map(
                        location=center,
                        zoom_start=11,
                        tiles=None,
                        control_scale=True,
                        prefer_canvas=True,
                    )

                    folium.TileLayer(
                        tiles="CartoDB Voyager",
                        name="台北市地圖",
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

                    for _, store in filtered.iterrows():
                        intensity = to_number(
                            store.get("intensity")
                        )

                        tooltip = short_store_name(
                            store.get("name"),
                            28,
                        )

                        if intensity is not None:
                            tooltip += f"｜🔥 {intensity:.1f}"

                            heat_points.append(
                                [
                                    float(store["lat"]),
                                    float(store["lng"]),
                                    float(intensity),
                                ]
                            )

                        Marker(
                            location=[
                                float(store["lat"]),
                                float(store["lng"]),
                            ],
                            icon=make_flame_icon(
                                intensity
                            ),
                            tooltip=tooltip,
                            popup=folium.Popup(
                                map_popup(store),
                                max_width=320,
                            ),
                        ).add_to(marker_parent)

                    if heat_points:
                        HeatMap(
                            heat_points,
                            name="烈度熱區",
                            radius=28,
                            blur=24,
                            min_opacity=0.22,
                            show=False,
                        ).add_to(drama_map)

                        folium.LayerControl(
                            collapsed=True
                        ).add_to(drama_map)

                    if len(filtered) > 1:
                        drama_map.fit_bounds(
                            filtered[
                                ["lat", "lng"]
                            ].values.tolist(),
                            padding=(25, 25),
                        )

                    st_folium(
                        drama_map,
                        height=720,
                        use_container_width=True,
                        returned_objects=[],
                        key="drama_map_v8",
                    )

            with side_col:
                ai_cases = filtered[
                    filtered["has_ai"]
                    & filtered["intensity"].notna()
                ].copy()

                if not ai_cases.empty:
                    st.markdown("### 🔥 熱門對決")
                    render_rank(
                        ai_cases,
                        "intensity",
                        "🔥",
                        limit=8,
                    )
                else:
                    st.markdown("### 💬 回覆案例多")
                    render_rank(
                        filtered,
                        "owner_replies",
                        "則",
                        limit=8,
                    )


# ============================================================
# PAGE: Classic fights
# ============================================================

elif current_page == PAGE_CLASSIC:
    page_title("經典對決")

    if df.empty:
        st.info("目前沒有店家資料。")
    else:
        # 經典對決頁只列出至少有一則店家回覆的店家。
        options = (
            df[
                df["owner_replies"].fillna(0) > 0
            ][
                [
                    "store_id",
                    "name",
                    "district",
                    "db_review_count",
                    "owner_replies",
                ]
            ]
            .drop_duplicates("store_id")
            .sort_values(
                ["owner_replies", "db_review_count"],
                ascending=[False, False],
            )
        )

        if options.empty:
            st.info("目前沒有店家回覆案例。")
        else:
            ids = options[
                "store_id"
            ].astype(str).tolist()

            default_store_index = 0

            if requested_store in ids:
                default_store_index = ids.index(
                    requested_store
                )

            selected_id = st.selectbox(
                "選擇店家",
                ids,
                index=default_store_index,
                format_func=lambda pid: short_store_name(
                    options.loc[
                        options["store_id"].astype(str) == pid,
                        "name",
                    ].iloc[0],
                    42,
                ),
                key="classic_store_v8",
            )

            selected_store = df[
                df["store_id"].astype(str)
                == selected_id
            ].iloc[0]

            reviews = load_reviews(
                selected_id
            )

            replied_reviews = (
                reviews[
                    reviews["has_owner_reply"]
                ].copy()
                if not reviews.empty
                else pd.DataFrame()
            )

            if replied_reviews.empty:
                st.info("這家店目前沒有店家回覆案例。")
            else:
                ai_reviews = replied_reviews[
                    replied_reviews["has_ai"]
                    & replied_reviews["intensity"].notna()
                ].copy()

                # 有 AI 時只用正式分析結果排序；
                # 沒 AI 時顯示「回覆案例預覽」，不宣稱已判定成真正互嗆。
                if not ai_reviews.empty:
                    display_reviews = ai_reviews.sort_values(
                        ["intensity", "published_at"],
                        ascending=[False, False],
                        na_position="last",
                    ).reset_index(drop=True)

                    preview_mode = False
                else:
                    display_reviews = replied_reviews.sort_values(
                        "published_at",
                        ascending=False,
                        na_position="last",
                    ).reset_index(drop=True)

                    preview_mode = True

                header_left, header_right = st.columns(
                    [5, 1]
                )

                with header_left:
                    render_html(
                        f"""
                        <div style="margin:4px 0 10px;">
                            <div style="font-size:1.4rem;font-weight:950;">
                                {safe_text(short_store_name(selected_store.get("name"), 36))}
                            </div>
                            <div class="small-muted">
                                {safe_text(selected_store.get("district") or "")}
                                ｜回覆案例 {len(replied_reviews)} 則
                            </div>
                        </div>
                        """
                    )

                with header_right:
                    store_url = safe_url(
                        selected_store.get("store_url")
                    )

                    if store_url:
                        st.link_button(
                            "Google Maps",
                            store_url,
                            use_container_width=True,
                        )

                case_labels = [
                    format_case_label(
                        row,
                        index + 1,
                    )
                    for index, (_, row)
                    in enumerate(
                        display_reviews.iterrows()
                    )
                ]

                selected_case = st.selectbox(
                    "選擇案例",
                    list(range(len(display_reviews))),
                    format_func=lambda index: case_labels[index],
                    key=f"classic_case_v8_{selected_id}",
                )

                review = display_reviews.iloc[
                    int(selected_case)
                ]

                render_featured_duel(
                    selected_store,
                    review,
                    preview_mode=preview_mode,
                )

                action_left, action_right = st.columns(
                    [1, 5]
                )

                with action_left:
                    review_url = safe_url(
                        review.get("review_url")
                    )

                    if review_url:
                        st.link_button(
                            "Google Review",
                            review_url,
                            use_container_width=True,
                        )

                with action_right:
                    if not preview_mode:
                        st.caption(
                            "案例依正式 AI 烈度由高到低排列。"
                        )


# ============================================================
# PAGE: Analysis
# ============================================================

elif current_page == PAGE_ANALYSIS:
    page_title("戰況分析")

    ai_df = (
        df[df["has_ai"]].copy()
        if not df.empty
        else pd.DataFrame()
    )

    if ai_df.empty:
        st.info("目前尚無戰況分析資料。")
    else:
        review_scores = pd.to_numeric(
            ai_df["review_score"],
            errors="coerce",
        ).dropna()

        owner_scores = pd.to_numeric(
            ai_df["owner_score"],
            errors="coerce",
        ).dropna()

        intensities = pd.to_numeric(
            ai_df["intensity"],
            errors="coerce",
        ).dropna()

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "顧客平均火力",
            f"{review_scores.mean():.1f}"
            if not review_scores.empty
            else "—",
        )

        c2.metric(
            "店家平均火力",
            f"{owner_scores.mean():.1f}"
            if not owner_scores.empty
            else "—",
        )

        c3.metric(
            "平均總烈度",
            f"{intensities.mean():.1f}/20"
            if not intensities.empty
            else "—",
        )

        left, right = st.columns(2)

        with left:
            st.markdown("### 😡 顧客情緒")
            customer_sentiment = (
                ai_df["review_sentiment"]
                .replace("", "未標記")
                .value_counts()
                .rename_axis("sentiment")
                .to_frame("店家數")
            )

            st.bar_chart(
                customer_sentiment,
                height=320,
                use_container_width=True,
            )

        with right:
            st.markdown("### 🏪 店家情緒")
            owner_sentiment = (
                ai_df["owner_sentiment"]
                .replace("", "未標記")
                .value_counts()
                .rename_axis("sentiment")
                .to_frame("店家數")
            )

            st.bar_chart(
                owner_sentiment,
                height=320,
                use_container_width=True,
            )

        st.markdown("### ⚔️ 顧客 vs 店家")

        scatter = ai_df[
            [
                "name",
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
                height=430,
                use_container_width=True,
            )


# ============================================================
# PAGE: Ranking
# ============================================================

elif current_page == PAGE_RANKING:
    page_title("趣味排行")

    if df.empty:
        st.info("目前沒有排行資料。")
    else:
        ranking_options = [
            "💬 低星評論最多",
            "🏪 店家回覆率最高",
            "⭐ Google 評分最低",
        ]

        if df["has_ai"].any():
            ranking_options.append(
                "🔥 AI 烈度最高"
            )

        ranking_type = st.radio(
            "排行",
            ranking_options,
            horizontal=True,
            label_visibility="collapsed",
        )

        if ranking_type == "💬 低星評論最多":
            render_rank(
                df,
                "db_review_count",
                "則",
                limit=15,
            )

        elif ranking_type == "🏪 店家回覆率最高":
            render_rank(
                df[
                    df["db_review_count"].fillna(0) > 0
                ],
                "reply_rate",
                "",
                limit=15,
                percentage=True,
            )

        elif ranking_type == "⭐ Google 評分最低":
            render_rank(
                df,
                "google_score",
                "⭐",
                limit=15,
                ascending=True,
            )

        else:
            render_rank(
                df[
                    df["has_ai"]
                ],
                "intensity",
                "🔥",
                limit=15,
            )


# ============================================================
# PAGE: PR Rescue
# ============================================================

elif current_page == PAGE_PR:
    page_title("公關救援")

    if df.empty:
        st.info("目前沒有資料。")
    else:
        pr_cases: list[tuple[str, str, pd.Series]] = []

        for _, store in df.iterrows():
            reviews = load_reviews(
                str(store["store_id"])
            )

            if reviews.empty:
                continue

            with_pr = reviews[
                reviews["pr_reply"].str.strip().ne("")
            ]

            for _, review in with_pr.iterrows():
                pr_cases.append(
                    (
                        str(store["name"]),
                        str(store["store_id"]),
                        review,
                    )
                )

        if not pr_cases:
            st.info("目前尚無公關救援案例。")
        else:
            for store_name, _, review in pr_cases[:20]:
                render_html(
                    f"""
                    <div class="battle-card">
                        <div class="battle-name">{safe_text(store_name)}</div>

                        <div class="battle-side battle-customer">
                            <b>😡 原始評論</b><br>
                            {safe_text(review.get("review_text") or "")}
                        </div>

                        <div class="battle-side battle-owner">
                            <b>🏪 店家原回覆</b><br>
                            {safe_text(review.get("owner_reply") or "") or "（尚未回覆）"}
                        </div>

                        <div class="ai-card">
                            <b>🤖 AI 建議</b><br>
                            {safe_text(review.get("pr_reply") or "")}
                        </div>
                    </div>
                    """
                )


# ============================================================
# PAGE: Anonymous report
# ============================================================

elif current_page == PAGE_REPORT:
    page_title("匿名爆料")

    # schema.sql 沒有投稿 table，因此只做 Session 暫存。
    if "session_reports" not in st.session_state:
        st.session_state["session_reports"] = []

    with st.form(
        "anonymous_report_form",
        clear_on_submit=True,
    ):
        left, right = st.columns(2)

        with left:
            store_name = st.text_input("店家名稱 *")
            location = st.text_input("店家地點（台北市）")

        with right:
            category = st.text_input(
                "事件標籤",
                placeholder="例如：排隊、態度",
            )
            evidence_url = st.text_input(
                "公開證據網址（選填）"
            )

        description = st.text_area(
            "事件內容 *",
            height=180,
        )

        submitted = st.form_submit_button(
            "建立草稿",
            use_container_width=True,
        )

        if submitted:
            if (
                not store_name.strip()
                or not description.strip()
            ):
                st.warning(
                    "請至少填寫店家名稱與事件內容。"
                )
            else:
                st.session_state[
                    "session_reports"
                ].append(
                    {
                        "store_name": store_name.strip(),
                        "location": location.strip(),
                        "category": category.strip(),
                        "description": description.strip(),
                        "evidence_url": evidence_url.strip(),
                    }
                )

                st.success("已建立本次 Session 草稿。")

    reports = st.session_state["session_reports"]

    if reports:
        st.subheader(
            f"本次草稿（{len(reports)}）"
        )

        for index, report in enumerate(
            reports,
            start=1,
        ):
            title = (
                f"#{index} {report['store_name']}"
                + (
                    f"｜{report['category']}"
                    if report["category"]
                    else ""
                )
            )

            with st.expander(title):
                st.write(
                    report["description"]
                )

                if report["location"]:
                    st.caption(
                        f"地點：{report['location']}"
                    )

                evidence = safe_url(
                    report["evidence_url"]
                )

                if evidence:
                    st.link_button(
                        "公開證據",
                        evidence,
                    )