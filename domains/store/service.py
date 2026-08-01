"""Transform PostgreSQL rows (schema.sql) into Dashboard DataFrame.

正式路徑：repository.fetch_* → 本檔轉換 → dashboard/app.py
禁止：靜默改用假資料。DEMO seed 只在 domains/store/seed_rows.py。
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from domains.store.repository import (
    fetch_dashboard_rows,
    fetch_pr_reply_examples,
    fetch_store_reviews,
)


DASHBOARD_COLUMNS = [
    "store_id",
    "name",
    "city",
    "district",
    "category",
    "address",
    "store_url",
    "lat",
    "lng",
    "intensity",
    "reason",
    "persona",
    "guest_persona",
    "owner_persona",
    "guest_score",
    "owner_score",
    "guest_sentiment",
    "owner_sentiment",
    "review_text",
    "owner_reply",
    "pr_reply",
    "review_url",
    "reviews",
    "db_review_count",
    "owner_replies",
    "__data_source",
    "__error",
]

# 組長：沒吵架成分的不要放（1–2★ 已在 SQL；再擋低烈度）
MIN_DRAMA_INTENSITY = 5.5

DISTRICT_PATTERN = re.compile(
    r"(台北市|臺北市).*?([\u4e00-\u9fff]{1,4}區)"
)


def _location_from_address(address: object) -> tuple[str, str]:
    text = "" if address is None else str(address)
    match = DISTRICT_PATTERN.search(text)
    if not match:
        return "台北市", "未分類"
    return match.group(1).replace("臺", "台"), match.group(2)


def _normalise_intensity(
    review_score: object,
    owner_score: object,
    *,
    drama_stars: object = None,
    owner_reply: object = None,
) -> float:
    values: list[float] = []
    for value in (review_score, owner_score):
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue

    if values and max(values) > 0:
        raw = max(values)
        if raw > 10:
            raw /= 10
        return round(max(1.0, min(raw, 10.0)), 1)

    try:
        stars = float(drama_stars) if drama_stars else 3.0
    except (TypeError, ValueError):
        stars = 3.0
    stars = max(1.0, min(stars, 5.0))
    intensity = max(1.0, min(10.0, (6.0 - stars) * 1.6 + 1.0))
    owner_text = "" if owner_reply is None else str(owner_reply)
    if any(word in owner_text for word in ("不要來", "不缺", "不爽")):
        intensity = min(10.0, intensity + 2.5)
    elif owner_text and owner_text not in {"店家尚未回覆", ""}:
        intensity = min(10.0, intensity + 1.0)
    return round(intensity, 1)


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


def _persona_from_sentiment(
    sentiment: object,
    score: object,
    *,
    side: str,
    fallback_text: object = "",
) -> str:
    """Display label from schema ai_analysis sentiment + score."""

    sent = str(sentiment or "").lower().strip()
    try:
        value = float(score or 0)
    except (TypeError, ValueError):
        value = 0.0
    text = str(fallback_text or "")

    if side == "guest":
        if sent in {"negative", "怒", "負面"} or value >= 7:
            return "😤 憤怒客訴"
        if sent in {"positive", "正面"} or value <= 2:
            return "🙂 平和評價"
        if any(word in text for word in ("排隊", "久等", "態度")):
            return "🗯️ 據理力爭"
        return "😐 一般客評"

    if any(word in text for word in ("不要來", "不缺", "不爽")):
        return "🔥 正面開戰"
    if any(word in text for word in ("抱歉", "改善", "謝謝", "致歉")):
        return "🙏 願意改善"
    if "反串" in sent or any(word in text for word in ("唯一", "恭喜", "精準")):
        return "🤡 高級反串"
    if sent in {"negative", "怒", "負面"} or value >= 7:
        return "😤 強硬防禦"
    if value >= 4:
        return "📣 理性反擊"
    return "🙂 禮貌說明"


def _empty_frame(source: str, error: str = "") -> pd.DataFrame:
    frame = pd.DataFrame(columns=DASHBOARD_COLUMNS)
    frame.attrs["data_source"] = source
    frame.attrs["error"] = error
    return frame


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
            drama_stars=row.get("drama_stars"),
            owner_reply=row.get("owner_reply"),
        ),
        axis=1,
    )
    frame["reason"] = frame.apply(_reason_from_text, axis=1)
    frame["guest_score"] = pd.to_numeric(
        frame.get("review_score"), errors="coerce"
    ).fillna(0)
    frame["owner_score"] = pd.to_numeric(
        frame.get("owner_score"), errors="coerce"
    ).fillna(0)
    frame["guest_sentiment"] = frame.get(
        "review_sentiment", pd.Series([""] * len(frame))
    ).fillna("")
    frame["owner_sentiment"] = frame.get(
        "owner_sentiment", pd.Series([""] * len(frame))
    ).fillna("")
    frame["guest_persona"] = frame.apply(
        lambda row: _persona_from_sentiment(
            row.get("review_sentiment"),
            row.get("review_score"),
            side="guest",
            fallback_text=row.get("review_text"),
        ),
        axis=1,
    )
    frame["owner_persona"] = frame.apply(
        lambda row: _persona_from_sentiment(
            row.get("owner_sentiment"),
            row.get("owner_score"),
            side="owner",
            fallback_text=row.get("owner_reply"),
        ),
        axis=1,
    )
    frame["persona"] = frame["owner_persona"]
    frame["store_url"] = frame.get(
        "store_url", pd.Series([""] * len(frame))
    ).fillna("")
    frame["address"] = frame.get(
        "address", pd.Series([""] * len(frame))
    ).fillna("")
    frame["review_url"] = frame.get(
        "review_url", pd.Series([""] * len(frame))
    ).fillna("")
    if "pr_reply" not in frame.columns:
        frame["pr_reply"] = ""
    frame["pr_reply"] = frame["pr_reply"].fillna("").astype(str)
    frame["reviews"] = (
        pd.to_numeric(frame["reviews"], errors="coerce").fillna(0).astype(int)
    )
    frame["db_review_count"] = (
        pd.to_numeric(frame.get("db_review_count"), errors="coerce")
        .fillna(0)
        .astype(int)
    )
    frame["owner_replies"] = (
        pd.to_numeric(frame["owner_replies"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    frame["lat"] = pd.to_numeric(frame["lat"], errors="coerce")
    frame["lng"] = pd.to_numeric(frame["lng"], errors="coerce")
    frame["__data_source"] = "database"
    frame["__error"] = ""

    frame = frame.dropna(subset=["lat", "lng"])
    frame = frame[frame["name"].fillna("").astype(str).str.strip().ne("")]
    frame = frame[frame["city"] == "台北市"]
    frame = frame[frame["intensity"] >= MIN_DRAMA_INTENSITY]
    soft_personas = {"🙂 禮貌說明", "🌱 溫和改善"}
    frame = frame[
        ~((frame["intensity"] < 7.0) & (frame["owner_persona"].isin(soft_personas)))
    ]

    return frame.reindex(columns=DASHBOARD_COLUMNS)


def get_store_reviews_dataframe(place_id: str, limit: int = 50) -> pd.DataFrame:
    """READ schema.sql review + ai_analysis for one store (many rows)."""

    rows = fetch_store_reviews(place_id, limit=limit)
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    frame["guest_persona"] = frame.apply(
        lambda row: _persona_from_sentiment(
            row.get("guest_sentiment"),
            row.get("guest_score"),
            side="guest",
            fallback_text=row.get("review_text"),
        ),
        axis=1,
    )
    frame["owner_persona"] = frame.apply(
        lambda row: _persona_from_sentiment(
            row.get("owner_sentiment"),
            row.get("owner_score"),
            side="owner",
            fallback_text=row.get("owner_reply"),
        ),
        axis=1,
    )
    return frame


def get_pr_reply_examples(limit: int = 20) -> pd.DataFrame:
    """READ ai_analysis.pr_reply examples for 公關回覆教室."""

    rows = fetch_pr_reply_examples(limit=limit)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_dashboard_dataframe(limit: int = 300) -> pd.DataFrame:
    """Load Taipei drama stores from PostgreSQL only. No demo fallback."""

    try:
        rows = fetch_dashboard_rows(limit=limit)
        database_frame = _transform_database_rows(rows)
        if database_frame.empty:
            empty = _empty_frame("database_empty")
            empty.attrs["error"] = (
                "已連線 PostgreSQL，但沒有符合條件的台北市吵架店家"
                "（需 store + 1–2★ review）。不會顯示假資料。"
            )
            return empty
        result = database_frame.reset_index(drop=True)
        result.attrs["data_source"] = "database"
        result.attrs["error"] = ""
        return result
    except Exception as exc:
        empty = _empty_frame("error", str(exc))
        empty.attrs["error"] = f"PostgreSQL 讀取失敗：{exc}"
        return empty
