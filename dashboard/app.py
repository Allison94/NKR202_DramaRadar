from __future__ import annotations
from datetime import datetime

import html
import sys
import time
from pathlib import Path
from textwrap import dedent

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
    get_pr_reply_examples,
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
# 開場動畫
# 不使用 st.progress，避免出現看起來像兩條的進度條
# ============================================================

def show_splash_screen() -> None:
    if st.session_state.get("splash_finished", False):
        return

    render_html(
        """
        <style>
        [data-testid="stSidebar"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        #MainMenu,
        footer {
            display: none !important;
        }

        .stApp {
            background: #07050a;
        }

        .block-container {
            max-width: 1400px !important;
            padding: 0.5rem 1rem 1rem !important;
        }

        [data-testid="stImage"] {
            display: flex;
            justify-content: center;
        }

        [data-testid="stImage"] img {
            width: 100%;
            max-width: 1120px;
            max-height: 78vh;
            object-fit: contain;
            object-position: center;
        }

        .splash-progress-wrap {
            width: min(720px, 82vw);
            margin: 16px auto 0;
        }

        .splash-progress-track {
            width: 100%;
            height: 14px;
            padding: 2px;
            overflow: hidden;
            border: 1px solid #d93eff;
            border-radius: 999px;
            background: #211525;
            box-sizing: border-box;
        }

        .splash-progress-fill {
            height: 100%;
            border-radius: 999px;
            background:
                linear-gradient(
                    90deg,
                    #ff315d 0%,
                    #b53cff 55%,
                    #ef4cff 100%
                );
            transition: width 0.05s linear;
        }

        .splash-loading-text {
            margin-top: 16px;
            color: #e34cff;
            text-align: center;
            font-size: clamp(15px, 2vw, 20px);
            font-weight: 800;
            letter-spacing: 0.04em;
        }

        @media (max-width: 700px) {
            [data-testid="stImage"] img {
                max-height: 68vh;
            }

            .block-container {
                padding-left: 0.3rem !important;
                padding-right: 0.3rem !important;
            }
        }
        </style>
        """
    )

    if not SPLASH_IMAGE.exists():
        st.error(
            "找不到開場圖片，請確認檔案位於："
            "`dashboard/assets/splash.png`"
        )
        st.stop()

    st.image(
        str(SPLASH_IMAGE),
        width="stretch",
    )

    skip_col, progress_col = st.columns([1, 4])
    with skip_col:
        if st.button("跳過開場", use_container_width=True):
            st.session_state["splash_finished"] = True
            st.rerun()

    progress_placeholder = progress_col.empty()

    for progress in range(0, 101, 2):
        render_html(
            f"""
            <div class="splash-progress-wrap">
                <div class="splash-progress-track">
                    <div
                        class="splash-progress-fill"
                        style="width: {progress}%"
                    ></div>
                </div>

                <div class="splash-loading-text">
                    正在搜尋台北吵架戰場...
                </div>
            </div>
            """,
            container=progress_placeholder,
        )

        time.sleep(0.025)

    st.session_state["splash_finished"] = True
    st.rerun()


show_splash_screen()


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
    "database_last_loaded_at" not in st.session_state
    or refresh_requested
):
    st.session_state["database_last_loaded_at"] = (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

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
        margin-top: 12px;
        padding: 16px;
        border: 1px dashed rgba(255, 255, 255, 0.16);
        border-radius: 13px;
        color: var(--drama-muted);
        text-align: center;
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
# Popup 資訊卡
# ============================================================

def create_popup_html(row: pd.Series) -> str:
    return dedent(
        f"""
        <div
            style="
                width: 270px;
                padding: 5px;
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
                    font-size: 17px;
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
                    margin-bottom: 9px;
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

            <div style="margin-bottom: 4px; color: #40353b; font-size: 12px;">
                <strong>客人：</strong>
                {float(row.get("guest_score") or 0):.0f} 分
                ・{safe_text(row.get("guest_persona") or "尚無人設")}
            </div>

            <div style="margin-bottom: 9px; color: #40353b; font-size: 12px;">
                <strong>老闆：</strong>
                {float(row.get("owner_score") or 0):.0f} 分
                ・{safe_text(row.get("owner_persona") or row.get("persona") or "尚無人設")}
            </div>

            <div
                style="
                    margin-bottom: 7px;
                    padding: 8px;
                    border-radius: 8px;
                    background: #f4f0f2;
                    color: #40353b;
                    font-size: 12px;
                    line-height: 1.55;
                "
            >
                <strong>顧客怎麼說：</strong><br>
                {safe_text(row["review_text"])}
            </div>

            <div
                style="
                    margin-bottom: 7px;
                    padding: 8px;
                    border-left: 3px solid #e3245b;
                    border-radius: 8px;
                    background: #fff0f4;
                    color: #40353b;
                    font-size: 12px;
                    line-height: 1.55;
                "
            >
                <strong>老闆怎麼回：</strong><br>
                {safe_text(row["owner_reply"])}
            </div>

            <div
                style="
                    margin-bottom: 7px;
                    padding: 8px;
                    border-left: 3px solid #2f6fed;
                    border-radius: 8px;
                    background: #eef4ff;
                    color: #40353b;
                    font-size: 12px;
                    line-height: 1.55;
                "
            >
                <strong>AI 公關範例：</strong><br>
                {safe_text(str(row.get("pr_reply") or "").strip() or "（還沒有公關範例）")}
            </div>

            <div style="margin-top: 8px; font-size: 11px; line-height: 1.6;">
                {"<a href='" + html.escape(str(row.get("store_url") or ""), quote=True) + "' target='_blank' rel='noopener'>看店家地圖</a>" if row.get("store_url") else "尚無店家連結"}
                ・
                {"<a href='" + html.escape(str(row.get("review_url") or ""), quote=True) + "' target='_blank' rel='noopener'>看原始評論</a>" if row.get("review_url") else "尚無評論連結"}
            </div>
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

with st.sidebar:
    st.markdown("## 🔥 Drama Radar")
    st.caption("台北市吵架地圖")

    st.divider()

    current_page = st.radio(
        "功能選單",
        [
            "🗺️ 吵架地圖",
            "🏆 趣味排行榜",
            "📊 數據分析",
            "⚔️ 精選對決",
            "💬 公關回覆教室",
            "🎭 匿名爆料",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    st.caption("範圍")
    st.write("台北市")

    last_loaded_at = st.session_state.get(
        "database_last_loaded_at",
        "尚未更新",
    )
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
        "重新播放開場",
        use_container_width=True,
    ):
        st.session_state["splash_finished"] = False
        st.rerun()

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
                火焰越大，代表這家店吵得越兇。點標記可看評論與老闆回覆。
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
                max_width=310,
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

    if filtered_df.empty:
        render_html(
            """
            <div class="empty-result">
                找不到符合條件的店家，
                請清除部分篩選或降低最低烈度。
            </div>
            """
        )


# ============================================================
# 分頁：趣味排行榜
# ============================================================

elif current_page == "🏆 趣味排行榜":
    st.title("趣味排行榜")

    st.caption("看看誰最兇、誰最會回、哪個區最熱鬧。")

    if df.empty:
        st.error(db_error or "目前沒有可排行的店家資料。")
        st.stop()

    ranking_type = st.selectbox(
        "選擇排行榜",
        [
            "🔥 十大暴躁老闆",
            "🤡 全台北最會酸",
            "💬 店家回覆王",
            "⭐ 一星評論王",
            "🏘️ 行政區戰力榜",
        ],
    )

    def _render_ranking_bar_chart(
        ranking_frame: pd.DataFrame,
        label_col: str,
        value_col: str,
        *,
        title: str,
        suffix: str,
    ) -> None:
        if ranking_frame.empty:
            return

        plot_df = ranking_frame.head(10).copy()
        plot_df["display"] = plot_df[label_col].astype(str)
        if suffix.strip() == "分":
            plot_df["數值"] = plot_df[value_col].astype(float)
        else:
            plot_df["數值"] = plot_df[value_col].astype(int)

        chart = (
            alt.Chart(plot_df)
            .mark_bar(color="#ff315d")
            .encode(
                x=alt.X("數值:Q", title=f"數值{suffix}"),
                y=alt.Y("display:N", sort="-x", title="店家"),
                tooltip=["display", "數值"],
            )
            .properties(title=title, height=380)
        )
        st.altair_chart(chart, use_container_width=True)

    if ranking_type == "🔥 十大暴躁老闆":
        ranking_df = df.sort_values(
            ["intensity", "owner_replies"],
            ascending=[False, False],
        )

        score_column = "intensity"
        score_suffix = " 分"

    elif ranking_type == "🤡 全台北最會酸":
        ranking_df = df[
            df["persona"] == "🤡 高級反串"
        ].sort_values(
            "intensity",
            ascending=False,
        )

        score_column = "intensity"
        score_suffix = " 分"

    elif ranking_type == "💬 店家回覆王":
        ranking_df = df.sort_values(
            "owner_replies",
            ascending=False,
        )

        score_column = "owner_replies"
        score_suffix = " 則"

    elif ranking_type == "⭐ 一星評論王":
        ranking_df = df.sort_values(
            "reviews",
            ascending=False,
        )

        score_column = "reviews"
        score_suffix = " 則"

    else:
        ranking_df = pd.DataFrame()

        district_ranking = (
            df.groupby(
                ["city", "district"],
                as_index=False,
            )
            .agg(
                store_count=("store_id", "count"),
                average_intensity=("intensity", "mean"),
                review_count=("reviews", "sum"),
            )
            .sort_values(
                [
                    "average_intensity",
                    "review_count",
                ],
                ascending=[False, False],
            )
            .reset_index(drop=True)
        )

        district_ranking["地區"] = (
            district_ranking["city"] + district_ranking["district"]
        )

        district_plot = district_ranking.rename(
            columns={"average_intensity": "平均烈度"}
        )
        render_bar(
            district_plot,
            "地區",
            "平均烈度",
            title="🏘️ 行政區戰力榜 — 圖表",
            horizontal=True,
            color="#be3cff",
        )

        with st.expander("查看卡片式排行"):
            for position, row in district_ranking.iterrows():
                percentage = min(
                    float(row["average_intensity"]) * 10,
                    100,
                )

                render_html(
                    f"""
                    <div class="ranking-card">
                        <div class="ranking-row">
                            <div class="ranking-number">
                                {position + 1}
                            </div>

                            <div class="ranking-content">
                                <div class="ranking-name">
                                    {safe_text(row["city"])}
                                    {safe_text(row["district"])}
                                </div>

                                <div class="ranking-meta">
                                    {int(row["store_count"])} 家店・
                                    {int(row["review_count"])} 則評論
                                </div>
                            </div>

                            <div class="ranking-score">
                                {float(row["average_intensity"]):.1f} 分
                            </div>
                        </div>

                        <div class="ranking-track">
                            <div
                                class="ranking-fill"
                                style="width: {percentage}%"
                            ></div>
                        </div>
                    </div>
                    """
                )

    if not ranking_df.empty:
        ranking_df = ranking_df.head(10)

        _render_ranking_bar_chart(
            ranking_df,
            "name",
            score_column,
            title=f"{ranking_type} — 圖表",
            suffix=score_suffix,
        )

        with st.expander("查看卡片式排行"):
            maximum_score = float(
                ranking_df[score_column].max()
            )

            for position, (_, row) in enumerate(
                ranking_df.iterrows(),
                start=1,
            ):
                raw_score = float(row[score_column])

                percentage = (
                    raw_score / maximum_score * 100
                    if maximum_score > 0
                    else 0
                )

                if score_column == "intensity":
                    score_text = f"{raw_score:.1f}"
                else:
                    score_text = str(int(raw_score))

                render_html(
                    f"""
                    <div class="ranking-card">
                        <div class="ranking-row">
                            <div class="ranking-number">
                                {position}
                            </div>

                            <div class="ranking-content">
                                <div class="ranking-name">
                                    {safe_text(row["name"])}
                                </div>

                                <div class="ranking-meta">
                                    {safe_text(row["city"])}
                                    {safe_text(row["district"])}
                                    ・{safe_text(row["persona"])}
                                </div>
                            </div>

                            <div class="ranking-score">
                                {score_text}{score_suffix}
                            </div>
                        </div>

                        <div class="ranking-track">
                            <div
                                class="ranking-fill"
                                style="width: {percentage}%"
                            ></div>
                        </div>
                    </div>
                    """
                )


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
        st.metric("評論數", f"{int(df['reviews'].sum())} 則")
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
            horizontal=True,
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
                horizontal=True,
                color="#ff6687",
            )
        with c2:
            top_df = cached_top_intensity(limit=10)
            if top_df.empty:
                st.info("十大高烈度店家尚無資料。")
            else:
                top_chart = (
                    alt.Chart(top_df)
                    .mark_bar(color="#e00043", cornerRadiusEnd=4)
                    .encode(
                        x=alt.X("烈度:Q", title="烈度"),
                        y=alt.Y("店家:N", sort="-x", title="店家"),
                        tooltip=["店家", "烈度"],
                    )
                    .properties(title="十大高烈度店家", height=320)
                )
                st.altair_chart(top_chart, use_container_width=True)

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

elif current_page == "⚔️ 精選對決":
    st.title("精選對決")
    st.caption("挑一家店，把吵架原文一次攤開來看。")

    if df.empty:
        st.error(db_error or "目前沒有可對決的店家資料。")
        st.stop()

    store_options = {
        f"{row['name']}（{int(row.get('db_review_count') or 0)} 則）": row["store_id"]
        for _, row in df.sort_values("intensity", ascending=False).iterrows()
    }
    selected_label = st.selectbox("選店家", list(store_options.keys()))
    selected_place_id = store_options[selected_label]
    store_row = df[df["store_id"] == selected_place_id].iloc[0]

    st.subheader("店家資訊")
    info_cols = st.columns(4)
    info_cols[0].metric("烈度", f"{float(store_row['intensity']):.1f}")
    info_cols[1].metric("客人評分", f"{float(store_row.get('guest_score') or 0):.0f}")
    info_cols[2].metric("老闆評分", f"{float(store_row.get('owner_score') or 0):.0f}")
    info_cols[3].metric("評論數", f"{int(store_row.get('db_review_count') or 0)}")

    st.write(f"**地址：** {store_row.get('address') or '（沒有地址）'}")
    st.write(
        f"**客人人設：** {store_row.get('guest_persona') or '尚無'}　"
        f"**老闆人設：** {store_row.get('owner_persona') or store_row.get('persona') or '尚無'}"
    )
    store_url = str(store_row.get("store_url") or "").strip()
    if store_url:
        st.markdown(f"[打開店家地圖]({store_url})")
    else:
        st.caption("這家還沒有地圖連結。")

    st.subheader("評論原文")
    reviews_df = get_store_reviews_dataframe(str(selected_place_id), limit=50)
    if reviews_df.empty:
        st.warning("這家店目前沒有抓到評論。")
    else:
        st.caption(f"一共 {len(reviews_df)} 則")
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
                pr_text = str(rev.get("pr_reply") or "").strip()
                st.write("**AI 公關範例：**")
                st.info(pr_text if pr_text else "（還沒有公關範例）")
                review_url = str(rev.get("review_url") or "").strip()
                if review_url:
                    st.markdown(f"[看原始評論]({review_url})")
                else:
                    st.caption("這則沒有原始連結。")


# ============================================================
# 分頁：公關回覆教室
# ============================================================

elif current_page == "💬 公關回覆教室":
    st.title("公關回覆教室")
    st.caption("先看老闆原本怎麼回，再對照 AI 建議的公關說法。")

    pr_df = get_pr_reply_examples(limit=30)
    if pr_df.empty:
        st.warning("目前還沒有可用的公關範例，等資料進來再看。")
    else:
        labels = [
            f"{row['store_name']}｜客人 {int(row.get('guest_score') or 0)} / "
            f"老闆 {int(row.get('owner_score') or 0)}"
            for _, row in pr_df.iterrows()
        ]
        choice = st.selectbox("選一個案例", labels)
        case = pr_df.iloc[labels.index(choice)]

        st.subheader("老闆原本的回覆")
        st.write(str(case.get("owner_reply") or "（還沒回）"))

        st.subheader("AI 公關範例")
        st.success(str(case.get("pr_reply") or ""))

        st.write("**當時客人怎麼說：**")
        st.write(str(case.get("review_text") or ""))
        review_url = str(case.get("review_url") or "").strip()
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