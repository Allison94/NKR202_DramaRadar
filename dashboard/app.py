from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
import html
import re
import sys

import folium
import pandas as pd
import streamlit as st
from folium import DivIcon, Marker
from streamlit_folium import st_folium


# ============================================================
# 專案路徑 / import
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domains.store.service import (
    get_dashboard_dataframe,
    get_store_reviews_dataframe,
)


# ============================================================
# Streamlit 基本設定
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
PAGE_ANALYSIS = "📊 吵架分析"
PAGE_CLASSIC = "💬 經典吵架 / 公關回覆"
PAGE_RANKING = "🏆 趣味排行榜"
PAGE_REPORT = "🕵️ 匿名爆料"

# 舊頁面名稱保留成 alias，讓既有功能可以合併進 5 個入口，不必重寫資料邏輯。
PAGE_INTENSITY = PAGE_ANALYSIS
PAGE_REASON = PAGE_ANALYSIS
PAGE_PERSONA = PAGE_CLASSIC
PAGE_PR = PAGE_CLASSIC

PAGE_OPTIONS = [
    PAGE_MAP,
    PAGE_ANALYSIS,
    PAGE_CLASSIC,
    PAGE_RANKING,
    PAGE_REPORT,
]

TAIPEI_CENTER = [25.0478, 121.5319]


# ============================================================
# 共用工具
# ============================================================

def render_html(content: str) -> None:
    """安全地渲染本站自行產生的 HTML。"""
    st.html(dedent(content).strip())


def safe_text(value: object) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def ensure_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Dashboard 只做「顯示層防呆」，不改 DB schema。
    後端若暫時缺 AI 欄位，前端仍能顯示真實 review/store 資料。
    """
    result = frame.copy()

    defaults: dict[str, object] = {
        "store_id": "",
        "name": "",
        "category": "未分類",
        "address": "",
        "city": "台北市",
        "district": "未辨識行政區",
        "lat": 25.0478,
        "lng": 121.5319,
        "intensity": 1.0,
        "google_score": 0.0,
        "reviews": 0,
        "db_review_count": 0,
        "owner_replies": 0,
        "review_text": "",
        "owner_reply": "",
        "review_url": "",
        "pr_reply": "",
        "guest_score": 0.0,
        "owner_score": 0.0,
        "guest_persona": "",
        "owner_persona": "",
        "persona": "",
        "reason": "",
    }

    for column, default in defaults.items():
        if column not in result.columns:
            result[column] = default

    # 數值欄位
    numeric_columns = [
        "lat",
        "lng",
        "intensity",
        "google_score",
        "reviews",
        "db_review_count",
        "owner_replies",
        "guest_score",
        "owner_score",
    ]
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(
            defaults[column]
        )

    # 文字欄位
    text_columns = [
        "store_id",
        "name",
        "category",
        "address",
        "city",
        "district",
        "review_text",
        "owner_reply",
        "review_url",
        "pr_reply",
        "guest_persona",
        "owner_persona",
        "persona",
        "reason",
    ]
    for column in text_columns:
        result[column] = result[column].fillna("").astype(str)

    # 目前專案只做台北市：前端再保險過濾一次
    taipei_mask = (
        result["city"].str.contains("台北", na=False)
        | result["address"].str.contains("台北市", na=False)
    )
    if taipei_mask.any():
        result = result[taipei_mask].copy()

    # intensity 固定 1~10
    result["intensity"] = result["intensity"].clip(lower=1.0, upper=10.0)

    # AI 尚未產 reason 時，前端僅做展示用 fallback，不回寫 DB
    result["reason_display"] = result.apply(derive_reason, axis=1)
    result["persona_display"] = result.apply(derive_persona, axis=1)

    return result


def derive_reason(row: pd.Series) -> str:
    existing = str(row.get("reason") or "").strip()
    if existing and existing not in {"未分類", "其他", "None", "nan"}:
        return existing

    text = " ".join(
        [
            str(row.get("review_text") or ""),
            str(row.get("owner_reply") or ""),
        ]
    )

    rules = [
        ("價格", r"價格|漲價|太貴|貴|收費|價錢|錢"),
        ("排隊", r"排隊|等太久|久等|候位|等位|插隊|出餐慢"),
        ("態度", r"態度|沒禮貌|口氣|服務|嗆|罵|兇|不耐煩"),
        ("品質", r"品質|難吃|頭髮|臭|酸掉|不新鮮|油耗|份量|食物|餐點"),
        ("熱點新聞", r"新聞|爆料|虐狗|監視器|影片|上新聞|炎上"),
    ]
    for label, pattern in rules:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return "其他"


def derive_persona(row: pd.Series) -> str:
    raw = " ".join(
        [
            str(row.get("owner_persona") or ""),
            str(row.get("persona") or ""),
            str(row.get("owner_reply") or ""),
        ]
    ).strip()

    if re.search(r"反串|嘲諷|酸|陰陽|高級反串|🤡", raw, flags=re.IGNORECASE):
        return "A｜🤡 高級反串"
    if re.search(r"暴躁|開嗆|情緒|勒索|兇|😡", raw, flags=re.IGNORECASE):
        return "B｜😡 暴躁老哥"
    if re.search(
        r"公關|制式|抱歉|很抱歉|造成困擾|努力改進|謝謝.*惠顧|🤖",
        raw,
        flags=re.IGNORECASE,
    ):
        return "C｜🤖 無聊公關"
    return "尚未分類"


@st.cache_data(ttl=300, show_spinner="正在載入台北市店家資料...")
def load_dashboard_data(limit: int = 300) -> pd.DataFrame:
    frame = get_dashboard_dataframe(limit=limit)
    return ensure_columns(frame)


def refresh_dashboard() -> None:
    st.cache_data.clear()
    st.session_state["last_refresh_utc"] = datetime.now(timezone.utc)
    st.rerun()


# ============================================================
# 資料載入
# ============================================================

try:
    df = load_dashboard_data(limit=300)
    db_error = str(df.attrs.get("error", "") or "")
except Exception as exc:
    df = ensure_columns(pd.DataFrame())
    db_error = str(exc)

if "last_refresh_utc" not in st.session_state:
    st.session_state["last_refresh_utc"] = datetime.now(timezone.utc)


# ============================================================
# CSS
# 不隱藏 Streamlit header / sidebar toggle，避免 sidebar 收合後叫不回來
# ============================================================

render_html(
    """
    <style>
    :root {
        --bg: #0c090d;
        --panel: #171219;
        --panel-2: #211821;
        --border: rgba(255,255,255,.09);
        --text: #fff9fc;
        --muted: #b9aab3;
        --red: #ff315d;
        --orange: #ff811b;
        --purple: #be3cff;
        --yellow: #f7ba38;
    }

    .stApp {
        background:
            radial-gradient(circle at 90% 0%, rgba(190,60,255,.08), transparent 30%),
            var(--bg);
        color: var(--text);
    }

    [data-testid="stHeader"] {
        background: rgba(12,9,13,.92);
        border-bottom: 1px solid var(--border);
    }

    /* V2：原生 sidebar 不使用，導覽改到 Hero 圖下方左欄 */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }


    /* 只藏 footer，不碰 header / sidebar toggle */
    footer {
        display: none !important;
    }

    [data-testid="stSidebar"] {
        background: #141017;
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] * {
        color: #f9f1f5;
    }

    .block-container {
        max-width: 1580px;
        padding-top: 4.2rem;
        padding-bottom: 2.5rem;
    }

    h1, h2, h3 {
        color: var(--text) !important;
    }

    .hero-wrap {
        overflow: hidden;
        margin-bottom: 10px;
        border: 1px solid rgba(255,49,93,.22);
        border-radius: 20px;
        background: #070509;
    }

    .hero-hint {
        margin: 10px auto 20px;
        padding: 9px 15px;
        max-width: 440px;
        border: 1px solid rgba(255,49,93,.30);
        border-radius: 999px;
        background: rgba(255,49,93,.09);
        color: #ffb5c5;
        text-align: center;
        font-weight: 800;
    }

    .page-title {
        margin: 0;
        font-size: clamp(1.8rem, 3vw, 2.5rem);
        font-weight: 900;
        letter-spacing: -.04em;
    }

    .page-subtitle {
        margin: 5px 0 18px;
        color: var(--muted);
        font-size: .92rem;
    }

    .section-card {
        margin-bottom: 14px;
        padding: 17px 18px;
        border: 1px solid var(--border);
        border-radius: 16px;
        background: linear-gradient(145deg, rgba(23,18,25,.96), rgba(33,24,33,.90));
    }

    .persona-card {
        min-height: 175px;
        padding: 18px;
        border: 1px solid var(--border);
        border-radius: 16px;
        background: var(--panel);
    }

    .persona-title {
        margin-bottom: 9px;
        font-size: 1.1rem;
        font-weight: 900;
    }

    .muted {
        color: var(--muted);
    }

    .legend {
        display: flex;
        flex-wrap: wrap;
        gap: 12px 18px;
        align-items: center;
        margin: 10px 0 13px;
        padding: 11px 14px;
        border: 1px solid var(--border);
        border-radius: 14px;
        background: rgba(23,18,25,.94);
    }

    .legend-item {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: var(--muted);
        font-size: .82rem;
        font-weight: 700;
    }

    .scale-row {
        display: grid;
        grid-template-columns: 52px 1fr 170px;
        gap: 12px;
        align-items: center;
        margin: 8px 0;
        padding: 10px 12px;
        border: 1px solid var(--border);
        border-radius: 12px;
        background: rgba(23,18,25,.88);
    }

    .scale-no {
        font-size: 1.05rem;
        font-weight: 900;
        color: #ff8aa4;
    }

    .scale-bar {
        height: 9px;
        overflow: hidden;
        border-radius: 999px;
        background: #382c36;
    }

    .scale-fill {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #f7ba38, #ff811b, #ff315d, #be3cff);
    }

    .tag {
        display: inline-block;
        margin: 2px 4px 2px 0;
        padding: 4px 8px;
        border: 1px solid rgba(255,255,255,.10);
        border-radius: 999px;
        background: rgba(255,255,255,.05);
        color: #e8dce3;
        font-size: .78rem;
        font-weight: 750;
    }

    .pr-card {
        padding: 16px;
        border: 1px solid rgba(190,60,255,.22);
        border-radius: 15px;
        background: rgba(190,60,255,.06);
    }

    .empty-note {
        padding: 14px 16px;
        border: 1px dashed rgba(255,255,255,.14);
        border-radius: 13px;
        color: var(--muted);
        background: rgba(255,255,255,.025);
    }

    [data-testid="stMetric"] {
        padding: 14px;
        border: 1px solid var(--border);
        border-radius: 15px;
        background: var(--panel);
    }

    .stButton > button,
    [data-testid="stFormSubmitButton"] button {
        border: 1px solid rgba(255,49,93,.34);
        border-radius: 10px;
        background: linear-gradient(90deg, #a81c49, #782078);
        color: white;
        font-weight: 800;
    }

    .analysis-summary {
        padding: 16px 18px;
        border: 1px solid var(--border);
        border-radius: 15px;
        background: var(--panel);
        line-height: 1.8;
    }

    .podium-wrap {
        display: grid;
        grid-template-columns: 1fr 1.15fr 1fr;
        gap: 12px;
        align-items: end;
        margin: 18px 0 20px;
    }

    .podium-card {
        padding: 16px 12px;
        border: 1px solid var(--border);
        border-radius: 16px 16px 8px 8px;
        background: linear-gradient(160deg, rgba(31,24,33,.98), rgba(18,14,20,.98));
        text-align: center;
    }

    .podium-card.first { min-height: 190px; border-color: rgba(247,186,56,.42); }
    .podium-card.second { min-height: 160px; }
    .podium-card.third { min-height: 145px; }
    .podium-medal { font-size: 2rem; }
    .podium-name { margin-top: 6px; font-size: 1rem; font-weight: 900; }
    .podium-score { margin-top: 6px; color: #ff8aa4; font-size: 1.15rem; font-weight: 900; }
    .podium-note { margin-top: 8px; color: var(--muted); font-size: .78rem; line-height: 1.5; }

    @media (max-width: 800px) {
        .block-container {
            padding-left: .8rem;
            padding-right: .8rem;
            padding-top: 3.7rem;
        }

        .scale-row {
            grid-template-columns: 42px 1fr;
        }

        .scale-row .scale-label {
            grid-column: 1 / -1;
        }

        [data-testid="stSidebar"] {
            min-width: 245px;
        }
    }
    </style>
    """
)


# ============================================================
# 火焰 Marker
# ============================================================

def ai_fire_score(row: pd.Series) -> float | None:
    """組長規格：review_score + owner_score。沒有正式 AI 分數時不製造假分數。"""
    guest = pd.to_numeric(pd.Series([row.get("guest_score")]), errors="coerce").iloc[0]
    owner = pd.to_numeric(pd.Series([row.get("owner_score")]), errors="coerce").iloc[0]
    if pd.isna(guest) or pd.isna(owner) or float(guest) <= 0 or float(owner) <= 0:
        return None
    return float(guest) + float(owner)


def flame_size(score: float | None) -> int:
    if score is None:
        return 34
    value = max(2.0, min(float(score), 20.0))
    return int(24 + ((value - 2.0) / 18.0) * 42)


def flame_colors(score: float | None) -> tuple[str, str, str]:
    if score is None:
        return "#ff811b", "#ffd05b", "rgba(255,129,27,.38)"
    value = max(2.0, min(float(score), 20.0))
    if value <= 7:
        return "#f7ba38", "#fff0a5", "rgba(247,186,56,.45)"
    if value <= 12:
        return "#ff811b", "#ffd05b", "rgba(255,129,27,.50)"
    if value <= 16:
        return "#ff4338", "#ffad3d", "rgba(255,67,56,.62)"
    return "#e00043", "#ff7138", "rgba(224,0,67,.84)"


def create_flame_icon(score: float | None) -> DivIcon:
    size = flame_size(score)
    outer, inner, glow = flame_colors(score)
    pulse = "flame-pulse" if score is not None and score >= 17 else ""
    score_html = (
        f'<div class="drama-flame-score">{score:.0f}</div>'
        if score is not None
        else ''
    )

    marker_html = dedent(
        f"""
        <div class="drama-flame-marker {pulse}"
             style="width:{size}px;height:{size + 18}px;">
            <div class="drama-flame-svg"
                 style="width:{size}px;height:{size}px;
                        filter:drop-shadow(0 0 {max(4, size // 7)}px {glow});">
                <svg width="{size}" height="{size}" viewBox="0 0 64 64"
                     xmlns="http://www.w3.org/2000/svg">
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
            </div>
            {score_html}
        </div>
        """
    ).strip()

    return DivIcon(
        html=marker_html,
        icon_size=(size, size + 18),
        icon_anchor=(size // 2, size + 8),
        popup_anchor=(0, -size),
        class_name="drama-flame-div-icon",
    )


def add_map_styles(drama_map: folium.Map) -> None:
    drama_map.get_root().header.add_child(
        folium.Element(
            """
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
                transition: transform .18s ease;
            }
            .drama-flame-marker:hover {
                z-index: 9999 !important;
                transform: scale(1.18);
            }
            .drama-flame-score {
                position: absolute;
                bottom: 0;
                left: 50%;
                transform: translateX(-50%);
                min-width: 28px;
                padding: 1px 5px;
                border: 1px solid rgba(255,255,255,.30);
                border-radius: 999px;
                background: rgba(18,13,18,.92);
                color: white;
                font: 800 10px/14px Arial, sans-serif;
                text-align: center;
            }
            @keyframes dramaPulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.11); }
                100% { transform: scale(1); }
            }
            .flame-pulse .drama-flame-svg {
                animation: dramaPulse 1.15s ease-in-out infinite;
            }
            </style>
            """
        )
    )


def popup_html(row: pd.Series) -> str:
    """地圖火焰點擊後，只顯示使用者真正需要的資訊。"""
    review = safe_text(str(row.get("review_text") or "")[:180])
    owner = safe_text(str(row.get("owner_reply") or "")[:180])
    store_url = str(row.get("store_url") or "").strip()
    review_url = str(row.get("review_url") or "").strip()

    google_score = float(row.get("google_score") or 0)
    fire_score = ai_fire_score(row)

    target_url = store_url or review_url
    map_button = ""
    if target_url:
        map_button = (
            f'<a href="{html.escape(target_url, quote=True)}" target="_blank" '
            'style="display:inline-block;margin-top:10px;padding:8px 12px;'
            'border-radius:8px;background:#242126;color:white;font-weight:800;'
            'text-decoration:none;font-size:12px;">Google Maps</a>'
        )

    return dedent(
        f"""
        <div style="width:300px;padding:8px;font-family:Arial,'Microsoft JhengHei',sans-serif;">
            <div style="font-size:17px;font-weight:900;color:#241820;margin-bottom:6px;">
                {safe_text(row.get("name") or "未命名店家")}
            </div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;">
                <span style="padding:4px 8px;border-radius:999px;background:#fff4d8;color:#9a6900;font-size:12px;font-weight:900;">
                    ⭐ Google {google_score:.1f}
                </span>
                {f'<span style="padding:4px 8px;border-radius:999px;background:#ffe7ed;color:#d71952;font-size:12px;font-weight:900;">🔥 火焰 {fire_score:.0f}/20</span>' if fire_score is not None else ''}
            </div>
            <div style="margin-bottom:10px;color:#74666e;font-size:12px;line-height:1.5;">
                📍 {safe_text(row.get("address") or "")}
            </div>
            <div style="padding:8px;border-radius:8px;background:#fff7f8;font-size:12px;line-height:1.6;color:#41363c;">
                <b>顧客評論</b><br>{review or "（沒有評論內容）"}
            </div>
            <div style="margin-top:7px;padding:8px;border-radius:8px;background:#f7f7f7;font-size:12px;line-height:1.6;color:#41363c;">
                <b>店家回覆</b><br>{owner or "（店家尚未回覆）"}
            </div>
            <div>{map_button}</div>
        </div>
        """
    ).strip()


# ============================================================
# 首頁 Hero + 內嵌導覽
# ============================================================

if SPLASH_IMAGE.exists():
    st.image(str(SPLASH_IMAGE), use_container_width=True)
else:
    st.warning("找不到 `dashboard/assets/splash.png`")

st.write("")
nav_col, content_col = st.columns([1.15, 4.85], gap="large")

with nav_col:
    st.markdown("### 🔥 Drama Radar")
    current_page = st.radio(
        "功能",
        PAGE_OPTIONS,
        key="nav_page",
        label_visibility="collapsed",
    )


def page_heading(title: str) -> None:
    render_html(f'<div class="page-title">{safe_text(title)}</div>')


def render_podium(frame: pd.DataFrame, score_col: str, score_label: str) -> None:
    ranked = frame.copy()
    ranked[score_col] = pd.to_numeric(ranked[score_col], errors="coerce").fillna(0)
    ranked = ranked[ranked[score_col] > 0].sort_values(score_col, ascending=False)
    ranked = ranked.drop_duplicates("store_id").head(5)

    if ranked.empty:
        st.info("目前資料庫尚未有可用的正式 AI 分數。")
        return

    top = ranked.head(3).reset_index(drop=True)
    cards: list[str] = []
    slots = [(1, "🥇", "first"), (0, "🥈", "second"), (2, "🥉", "third")]
    for idx, medal, css_class in slots:
        if idx < len(top):
            row = top.iloc[idx]
            note = str(row.get("owner_reply") or row.get("review_text") or "").strip()[:55]
            cards.append(
                f'<div class="podium-card {css_class}">'
                f'<div class="podium-medal">{medal}</div>'
                f'<div class="podium-name">{safe_text(row.get("name") or "未命名店家")}</div>'
                f'<div class="podium-score">{score_label} {float(row[score_col]):.1f}</div>'
                f'<div class="podium-note">{safe_text(note) if note else ""}</div>'
                '</div>'
            )
        else:
            cards.append(f'<div class="podium-card {css_class}"></div>')

    render_html('<div class="podium-wrap">' + ''.join(cards) + '</div>')

    if len(ranked) > 3:
        st.markdown("**其他上榜店家**")
        for rank, (_, row) in enumerate(ranked.iloc[3:].iterrows(), start=4):
            st.write(f"**{rank}. {row['name']}**　{score_label} {float(row[score_col]):.1f}")


with content_col:
    if current_page == PAGE_MAP:
        page_heading("台北吵架地圖")

        if df.empty:
            st.error(db_error or "目前沒有台北市店家可以顯示。")
            st.stop()

        search_col, district_col = st.columns([3.4, 1.4])
        with search_col:
            keyword = st.text_input("搜尋店家", placeholder="搜尋店名、地址、餐飲類型…")

        district_values = sorted(
            x for x in df["district"].dropna().unique().tolist() if str(x).strip()
        )
        with district_col:
            district = st.selectbox("行政區", ["全部", *district_values])

        filtered = df.copy()
        clean_keyword = keyword.strip()
        if clean_keyword:
            keyword_mask = (
                filtered["name"].str.contains(clean_keyword, case=False, na=False)
                | filtered["address"].str.contains(clean_keyword, case=False, na=False)
                | filtered["category"].str.contains(clean_keyword, case=False, na=False)
            )
            filtered = filtered[keyword_mask]
        if district != "全部":
            filtered = filtered[filtered["district"] == district]

        if filtered.empty:
            st.warning("目前找不到符合條件的店家，請清除搜尋或更換篩選條件。")
        else:
            valid_geo = filtered[
                filtered["lat"].between(24.8, 25.3)
                & filtered["lng"].between(121.2, 122.0)
            ].copy()

            if valid_geo.empty:
                st.warning("店家資料有載入，但目前沒有可用的經緯度。")
            else:
                map_center = [float(valid_geo["lat"].mean()), float(valid_geo["lng"].mean())]
                zoom = 13 if len(valid_geo) <= 2 else 11
                drama_map = folium.Map(
                    location=map_center,
                    zoom_start=zoom,
                    control_scale=True,
                    tiles=None,
                    prefer_canvas=False,
                )
                folium.TileLayer(
                    tiles="CartoDB Voyager",
                    name="台北市地圖",
                    control=False,
                ).add_to(drama_map)
                add_map_styles(drama_map)

                for _, store in valid_geo.iterrows():
                    fire_score = ai_fire_score(store)
                    tooltip = str(store["name"])
                    if fire_score is not None:
                        tooltip += f"｜火焰 {fire_score:.0f}/20"
                    Marker(
                        location=[float(store["lat"]), float(store["lng"])],
                        icon=create_flame_icon(fire_score),
                        tooltip=tooltip,
                        popup=folium.Popup(popup_html(store), max_width=320),
                    ).add_to(drama_map)

                if len(valid_geo) >= 3:
                    drama_map.fit_bounds(
                        valid_geo[["lat", "lng"]].values.tolist(),
                        padding=(28, 28),
                    )

                st_folium(
                    drama_map,
                    height=760,
                    use_container_width=True,
                    returned_objects=[],
                    key="drama_main_map",
                )

    elif current_page == PAGE_ANALYSIS:
        page_heading("吵架分析")

        if df.empty:
            st.info("目前沒有可分析的資料。")
        else:
            st.subheader("大家都在吵什麼？")
            reason_counts = (
                df["reason_display"]
                .replace("", "其他")
                .value_counts()
                .rename_axis("糾紛原因")
                .reset_index(name="店家數")
            )
            st.bar_chart(reason_counts.set_index("糾紛原因"), height=330, use_container_width=True)

            st.divider()
            st.subheader("顧客 vs 店家，誰比較火？")
            guest_scores = pd.to_numeric(df["guest_score"], errors="coerce").fillna(0)
            owner_scores = pd.to_numeric(df["owner_score"], errors="coerce").fillna(0)
            guest_valid = guest_scores[guest_scores > 0]
            owner_valid = owner_scores[owner_scores > 0]

            if guest_valid.empty and owner_valid.empty:
                st.info("目前 ai_analysis 尚未產生正式分數；資料進來後這裡會直接顯示 AI 分析結果。")
            else:
                g_avg = float(guest_valid.mean()) if not guest_valid.empty else 0.0
                o_avg = float(owner_valid.mean()) if not owner_valid.empty else 0.0
                score_frame = pd.DataFrame(
                    {"平均分數": [g_avg, o_avg]},
                    index=["😡 顧客", "🤬 店家"],
                )
                st.bar_chart(score_frame, height=260, use_container_width=True)
                top_reason = reason_counts.iloc[0]["糾紛原因"] if not reason_counts.empty else "尚無"
                render_html(
                    f'<div class="analysis-summary"><b>目前分析摘要</b><br>'
                    f'最常見糾紛：{safe_text(top_reason)}<br>'
                    f'顧客平均分數：{g_avg:.1f} / 10<br>'
                    f'店家平均分數：{o_avg:.1f} / 10</div>'
                )

    elif current_page == PAGE_CLASSIC:
        page_heading("經典吵架")

        if df.empty:
            st.info("目前沒有店家資料。")
        else:
            store_options = (
                df.drop_duplicates("store_id")
                .sort_values("intensity", ascending=False)
                [["store_id", "name"]]
            )
            store_ids = store_options["store_id"].astype(str).tolist()
            selected_id = st.selectbox(
                "選擇店家",
                store_ids,
                format_func=lambda pid: store_options.loc[
                    store_options["store_id"].astype(str) == pid,
                    "name",
                ].iloc[0],
            )

            store_row = df[df["store_id"].astype(str) == selected_id].iloc[0]
            st.markdown(f"## {store_row['name']}")
            tags = []
            persona = str(store_row.get("persona_display") or "").strip()
            reason_display = str(store_row.get("reason_display") or "").strip()
            if persona and persona != "尚未分類":
                tags.append(persona)
            if reason_display:
                tags.append(f"🧨 {reason_display}")
            if tags:
                st.caption("　".join(tags))

            reviews_df = get_store_reviews_dataframe(selected_id, limit=20)
            if reviews_df.empty:
                st.warning("這家店目前沒有評論資料。")
            else:
                for _, rev in reviews_df.iterrows():
                    review_text = str(rev.get("review_text") or "").strip()
                    owner_reply = str(rev.get("owner_reply") or "").strip()
                    pr_reply = str(rev.get("pr_reply") or "").strip()
                    guest_score = float(rev.get("guest_score") or 0)
                    owner_score = float(rev.get("owner_score") or 0)

                    with st.container(border=True):
                        score_tags = []
                        if guest_score > 0:
                            score_tags.append(f"😡 顧客 {guest_score:.1f}")
                        if owner_score > 0:
                            score_tags.append(f"🤬 店家 {owner_score:.1f}")
                        if score_tags:
                            st.caption("　".join(score_tags))

                        st.markdown("### 😡 顧客")
                        st.write(review_text or "（沒有評論內容）")
                        st.markdown("### 🏪 店家")
                        st.write(owner_reply or "（店家尚未回覆）")
                        st.markdown("### 🤖 AI 公關救援")
                        if pr_reply:
                            render_html(f'<div class="pr-card">{safe_text(pr_reply)}</div>')
                        else:
                            st.caption("AI 公關建議尚未產生。")

                        review_url = str(rev.get("review_url") or "").strip()
                        if review_url:
                            st.link_button("Google Maps", review_url)

    elif current_page == PAGE_RANKING:
        page_heading("趣味排行榜")

        if df.empty:
            st.info("目前沒有可排行的店家。")
        else:
            ranking_type = st.radio(
                "排行榜",
                ["🔥 最激烈店家", "😡 最怒顧客", "🤬 最嗆老闆"],
                horizontal=True,
                label_visibility="collapsed",
            )
            if ranking_type == "🔥 最激烈店家":
                render_podium(df, "intensity", "🔥")
            elif ranking_type == "😡 最怒顧客":
                render_podium(df, "guest_score", "😡")
            else:
                render_podium(df, "owner_score", "🤬")

    elif current_page == PAGE_REPORT:
        page_heading("匿名爆料")
        st.caption("提供公開可查證的資訊即可；正式資料是否入庫，交由後續審核流程決定。")

        if "session_reports" not in st.session_state:
            st.session_state["session_reports"] = []

        with st.form("anonymous_report_form", clear_on_submit=True):
            store_name = st.text_input("店家名稱 *")
            location = st.text_input("店家地點（台北市）")
            category = st.selectbox(
                "事件類型",
                ["態度", "價格", "排隊", "品質", "熱點新聞", "其他"],
            )
            description = st.text_area("事件內容 *", height=180)
            evidence_url = st.text_input("公開證據網址（選填）")
            submitted = st.form_submit_button("送出匿名爆料", use_container_width=True)

            if submitted:
                if not store_name.strip() or not description.strip():
                    st.warning("請至少填寫店家名稱與事件內容。")
                else:
                    st.session_state["session_reports"].append(
                        {
                            "store_name": store_name.strip(),
                            "location": location.strip(),
                            "category": category,
                            "description": description.strip(),
                            "evidence_url": evidence_url.strip(),
                        }
                    )
                    st.success("已收到這筆爆料（目前暫存在本次工作階段）。")