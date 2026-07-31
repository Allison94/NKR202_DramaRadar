"""
只負責處理 Google Maps Reviews API 連線與取得資料，
不處理資料清洗、轉換或寫入資料庫。
"""

from __future__ import annotations

from typing import Any

from apify_client import ApifyClient

from shared.config import settings


client = ApifyClient(settings.apify_review)

ACTOR_ID = "compass/google-maps-reviews-scraper"


def start_review_actor(params: dict[str, Any], *, max_total_charge_usd: float = 0.05):
    """啟動 Google Maps Reviews Scraper。"""
    actor = client.actor(ACTOR_ID)

    return actor.start(
        run_input=params,
        max_total_charge_usd=max_total_charge_usd,
    )


def check_status(run_id: str):
    """查詢 Actor 執行狀態。"""
    return client.run(run_id).get()


def get_dataset(dataset_id: str) -> list[dict]:
    """根據 Dataset ID 取得評論資料。"""
    return list(client.dataset(dataset_id).list_items().items)