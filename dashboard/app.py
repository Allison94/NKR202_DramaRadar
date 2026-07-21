from __future__ import annotations

from datetime import datetime

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


# =========================================================
# 網頁設定
# =========================================================
st.set_page_config(
    page_title="Drama Radar",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# RWD 與網站樣式
# =========================================================
st.markdown(
    """
    <style>
    :root {
        --wine: #8b2635;
        --wine-dark: #351a20;
        --wine-soft: #f8ecee;
        --cream: #f7f5f2;
        --surface: #ffffff;
        --text: #242424;
        --muted: #77716f;
        --border: #e7e1dd;
        --shadow: 0 8px 24px rgba(53, 26, 32, 0.06);
    }

    html,
    body,
    [class*="css"] {
        font-family:
            "Noto Sans TC",
            "Microsoft JhengHei",
            Arial,
            sans-serif;
    }

    .stApp {
        background-color: var(--cream);
        color: var(--text);
    }

    .block-container {
        width: 100%;
        max-width: 1320px;
        padding-top: 2rem;
        padding-right: 2.2rem;
        padding-bottom: 4rem;
        padding-left: 2.2rem;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: var(--wine-dark);
        border-right: 0;
    }

    [data-testid="stSidebar"] * {
        color: #f9f4f5;
    }

    [data-testid="stSidebar"] [data-testid="stAlert"] {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.12);
    }

    [data-testid="stSidebar"] hr {
        border-color: rgba(255, 255, 255, 0.14);
    }

    [data-testid="stSidebar"] label {
        color: #f9f4f5 !important;
    }

    /* Radio 選單 */
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        margin-bottom: 0.35rem;
        padding: 0.7rem 0.75rem;
        border-radius: 9px;
        transition: background 0.2s ease;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background: rgba(255, 255, 255, 0.08);
    }

    /* Hero */
    .hero {
        position: relative;
        width: 100%;
        padding: clamp(1.7rem, 5vw, 3.2rem);
        margin-bottom: 1.5rem;
        overflow: hidden;
        color: white;
        background:
            radial-gradient(
                circle at 88% 20%,
                rgba(255, 255, 255, 0.13),
                transparent 24%
            ),
            linear-gradient(
                135deg,
                #351a20 0%,
                #6f2330 55%,
                #8b2635 100%
            );
        border-radius: 20px;
        box-shadow: var(--shadow);
    }

    .hero::after {
        content: "";
        position: absolute;
        right: -60px;
        bottom: -90px;
        width: 240px;
        height: 240px;
        border: 38px solid rgba(255, 255, 255, 0.05);
        border-radius: 50%;
    }

    .hero-badge {
        display: inline-flex;
        align-items: center;
        margin-bottom: 1rem;
        padding: 0.38rem 0.75rem;
        color: #5c202a;
        background: #fff7f8;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 750;
        letter-spacing: 0.04em;
    }

    .hero-title {
        position: relative;
        z-index: 1;
        margin: 0 0 0.7rem;
        font-size: clamp(2.1rem, 5vw, 3.7rem);
        font-weight: 850;
        line-height: 1.05;
        letter-spacing: -0.04em;
    }

    .hero-subtitle {
        position: relative;
        z-index: 1;
        max-width: 720px;
        margin: 0;
        color: #f5e9eb;
        font-size: clamp(0.95rem, 2vw, 1.08rem);
        line-height: 1.8;
    }

    /* 標題 */
    h1,
    h2,
    h3 {
        color: var(--text);
        letter-spacing: -0.02em;
    }

    h2 {
        margin-top: 0.4rem;
    }

    .section-description {
        margin-top: -0.45rem;
        margin-bottom: 1.25rem;
        color: var(--muted);
        font-size: 0.92rem;
    }

    /* Metric */
    [data-testid="stMetric"] {
        height: 100%;
        min-height: 116px;
        padding: 1.05rem 1.15rem;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        box-shadow: var(--shadow);
    }

    [data-testid="stMetricLabel"] {
        color: var(--muted);
        font-weight: 650;
    }

    [data-testid="stMetricValue"] {
        color: var(--wine-dark);
        font-size: clamp(1.65rem, 2.5vw, 2.2rem);
        font-weight: 800;
    }

    /* 有框容器 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        height: 100%;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        box-shadow: var(--shadow);
    }

    /* 表格 */
    [data-testid="stDataFrame"] {
        overflow: hidden;
        background: white;
        border: 1px solid var(--border);
        border-radius: 14px;
        box-shadow: var(--shadow);
    }

    /* Tabs */
    button[data-baseweb="tab"] {
        color: var(--muted);
        font-weight: 700;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--wine);
    }

    /* 按鈕 */
    .stButton > button,
    .stFormSubmitButton > button {
        min-height: 2.8rem;
        border: 0;
        border-radius: 9px;
        font-weight: 750;
    }

    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        color: white;
        background: var(--wine);
    }

    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover {
        background: #6f1f2c;
    }

    /* Input */
    input,
    textarea {
        border-radius: 9px !important;
    }

    /* 人設標籤 */
    .persona-badge {
        display: inline-block;
        padding: 0.3rem 0.7rem;
        color: var(--wine);
        background: var(--wine-soft);
        border: 1px solid #efcfd5;
        border-radius: 999px;
        font-size: 0.84rem;
        font-weight: 750;
    }

    iframe {
        width: 100% !important;
        max-width: 100% !important;
        border-radius: 14px;
        box-shadow: var(--shadow);
    }

    [data-testid="stHorizontalBlock"] {
        width: 100%;
        flex-wrap: wrap;
        gap: 1rem;
    }

    [data-testid="column"] {
        min-width: 0;
    }

    #MainMenu,
    footer {
        visibility: hidden;
    }

    /* 平板 */
    @media screen and (max-width: 900px) {
        .block-container {
            padding: 1.2rem 1.1rem 3rem;
        }

        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            flex: 1 1 calc(50% - 0.5rem) !important;
            width: calc(50% - 0.5rem) !important;
            min-width: 250px !important;
        }
    }

    /* 手機 */
    @media screen and (max-width: 640px) {
        .block-container {
            padding: 0.8rem 0.75rem 2.5rem;
        }

        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: column !important;
            gap: 0.8rem !important;
        }

        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            min-width: 100% !important;
        }

        .hero {
            padding: 1.4rem;
            border-radius: 14px;
        }

        .hero-title {
            font-size: 2.15rem;
        }

        .hero-subtitle {
            font-size: 0.92rem;
            line-height: 1.65;
        }

        [data-testid="stMetric"] {
            min-height: auto;
        }

        .stButton > button,
        .stFormSubmitButton > button {
            width: 100%;
        }

        iframe {
            min-height: 420px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 展示資料
# 正式版只需要把 load_data() 改成 SQL 查詢
# =========================================================
SAMPLE_DATA = [
    {
        "store_id": 1,
        "name": "深夜拉麵研究所",
        "city": "新北市",
        "district": "板橋區",
        "address": "新北市板橋區文化路一段 120 號",
        "category": "拉麵",
        "lat": 25.0151,
        "lng": 121.4624,
        "google_rating": 3.6,
        "one_star_reviews": 29,
        "owner_replies": 25,
        "intensity_score": 9.6,
        "persona": "暴躁老哥",
        "dispute_category": "品質",
        "review_text": "湯頭真的太鹹，跟店員反映後也沒有積極處理。",
        "owner_reply": "本店口味一直都是如此，大多數客人都可以接受。",
        "ai_summary": "顧客質疑餐點口味與現場處理方式，店家以強硬立場回應。",
        "is_hidden": False,
        "created_at": "2026-07-15",
    },
    {
        "store_id": 2,
        "name": "老地方牛肉麵",
        "city": "台北市",
        "district": "中正區",
        "address": "台北市中正區衡陽路 12 號",
        "category": "牛肉麵",
        "lat": 25.0422,
        "lng": 121.5107,
        "google_rating": 3.7,
        "one_star_reviews": 38,
        "owner_replies": 27,
        "intensity_score": 9.3,
        "persona": "高級反串",
        "dispute_category": "態度",
        "review_text": "等了快四十分鐘才上餐，詢問時服務態度也很差。",
        "owner_reply": "謝謝您在尖峰時段用餐，還能精準計算每一分鐘。",
        "ai_summary": "顧客抱怨等待時間與服務態度，店家以反諷方式回覆。",
        "is_hidden": False,
        "created_at": "2026-07-14",
    },
    {
        "store_id": 3,
        "name": "山城麻辣鍋",
        "city": "台北市",
        "district": "大安區",
        "address": "台北市大安區忠孝東路四段 85 號",
        "category": "火鍋",
        "lat": 25.0417,
        "lng": 121.5478,
        "google_rating": 3.9,
        "one_star_reviews": 31,
        "owner_replies": 23,
        "intensity_score": 8.8,
        "persona": "無聊公關",
        "dispute_category": "價格",
        "review_text": "價格很高，但肉量比照片看起來少很多。",
        "owner_reply": "感謝您的建議，本店將持續檢討並精進服務品質。",
        "ai_summary": "顧客認為價格與份量不符，店家以制式公關內容回覆。",
        "is_hidden": False,
        "created_at": "2026-07-13",
    },
    {
        "store_id": 4,
        "name": "港口海鮮食堂",
        "city": "基隆市",
        "district": "仁愛區",
        "address": "基隆市仁愛區愛三路 19 號",
        "category": "海鮮",
        "lat": 25.1282,
        "lng": 121.7415,
        "google_rating": 3.8,
        "one_star_reviews": 24,
        "owner_replies": 20,
        "intensity_score": 8.4,
        "persona": "暴躁老哥",
        "dispute_category": "價格",
        "review_text": "結帳金額比預期高，點餐時也沒有講清楚。",
        "owner_reply": "海鮮每日價格不同，菜單及現場都已經寫得很清楚。",
        "ai_summary": "顧客質疑計價方式，店家強調現場已有標示。",
        "is_hidden": False,
        "created_at": "2026-07-12",
    },
    {
        "store_id": 5,
        "name": "炭火燒肉本舖",
        "city": "新北市",
        "district": "新店區",
        "address": "新北市新店區北新路二段 66 號",
        "category": "燒肉",
        "lat": 24.9741,
        "lng": 121.5438,
        "google_rating": 4.0,
        "one_star_reviews": 22,
        "owner_replies": 16,
        "intensity_score": 7.7,
        "persona": "無聊公關",
        "dispute_category": "排隊",
        "review_text": "明明有訂位，到現場後還是等了二十分鐘。",
        "owner_reply": "當日現場人潮較多，造成不便敬請見諒。",
        "ai_summary": "顧客抱怨訂位後仍需等待，店家以正式語氣道歉。",
        "is_hidden": False,
        "created_at": "2026-07-11",
    },
    {
        "store_id": 6,
        "name": "日光早午餐",
        "city": "桃園市",
        "district": "桃園區",
        "address": "桃園市桃園區中正路 235 號",
        "category": "早午餐",
        "lat": 24.9945,
        "lng": 121.3012,
        "google_rating": 4.1,
        "one_star_reviews": 18,
        "owner_replies": 11,
        "intensity_score": 6.8,
        "persona": "高級反串",
        "dispute_category": "環境",
        "review_text": "餐點普通，假日現場非常吵，完全沒辦法聊天。",
        "owner_reply": "很抱歉週末其他客人也選擇出門用餐。",
        "ai_summary": "顧客抱怨環境吵雜，店家以略帶反諷的方式回覆。",
        "is_hidden": False,
        "created_at": "2026-07-10",
    },
    {
        "store_id": 7,
        "name": "巷口雞排",
        "city": "新北市",
        "district": "三重區",
        "address": "新北市三重區重新路二段 51 號",
        "category": "小吃",
        "lat": 25.0615,
        "lng": 121.4881,
        "google_rating": 3.5,
        "one_star_reviews": 35,
        "owner_replies": 30,
        "intensity_score": 9.1,
        "persona": "暴躁老哥",
        "dispute_category": "態度",
        "review_text": "老闆講話很兇，只是詢問要等多久就被瞪。",
        "owner_reply": "現場很多客人都在等，不可能只服務您一位。",
        "ai_summary": "顧客批評店家態度，店家直接反擊並強調現場繁忙。",
        "is_hidden": False,
        "created_at": "2026-07-09",
    },
    {
        "store_id": 8,
        "name": "海景景觀餐廳",
        "city": "新北市",
        "district": "淡水區",
        "address": "新北市淡水區中正路 201 號",
        "category": "景觀餐廳",
        "lat": 25.1676,
        "lng": 121.4450,
        "google_rating": 4.2,
        "one_star_reviews": 15,
        "owner_replies": 12,
        "intensity_score": 7.3,
        "persona": "無聊公關",
        "dispute_category": "品質",
        "review_text": "餐點冷掉了才送上來，景色不錯但食物普通。",
        "owner_reply": "感謝您的回饋，我們會再加強出餐流程。",
        "ai_summary": "顧客對餐點溫度與品質不滿，店家表示會改善流程。",
        "is_hidden": True,
        "created_at": "2026-07-08",
    },
]


@st.cache_data
def load_data() -> pd.DataFrame:
    """正式版將此函式改成 SQL 查詢。"""
    return pd.DataFrame(SAMPLE_DATA)


df = load_data()


# =========================================================
# 共用函式
# =========================================================
def persona_label(persona: str) -> str:
    labels = {
        "高級反串": "🤡 高級反串",
        "暴躁老哥": "😡 暴躁老哥",
        "無聊公關": "🤖 無聊公關",
    }
    return labels.get(persona, persona)


def intensity_level(score: float) -> str:
    if score >= 9:
        return "史詩級互嗆"
    if score >= 7:
        return "高烈度"
    if score >= 4:
        return "中烈度"
    return "理性溝通"


def marker_color(score: float) -> str:
    if score >= 9:
        return "darkred"
    if score >= 7:
        return "red"
    if score >= 4:
        return "orange"
    return "green"


def render_page_header(title: str, description: str) -> None:
    st.title(title)
    st.markdown(
        f'<p class="section-description">{description}</p>',
        unsafe_allow_html=True,
    )


def render_store_table(data: pd.DataFrame) -> None:
    if data.empty:
        st.info("目前沒有符合條件的資料。")
        return

    display_df = data[
        [
            "name",
            "city",
            "category",
            "one_star_reviews",
            "owner_replies",
            "intensity_score",
            "persona",
        ]
    ].copy()

    display_df["persona"] = display_df["persona"].map(persona_label)

    display_df = display_df.rename(
        columns={
            "name": "店家",
            "city": "縣市",
            "category": "類型",
            "one_star_reviews": "一星評論",
            "owner_replies": "店家回覆",
            "intensity_score": "烈度",
            "persona": "回覆人設",
        }
    )

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        column_config={
            "烈度": st.column_config.ProgressColumn(
                "烈度",
                min_value=1,
                max_value=10,
                format="%.1f",
            )
        },
    )


def render_sidebar() -> str:
    with st.sidebar:
        st.title("Drama Radar")
        st.caption("餐廳負評與店家回覆觀察平台")

        page = st.radio(
            "功能選單",
            [
                "首頁總覽",
                "爭議地圖",
                "趣味排行榜",
                "評論詳情",
                "公關回覆教室",
                "匿名爆料",
            ],
        )

        st.divider()
        st.caption("資料來源")
        st.write("Google Maps 評論與店家回覆")

        st.caption("資料更新")
        st.write(datetime.now().strftime("%Y/%m/%d"))

        st.caption("系統版本")
        st.write("Prototype 1.0")

        st.info("目前使用展示資料，之後改由 SQL 資料庫載入。")

    return page


page = render_sidebar()


# =========================================================
# 首頁
# =========================================================
if page == "首頁總覽":
    st.markdown(
        """
        <section class="hero">
            <div class="hero-badge">餐飲評論互動觀察平台</div>
            <h1 class="hero-title">Drama Radar</h1>
            <p class="hero-subtitle">
                從一星評論到店家神回覆，整理餐飲現場最具爭議性的互動，
                透過地圖、排行榜與摘要，快速掌握近期熱門論戰。
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric("收錄店家", f"{len(df)} 家")
    metric2.metric("一星評論", f"{int(df['one_star_reviews'].sum())} 則")
    metric3.metric("店家回覆", f"{int(df['owner_replies'].sum())} 則")
    metric4.metric("平均烈度", f"{df['intensity_score'].mean():.1f} / 10")

    st.divider()

    ranking_column, chart_column = st.columns([1.7, 1])

    with ranking_column:
        st.subheader("本週熱門論戰")

        ranking = (
            df.sort_values("intensity_score", ascending=False)
            .head(5)
            .copy()
        )
        ranking.insert(0, "排名", range(1, len(ranking) + 1))

        ranking_display = ranking[
            [
                "排名",
                "name",
                "city",
                "dispute_category",
                "intensity_score",
            ]
        ].rename(
            columns={
                "name": "店家",
                "city": "縣市",
                "dispute_category": "糾紛原因",
                "intensity_score": "烈度",
            }
        )

        st.dataframe(
            ranking_display,
            width="stretch",
            hide_index=True,
            column_config={
                "烈度": st.column_config.ProgressColumn(
                    "烈度",
                    min_value=1,
                    max_value=10,
                    format="%.1f",
                )
            },
        )

    with chart_column:
        st.subheader("糾紛原因")

        category_counts = (
            df["dispute_category"]
            .value_counts()
            .rename_axis("糾紛類型")
            .reset_index(name="數量")
        )

        st.bar_chart(
            category_counts,
            x="糾紛類型",
            y="數量",
            width="stretch",
        )

    st.divider()
    st.subheader("店家回覆人設")

    persona_columns = st.columns(3)
    personas = [
        (
            "🤡 高級反串",
            "高級反串",
            "表面客氣，內容帶有明顯反諷。",
        ),
        (
            "😡 暴躁老哥",
            "暴躁老哥",
            "直接開嗆，與評論者正面交鋒。",
        ),
        (
            "🤖 無聊公關",
            "無聊公關",
            "使用制式、官方的回覆內容。",
        ),
    ]

    for column, (title, key, description) in zip(
        persona_columns,
        personas,
    ):
        with column:
            with st.container(border=True):
                st.markdown(f"### {title}")
                st.metric("收錄筆數", int((df["persona"] == key).sum()))
                st.caption(description)

    st.divider()
    st.subheader("最新收錄")

    recent_df = df.sort_values("created_at", ascending=False).head(3)
    recent_columns = st.columns(3)

    for column, (_, row) in zip(
        recent_columns,
        recent_df.iterrows(),
    ):
        with column:
            with st.container(border=True):
                st.markdown(f"### {row['name']}")
                st.caption(
                    f"{row['city']}・"
                    f"{row['district']}・"
                    f"{row['category']}"
                )
                st.metric("烈度", f"{row['intensity_score']:.1f} / 10")
                st.markdown(
                    f'<span class="persona-badge">'
                    f'{persona_label(row["persona"])}'
                    f"</span>",
                    unsafe_allow_html=True,
                )
                st.write("")
                st.write(f"主要糾紛：{row['dispute_category']}")
                st.caption(row["ai_summary"])


# =========================================================
# 地圖
# =========================================================
elif page == "爭議地圖":
    render_page_header(
        "爭議地圖",
        "依縣市、餐廳類型、糾紛原因與烈度查看店家分布。",
    )

    filter1, filter2, filter3, filter4 = st.columns(4)

    with filter1:
        city = st.selectbox(
            "縣市",
            ["全部"] + sorted(df["city"].unique().tolist()),
        )

    with filter2:
        category = st.selectbox(
            "餐廳類型",
            ["全部"] + sorted(df["category"].unique().tolist()),
        )

    with filter3:
        dispute = st.selectbox(
            "糾紛原因",
            ["全部"]
            + sorted(df["dispute_category"].unique().tolist()),
        )

    with filter4:
        minimum_score = st.slider(
            "最低烈度",
            min_value=1.0,
            max_value=10.0,
            value=1.0,
            step=0.5,
        )

    filtered_df = df.copy()

    if city != "全部":
        filtered_df = filtered_df[filtered_df["city"] == city]

    if category != "全部":
        filtered_df = filtered_df[
            filtered_df["category"] == category
        ]

    if dispute != "全部":
        filtered_df = filtered_df[
            filtered_df["dispute_category"] == dispute
        ]

    filtered_df = filtered_df[
        filtered_df["intensity_score"] >= minimum_score
    ]

    st.caption(f"目前顯示 {len(filtered_df)} 家店家")

    if filtered_df.empty:
        st.warning("沒有符合目前篩選條件的店家。")
    else:
        center = [
            filtered_df["lat"].mean(),
            filtered_df["lng"].mean(),
        ]

        store_map = folium.Map(
            location=center,
            zoom_start=10,
            tiles="CartoDB positron",
            control_scale=True,
        )

        for _, row in filtered_df.iterrows():
            source = "匿名爆料" if row["is_hidden"] else "公開評論"

            popup_html = f"""
            <div style="
                width: 250px;
                max-width: 100%;
                font-family: Arial, sans-serif;
                line-height: 1.5;
            ">
                <h3 style="margin: 0 0 8px;">
                    {row['name']}
                </h3>
                <div>
                    {row['city']} {row['district']}｜{row['category']}
                </div>
                <hr>
                <div>Google 評分：{row['google_rating']}</div>
                <div>糾紛原因：{row['dispute_category']}</div>
                <div>回覆人設：{row['persona']}</div>
                <div>
                    <strong>
                        烈度：{row['intensity_score']} / 10
                    </strong>
                </div>
                <div>資料來源：{source}</div>
                <hr>
                <div>
                    <strong>評論：</strong>
                    {row['review_text']}
                </div>
                <br>
                <div>
                    <strong>店家回覆：</strong>
                    {row['owner_reply']}
                </div>
            </div>
            """

            folium.Marker(
                location=[row["lat"], row["lng"]],
                tooltip=(
                    f"{row['name']}｜"
                    f"烈度 {row['intensity_score']}"
                ),
                popup=folium.Popup(
                    popup_html,
                    max_width=300,
                ),
                icon=folium.Icon(
                    color=marker_color(row["intensity_score"]),
                    icon="fire",
                    prefix="fa",
                ),
            ).add_to(store_map)

        st_folium(
            store_map,
            width=None,
            height=520,
            returned_objects=[],
        )

        st.subheader("店家清單")
        render_store_table(filtered_df)


# =========================================================
# 趣味排行榜
# =========================================================
elif page == "趣味排行榜":
    render_page_header(
        "趣味排行榜",
        "從評論烈度、店家回覆與糾紛分類整理趣味數據。",
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "暴躁老闆",
            "抱怨原因",
            "最會酸老闆",
            "監視器還原大師",
        ]
    )

    with tab1:
        selected_city = st.selectbox(
            "選擇地區",
            ["全部"] + sorted(df["city"].unique().tolist()),
            key="ranking_city",
        )

        ranking_df = df.copy()

        if selected_city != "全部":
            ranking_df = ranking_df[
                ranking_df["city"] == selected_city
            ]

        ranking_df = ranking_df.sort_values(
            ["intensity_score", "owner_replies"],
            ascending=False,
        ).head(10)

        render_store_table(ranking_df)

    with tab2:
        complaint_counts = (
            df["dispute_category"]
            .value_counts()
            .rename_axis("抱怨原因")
            .reset_index(name="出現次數")
        )

        st.bar_chart(
            complaint_counts,
            x="抱怨原因",
            y="出現次數",
            width="stretch",
        )

        st.dataframe(
            complaint_counts,
            width="stretch",
            hide_index=True,
        )

    with tab3:
        sarcastic_df = (
            df[df["persona"] == "高級反串"]
            .sort_values("intensity_score", ascending=False)
            .copy()
        )

        render_store_table(sarcastic_df)

        for _, row in sarcastic_df.iterrows():
            with st.expander(
                f"{row['name']}｜烈度 "
                f"{row['intensity_score']}"
            ):
                st.markdown("**顧客評論**")
                st.write(row["review_text"])
                st.markdown("**店家回覆**")
                st.warning(row["owner_reply"])

    with tab4:
        reconstruction_df = (
            df[df["persona"].isin(["暴躁老哥", "高級反串"])]
            .sort_values("owner_replies", ascending=False)
            .head(10)
        )

        st.caption(
            "目前以回覆數與強硬回覆類型模擬排名，"
            "正式版可改用 AI 分析結果。"
        )
        render_store_table(reconstruction_df)


# =========================================================
# 評論詳情
# =========================================================
elif page == "評論詳情":
    render_page_header(
        "評論詳情",
        "查看單一店家的負評、回覆、摘要與分類結果。",
    )

    selected_store = st.selectbox(
        "選擇店家",
        df["name"].tolist(),
    )

    store = df[df["name"] == selected_store].iloc[0]

    title_column, score_column = st.columns([4, 1])

    with title_column:
        st.header(store["name"])
        st.caption(
            f"{store['city']}・"
            f"{store['district']}・"
            f"{store['category']}・"
            f"{store['address']}"
        )

    with score_column:
        st.metric(
            "烈度",
            f"{store['intensity_score']:.1f}",
            intensity_level(store["intensity_score"]),
        )

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric("Google 評分", store["google_rating"])
    metric2.metric("一星評論", store["one_star_reviews"])
    metric3.metric("店家回覆", store["owner_replies"])
    metric4.metric("糾紛原因", store["dispute_category"])

    st.divider()

    review_column, reply_column = st.columns(2)

    with review_column:
        st.subheader("顧客評論")
        with st.container(border=True):
            st.write(store["review_text"])

    with reply_column:
        st.subheader("店家回覆")
        with st.container(border=True):
            st.write(store["owner_reply"])

    st.subheader("分析結果")

    analysis1, analysis2, analysis3 = st.columns(3)

    with analysis1:
        with st.container(border=True):
            st.caption("回覆人設")
            st.markdown(f"### {persona_label(store['persona'])}")

    with analysis2:
        with st.container(border=True):
            st.caption("互動烈度")
            st.markdown(
                f"### {intensity_level(store['intensity_score'])}"
            )

    with analysis3:
        source = "匿名爆料" if store["is_hidden"] else "公開評論"

        with st.container(border=True):
            st.caption("資料來源")
            st.markdown(f"### {source}")

    st.subheader("AI 摘要")
    st.success(store["ai_summary"])


# =========================================================
# 公關回覆教室
# =========================================================
elif page == "公關回覆教室":
    render_page_header(
        "公關回覆教室",
        "將容易引起爭議的文字改寫為較適合公開發布的回覆。",
    )

    input_column, setting_column = st.columns([2, 1])

    with input_column:
        complaint = st.text_area(
            "顧客評論",
            placeholder="例如：等了很久，店員態度也很差。",
            height=150,
        )

        original_reply = st.text_area(
            "原始店家回覆",
            placeholder="例如：不能等就不要來。",
            height=130,
        )

    with setting_column:
        tone = st.selectbox(
            "建議語氣",
            [
                "溫和正式",
                "誠懇道歉",
                "簡潔專業",
                "輕鬆友善",
            ],
        )

        st.info(
            "目前為規則式展示版本，"
            "之後可改成呼叫 LLM API。"
        )

    templates = {
        "溫和正式": (
            "感謝您提供意見。對於此次用餐體驗未能符合期待，"
            "我們深感抱歉。相關問題將交由現場團隊確認，"
            "並持續改善服務流程。"
        ),
        "誠懇道歉": (
            "很抱歉這次的服務讓您感到不舒服，"
            "我們會重新檢視當日狀況並加強人員訓練。"
            "謝謝您願意反映問題，讓我們有改善的機會。"
        ),
        "簡潔專業": (
            "感謝您的回饋。針對您反映的問題，"
            "我們已交由相關人員確認並進行改善，"
            "造成不便敬請見諒。"
        ),
        "輕鬆友善": (
            "謝謝您告訴我們這次的感受。"
            "很抱歉讓您留下不好的印象，"
            "我們會把問題記錄下來並努力改善。"
        ),
    }

    if st.button(
        "產生建議回覆",
        type="primary",
        width="stretch",
    ):
        if not complaint.strip():
            st.warning("請先輸入顧客評論。")
        else:
            st.subheader("建議回覆")
            st.success(templates[tone])

            with st.expander("修改重點"):
                st.write("1. 先承認顧客的不佳感受。")
                st.write("2. 避免直接質疑或攻擊顧客。")
                st.write("3. 說明後續確認與改善方式。")
                st.write("4. 避免進行第二輪公開爭辯。")


# =========================================================
# 匿名爆料
# =========================================================
elif page == "匿名爆料":
    render_page_header(
        "匿名爆料",
        "提供餐飲消費事件的匿名投稿管道。",
    )

    with st.form("anonymous_report"):
        store_name = st.text_input("店家名稱")

        city_column, category_column = st.columns(2)

        with city_column:
            city = st.selectbox(
                "縣市",
                [
                    "台北市",
                    "新北市",
                    "基隆市",
                    "桃園市",
                    "其他",
                ],
            )

        with category_column:
            dispute_category = st.selectbox(
                "事件類型",
                [
                    "價格",
                    "態度",
                    "排隊",
                    "品質",
                    "環境",
                    "新聞事件",
                    "其他",
                ],
            )

        report_content = st.text_area(
            "事件內容",
            placeholder=(
                "請描述事件經過，避免填寫姓名、電話、"
                "地址等個人資料。"
            ),
            height=190,
        )

        evidence = st.file_uploader(
            "補充圖片（選填）",
            type=["jpg", "jpeg", "png"],
        )

        agreed = st.checkbox(
            "我確認內容為親身經歷，"
            "並同意平台進行必要的內容審核。"
        )

        submitted = st.form_submit_button(
            "匿名送出",
            type="primary",
            width="stretch",
        )

    if submitted:
        if not store_name.strip():
            st.error("請填寫店家名稱。")
        elif len(report_content.strip()) < 10:
            st.error("事件內容至少需要 10 個字。")
        elif not agreed:
            st.error("請先確認投稿聲明。")
        else:
            st.success(
                "投稿已送出，內容將在審核後決定是否公開。"
            )
            st.info(
                f"店家：{store_name}\n\n"
                f"地區：{city}\n\n"
                f"事件類型：{dispute_category}"
            )