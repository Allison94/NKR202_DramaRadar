from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import html
import sys
from pathlib import Path
from textwrap import dedent

TIMEZONE_OPTIONS = {
    "台灣時間（台北）": "Asia/Taipei",
    "日本時間": "Asia/Tokyo",
    "UTC": "UTC",
}


def format_display_time(
    when: datetime | None = None,
    *,
    tz_name: str = "Asia/Taipei",
) -> str:
    """把時間轉成指定時區的可讀字串。"""

    moment = when or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(ZoneInfo(tz_name))
    return local.strftime("%Y-%m-%d %H:%M:%S")

import folium
import pandas as pd
import streamlit as st
import altair as alt
from folium import DivIcon, Marker
from streamlit_folium import st_folium


PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from domains.store.service import (
    get_dashboard_dataframe,
    get_store_reviews_dataframe,
)
from dashboard import charts as chart_data
from dashboard.theme import (
    cached_star_distribution,
    cached_top_intensity,
    configure_altair_theme,
    render_bar,
    render_pie,
    render_scatter,
)

configure_altair_theme()


# ============================================================
# 頁面基本設定
# ============================================================

st.set_page_config(
    page_title="Drama Radar｜台北吵架地圖",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
SPLASH_IMAGE = ASSETS_DIR / "splash.png"


# ============================================================
# HTML 顯示工具
# 這個函式會移除縮排，避免 HTML 被 Streamlit 當成程式碼
# ============================================================

def render_html(content: str, container=None) -> None:
    """
    直接渲染 HTML，不經過 Markdown 解析。

    使用 st.html() 可以避免：
    - HTML 顯示成白色程式碼框
    - 縮排被判斷成 code block
    - 開場文字顯示出 <div>
    - 排行榜與圖例無法正常排版
    """

    cleaned_html = dedent(content).strip()

    if container is None:
        st.html(cleaned_html)
    else:
        container.html(cleaned_html)


def safe_text(value: object) -> str:
    if value is None:
        return ""

    return html.escape(str(value))


# ============================================================
# 從 PostgreSQL 讀取 Dashboard 資料（domains/store/repository.py）
# 依 db/schema.sql 的 store / review / ai_analysis；範圍：台北市
# ============================================================

@st.cache_data(ttl=300, show_spinner="正在載入店家資料...")
def load_dashboard_data(limit: int = 300) -> pd.DataFrame:
    return get_dashboard_dataframe(limit=limit)


refresh_requested = st.session_state.pop(
    "database_refresh_requested",
    False,
)

df = load_dashboard_data(limit=300)
data_source = str(df.attrs.get("data_source", ""))
if not data_source and not df.empty and "__data_source" in df.columns:
    data_source = str(df["__data_source"].iloc[0])
db_error = str(df.attrs.get("error", "") or "")

if (
    "database_loaded_at_utc" not in st.session_state
    or refresh_requested
):
    st.session_state["database_loaded_at_utc"] = datetime.now(timezone.utc)

st.session_state["database_row_count"] = len(df)
st.session_state["database_data_source"] = data_source
st.session_state["database_error"] = db_error




# ============================================================
# 網站 CSS
# ============================================================

render_html(
    """
    <style>
    /* 關掉 Streamlit 右上角主題燈光 / 選單（組長：兩個燈光在做寂寞） */
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    #MainMenu,
    header [data-testid="baseButton-header"],
    div[data-testid="stToolbarActions"],
    footer {
        display: none !important;
        visibility: hidden !important;
    }

    :root {
        --drama-bg: #0b090d;
        --drama-panel: #151118;
        --drama-panel-2: #1b151d;
        --drama-border: rgba(255, 255, 255, 0.09);
        --drama-text: #fff9fc;
        --drama-muted: #a99ca4;
        --drama-red: #ff315d;
        --drama-purple: #be3cff;
    }

    .stApp {
        background: var(--drama-bg);
        color: var(--drama-text);
    }

    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(
                circle at 85% 5%,
                rgba(151, 35, 114, 0.10),
                transparent 30%
            ),
            var(--drama-bg);
    }

    [data-testid="stHeader"] {
        background: rgba(11, 9, 13, 0.94);
        border-bottom: 1px solid var(--drama-border);
    }

    .block-container {
        max-width: 1600px;
        padding-top: 4.5rem;
        padding-bottom: 2rem;
    }

    [data-testid="stSidebar"] {
        background: #141017;
        border-right: 1px solid var(--drama-border);
    }

    [data-testid="stSidebar"] * {
        color: #f9f1f5;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label {
        padding: 6px 4px;
        border-radius: 9px;
    }

    h1,
    h2,
    h3 {
        color: var(--drama-text) !important;
    }

    p,
    label,
    .stCaption {
        color: #d8cdd3;
    }

    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] > div > div {
        background: var(--drama-panel) !important;
        border-color: var(--drama-border) !important;
        color: var(--drama-text) !important;
    }

    [data-testid="stSlider"] {
        padding-top: 0;
    }

    .drama-page-title {
        margin: 0;
        color: var(--drama-text);
        font-size: clamp(1.7rem, 3vw, 2.3rem);
        font-weight: 900;
        letter-spacing: -0.04em;
    }

    .drama-page-subtitle {
        margin-top: 4px;
        color: var(--drama-muted);
        font-size: 0.88rem;
    }

    .result-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 7px 12px;
        border: 1px solid rgba(255, 49, 93, 0.32);
        border-radius: 999px;
        background: rgba(255, 49, 93, 0.08);
        color: #ff6888;
        font-size: 0.8rem;
        font-weight: 800;
        white-space: nowrap;
    }

    .legend-panel {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 18px;
        margin: 12px 0;
        padding: 10px 14px;
        border: 1px solid var(--drama-border);
        border-radius: 13px;
        background: rgba(21, 17, 24, 0.92);
    }

    .legend-label {
        color: #d8cdd3;
        font-size: 0.8rem;
        font-weight: 800;
    }

    .legend-item {
        display: inline-flex;
        align-items: flex-end;
        gap: 7px;
        color: var(--drama-muted);
        font-size: 0.76rem;
    }

    .legend-fire {
        display: inline-flex;
        align-items: flex-end;
        justify-content: center;
        line-height: 1;
        transform-origin: center bottom;
    }

    .legend-fire-small {
        font-size: 18px;
    }

    .legend-fire-medium {
        font-size: 27px;
    }

    .legend-fire-large {
        font-size: 38px;
    }

    .legend-fire-extreme {
        font-size: 49px;
    }

    iframe {
        border: 1px solid var(--drama-border) !important;
        border-radius: 15px;
        overflow: hidden;
    }

    .ranking-card {
        margin-bottom: 12px;
        padding: 15px;
        border: 1px solid var(--drama-border);
        border-radius: 15px;
        background: var(--drama-panel);
    }

    .ranking-row {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .ranking-number {
        display: flex;
        width: 34px;
        height: 34px;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        border-radius: 10px;
        background: rgba(255, 49, 93, 0.14);
        color: #ff6687;
        font-weight: 900;
    }

    .ranking-content {
        min-width: 0;
        flex: 1;
    }

    .ranking-name {
        overflow: hidden;
        color: var(--drama-text);
        font-size: 0.98rem;
        font-weight: 800;
        white-space: nowrap;
        text-overflow: ellipsis;
    }

    .ranking-meta {
        margin-top: 3px;
        color: var(--drama-muted);
        font-size: 0.77rem;
    }

    .ranking-score {
        color: #ff6687;
        font-weight: 900;
        white-space: nowrap;
    }

    .ranking-track {
        height: 8px;
        margin-top: 11px;
        overflow: hidden;
        border-radius: 999px;
        background: #332a33;
    }

    .ranking-fill {
        height: 100%;
        border-radius: 999px;
        background:
            linear-gradient(
                90deg,
                var(--drama-red),
                var(--drama-purple)
            );
    }

    .duel-card {
        min-height: 300px;
        margin-bottom: 14px;
        padding: 15px;
        border: 1px solid var(--drama-border);
        border-radius: 15px;
        background: var(--drama-panel);
    }

    .duel-title {
        color: var(--drama-text);
        font-size: 1rem;
        font-weight: 850;
    }

    .duel-meta {
        margin: 4px 0 11px;
        color: var(--drama-muted);
        font-size: 0.76rem;
    }

    .duel-message {
        margin-bottom: 9px;
        padding: 10px;
        border-radius: 10px;
        background: #211a22;
        color: #e2d8dd;
        font-size: 0.84rem;
        line-height: 1.6;
    }

    .duel-owner {
        border-left: 3px solid var(--drama-red);
        background: rgba(255, 49, 93, 0.08);
    }

    .duel-score {
        margin-top: 12px;
        color: #ff6687;
        font-weight: 900;
        text-align: right;
    }

    .stMetric {
        padding: 1rem;
        border: 1px solid var(--drama-border);
        border-radius: 14px;
        background: linear-gradient(145deg, var(--drama-panel), var(--drama-panel-2));
    }

    [data-testid="stMetricValue"] {
        color: var(--drama-text);
        font-weight: 800;
    }

    [data-testid="stMetricLabel"] {
        color: var(--drama-muted);
    }

    .chart-panel {
        margin-bottom: 0.5rem;
        padding: 0.75rem 0.9rem 0.2rem;
        border: 1px solid var(--drama-border);
        border-radius: 14px;
        background: rgba(21, 17, 24, 0.88);
    }

    div[data-testid="stVerticalBlock"] div[data-testid="stAltairChart"] {
        background: transparent;
    }

    [data-testid="stTabs"] button {
        color: #d8cdd3;
        font-weight: 700;
    }

    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #ff6687;
    }

    @media (max-width: 800px) {
        .block-container {
            padding-left: 0.8rem;
            padding-right: 0.8rem;
            padding-top: 3.5rem;
        }

        .legend-panel {
            gap: 10px;
        }

        .drama-page-title {
            font-size: 1.45rem;
        }

        [data-testid="stSidebar"] {
            min-width: 240px;
        }
    }

    .stButton > button,
    [data-testid="stFormSubmitButton"] button {
        border: 1px solid rgba(255, 49, 93, 0.34);
        border-radius: 10px;
        background:
            linear-gradient(
                90deg,
                #a81c49,
                #782078
            );
        color: white;
        font-weight: 800;
    }

    .empty-result {
        margin: 4px 0 14px 0;
        padding: 18px 20px;
        border: 3px solid #ff2d55;
        border-radius: 14px;
        background: #ff2d55;
        color: #ffffff;
        text-align: center;
        font-size: 1.2rem;
        font-weight: 900;
        letter-spacing: 0.03em;
        box-shadow: 0 0 0 4px rgba(255, 45, 85, 0.35);
    }

    .empty-result strong {
        display: block;
        margin-bottom: 6px;
        color: #fff7b0;
        font-size: 1.45rem;
        font-weight: 900;
    }

    .empty-result span {
        display: block;
        color: #ffffff;
        font-size: 1.05rem;
        font-weight: 700;
    }

    /* 首頁固定 hero（不再幾秒後消失） */
    .home-hero {
        margin: 0 0 8px 0;
        overflow: hidden;
        border: 1px solid rgba(255, 49, 93, 0.28);
        border-radius: 18px;
        background: #07050a;
    }

    .home-hero img {
        display: block;
        width: 100%;
        height: auto;
        max-height: min(78vh, 720px);
        object-fit: cover;
        object-position: center top;
    }

    .home-hero-scroll-hint {
        margin: 10px 0 18px 0;
        padding: 10px 14px;
        border-radius: 999px;
        background: rgba(255, 49, 93, 0.12);
        border: 1px solid rgba(255, 49, 93, 0.35);
        color: #ffb0c4;
        text-align: center;
        font-weight: 800;
        letter-spacing: 0.04em;
    }

    .map-section-anchor {
        scroll-margin-top: 12px;
    }

    @media (max-width: 800px) {
        .block-container {
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }

        .legend-panel {
            gap: 10px;
        }
    }
    </style>
    """
)


# ============================================================
# 火焰 Marker
# ============================================================

def flame_size(intensity: float) -> int:
    intensity = max(1.0, min(float(intensity), 10.0))
    return int(18 + intensity * 4.3)


def flame_colors(intensity: float) -> tuple[str, str, str]:
    if intensity < 4:
        return (
            "#f7ba38",
            "#fff0a5",
            "rgba(247, 186, 56, 0.40)",
        )

    if intensity < 7:
        return (
            "#ff811b",
            "#ffd05b",
            "rgba(255, 129, 27, 0.48)",
        )

    if intensity < 9:
        return (
            "#ff4338",
            "#ffad3d",
            "rgba(255, 67, 56, 0.60)",
        )

    return (
        "#e00043",
        "#ff7138",
        "rgba(224, 0, 67, 0.82)",
    )


def create_flame_icon(intensity: float) -> DivIcon:
    intensity = max(1.0, min(float(intensity), 10.0))

    size = flame_size(intensity)
    outer_color, inner_color, glow = flame_colors(intensity)

    pulse_class = "flame-pulse" if intensity >= 9 else ""

    marker_html = dedent(
        f"""
        <div
            class="drama-flame-marker {pulse_class}"
            style="
                width: {size}px;
                height: {size + 17}px;
            "
        >
            <div
                class="drama-flame-svg"
                style="
                    width: {size}px;
                    height: {size}px;
                    filter:
                        drop-shadow(
                            0 0 {max(4, size // 7)}px
                            {glow}
                        );
                "
            >
                <svg
                    width="{size}"
                    height="{size}"
                    viewBox="0 0 64 64"
                    xmlns="http://www.w3.org/2000/svg"
                >
                    <path
                        d="
                            M34 3
                            C37 13 31 17 38 25
                            C41 20 45 16 45 10
                            C55 21 60 31 57 43
                            C54 55 45 62 32 62
                            C18 62 8 53 7 41
                            C6 31 12 23 20 17
                            C19 26 24 29 27 23
                            C31 16 27 10 34 3
                            Z
                        "
                        fill="{outer_color}"
                    />

                    <path
                        d="
                            M33 28
                            C38 34 43 38 42 46
                            C41 54 36 58 30 58
                            C23 58 18 53 19 46
                            C20 40 25 37 28 32
                            C29 37 32 39 34 36
                            C36 33 34 30 33 28
                            Z
                        "
                        fill="{inner_color}"
                    />
                </svg>
            </div>

            <div class="drama-flame-score">
                {intensity:.1f}
            </div>
        </div>
        """
    ).strip()

    return DivIcon(
        html=marker_html,
        icon_size=(size, size + 17),
        icon_anchor=(size // 2, size + 7),
        popup_anchor=(0, -size),
        class_name="drama-flame-div-icon",
    )


def add_map_marker_styles(drama_map: folium.Map) -> None:
    marker_css = """
    <style>
    .drama-flame-div-icon {
        background: transparent !important;
        border: none !important;
    }

    .drama-flame-marker {
        position: relative;
        display: flex;
        justify-content: center;
        cursor: pointer;
        transform-origin: center bottom;
        transition: transform 0.18s ease;
    }

    .drama-flame-marker:hover {
        z-index: 9999 !important;
        transform: scale(1.18);
    }

    .drama-flame-svg {
        display: flex;
        align-items: center;
        justify-content: center;
        transform-origin: center bottom;
    }

    .drama-flame-score {
        position: absolute;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        min-width: 27px;
        padding: 1px 5px;
        border: 1px solid rgba(255, 255, 255, 0.30);
        border-radius: 999px;
        background: rgba(18, 13, 18, 0.91);
        color: white;
        font-family: Arial, sans-serif;
        font-size: 10px;
        font-weight: 800;
        line-height: 14px;
        text-align: center;
    }

    @keyframes dramaPulse {
        0% {
            transform: scale(1);
        }

        50% {
            transform: scale(1.11);
        }

        100% {
            transform: scale(1);
        }
    }

    .flame-pulse .drama-flame-svg {
        animation:
            dramaPulse
            1.15s
            ease-in-out
            infinite;
    }

    .flame-pulse:hover .drama-flame-svg {
        animation-play-state: paused;
    }
    </style>
    """

    drama_map.get_root().header.add_child(
        folium.Element(marker_css)
    )


# ============================================================
# Popup 資訊卡（精簡：不塞全文，連到站內評論清單）
# ============================================================

PAGE_SHOWDOWN = "⚔️ 精選對決"
PAGE_OPTIONS = [
    "🗺️ 吵架地圖",
    "🏆 趣味排行榜",
    "📊 數據分析",
    PAGE_SHOWDOWN,
    "🎭 匿名爆料",
]


def create_popup_html(row: pd.Series) -> str:
    """地圖點擊只秀摘要 +「看更多留言」連到精選對決（用 store_id）。"""

    place_id = html.escape(str(row.get("store_id") or "").strip(), quote=True)
    more_href = f"?page=showdown&store_id={place_id}"

    return dedent(
        f"""
        <div
            style="
                width: 240px;
                padding: 6px;
                font-family:
                    Arial,
                    'Microsoft JhengHei',
                    sans-serif;
            "
        >
            <div
                style="
                    margin-bottom: 5px;
                    color: #21161e;
                    font-size: 16px;
                    font-weight: 800;
                "
            >
                {safe_text(row["name"])}
            </div>

            <div
                style="
                    margin-bottom: 8px;
                    color: #74666e;
                    font-size: 12px;
                "
            >
                📍 {safe_text(row.get("address") or (str(row.get("city", "")) + str(row.get("district", ""))))}
                ・{safe_text(row["category"])}
            </div>

            <div
                style="
                    display: inline-block;
                    margin-bottom: 10px;
                    padding: 4px 9px;
                    border-radius: 999px;
                    background: #ffe7ed;
                    color: #d71952;
                    font-size: 13px;
                    font-weight: 800;
                "
            >
                烈度 {float(row["intensity"]):.1f} / 10
                ・{int(row.get("db_review_count") or 0)} 則評論
            </div>

            <div style="margin-bottom: 10px; color: #40353b; font-size: 12px;">
                客人 {float(row.get("guest_score") or 0):.0f}
                ・老闆 {float(row.get("owner_score") or 0):.0f}
            </div>

            <a
                href="{more_href}"
                target="_top"
                style="
                    display: inline-block;
                    padding: 8px 12px;
                    border-radius: 8px;
                    background: #e3245b;
                    color: #fff;
                    font-size: 13px;
                    font-weight: 800;
                    text-decoration: none;
                "
            >
                看更多留言 →
            </a>
        </div>
        """
    ).strip()


# ============================================================
# 資料篩選
# ============================================================

def filter_data(
    source_df: pd.DataFrame,
    keyword: str,
    city: str,
    district: str,
    reason: str,
    minimum_intensity: float,
) -> pd.DataFrame:
    result = source_df.copy()

    clean_keyword = keyword.strip()

    if clean_keyword:
        search_columns = [
            "name",
            "city",
            "district",
            "category",
            "reason",
            "persona",
        ]

        mask = pd.Series(
            False,
            index=result.index,
        )

        for column in search_columns:
            mask = mask | result[column].str.contains(
                clean_keyword,
                case=False,
                na=False,
            )

        result = result[mask]

    if city != "全部":
        result = result[result["city"] == city]

    if district != "全部":
        result = result[
            result["district"] == district
        ]

    if reason != "全部":
        result = result[result["reason"] == reason]

    result = result[
        result["intensity"] >= minimum_intensity
    ]

    return result


# ============================================================
# 側邊欄
# ============================================================

# 地圖「看更多留言」→ ?page=showdown&store_id=<placeId>
# 用 token 避免選單切走後被 query string 強制拉回
_qp_page = str(st.query_params.get("page") or "").strip().lower()
_qp_store = str(st.query_params.get("store_id") or "").strip()
_deep_link_token = f"{_qp_page}:{_qp_store}"
if _qp_page == "showdown" and _qp_store:
    if st.session_state.get("_last_deep_link") != _deep_link_token:
        st.session_state["nav_page"] = PAGE_SHOWDOWN
        st.session_state["showdown_store_select"] = _qp_store
        st.session_state["_last_deep_link"] = _deep_link_token

with st.sidebar:
    st.markdown("## 🔥 Drama Radar")
    st.caption("台北市吵架地圖")

    st.divider()

    current_page = st.radio(
        "功能選單",
        PAGE_OPTIONS,
        key="nav_page",
        label_visibility="collapsed",
    )

    st.divider()

    st.caption("範圍")
    st.write("台北市")

    tz_label = st.selectbox(
        "時間顯示",
        list(TIMEZONE_OPTIONS.keys()),
        index=0,
        key="display_timezone_label",
        help="預設台灣時間；可改成其他時區。",
    )
    tz_name = TIMEZONE_OPTIONS[tz_label]
    loaded_utc = st.session_state.get("database_loaded_at_utc")
    if isinstance(loaded_utc, datetime):
        last_loaded_at = (
            f"{format_display_time(loaded_utc, tz_name=tz_name)}（{tz_label}）"
        )
    else:
        last_loaded_at = "尚未更新"

    database_row_count = st.session_state.get(
        "database_row_count",
        0,
    )
    data_source = st.session_state.get("database_data_source", "")
    db_error = st.session_state.get("database_error", "")

    if data_source == "database" and database_row_count > 0:
        st.success(
            f"目前抓到 {database_row_count} 家店\n\n"
            f"更新時間：{last_loaded_at}"
        )
    elif data_source == "database_empty":
        st.warning(
            "資料庫裡還沒有台北市的店家資料。\n\n"
            f"上次檢查：{last_loaded_at}"
        )
    else:
        st.error(
            "連不上資料庫，暫時沒辦法載入店家。\n\n"
            f"{db_error or '請確認資料庫有開著。'}"
        )

    if st.session_state.pop(
        "database_refresh_message",
        False,
    ):
        st.info(f"已更新，現在有 {database_row_count} 家店。")

    if st.button(
        "重新整理資料",
        use_container_width=True,
    ):
        st.cache_data.clear()
        st.session_state["database_refresh_requested"] = True
        st.session_state["database_refresh_message"] = True
        st.rerun()


# ============================================================
# 分頁：吵架地圖
# ============================================================

if current_page == "🗺️ 吵架地圖":
    # 首頁固定海報；往下捲才是地圖（不再幾秒後消失）
    if SPLASH_IMAGE.exists():
        st.image(str(SPLASH_IMAGE), use_container_width=True)
        render_html(
            """
            <div class="home-hero-scroll-hint">
                ↓ 往下滑看台北吵架地圖
            </div>
            """
        )
    else:
        st.warning("找不到首頁圖 `dashboard/assets/splash.png`")

    header_left, header_right = st.columns(
        [5, 1],
        vertical_alignment="center",
    )

    with header_left:
        render_html(
            """
            <div class="drama-page-title">
                台北吵架地圖
            </div>

            <div class="drama-page-subtitle">
                火焰越大，評論與店家回覆越激烈。點火焰看摘要，再連到評論清單。
            </div>
            """
        )

    if df.empty:
        st.error(
            db_error
            or "目前沒有可顯示的台北市店家，先確認資料庫有資料再重新整理。"
        )
        st.stop()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("收錄店家", f"{len(df)} 家")
    with kpi2:
        st.metric("平均烈度", f"{float(df['intensity'].mean()):.1f}")
    with kpi3:
        hot_count = int((df["intensity"] >= 7).sum())
        st.metric("高烈度店家", f"{hot_count} 家")
    with kpi4:
        st.metric("有回覆店家", f"{int((df['owner_replies'] > 0).sum())} 家")

    search_column, city_column, district_column = st.columns(
        [2.2, 1, 1]
    )

    with search_column:
        keyword = st.text_input(
            "搜尋店家",
            placeholder="搜尋店家、行政區、餐飲類型或糾紛原因",
        )

    with city_column:
        selected_city = st.selectbox(
            "縣市",
            ["全部", "台北市"],
        )

    district_source = df.copy()

    if selected_city != "全部":
        district_source = district_source[
            district_source["city"] == selected_city
        ]

    district_options = [
        "全部",
        *sorted(
            district_source["district"]
            .dropna()
            .unique()
            .tolist()
        ),
    ]

    with district_column:
        selected_district = st.selectbox(
            "行政區",
            district_options,
        )

    reason_column, intensity_column = st.columns([1, 2])

    with reason_column:
        selected_reason = st.selectbox(
            "糾紛類型",
            [
                "全部",
                *sorted(
                    df["reason"]
                    .dropna()
                    .unique()
                    .tolist()
                ),
            ],
        )

    with intensity_column:
        minimum_intensity = st.slider(
            "最低烈度",
            min_value=1.0,
            max_value=10.0,
            value=1.0,
            step=0.5,
            help="向右拖動，只顯示烈度較高的店家。",
        )

    filtered_df = filter_data(
        source_df=df,
        keyword=keyword,
        city=selected_city,
        district=selected_district,
        reason=selected_reason,
        minimum_intensity=minimum_intensity,
    )
    with header_right:
        render_html(
            f"""
            <div class="result-badge">
                顯示 {len(filtered_df)} 家店
            </div>
            """
        )

    # 搜不到：緊接在篩選下方（地圖上方箭頭處），紅底黃字很明顯
    if filtered_df.empty:
        render_html(
            f"""
            <div class="empty-result">
                <strong>⚠ 找不到符合條件的店家</strong>
                <span>
                    關鍵字「{safe_text(keyword) or "（空白）"}」沒有結果。
                    請清除搜尋、改行政區，或把最低烈度往左調。
                </span>
            </div>
            """
        )
        st.error(
            "找不到符合條件的店家 — 請清除上方篩選後再試。"
        )
    else:
        # 注意：這段使用 render_html，不會再顯示成 HTML 程式碼
        render_html(
            """
            <div class="legend-panel">
                <span class="legend-label">
                    烈度
                </span>

                <span class="legend-item">
                    <span class="legend-fire legend-fire-small">
                        🔥
                    </span>
                    1～3
                </span>

                <span class="legend-item">
                    <span class="legend-fire legend-fire-medium">
                        🔥
                    </span>
                    4～6
                </span>

                <span class="legend-item">
                    <span class="legend-fire legend-fire-large">
                        🔥
                    </span>
                    7～8
                </span>

                <span class="legend-item">
                    <span class="legend-fire legend-fire-extreme">
                        🔥
                    </span>
                    9～10
                </span>
            </div>
            """
        )

        drama_map = folium.Map(
            location=[25.065, 121.52],
            zoom_start=11,
            control_scale=True,
            tiles=None,
            prefer_canvas=False,
        )

        folium.TileLayer(
            tiles="CartoDB positron",
            name="地圖",
            control=False,
        ).add_to(drama_map)

        add_map_marker_styles(drama_map)

        for _, store in filtered_df.iterrows():
            intensity = float(store["intensity"])

            Marker(
                location=[
                    float(store["lat"]),
                    float(store["lng"]),
                ],
                icon=create_flame_icon(intensity),
                tooltip=(
                    f"{store['name']}｜"
                    f"烈度 {intensity:.1f}"
                ),
                popup=folium.Popup(
                    create_popup_html(store),
                    max_width=280,
                ),
            ).add_to(drama_map)

        if len(filtered_df) >= 2:
            points = filtered_df[
                ["lat", "lng"]
            ].values.tolist()

            drama_map.fit_bounds(
                points,
                padding=(35, 35),
            )

        st_folium(
            drama_map,
            height=680,
            use_container_width=True,
            returned_objects=[],
            key="drama_main_map",
        )


# ============================================================
# 分頁：趣味排行榜
# ============================================================

elif current_page == "🏆 趣味排行榜":
    st.title("趣味排行榜")
    st.caption("同一頁看多個榜・直條圖・點店名看評論（沒有下拉選單）")

    if df.empty:
        st.error(db_error or "目前沒有可排行的店家資料。")
        st.stop()

    def _rank_chart(
        ranking_frame: pd.DataFrame,
        value_col: str,
        *,
        title: str,
        value_title: str,
        color: str,
    ) -> pd.DataFrame:
        """直條圖：X 軸只用 1 2 3，店名絕不畫在軸上（避免直立難讀）。"""

        plot_df = (
            ranking_frame.head(8)
            .copy()
            .reset_index(drop=True)
        )
        if plot_df.empty:
            st.info(f"{title} 尚無資料")
            return plot_df

        plot_df["rank_no"] = list(range(1, len(plot_df) + 1))
        plot_df["score"] = pd.to_numeric(
            plot_df[value_col], errors="coerce"
        ).fillna(0)

        # 用 Streamlit 原生直條圖，軸上只有數字，不會把中文轉直立
        chart_data = (
            plot_df[["rank_no", "score"]]
            .rename(columns={"rank_no": "名次", "score": value_title})
            .set_index("名次")
        )
        st.bar_chart(
            chart_data,
            color=color,
            height=260,
            use_container_width=True,
        )
        return plot_df

    def _rank_store_list(
        plot_df: pd.DataFrame,
        *,
        board_key: str,
        score_suffix: str,
        use_float: bool,
    ) -> None:
        """店名用一般橫排文字列出，點了右邊就開評論。"""

        if plot_df.empty:
            return

        for row in plot_df.itertuples():
            score_text = (
                f"{float(row.score):.1f}{score_suffix}"
                if use_float
                else f"{int(row.score)}{score_suffix}"
            )
            left, right = st.columns([4, 1])
            with left:
                st.markdown(
                    f"**第 {row.rank_no} 名　{row.name}**　"
                    f"<span style='color:#ff9db4'>{score_text}</span>",
                    unsafe_allow_html=True,
                )
            with right:
                if st.button(
                    "看評論",
                    key=f"rank_pick_{board_key}_{row.store_id}",
                    use_container_width=True,
                ):
                    st.session_state["ranking_selected_place"] = str(
                        row.store_id
                    )
                    st.session_state["ranking_selected_name"] = str(row.name)

    sarcastic = df[
        df["guest_persona"].astype(str).str.contains(
            "反串|酸|憤怒|客訴",
            na=False,
        )
        | df["persona"].astype(str).str.contains(
            "反串|酸|憤怒|防禦",
            na=False,
        )
    ]
    if sarcastic.empty:
        sarcastic = df.sort_values("intensity", ascending=False)

    boards = [
        (
            "🔥 十大暴躁老闆",
            "依吵架烈度排序",
            df.sort_values(
                ["intensity", "owner_replies"],
                ascending=[False, False],
            ),
            "intensity",
            "分",
            True,
            "#ff315d",
            "boss",
        ),
        (
            "🤡 全台北最會酸",
            "依客人／老闆嗆度排序",
            sarcastic.sort_values("intensity", ascending=False),
            "intensity",
            "分",
            True,
            "#be3cff",
            "sarcasm",
        ),
        (
            "💬 店家回覆王",
            "依老闆回覆則數排序",
            df.sort_values("owner_replies", ascending=False),
            "owner_replies",
            "則",
            False,
            "#ff811b",
            "reply",
        ),
        (
            "⭐ 一星評論王",
            "依資料庫評論則數排序",
            df.sort_values("db_review_count", ascending=False),
            "db_review_count",
            "則",
            False,
            "#f7ba38",
            "onestar",
        ),
    ]

    boards_col, review_col = st.columns([1.35, 1], gap="large")

    with boards_col:
        for title, subtitle, frame, score_col, suffix, use_float, color, key in boards:
            with st.container(border=True):
                st.markdown(f"### {title}")
                st.caption(subtitle)
                plot_df = _rank_chart(
                    frame,
                    score_col,
                    title="",
                    value_title=suffix,
                    color=color,
                )
                _rank_store_list(
                    plot_df,
                    board_key=key,
                    score_suffix=suffix,
                    use_float=use_float,
                )

        with st.container(border=True):
            st.markdown("### 🏘️ 行政區戰力榜")
            st.caption("各行政區平均烈度")
            district_ranking = (
                df.groupby("district", as_index=False)
                .agg(
                    average_intensity=("intensity", "mean"),
                    store_count=("store_id", "count"),
                )
                .sort_values("average_intensity", ascending=False)
                .reset_index(drop=True)
            )
            if district_ranking.empty:
                st.info("尚無行政區資料")
            else:
                district_ranking["rank_no"] = list(
                    range(1, len(district_ranking) + 1)
                )
                district_ranking["score"] = district_ranking[
                    "average_intensity"
                ]
                st.bar_chart(
                    district_ranking[["rank_no", "score"]]
                    .rename(columns={"rank_no": "名次", "score": "平均烈度"})
                    .set_index("名次"),
                    color="#e00043",
                    height=240,
                    use_container_width=True,
                )
                for row in district_ranking.itertuples():
                    st.markdown(
                        f"**第 {row.rank_no} 名　{row.district}**　"
                        f"平均烈度 {float(row.score):.1f}　"
                        f"（{int(row.store_count)} 家）"
                    )

    with review_col:
        st.markdown("### 💬 店家評論")
        st.caption("點左邊「看評論」後，內容會顯示在這裡")
        selected_place = st.session_state.get("ranking_selected_place")
        selected_name = st.session_state.get("ranking_selected_name", "")

        if not selected_place:
            st.info("還沒選店家。請點左邊任一間的「看評論」。")
        else:
            st.success(f"目前查看：{selected_name}")
            reviews_df = get_store_reviews_dataframe(
                str(selected_place),
                limit=30,
            )
            if reviews_df.empty:
                st.warning("這家店在資料庫還沒有評論。")
            else:
                st.caption(f"共 {len(reviews_df)} 則")
                for _, rev in reviews_df.iterrows():
                    with st.container(border=True):
                        st.markdown(
                            f"**顧客：** "
                            f"{rev.get('review_text') or '（無文字）'}"
                        )
                        st.markdown(
                            f"**老闆：** "
                            f"{rev.get('owner_reply') or '（尚未回覆）'}"
                        )
                        pr_text = str(rev.get("pr_reply") or "").strip()
                        if pr_text:
                            st.markdown(f"**AI 公關範例：** {pr_text}")
                        review_url = str(
                            rev.get("review_url") or ""
                        ).strip()
                        if review_url:
                            st.markdown(f"[看原始評論]({review_url})")


# ============================================================
# 分頁：數據分析
# ============================================================

elif current_page == "📊 數據分析":
    st.title("數據分析")
    st.caption("用圖表快速看台北市吵架分布。")

    if df.empty:
        st.error(db_error or "目前沒有可分析的店家資料。")
        st.stop()

    metric_columns = st.columns(4)
    with metric_columns[0]:
        st.metric("收錄店家", f"{len(df)} 家")
    with metric_columns[1]:
        # 用 DB review 筆數，不是 Google reviewsCount（會變成幾千）
        st.metric(
            "DB 評論數",
            f"{int(df['db_review_count'].sum())} 則",
        )
    with metric_columns[2]:
        st.metric("店家回覆", f"{int(df['owner_replies'].sum())} 則")
    with metric_columns[3]:
        st.metric("平均烈度", f"{float(df['intensity'].mean()):.1f}")

    tab_overview, tab_region, tab_review = st.tabs(
        ["📌 概況", "🗺️ 地區", "💬 評論"]
    )

    with tab_overview:
        c1, c2 = st.columns(2)
        with c1:
            render_pie(
                chart_data.reason_chart_data(df),
                "糾紛類型",
                "店家數",
                title="糾紛類型分布",
            )
        with c2:
            render_bar(
                chart_data.intensity_bucket_data(df),
                "烈度區間",
                "店家數",
                title="烈度分級分布",
                color="#ff811b",
            )

        render_bar(
            chart_data.persona_chart_data(df),
            "店家人設",
            "店家數",
            title="店家人設分布",
            horizontal=False,
            color="#be3cff",
        )

    with tab_region:
        c1, c2 = st.columns(2)
        with c1:
            render_bar(
                chart_data.district_chart_data(df),
                "地區",
                "平均烈度",
                title="行政區平均烈度",
                horizontal=False,
                color="#ff6687",
            )
        with c2:
            top_df = cached_top_intensity(limit=10)
            if top_df.empty:
                st.info("十大高烈度店家尚無資料。")
            else:
                render_bar(
                    top_df,
                    "店家",
                    "烈度",
                    title="十大高烈度店家",
                    horizontal=False,
                    color="#e00043",
                )

    with tab_review:
        c1, c2 = st.columns(2)
        with c1:
            render_bar(
                cached_star_distribution(),
                "星等",
                "評論數",
                title="評論星等分布（review 表）",
                color="#f7ba38",
            )
        with c2:
            render_scatter(
                chart_data.scatter_intensity_reviews(df),
                title="烈度 vs 評論數",
            )

    with st.expander("查看行政區聚合表格"):
        st.dataframe(
            chart_data.district_chart_data(df)[["地區", "平均烈度", "店家數"]],
            hide_index=True,
            use_container_width=True,
        )


# ============================================================
# 分頁：精選對決
# ============================================================

elif current_page == PAGE_SHOWDOWN:
    st.title("店家評論清單")
    st.caption("用店家 ID（placeId）切換；地圖「看更多留言」會帶 store_id 過來。")

    if df.empty:
        st.error(db_error or "目前沒有可對決的店家資料。")
        st.stop()

    # 一店一列，避免選單重複
    store_frame = (
        df.drop_duplicates(subset=["store_id"])
        .sort_values("intensity", ascending=False)
        .reset_index(drop=True)
    )
    store_ids = store_frame["store_id"].astype(str).tolist()
    # 地圖連結帶進來的 store_id 優先
    preset = str(st.session_state.get("showdown_store_select") or "").strip()
    if preset and preset in store_ids:
        st.session_state["showdown_store_select"] = preset
    elif store_ids and st.session_state.get("showdown_store_select") not in store_ids:
        st.session_state["showdown_store_select"] = store_ids[0]

    selected_place_id = st.selectbox(
        "選店家（依 placeId）",
        options=store_ids,
        format_func=lambda pid: (
            f"{store_frame.loc[store_frame['store_id'].astype(str) == pid, 'name'].iloc[0]}"
            f"｜{pid}"
            f"（DB {int(store_frame.loc[store_frame['store_id'].astype(str) == pid, 'db_review_count'].iloc[0])} 則）"
        ),
        key="showdown_store_select",
    )
    # 同步網址，方便複製 / 地圖連進來
    st.query_params["page"] = "showdown"
    st.query_params["store_id"] = str(selected_place_id)

    store_row = store_frame[
        store_frame["store_id"].astype(str) == str(selected_place_id)
    ].iloc[0]
    st.caption(f"目前店家 ID：`{selected_place_id}`")

    st.subheader("店家資訊")
    info_cols = st.columns(4)
    info_cols[0].metric("烈度", f"{float(store_row['intensity']):.1f}")
    info_cols[1].metric("客人評分", f"{float(store_row.get('guest_score') or 0):.0f}")
    info_cols[2].metric("老闆評分", f"{float(store_row.get('owner_score') or 0):.0f}")
    info_cols[3].metric("DB 評論數", f"{int(store_row.get('db_review_count') or 0)}")

    st.write(f"**地址：** {store_row.get('address') or '（沒有地址）'}")
    st.write(
        f"**客人人設：** {store_row.get('guest_persona') or '尚無'}　"
        f"**老闆人設：** {store_row.get('owner_persona') or store_row.get('persona') or '尚無'}"
    )
    review_url_one = str(store_row.get("review_url") or "").strip()
    if review_url_one:
        st.markdown(f"[看原始評論]({review_url_one})")

    st.subheader(f"評論原文（僅 {store_row['name']}）")
    reviews_df = get_store_reviews_dataframe(str(selected_place_id), limit=50)
    if not reviews_df.empty and "place_id" in reviews_df.columns:
        reviews_df = reviews_df[
            reviews_df["place_id"].astype(str) == str(selected_place_id)
        ]
    if reviews_df.empty:
        st.warning("這家店目前沒有抓到評論。")
    else:
        st.caption(f"這家店一共 {len(reviews_df)} 則（已依 placeId 篩選）")
        for _, rev in reviews_df.iterrows():
            with st.container(border=True):
                top = st.columns([1, 1, 2])
                top[0].write(f"**星等：** {int(rev.get('stars') or 0)}★")
                top[1].write(
                    f"**客人 {float(rev.get('guest_score') or 0):.0f}** "
                    f"/ {rev.get('guest_persona') or '尚無'}"
                )
                top[2].write(
                    f"**老闆 {float(rev.get('owner_score') or 0):.0f}** "
                    f"/ {rev.get('owner_persona') or '尚無'}"
                )
                st.write("**顧客怎麼說：**")
                st.write(str(rev.get("review_text") or "（沒有內容）"))
                owner_text = str(rev.get("owner_reply") or "").strip()
                st.write("**老闆怎麼回：**")
                st.write(owner_text if owner_text else "（還沒回）")
                # AI 公關範例只掛在留言區（地圖 popup / 這裡），沒有獨立頁
                pr_text = str(rev.get("pr_reply") or "").strip()
                st.write("**AI 公關範例：**")
                st.info(pr_text if pr_text else "（還沒有公關範例）")
                review_url = str(rev.get("review_url") or "").strip()
                if review_url:
                    st.markdown(f"[看原始評論]({review_url})")


# ============================================================
# 分頁：匿名爆料
# ============================================================

elif current_page == "🎭 匿名爆料":
    st.title("匿名爆料")

    st.caption(
        "投稿內容需經過審核後才會公開。"
    )

    with st.form("anonymous_report_form"):
        report_store_name = st.text_input(
            "店家名稱"
        )

        report_location = st.text_input(
            "店家地點"
        )

        report_category = st.selectbox(
            "事件類型",
            [
                "態度",
                "價格",
                "排隊",
                "品質",
                "份量",
                "新聞事件",
                "其他",
            ],
        )

        report_description = st.text_area(
            "事件內容",
            height=180,
        )

        report_url = st.text_input(
            "Google Maps、新聞或其他證據網址（選填）"
        )

        submitted = st.form_submit_button(
            "送出爆料",
            use_container_width=True,
        )

        if submitted:
            if (
                not report_store_name.strip()
                or not report_description.strip()
            ):
                st.warning(
                    "請至少填寫店家名稱與事件內容。"
                )
            else:
                st.success(
                    "展示版本已收到投稿。"
                    "之後會接上資料庫與審核機制。"
                )