"""Build chart-ready DataFrames from PostgreSQL for Dashboard."""

from __future__ import annotations

from typing import Any

import pandas as pd

from domains.store.repository import (
    fetch_dashboard_rows,
    fetch_review_star_distribution,
    fetch_store_intensity_ranking,
)


def get_store_chart_frame(limit: int = 300) -> pd.DataFrame:
    rows = fetch_dashboard_rows(limit=limit)
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    frame["intensity"] = frame.apply(
        lambda r: _intensity_from_row(r),
        axis=1,
    )
    return frame


def _intensity_from_row(row: pd.Series) -> float:
    review_score = float(row.get("review_score") or 0)
    owner_score = float(row.get("owner_score") or 0)
    if max(review_score, owner_score) > 0:
        raw = max(review_score, owner_score)
        if raw > 10:
            raw /= 10
        return round(max(1.0, min(raw, 10.0)), 1)

    stars = float(row.get("drama_stars") or 3)
    intensity = max(1.0, min(10.0, (6.0 - stars) * 1.6 + 1.0))
    owner = str(row.get("owner_reply") or "")
    if any(w in owner for w in ("不要來", "不缺", "不爽")):
        intensity = min(10.0, intensity + 2.5)
    elif owner and owner not in {"店家尚未回覆", ""}:
        intensity = min(10.0, intensity + 1.0)
    return round(intensity, 1)


def reason_chart_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "reason" not in df.columns:
        return pd.DataFrame(columns=["糾紛類型", "店家數"])
    return (
        df["reason"]
        .value_counts()
        .rename_axis("糾紛類型")
        .reset_index(name="店家數")
    )


def persona_chart_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "persona" not in df.columns:
        return pd.DataFrame(columns=["店家人設", "店家數"])
    return (
        df["persona"]
        .value_counts()
        .rename_axis("店家人設")
        .reset_index(name="店家數")
    )


def district_chart_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["地區", "平均烈度", "店家數"])

    grouped = (
        df.groupby(["city", "district"], as_index=False)
        .agg(平均烈度=("intensity", "mean"), 店家數=("store_id", "count"))
    )
    grouped["地區"] = grouped["city"] + grouped["district"]
    return grouped.sort_values("平均烈度", ascending=False)


def intensity_bucket_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["烈度區間", "店家數"])

    bins = [0, 3, 5, 7, 9, 10.1]
    labels = ["1–3 理性", "4–5 升溫", "6–7 激烈", "8–9 火爆", "10 史詩"]
    bucketed = pd.cut(df["intensity"], bins=bins, labels=labels, right=True)
    return (
        bucketed.value_counts(sort=False)
        .rename_axis("烈度區間")
        .reset_index(name="店家數")
    )


def star_distribution_data() -> pd.DataFrame:
    rows = fetch_review_star_distribution()
    if not rows:
        return pd.DataFrame(columns=["星等", "評論數"])
    frame = pd.DataFrame(rows)
    frame["星等"] = frame["stars"].astype(str) + " 星"
    return frame.rename(columns={"review_count": "評論數"})[["星等", "評論數"]]


def top_intensity_data(limit: int = 10) -> pd.DataFrame:
    rows = fetch_store_intensity_ranking(limit=limit)
    if not rows:
        return pd.DataFrame(columns=["店家", "烈度"])
    frame = pd.DataFrame(rows)
    return frame.rename(columns={"name": "店家", "intensity": "烈度"})


def scatter_intensity_reviews(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["reviews", "intensity", "name"])
    # 散點用 DB 評論數，避免 Google reviewsCount 膨脹
    frame = df.copy()
    if "db_review_count" in frame.columns:
        frame["reviews"] = frame["db_review_count"]
    return frame[["name", "reviews", "intensity"]].rename(columns={"name": "店家"})
