"""Transform database records into the DataFrame expected by the dashboard."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from domains.store.repository import fetch_dashboard_rows


DASHBOARD_COLUMNS = [
    "store_id",
    "name",
    "city",
    "district",
    "category",
    "lat",
    "lng",
    "intensity",
    "reason",
    "persona",
    "review_text",
    "owner_reply",
    "reviews",
    "owner_replies",
    "__data_source",
]


DEMO_ROWS: list[dict[str, Any]] = [
    {
        "store_id": "demo-001",
        "name": "板橋火爆牛肉麵",
        "city": "新北市",
        "district": "板橋區",
        "category": "牛肉麵",
        "lat": 25.0114,
        "lng": 121.4618,
        "intensity": 9.6,
        "reason": "態度",
        "persona": "🔥 正面開戰",
        "review_text": "等了很久詢問餐點，店員口氣讓人不舒服。",
        "owner_reply": "現場忙成這樣還一直催，不喜歡可以不要來。",
        "reviews": 368,
        "owner_replies": 74,
    },
    {
        "store_id": "demo-002",
        "name": "西門嘴硬雞排",
        "city": "台北市",
        "district": "萬華區",
        "category": "炸物",
        "lat": 25.0436,
        "lng": 121.5077,
        "intensity": 9.1,
        "reason": "品質",
        "persona": "🤡 高級反串",
        "review_text": "雞排偏乾，跟以前吃到的品質不太一樣。",
        "owner_reply": "謝謝您精準找出本店唯一一塊不合口味的雞排。",
        "reviews": 912,
        "owner_replies": 129,
    },
    {
        "store_id": "demo-003",
        "name": "信義排隊拉麵",
        "city": "台北市",
        "district": "信義區",
        "category": "拉麵",
        "lat": 25.0334,
        "lng": 121.5645,
        "intensity": 8.7,
        "reason": "排隊",
        "persona": "📣 規則至上",
        "review_text": "排到一半離開五分鐘，回來就被取消資格。",
        "owner_reply": "規則已張貼於門口，無法接受規則請勿排隊。",
        "reviews": 1450,
        "owner_replies": 203,
    },
    {
        "store_id": "demo-004",
        "name": "三重份量系滷肉飯",
        "city": "新北市",
        "district": "三重區",
        "category": "小吃",
        "lat": 25.0617,
        "lng": 121.4881,
        "intensity": 8.2,
        "reason": "份量",
        "persona": "🧾 數據反擊",
        "review_text": "照片看起來很多，實際拿到的份量很少。",
        "owner_reply": "每碗固定秤重，照片與現場規格完全相同。",
        "reviews": 528,
        "owner_replies": 66,
    },
    {
        "store_id": "demo-005",
        "name": "中山價格自由咖啡",
        "city": "台北市",
        "district": "中山區",
        "category": "咖啡廳",
        "lat": 25.0521,
        "lng": 121.5226,
        "intensity": 7.8,
        "reason": "價格",
        "persona": "💎 價值辯護",
        "review_text": "一杯飲料接近三百元，覺得性價比不高。",
        "owner_reply": "價格包含空間、原料與服務，並非只計算液體成本。",
        "reviews": 730,
        "owner_replies": 88,
    },
    {
        "store_id": "demo-006",
        "name": "新店慢慢早午餐",
        "city": "新北市",
        "district": "新店區",
        "category": "早午餐",
        "lat": 24.9676,
        "lng": 121.5415,
        "intensity": 6.9,
        "reason": "排隊",
        "persona": "😤 忙碌防禦",
        "review_text": "餐點等了四十分鐘，希望店家能先告知。",
        "owner_reply": "尖峰時段人力有限，已於點餐時說明可能久候。",
        "reviews": 284,
        "owner_replies": 31,
    },
    {
        "store_id": "demo-007",
        "name": "永和堅持豆漿店",
        "city": "新北市",
        "district": "永和區",
        "category": "早餐",
        "lat": 25.0081,
        "lng": 121.5154,
        "intensity": 6.4,
        "reason": "態度",
        "persona": "🧊 冷淡說明",
        "review_text": "詢問是否能調整甜度，店員沒有回應。",
        "owner_reply": "本店豆漿為固定甜度，現場無客製服務。",
        "reviews": 641,
        "owner_replies": 42,
    },
    {
        "store_id": "demo-008",
        "name": "士林脆皮臭豆腐",
        "city": "台北市",
        "district": "士林區",
        "category": "夜市小吃",
        "lat": 25.0878,
        "lng": 121.5242,
        "intensity": 5.8,
        "reason": "品質",
        "persona": "🛠️ 願意改善",
        "review_text": "這次外皮沒有以前酥脆，泡菜也比較少。",
        "owner_reply": "謝謝提醒，我們會檢查當天油溫與出餐份量。",
        "reviews": 1180,
        "owner_replies": 95,
    },
    {
        "store_id": "demo-009",
        "name": "淡水景觀鬆餅屋",
        "city": "新北市",
        "district": "淡水區",
        "category": "甜點",
        "lat": 25.1676,
        "lng": 121.4453,
        "intensity": 5.1,
        "reason": "價格",
        "persona": "🙂 禮貌解釋",
        "review_text": "景色不錯，但低消與服務費加起來偏高。",
        "owner_reply": "謝謝回饋，低消用於維護景觀座位與空間品質。",
        "reviews": 856,
        "owner_replies": 73,
    },
    {
        "store_id": "demo-010",
        "name": "大安職人飯糰",
        "city": "台北市",
        "district": "大安區",
        "category": "日式料理",
        "lat": 25.0268,
        "lng": 121.5434,
        "intensity": 4.3,
        "reason": "份量",
        "persona": "📏 規格說明",
        "review_text": "飯糰比想像中小，吃完沒有飽足感。",
        "owner_reply": "每份克數標示於菜單，建議可搭配套餐。",
        "reviews": 390,
        "owner_replies": 27,
    },
    {
        "store_id": "demo-011",
        "name": "土城暖心鍋物",
        "city": "新北市",
        "district": "土城區",
        "category": "火鍋",
        "lat": 24.9732,
        "lng": 121.4436,
        "intensity": 3.7,
        "reason": "服務",
        "persona": "🙏 正式道歉",
        "review_text": "加湯等了一段時間，可能現場比較忙。",
        "owner_reply": "很抱歉讓您久候，我們會調整尖峰時段的人力安排。",
        "reviews": 477,
        "owner_replies": 51,
    },
    {
        "store_id": "demo-012",
        "name": "北投溫柔甜湯",
        "city": "台北市",
        "district": "北投區",
        "category": "甜品",
        "lat": 25.1323,
        "lng": 121.4982,
        "intensity": 2.8,
        "reason": "品質",
        "persona": "🌱 溫和改善",
        "review_text": "今天紅豆稍微偏硬，其他部分都不錯。",
        "owner_reply": "謝謝您的提醒，我們會再調整紅豆熬煮時間。",
        "reviews": 322,
        "owner_replies": 39,
    },
]


DISTRICT_PATTERN = re.compile(
    r"(台北市|臺北市|新北市).*?([\u4e00-\u9fff]{1,4}(?:區|市))"
)


def _location_from_address(address: object) -> tuple[str, str]:
    text = "" if address is None else str(address)
    match = DISTRICT_PATTERN.search(text)

    if not match:
        return "雙北地區", "未分類"

    city = match.group(1).replace("臺", "台")
    return city, match.group(2)


def _normalise_intensity(review_score: object, owner_score: object) -> float:
    values: list[float] = []

    for value in (review_score, owner_score):
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue

    if not values or max(values) <= 0:
        return 1.0

    raw = max(values)
    # AI scores may be stored as either 0-10 or 0-100.
    if raw > 10:
        raw /= 10

    return round(max(1.0, min(raw, 10.0)), 1)


def _reason_from_text(row: pd.Series) -> str:
    text = " ".join(
        str(row.get(column, ""))
        for column in ("review_text", "owner_reply", "category")
    )

    keyword_groups = {
        "價格": ("價格", "太貴", "收費", "低消", "服務費"),
        "排隊": ("排隊", "久候", "等了", "等候", "訂位"),
        "態度": ("態度", "口氣", "不爽", "服務", "店員"),
        "份量": ("份量", "太少", "很小", "克數"),
        "品質": ("品質", "難吃", "不新鮮", "太硬", "太乾", "味道"),
    }

    for reason, keywords in keyword_groups.items():
        if any(keyword in text for keyword in keywords):
            return reason

    return "其他"


def _persona_from_row(row: pd.Series) -> str:
    owner_text = str(row.get("owner_reply", ""))
    sentiment = str(row.get("owner_sentiment", "")).lower()
    intensity = float(row.get("intensity", 1.0))

    if any(word in owner_text for word in ("抱歉", "改善", "謝謝", "致歉")):
        return "🙏 願意改善"
    if any(word in owner_text for word in ("不要來", "不缺", "不爽")):
        return "🔥 正面開戰"
    if "反串" in sentiment or any(word in owner_text for word in ("唯一", "恭喜", "精準")):
        return "🤡 高級反串"
    if intensity >= 8:
        return "😤 強硬防禦"
    if intensity >= 5:
        return "📣 理性反擊"
    return "🙂 禮貌說明"


def demo_dashboard_dataframe(limit: int = 300) -> pd.DataFrame:
    """Return deterministic fake data for development and presentation."""

    safe_limit = max(1, min(int(limit), len(DEMO_ROWS)))
    rows = [dict(row, __data_source="demo") for row in DEMO_ROWS[:safe_limit]]
    return pd.DataFrame(rows, columns=DASHBOARD_COLUMNS)


def _transform_database_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)

    if frame.empty:
        return frame

    locations = frame["address"].apply(_location_from_address)
    frame["city"] = locations.str[0]
    frame["district"] = locations.str[1]
    frame["intensity"] = frame.apply(
        lambda row: _normalise_intensity(
            row.get("review_score"),
            row.get("owner_score"),
        ),
        axis=1,
    )
    frame["reason"] = frame.apply(_reason_from_text, axis=1)
    frame["persona"] = frame.apply(_persona_from_row, axis=1)
    frame["reviews"] = pd.to_numeric(frame["reviews"], errors="coerce").fillna(0).astype(int)
    frame["owner_replies"] = (
        pd.to_numeric(frame["owner_replies"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    frame["lat"] = pd.to_numeric(frame["lat"], errors="coerce")
    frame["lng"] = pd.to_numeric(frame["lng"], errors="coerce")
    frame["__data_source"] = "database"

    frame = frame.dropna(subset=["lat", "lng"])
    frame = frame[frame["name"].fillna("").astype(str).str.strip().ne("")]

    return frame.reindex(columns=DASHBOARD_COLUMNS)


def get_dashboard_dataframe(limit: int = 300) -> pd.DataFrame:
    """Load PostgreSQL data, falling back to demo rows when unavailable/empty.

    This behaviour lets the team finish and demonstrate the dashboard before the
    crawler pipeline has inserted real data.  Once PostgreSQL contains store
    records, the same dashboard automatically switches to database rows.
    """

    try:
        rows = fetch_dashboard_rows(limit=limit)
        database_frame = _transform_database_rows(rows)

        if not database_frame.empty:
            return database_frame.reset_index(drop=True)
    except Exception:
        # The dashboard must remain demonstrable when PostgreSQL is offline.
        pass

    return demo_dashboard_dataframe(limit=limit).reset_index(drop=True)
