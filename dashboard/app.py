from __future__ import annotations

import html
import time
from pathlib import Path
from textwrap import dedent

import folium
import pandas as pd
import streamlit as st
from folium import DivIcon, Marker
from streamlit_folium import st_folium


# ============================================================
# 頁面基本設定
# ============================================================

st.set_page_config(
    page_title="Drama Radar｜雙北吵架地圖",
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

    progress_placeholder = st.empty()

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
                    正在搜尋雙北吵架戰場...
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
# 展示資料
# 未來可把這裡替換成 SQL 查詢結果
# ============================================================

SAMPLE_DATA = [
    {
        "store_id": 1,
        "name": "深夜拉麵研究所",
        "city": "新北市",
        "district": "板橋區",
        "category": "拉麵",
        "lat": 25.0151,
        "lng": 121.4624,
        "reviews": 42,
        "owner_replies": 38,
        "intensity": 9.6,
        "reason": "態度",
        "persona": "😡 暴躁老哥",
        "review_text": "等超久，詢問店員還被不耐煩回應。",
        "owner_reply": "現場客人很多，不想等可以選擇別間。",
    },
    {
        "store_id": 2,
        "name": "老地方牛肉麵",
        "city": "台北市",
        "district": "中山區",
        "category": "牛肉麵",
        "lat": 25.0578,
        "lng": 121.5331,
        "reviews": 37,
        "owner_replies": 29,
        "intensity": 9.3,
        "reason": "品質",
        "persona": "🤡 高級反串",
        "review_text": "湯頭太鹹，肉也有一點柴。",
        "owner_reply": "謝謝您精準的味覺分析，下次會準備白開水給您。",
    },
    {
        "store_id": 3,
        "name": "巷口雞排",
        "city": "新北市",
        "district": "三重區",
        "category": "炸物",
        "lat": 25.0615,
        "lng": 121.4881,
        "reviews": 31,
        "owner_replies": 27,
        "intensity": 9.1,
        "reason": "排隊",
        "persona": "😡 暴躁老哥",
        "review_text": "排隊順序很亂，後來的人反而先拿到。",
        "owner_reply": "號碼都有叫，是自己沒注意。",
    },
    {
        "store_id": 4,
        "name": "山城麻辣鍋",
        "city": "台北市",
        "district": "信義區",
        "category": "火鍋",
        "lat": 25.0360,
        "lng": 121.5670,
        "reviews": 28,
        "owner_replies": 22,
        "intensity": 8.8,
        "reason": "價格",
        "persona": "🤡 高級反串",
        "review_text": "這個份量配這個價格真的有點誇張。",
        "owner_reply": "原物料價格公開透明，歡迎比較後再消費。",
    },
    {
        "store_id": 5,
        "name": "港口海鮮食堂",
        "city": "新北市",
        "district": "淡水區",
        "category": "海鮮",
        "lat": 25.1676,
        "lng": 121.4450,
        "reviews": 26,
        "owner_replies": 20,
        "intensity": 8.4,
        "reason": "品質",
        "persona": "🤖 制式公關",
        "review_text": "海鮮不夠新鮮，服務也普通。",
        "owner_reply": "感謝您的指教，我們會再加強員工教育訓練。",
    },
    {
        "store_id": 6,
        "name": "早安蛋餅王",
        "city": "台北市",
        "district": "大安區",
        "category": "早餐",
        "lat": 25.0268,
        "lng": 121.5434,
        "reviews": 19,
        "owner_replies": 16,
        "intensity": 7.8,
        "reason": "態度",
        "persona": "🤡 高級反串",
        "review_text": "店員口氣不太好。",
        "owner_reply": "早上大家都比較忙，可能是您誤會了。",
    },
    {
        "store_id": 7,
        "name": "阿華便當",
        "city": "新北市",
        "district": "新莊區",
        "category": "便當",
        "lat": 25.0359,
        "lng": 121.4504,
        "reviews": 17,
        "owner_replies": 9,
        "intensity": 6.9,
        "reason": "價格",
        "persona": "🤖 制式公關",
        "review_text": "漲價後配菜反而變少。",
        "owner_reply": "感謝您的建議，我們會持續改善。",
    },
    {
        "store_id": 8,
        "name": "咖啡不能沒有你",
        "city": "台北市",
        "district": "萬華區",
        "category": "咖啡",
        "lat": 25.0429,
        "lng": 121.5063,
        "reviews": 12,
        "owner_replies": 3,
        "intensity": 5.7,
        "reason": "其他",
        "persona": "🥹 委屈老闆",
        "review_text": "環境不錯，但咖啡普通。",
        "owner_reply": "謝謝您的蒞臨，我們會繼續努力。",
    },
    {
        "store_id": 9,
        "name": "板橋厚切豬排",
        "city": "新北市",
        "district": "板橋區",
        "category": "日式料理",
        "lat": 25.0116,
        "lng": 121.4595,
        "reviews": 15,
        "owner_replies": 7,
        "intensity": 4.3,
        "reason": "份量",
        "persona": "🥹 委屈老闆",
        "review_text": "照片看起來很大，實際份量比較普通。",
        "owner_reply": "照片皆為現場餐點拍攝，謝謝您的意見。",
    },
    {
        "store_id": 10,
        "name": "信義深夜食堂",
        "city": "台北市",
        "district": "信義區",
        "category": "居酒屋",
        "lat": 25.0414,
        "lng": 121.5650,
        "reviews": 9,
        "owner_replies": 2,
        "intensity": 3.2,
        "reason": "其他",
        "persona": "🤖 制式公關",
        "review_text": "音樂有一點太大聲。",
        "owner_reply": "感謝您的建議。",
    },
]

df = pd.DataFrame(SAMPLE_DATA)


# ============================================================
# 網站 CSS
# ============================================================

render_html(
    """
    <style>
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

    [data-testid="stMetric"] {
        padding: 1rem;
        border: 1px solid var(--drama-border);
        border-radius: 14px;
        background: var(--drama-panel);
    }

    [data-testid="stMetricValue"] {
        color: var(--drama-text);
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
                📍 {safe_text(row["city"])}
                {safe_text(row["district"])}
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
            </div>

            <div
                style="
                    margin-bottom: 4px;
                    color: #40353b;
                    font-size: 13px;
                "
            >
                <strong>糾紛類型：</strong>
                {safe_text(row["reason"])}
            </div>

            <div
                style="
                    margin-bottom: 9px;
                    color: #40353b;
                    font-size: 13px;
                "
            >
                <strong>店家人設：</strong>
                {safe_text(row["persona"])}
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
                <strong>顧客：</strong><br>
                {safe_text(row["review_text"])}
            </div>

            <div
                style="
                    padding: 8px;
                    border-left: 3px solid #e3245b;
                    border-radius: 8px;
                    background: #fff0f4;
                    color: #40353b;
                    font-size: 12px;
                    line-height: 1.55;
                "
            >
                <strong>店家：</strong><br>
                {safe_text(row["owner_reply"])}
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
    st.caption("雙北吵架地圖")

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

    st.caption("目前資料範圍")
    st.write("台北市、新北市")

    st.caption("系統版本")
    st.write("Prototype 4.0")

    st.info(
        "目前使用展示資料，之後再串接 SQL 資料庫。"
    )

    if st.button(
        "重新播放開場",
        use_container_width=True,
    ):
        st.session_state["splash_finished"] = False
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
                雙北吵架地圖
            </div>

            <div class="drama-page-subtitle">
                火焰越大，代表評論與店家回覆越激烈。
            </div>
            """
        )

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
            ["全部", "台北市", "新北市"],
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

    reason_column, intensity_column = st.columns(
        [1, 2]
    )

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

    st.caption(
        "從不同角度整理雙北最值得圍觀的評論戰場。"
    )

    ranking_type = st.selectbox(
        "選擇排行榜",
        [
            "🔥 十大暴躁老闆",
            "🤡 全雙北最會酸",
            "💬 店家回覆王",
            "⭐ 一星評論王",
            "🏘️ 行政區戰力榜",
        ],
    )

    if ranking_type == "🔥 十大暴躁老闆":
        ranking_df = df.sort_values(
            ["intensity", "owner_replies"],
            ascending=[False, False],
        )

        score_column = "intensity"
        score_suffix = " 分"

    elif ranking_type == "🤡 全雙北最會酸":
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

    metric_columns = st.columns(4)

    with metric_columns[0]:
        st.metric(
            "收錄店家",
            f"{len(df)} 家",
        )

    with metric_columns[1]:
        st.metric(
            "評論數",
            f"{int(df['reviews'].sum())} 則",
        )

    with metric_columns[2]:
        st.metric(
            "店家回覆",
            f"{int(df['owner_replies'].sum())} 則",
        )

    with metric_columns[3]:
        st.metric(
            "平均烈度",
            f"{float(df['intensity'].mean()):.1f}",
        )

    st.subheader("糾紛類型分布")

    reason_analysis = (
        df["reason"]
        .value_counts()
        .rename_axis("糾紛類型")
        .reset_index(name="店家數")
    )

    st.bar_chart(
        reason_analysis,
        x="糾紛類型",
        y="店家數",
    )

    st.subheader("行政區戰況")

    district_analysis = (
        df.groupby(
            ["city", "district"],
            as_index=False,
        )
        .agg(
            平均烈度=("intensity", "mean"),
            店家數=("store_id", "count"),
            評論數=("reviews", "sum"),
        )
    )

    district_analysis["地區"] = (
        district_analysis["city"]
        + district_analysis["district"]
    )

    district_analysis = district_analysis.sort_values(
        "平均烈度",
        ascending=False,
    )

    st.dataframe(
        district_analysis[
            [
                "地區",
                "平均烈度",
                "店家數",
                "評論數",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# 分頁：精選對決
# ============================================================

elif current_page == "⚔️ 精選對決":
    st.title("精選對決")

    st.caption(
        "完整呈現具有代表性的顧客評論與店家回覆。"
    )

    selected_persona = st.selectbox(
        "店家人設",
        [
            "全部",
            *sorted(
                df["persona"]
                .dropna()
                .unique()
                .tolist()
            ),
        ],
    )

    duel_df = df.sort_values(
        "intensity",
        ascending=False,
    )

    if selected_persona != "全部":
        duel_df = duel_df[
            duel_df["persona"] == selected_persona
        ]

    duel_columns = st.columns(3)

    for index, (_, row) in enumerate(
        duel_df.iterrows()
    ):
        with duel_columns[index % 3]:
            render_html(
                f"""
                <div class="duel-card">
                    <div class="duel-title">
                        {safe_text(row["name"])}
                    </div>

                    <div class="duel-meta">
                        📍 {safe_text(row["city"])}
                        {safe_text(row["district"])}
                        ・{safe_text(row["reason"])}
                        ・{safe_text(row["persona"])}
                    </div>

                    <div class="duel-message">
                        <strong>顧客：</strong><br>
                        {safe_text(row["review_text"])}
                    </div>

                    <div class="duel-message duel-owner">
                        <strong>店家：</strong><br>
                        {safe_text(row["owner_reply"])}
                    </div>

                    <div class="duel-score">
                        烈度 {float(row["intensity"]):.1f}
                    </div>
                </div>
                """
            )


# ============================================================
# 分頁：公關回覆教室
# ============================================================

elif current_page == "💬 公關回覆教室":
    st.title("公關回覆教室")

    st.caption(
        "將容易引發爭議的店家回覆，"
        "改寫成比較適合公開發布的文字。"
    )

    original_reply = st.text_area(
        "店家原始回覆",
        placeholder=(
            "例如：不爽不要來，"
            "我們也不缺你一個客人。"
        ),
        height=150,
    )

    selected_tone = st.selectbox(
        "改寫風格",
        [
            "正式道歉",
            "親切說明",
            "幽默化解",
            "危機公關",
        ],
    )

    if st.button(
        "產生公關回覆",
        use_container_width=True,
    ):
        if not original_reply.strip():
            st.warning("請先輸入店家原始回覆。")

        else:
            demo_replies = {
                "正式道歉": (
                    "非常抱歉此次消費體驗未能符合您的期待，"
                    "我們會重新檢視服務流程並持續改善。"
                ),
                "親切說明": (
                    "謝謝您願意提供意見，當天現場較為繁忙，"
                    "若造成感受不佳，我們深感抱歉。"
                ),
                "幽默化解": (
                    "看來我們當天的火氣比餐點還熱，"
                    "這部分確實需要好好檢討，謝謝您的提醒。"
                ),
                "危機公關": (
                    "我們已收到您的反映，並正在確認當日狀況。"
                    "如服務過程造成不適，我們在此致歉，"
                    "並會針對相關流程進行改善。"
                ),
            }

            st.success("改寫完成")

            st.text_area(
                "建議回覆",
                value=demo_replies[selected_tone],
                height=150,
            )

            st.caption(
                "目前為展示版本，之後可串接 LLM。"
            )


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