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
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
SPLASH_IMAGE = ASSETS_DIR / "splash.png"

PAGE_MAP = "🗺️ 吵架地圖"
PAGE_INTENSITY = "🔥 烈度評分"
PAGE_PERSONA = "🎭 店家回覆類型"
PAGE_REASON = "🧨 糾紛分類"
PAGE_RANKING = "🏆 趣味排行榜"
PAGE_PR = "💬 經典公關回覆"
PAGE_REPORT = "🕵️ 匿名爆料"

PAGE_OPTIONS = [
    PAGE_MAP,
    PAGE_INTENSITY,
    PAGE_PERSONA,
    PAGE_REASON,
    PAGE_RANKING,
    PAGE_PR,
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

def flame_size(intensity: float) -> int:
    value = max(1.0, min(float(intensity), 10.0))
    return int(18 + value * 4.4)


def flame_colors(intensity: float) -> tuple[str, str, str]:
    if intensity <= 3:
        return "#f7ba38", "#fff0a5", "rgba(247,186,56,.45)"
    if intensity <= 6:
        return "#ff811b", "#ffd05b", "rgba(255,129,27,.50)"
    if intensity <= 8:
        return "#ff4338", "#ffad3d", "rgba(255,67,56,.62)"
    return "#e00043", "#ff7138", "rgba(224,0,67,.84)"


def create_flame_icon(intensity: float) -> DivIcon:
    value = max(1.0, min(float(intensity), 10.0))
    size = flame_size(value)
    outer, inner, glow = flame_colors(value)
    pulse = "flame-pulse" if value >= 9 else ""

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
            <div class="drama-flame-score">{value:.1f}</div>
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
    review = safe_text(str(row.get("review_text") or "")[:95])
    owner = safe_text(str(row.get("owner_reply") or "")[:95])
    review_url = str(row.get("review_url") or "").strip()

    link_html = ""
    if review_url:
        link_html = (
            f'<a href="{html.escape(review_url, quote=True)}" target="_blank" '
            'style="display:inline-block;margin-top:8px;padding:7px 10px;'
            'border-radius:8px;background:#e3245b;color:white;'
            'font-weight:800;text-decoration:none;">看原始評論 →</a>'
        )

    return dedent(
        f"""
        <div style="width:270px;padding:6px;
                    font-family:Arial,'Microsoft JhengHei',sans-serif;">
            <div style="font-size:16px;font-weight:900;color:#241820;">
                {safe_text(row.get("name") or "未命名店家")}
            </div>
            <div style="margin:4px 0 8px;color:#74666e;font-size:12px;">
                📍 {safe_text(row.get("address") or "")}
            </div>
            <div style="display:inline-block;margin-bottom:8px;padding:4px 8px;
                        border-radius:999px;background:#ffe7ed;color:#d71952;
                        font-size:12px;font-weight:900;">
                🔥 烈度 {float(row.get("intensity") or 1):.1f}/10
                ・{safe_text(row.get("reason_display") or "其他")}
            </div>
            <div style="font-size:12px;line-height:1.5;color:#41363c;">
                <b>顧客：</b>{review or "（沒有文字）"}
            </div>
            <div style="margin-top:6px;font-size:12px;line-height:1.5;color:#41363c;">
                <b>店家：</b>{owner or "（尚未回覆）"}
            </div>
            {link_html}
        </div>
        """
    ).strip()


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:
    st.markdown("# 🔥 Drama Radar")
    st.caption("台北市吵架地圖")
    st.divider()

    current_page = st.radio(
        "功能",
        PAGE_OPTIONS,
        key="nav_page",
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("目前範圍")
    st.markdown("**📍 台北市**")

    if db_error:
        st.error("資料庫讀取異常")
        st.caption(db_error)
    elif df.empty:
        st.warning("目前沒有可顯示的台北市資料")
    else:
        st.success(f"目前載入 {len(df)} 家店")

    if st.button("重新整理資料", use_container_width=True):
        refresh_dashboard()

    st.caption(
        "資料來源：PostgreSQL。AI 分析欄位若尚未產生，"
        "前端只做展示用 fallback，不回寫資料庫。"
    )


# ============================================================
# 共用頁首
# ============================================================

def page_heading(title: str, subtitle: str) -> None:
    render_html(
        f"""
        <div class="page-title">{safe_text(title)}</div>
        <div class="page-subtitle">{safe_text(subtitle)}</div>
        """
    )


# ============================================================
# 1. 吵架地圖
# ============================================================

if current_page == PAGE_MAP:
    if SPLASH_IMAGE.exists():
        st.image(str(SPLASH_IMAGE), use_container_width=True)
        render_html('<div class="hero-hint">↓ 往下滑，看台北市吵架熱點</div>')
    else:
        st.warning("找不到 `dashboard/assets/splash.png`")

    page_heading(
        "台北吵架地圖",
        "像看地圖一樣找店家；火焰越大，評論與店家回覆越激烈。",
    )

    if df.empty:
        st.error(db_error or "目前沒有台北市店家可以顯示。")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("收錄店家", f"{len(df)} 家")
    c2.metric("平均烈度", f"{df['intensity'].mean():.1f}")
    c3.metric("高烈度", f"{int((df['intensity'] >= 7).sum())} 家")
    c4.metric("有店家回覆", f"{int((df['owner_replies'] > 0).sum())} 家")

    st.write("")

    search_col, district_col, reason_col, intensity_col = st.columns(
        [2.2, 1.1, 1.1, 1.4]
    )

    with search_col:
        keyword = st.text_input(
            "搜尋店家",
            placeholder="店名、地址、餐飲類型…",
        )

    district_values = sorted(
        x for x in df["district"].dropna().unique().tolist() if str(x).strip()
    )
    with district_col:
        district = st.selectbox("行政區", ["全部", *district_values])

    reason_values = ["價格", "態度", "排隊", "品質", "熱點新聞", "其他"]
    with reason_col:
        reason = st.selectbox("糾紛分類", ["全部", *reason_values])

    with intensity_col:
        min_intensity = st.slider(
            "最低烈度",
            min_value=1.0,
            max_value=10.0,
            value=1.0,
            step=0.5,
        )

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

    if reason != "全部":
        filtered = filtered[filtered["reason_display"] == reason]

    filtered = filtered[filtered["intensity"] >= min_intensity]

    render_html(
        """
        <div class="legend">
            <span class="legend-item">🔥 小火｜1–3 理性溝通</span>
            <span class="legend-item">🔥 中火｜4–6 開始有火氣</span>
            <span class="legend-item">🔥 大火｜7–8 明顯互嗆</span>
            <span class="legend-item">🔥 爆炎｜9–10 史詩級互嗆</span>
        </div>
        """
    )

    if filtered.empty:
        st.warning("目前找不到符合條件的店家，請降低烈度或清除篩選。")
    else:
        valid_geo = filtered[
            filtered["lat"].between(24.8, 25.3)
            & filtered["lng"].between(121.2, 122.0)
        ].copy()

        if valid_geo.empty:
            st.warning("店家資料有載入，但目前沒有可用的經緯度。")
        else:
            map_center = [
                float(valid_geo["lat"].mean()),
                float(valid_geo["lng"].mean()),
            ]
            zoom = 13 if len(valid_geo) <= 2 else 11

            drama_map = folium.Map(
                location=map_center,
                zoom_start=zoom,
                control_scale=True,
                tiles=None,
                prefer_canvas=False,
            )

            # 視覺接近一般道路地圖，不需要 Google Maps API key
            folium.TileLayer(
                tiles="CartoDB Voyager",
                name="台北市地圖",
                control=False,
            ).add_to(drama_map)

            add_map_styles(drama_map)

            for _, store in valid_geo.iterrows():
                Marker(
                    location=[float(store["lat"]), float(store["lng"])],
                    icon=create_flame_icon(float(store["intensity"])),
                    tooltip=(
                        f"{store['name']}｜烈度 "
                        f"{float(store['intensity']):.1f}"
                    ),
                    popup=folium.Popup(popup_html(store), max_width=310),
                ).add_to(drama_map)

            if len(valid_geo) >= 3:
                drama_map.fit_bounds(
                    valid_geo[["lat", "lng"]].values.tolist(),
                    padding=(28, 28),
                )

            st_folium(
                drama_map,
                height=680,
                use_container_width=True,
                returned_objects=[],
                key="drama_main_map",
            )

            st.caption(
                f"目前顯示 {len(valid_geo)} 家。"
                "火焰大小依 intensity 1–10 動態縮放。"
            )


# ============================================================
# 2. 烈度評分
# ============================================================

elif current_page == PAGE_INTENSITY:
    page_heading(
        "烈度評分",
        "1 分是理性溝通，10 分是史詩級互嗆；地圖火焰大小直接跟著烈度變化。",
    )

    scale_labels = {
        1: "理性溝通",
        2: "有點不爽",
        3: "語氣變硬",
        4: "開始有火氣",
        5: "互不相讓",
        6: "明顯對嗆",
        7: "戰況升溫",
        8: "高強度互嗆",
        9: "接近炎上",
        10: "史詩級互嗆",
    }

    for score, label in scale_labels.items():
        render_html(
            f"""
            <div class="scale-row">
                <div class="scale-no">{score} 分</div>
                <div class="scale-bar">
                    <div class="scale-fill" style="width:{score * 10}%"></div>
                </div>
                <div class="scale-label">{safe_text(label)}</div>
            </div>
            """
        )

    st.divider()

    if df.empty:
        st.info("目前沒有店家資料。")
    else:
        threshold = st.slider(
            "只看烈度至少幾分",
            1.0,
            10.0,
            1.0,
            0.5,
            key="intensity_page_filter",
        )
        table = (
            df[df["intensity"] >= threshold]
            .sort_values("intensity", ascending=False)
            [["name", "district", "intensity", "db_review_count", "owner_replies"]]
            .rename(
                columns={
                    "name": "店家",
                    "district": "行政區",
                    "intensity": "烈度",
                    "db_review_count": "DB評論",
                    "owner_replies": "店家回覆",
                }
            )
        )
        st.dataframe(table, hide_index=True, use_container_width=True)


# ============================================================
# 3. 店家回覆類型
# ============================================================

elif current_page == PAGE_PERSONA:
    page_heading(
        "店家回覆類型",
        "把老闆回覆整理成三種最有戲的人設；C 類可提供後端作 hidden / skip 規則參考。",
    )

    a, b, c = st.columns(3)

    with a:
        render_html(
            """
            <div class="persona-card">
                <div class="persona-title">🤡 A｜高級反串</div>
                <div class="muted">
                    表面客氣，實際暗藏嘲諷、陰陽怪氣或高級酸。
                </div>
            </div>
            """
        )

    with b:
        render_html(
            """
            <div class="persona-card">
                <div class="persona-title">😡 B｜暴躁老哥</div>
                <div class="muted">
                    直接開嗆、情緒上頭、回覆帶強烈攻擊性或情緒勒索。
                </div>
            </div>
            """
        )

    with c:
        render_html(
            """
            <div class="persona-card">
                <div class="persona-title">🤖 C｜無聊公關</div>
                <div class="muted">
                    制式道歉、複製貼上式公關回覆；可作為後端隱藏名單規則參考。
                </div>
            </div>
            """
        )

    st.divider()

    if df.empty:
        st.info("目前沒有可分類的店家。")
    else:
        persona_counts = (
            df["persona_display"]
            .value_counts()
            .rename_axis("回覆類型")
            .reset_index(name="店家數")
        )

        st.bar_chart(
            persona_counts.set_index("回覆類型"),
            height=300,
            use_container_width=True,
        )

        selected_persona = st.selectbox(
            "查看某一類店家",
            ["全部", *persona_counts["回覆類型"].tolist()],
        )
        persona_df = df
        if selected_persona != "全部":
            persona_df = df[df["persona_display"] == selected_persona]

        st.dataframe(
            persona_df[
                ["name", "district", "persona_display", "owner_reply", "intensity"]
            ]
            .sort_values("intensity", ascending=False)
            .rename(
                columns={
                    "name": "店家",
                    "district": "行政區",
                    "persona_display": "回覆類型",
                    "owner_reply": "店家回覆",
                    "intensity": "烈度",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )


# ============================================================
# 4. 糾紛分類
# ============================================================

elif current_page == PAGE_REASON:
    page_heading(
        "糾紛分類",
        "價格、態度、排隊、品質、熱點新聞；AI 欄位尚未產生時，前端只做展示用關鍵字 fallback。",
    )

    categories = ["價格", "態度", "排隊", "品質", "熱點新聞", "其他"]

    cols = st.columns(3)
    category_icons = {
        "價格": "💸",
        "態度": "🙄",
        "排隊": "🕒",
        "品質": "🍽️",
        "熱點新聞": "📰",
        "其他": "💥",
    }

    for index, category in enumerate(categories):
        count = int((df["reason_display"] == category).sum()) if not df.empty else 0
        with cols[index % 3]:
            st.metric(
                f"{category_icons[category]} {category}",
                f"{count} 家",
            )

    st.divider()

    if not df.empty:
        reason_counts = (
            df["reason_display"]
            .value_counts()
            .reindex(categories, fill_value=0)
            .rename_axis("糾紛分類")
            .reset_index(name="店家數")
        )
        st.bar_chart(
            reason_counts.set_index("糾紛分類"),
            height=330,
            use_container_width=True,
        )

        chosen_reason = st.selectbox("查看分類", ["全部", *categories])
        reason_df = df if chosen_reason == "全部" else df[
            df["reason_display"] == chosen_reason
        ]

        for _, row in reason_df.sort_values(
            "intensity", ascending=False
        ).head(30).iterrows():
            with st.container(border=True):
                st.markdown(
                    f"### {row['name']}　🔥 {float(row['intensity']):.1f}"
                )
                st.caption(
                    f"{row['district']}｜{row['reason_display']}｜"
                    f"{row['persona_display']}"
                )
                st.write(row["review_text"] or "（目前沒有評論文字）")


# ============================================================
# 5. 趣味排行榜
# ============================================================

elif current_page == PAGE_RANKING:
    page_heading(
        "趣味排行榜",
        "把資料庫變成有社群分享感的榜單。目前資料範圍只計台北市。",
    )

    if df.empty:
        st.info("目前沒有可排行的店家。")
        st.stop()

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "🔥 台北十大暴躁老闆",
            "🗯️ 奧客最愛抱怨",
            "🤡 最會酸的老闆",
            "📹 監視器還原大師",
        ]
    )

    with tab1:
        top_boss = (
            df.sort_values(
                ["intensity", "owner_score", "owner_replies"],
                ascending=False,
            )
            .head(10)
            .copy()
        )
        top_boss["榜單分數"] = top_boss["intensity"].round(1)
        st.bar_chart(
            top_boss.set_index("name")[["榜單分數"]],
            height=360,
            use_container_width=True,
        )
        st.dataframe(
            top_boss[
                ["name", "district", "intensity", "persona_display", "owner_replies"]
            ].rename(
                columns={
                    "name": "店家",
                    "district": "行政區",
                    "intensity": "烈度",
                    "persona_display": "人設",
                    "owner_replies": "回覆數",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    with tab2:
        reason_counts = (
            df["reason_display"]
            .value_counts()
            .rename_axis("抱怨原因")
            .reset_index(name="店家數")
        )
        st.bar_chart(
            reason_counts.set_index("抱怨原因"),
            height=340,
            use_container_width=True,
        )
        if not reason_counts.empty:
            st.success(
                f"目前最常見：{reason_counts.iloc[0]['抱怨原因']} "
                f"（{int(reason_counts.iloc[0]['店家數'])} 家）"
            )

    with tab3:
        sarcastic_mask = df["persona_display"].str.startswith("A｜")
        sarcastic = df[sarcastic_mask].copy()
        if sarcastic.empty:
            st.info("目前資料還沒有被分類成「高級反串」的店家。")
        else:
            sarcastic = sarcastic.sort_values(
                ["owner_score", "intensity"],
                ascending=False,
            ).head(10)
            sarcastic["酸度"] = sarcastic[
                ["owner_score", "intensity"]
            ].max(axis=1)
            st.bar_chart(
                sarcastic.set_index("name")[["酸度"]],
                height=340,
                use_container_width=True,
            )
            st.dataframe(
                sarcastic[
                    ["name", "owner_reply", "owner_score", "intensity"]
                ].rename(
                    columns={
                        "name": "店家",
                        "owner_reply": "經典回覆",
                        "owner_score": "老闆分數",
                        "intensity": "烈度",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )

    with tab4:
        monitor_mask = (
            df["review_text"].str.contains(
                r"監視器|錄影|影片|畫面|調閱",
                regex=True,
                na=False,
            )
            | df["owner_reply"].str.contains(
                r"監視器|錄影|影片|畫面|調閱",
                regex=True,
                na=False,
            )
        )
        monitor_df = (
            df[monitor_mask]
            .sort_values("intensity", ascending=False)
            .head(10)
        )
        st.caption(
            "這個榜目前用評論 / 店家回覆中的「監視器、錄影、影片、畫面、調閱」"
            "關鍵字產生，之後可改接 AI 專屬標籤。"
        )
        if monitor_df.empty:
            st.info("目前還沒有符合「監視器還原大師」關鍵字的店家。")
        else:
            for rank, (_, row) in enumerate(monitor_df.iterrows(), start=1):
                with st.container(border=True):
                    st.markdown(
                        f"### 第 {rank} 名｜{row['name']}　"
                        f"🔥 {float(row['intensity']):.1f}"
                    )
                    st.write(
                        row["owner_reply"]
                        or row["review_text"]
                        or "（沒有文字）"
                    )


# ============================================================
# 6. 經典公關回覆
# ============================================================

elif current_page == PAGE_PR:
    page_heading(
        "經典公關回覆",
        "展示 LLM 已產生的公關示範；這個頁面不主動呼叫 AI，也不修改其他組員的 pipeline。",
    )

    if df.empty:
        st.info("目前沒有店家資料。")
        st.stop()

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
    st.caption(
        f"{store_row['district']}｜烈度 {float(store_row['intensity']):.1f}/10"
    )

    reviews_df = get_store_reviews_dataframe(selected_id, limit=50)

    if reviews_df.empty:
        st.warning("這家店目前沒有評論資料。")
    else:
        for _, rev in reviews_df.iterrows():
            with st.container(border=True):
                st.markdown("**顧客評論**")
                st.write(str(rev.get("review_text") or "（沒有內容）"))

                st.markdown("**店家原始回覆**")
                st.write(str(rev.get("owner_reply") or "（尚未回覆）"))

                pr_reply = str(rev.get("pr_reply") or "").strip()
                st.markdown("**LLM 公關示範**")
                if pr_reply:
                    render_html(
                        f'<div class="pr-card">{safe_text(pr_reply)}</div>'
                    )
                else:
                    st.info(
                        "目前 AI 尚未產生公關示範。"
                        "這裡只負責顯示，不會主動執行 AI pipeline。"
                    )

                review_url = str(rev.get("review_url") or "").strip()
                if review_url:
                    st.markdown(f"[查看原始 Google Maps 評論]({review_url})")


# ============================================================
# 7. 匿名爆料
# ============================================================

elif current_page == PAGE_REPORT:
    page_heading(
        "匿名爆料",
        "讓使用者補充 API 不一定抓得到的事件；目前是前端展示版，不假裝已寫入正式資料庫。",
    )

    st.info(
        "正式版建議流程：匿名投稿 → 待審核 → 人工確認 → "
        "再加入店家 / 事件資料。這樣才能避免惡意爆料直接公開。"
    )

    if "session_reports" not in st.session_state:
        st.session_state["session_reports"] = []

    with st.form("anonymous_report_form", clear_on_submit=True):
        store_name = st.text_input("店家名稱 *")
        location = st.text_input("店家地點（台北市）")
        category = st.selectbox(
            "事件類型",
            ["態度", "價格", "排隊", "品質", "熱點新聞", "其他"],
        )
        description = st.text_area(
            "事件內容 *",
            height=180,
            placeholder="請描述發生什麼事，避免填寫不必要的個人資料。",
        )
        evidence_url = st.text_input(
            "Google Maps / 新聞 / 公開證據網址（選填）"
        )
        submitted = st.form_submit_button(
            "送出匿名爆料",
            use_container_width=True,
        )

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
                st.success(
                    "展示版已暫存在這個瀏覽工作階段。"
                    "目前尚未寫入正式資料庫。"
                )

    if st.session_state["session_reports"]:
        st.divider()
        st.subheader("本次工作階段的投稿")
        st.caption(
            f"共 {len(st.session_state['session_reports'])} 筆；"
            "關閉工作階段後不保證保留。"
        )
        st.dataframe(
            pd.DataFrame(st.session_state["session_reports"]).rename(
                columns={
                    "store_name": "店家",
                    "location": "地點",
                    "category": "分類",
                    "description": "內容",
                    "evidence_url": "證據網址",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )