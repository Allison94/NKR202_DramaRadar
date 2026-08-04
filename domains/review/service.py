"""Review pipeline: store → Apify → ETL → review_source / review.

Rules (R002 + 組長):
- initial: maxReviews = oneStar + twoStar + 50, sort=newest
- daily: sort=lowestRating, reviewsStartDate=昨天（只抓新留言，不是全抓）
- skip_review_fetch=TRUE 的店不抓
- 不用 API 端 reviewsFilterString（貴）
- 每次 API 觸發都寫 execution_log（request + response/error）
- owner_reply_recheck / next_check_at 決定要不要再查老闆回覆
"""

from __future__ import annotations

import time
import traceback
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from domains.review.client import ACTOR_ID, check_status, get_dataset, start_review_actor
from domains.review.etl import transform_raw_reviews
from domains.review.logging_setup import get_logger
from domains.review.repository import (
    fetch_place_ids_for_review,
    fetch_reviews_needing_recheck,
    fetch_stores_for_review,
    filter_existing_place_ids,
    save_review_batch,
    write_execution_log,
)

log = get_logger(__name__)

PipelineMode = Literal["initial", "daily", "recheck", "manual"]


def initial_max_reviews(one_star: int, two_star: int, *, buffer: int = 50) -> int:
    return max(1, int(one_star) + int(two_star) + buffer)


def build_actor_input(
    place_ids: list[str],
    *,
    max_reviews: int,
    reviews_sort: str,
    reviews_start_date: str | None = None,
    language: str = "zh-TW",
) -> dict[str, Any]:
    """組 Apify input。刻意不帶昂貴的 reviewsFilterString。"""

    payload: dict[str, Any] = {
        "language": language,
        "maxReviews": max(1, int(max_reviews)),
        "personalData": True,
        "placeIds": place_ids,
        "reviewsSort": reviews_sort,
        "reviewsFilterString": "",  # 不用 API 篩選，本地 ETL 處理
        "reviewsOrigin": "all",
    }
    if reviews_start_date:
        payload["reviewsStartDate"] = reviews_start_date
    return payload


def wait_for_actor(
    run_id: str,
    *,
    poll_seconds: int = 5,
    timeout_seconds: int = 900,
) -> Any:
    deadline = time.time() + timeout_seconds
    while True:
        status = check_status(run_id)
        state = getattr(status, "status", None) or (
            status.get("status") if isinstance(status, dict) else None
        )
        if state == "SUCCEEDED":
            return status
        if state in {"FAILED", "ABORTED", "TIMED-OUT"}:
            raise RuntimeError(f"Apify actor failed: {state} (run_id={run_id})")
        if time.time() >= deadline:
            raise TimeoutError(f"Apify timeout {timeout_seconds}s run_id={run_id}")
        time.sleep(poll_seconds)


def _dataset_id_from_status(status: Any) -> str | None:
    dataset_id = getattr(status, "default_dataset_id", None)
    if dataset_id:
        return str(dataset_id)
    if isinstance(status, dict):
        return status.get("defaultDatasetId") or status.get("default_dataset_id")
    return None


def fetch_reviews_from_apify(
    place_ids: list[str],
    *,
    pipeline: str,
    max_reviews: int,
    reviews_sort: str,
    reviews_start_date: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """呼叫 Apify；無論成功失敗都寫 execution_log。"""

    started = datetime.now(timezone.utc)
    params = build_actor_input(
        place_ids,
        max_reviews=max_reviews,
        reviews_sort=reviews_sort,
        reviews_start_date=reviews_start_date,
    )
    run_id: str | None = None

    # 觸發當下先記一筆 started（有 request）
    write_execution_log(
        pipeline=pipeline,
        status="started",
        items_count=0,
        actor_name=ACTOR_ID,
        started_at=started,
        request_json=params,
        response_json={},
    )

    try:
        run = start_review_actor(params)
        run_id = str(getattr(run, "id", None) or run.get("id"))
        finished = wait_for_actor(run_id)
        dataset_id = _dataset_id_from_status(finished)
        if not dataset_id:
            raise RuntimeError(f"Apify run {run_id} has no dataset id")

        items = get_dataset(dataset_id)
        meta = {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "request": params,
            "item_count": len(items),
        }
        write_execution_log(
            pipeline=pipeline,
            status="success",
            items_count=len(items),
            apify_scheduler_id=run_id,
            actor_name=ACTOR_ID,
            started_at=started,
            finished_at=datetime.now(timezone.utc),
            request_json=params,
            response_json={
                "dataset_id": dataset_id,
                "item_count": len(items),
                "run_status": "SUCCEEDED",
            },
        )
        return items, meta
    except Exception as exc:
        log.exception("Apify fetch failed pipeline=%s", pipeline)
        write_execution_log(
            pipeline=pipeline,
            status="failed",
            items_count=0,
            apify_scheduler_id=run_id,
            actor_name=ACTOR_ID,
            started_at=started,
            finished_at=datetime.now(timezone.utc),
            request_json=params,
            response_json={},
            error_msg=f"{exc}\n{traceback.format_exc()}",
        )
        raise


def ingest_raw_reviews(raw_items: list[dict[str, Any]]) -> dict[str, int]:
    source_rows, review_rows, stats = transform_raw_reviews(raw_items)
    source_count, review_count = save_review_batch(source_rows, review_rows)
    return {
        **stats,
        "source_upserted": source_count,
        "review_upserted": review_count,
    }


def run_initial_fetch(*, store_limit: int = 50, dry_run: bool = False) -> dict[str, Any]:
    """第一次全量：每店 maxReviews = 1★+2★+50，sort=newest。"""

    log.info("run_initial_fetch store_limit=%s dry_run=%s", store_limit, dry_run)
    stores = fetch_stores_for_review(limit=store_limit)
    if not stores:
        log.warning("initial: store 無可抓店家（blocked=FALSE 且 skip_review_fetch=FALSE）")
        return {
            "mode": "initial",
            "stores": 0,
            "runs": [],
            "etl": {
                "raw_count": 0,
                "source_upserted": 0,
                "review_upserted": 0,
                "skipped": 0,
            },
            "message": "store 空或皆 skip_review_fetch=TRUE",
        }

    aggregate: dict[str, Any] = {
        "mode": "initial",
        "stores": len(stores),
        "runs": [],
        "etl": {
            "raw_count": 0,
            "source_upserted": 0,
            "review_upserted": 0,
            "skipped": 0,
        },
    }

    for store in stores:
        place_id = str(store["placeId"])
        max_reviews = initial_max_reviews(
            store.get("oneStar", 0),
            store.get("twoStar", 0),
        )
        run_info: dict[str, Any] = {
            "placeId": place_id,
            "maxReviews": max_reviews,
        }
        if dry_run:
            aggregate["runs"].append({**run_info, "dry_run": True})
            continue

        raw_items, meta = fetch_reviews_from_apify(
            [place_id],
            pipeline="review_initial",
            max_reviews=max_reviews,
            reviews_sort="newest",
        )
        raw_items = [
            item
            for item in raw_items
            if isinstance(item, dict) and str(item.get("placeId")) == place_id
        ]
        etl = ingest_raw_reviews(raw_items)
        run_info["apify"] = meta
        run_info["etl"] = etl
        aggregate["runs"].append(run_info)
        for key in ("raw_count", "source_upserted", "review_upserted", "skipped"):
            aggregate["etl"][key] = aggregate["etl"].get(key, 0) + etl.get(key, 0)

    return aggregate


def run_daily_fetch(*, store_limit: int = 100, dry_run: bool = False) -> dict[str, Any]:
    """每日增量：昨天留言 + lowestRating。不是一次抓全部。"""

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    log.info(
        "run_daily_fetch store_limit=%s reviewsStartDate=%s",
        store_limit,
        yesterday,
    )
    place_ids = fetch_place_ids_for_review(limit=store_limit)
    if not place_ids:
        log.warning("daily: store 無可抓店家（blocked=FALSE 且 skip_review_fetch=FALSE）")
        return {
            "mode": "daily",
            "place_ids": [],
            "reviews_start_date": yesterday,
            "reviews_sort": "lowestRating",
            "dry_run": dry_run,
            "etl": {"source_upserted": 0, "review_upserted": 0},
            "message": "store 空或皆 skip_review_fetch=TRUE",
        }

    result: dict[str, Any] = {
        "mode": "daily",
        "place_ids": place_ids,
        "reviews_start_date": yesterday,
        "reviews_sort": "lowestRating",
        "dry_run": dry_run,
    }
    if dry_run:
        result["etl"] = {"source_upserted": 0, "review_upserted": 0}
        return result

    # 每日用較小 maxReviews，靠 reviewsStartDate 抓新資料，省錢
    raw_items, meta = fetch_reviews_from_apify(
        place_ids,
        pipeline="review_daily",
        max_reviews=50,
        reviews_sort="lowestRating",
        reviews_start_date=yesterday,
    )
    allowed = set(place_ids)
    raw_items = [
        item
        for item in raw_items
        if isinstance(item, dict) and str(item.get("placeId")) in allowed
    ]
    result["apify"] = meta
    result["etl"] = ingest_raw_reviews(raw_items)

    # 同一天順便處理該查老闆回覆的評論
    recheck = run_owner_reply_recheck(limit=100)
    result["owner_reply_recheck"] = recheck
    return result


def run_owner_reply_recheck(*, limit: int = 100, dry_run: bool = False) -> dict[str, Any]:
    """依 owner_reply_recheck / next_check_at 再抓需要補老闆回覆的店。"""

    due = fetch_reviews_needing_recheck(limit=limit)
    place_ids = sorted({str(row["placeId"]) for row in due if row.get("placeId")})
    place_ids = filter_existing_place_ids(place_ids)
    result: dict[str, Any] = {
        "mode": "recheck",
        "due_reviews": len(due),
        "place_ids": place_ids,
        "dry_run": dry_run,
    }
    if not place_ids or dry_run:
        result["etl"] = {"source_upserted": 0, "review_upserted": 0}
        return result

    raw_items, meta = fetch_reviews_from_apify(
        place_ids,
        pipeline="review_owner_recheck",
        max_reviews=20,
        reviews_sort="newest",
    )
    allowed = set(place_ids)
    raw_items = [
        item
        for item in raw_items
        if isinstance(item, dict) and str(item.get("placeId")) in allowed
    ]
    result["apify"] = meta
    result["etl"] = ingest_raw_reviews(raw_items)
    return result


def run_review_pipeline(
    place_ids: list[str] | None = None,
    *,
    mode: PipelineMode = "manual",
    store_limit: int = 20,
    max_reviews: int = 5,
    reviews_sort: str = "newest",
    reviews_start_date: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """手動單次測試。"""

    if mode == "initial":
        return run_initial_fetch(store_limit=store_limit, dry_run=dry_run)
    if mode == "daily":
        return run_daily_fetch(store_limit=store_limit, dry_run=dry_run)
    if mode == "recheck":
        return run_owner_reply_recheck(limit=store_limit, dry_run=dry_run)

    if place_ids:
        resolved = filter_existing_place_ids(place_ids)
    else:
        resolved = fetch_place_ids_for_review(limit=store_limit)
    if not resolved:
        raise RuntimeError("沒有可用 placeId（請確認 store 且 skip_review_fetch=FALSE）")

    result: dict[str, Any] = {
        "mode": "manual",
        "place_ids": resolved,
        "dry_run": dry_run,
    }
    if dry_run:
        result["etl"] = {"source_upserted": 0, "review_upserted": 0}
        return result

    raw_items, meta = fetch_reviews_from_apify(
        resolved,
        pipeline="review_manual",
        max_reviews=max_reviews,
        reviews_sort=reviews_sort,
        reviews_start_date=reviews_start_date,
    )
    allowed = set(resolved)
    raw_items = [
        item
        for item in raw_items
        if isinstance(item, dict) and str(item.get("placeId")) in allowed
    ]
    result["apify"] = meta
    result["etl"] = ingest_raw_reviews(raw_items)
    return result
