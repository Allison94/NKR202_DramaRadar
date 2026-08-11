"""Apify Google Maps Reviews client — connect / start / poll / dataset only.

不做 ETL、不寫 DB。昂貴的 API 端篩選（reviewsFilterString）一律不用，
改在本地 filters/etl 處理。
"""

from __future__ import annotations

from typing import Any

from apify_client import ApifyClient

from domains.review.logging_setup import get_logger
from shared.config import settings

log = get_logger(__name__)

client = ApifyClient(settings.apify_review)
ACTOR_ID = "compass/google-maps-reviews-scraper"


def start_review_actor(
    params: dict[str, Any],
    *,
    max_total_charge_usd: float = 0.5,
) -> Any:
    """啟動 Actor。不帶 reviewsFilterString（API 端過濾很貴）。"""

    token = (settings.apify_review or "").strip()
    if not token:
        raise RuntimeError(
            "缺少 APIFY_REVIEW token（.env）。"
            "請填入 Apify token 後再跑 Google Maps Reviews Scraper。"
        )

    safe = dict(params)
    # 強制關閉昂貴篩選
    safe["reviewsFilterString"] = ""
    log.info(
        "start_review_actor placeIds=%s maxReviews=%s sort=%s startDate=%s",
        safe.get("placeIds"),
        safe.get("maxReviews"),
        safe.get("reviewsSort"),
        safe.get("reviewsStartDate"),
    )
    return client.actor(ACTOR_ID).start(
        run_input=safe,
        max_total_charge_usd=max_total_charge_usd,
    )


def check_status(run_id: str) -> Any:
    status = client.run(run_id).get()
    state = getattr(status, "status", None) or (
        status.get("status") if isinstance(status, dict) else None
    )
    log.debug("check_status run_id=%s state=%s", run_id, state)
    return status


def get_dataset(dataset_id: str) -> list[dict]:
    items = list(client.dataset(dataset_id).list_items().items)
    log.info("get_dataset dataset_id=%s items=%s", dataset_id, len(items))
    return items
