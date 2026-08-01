"""Review domain orchestration: resolve placeIds → Apify → ETL → PostgreSQL."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from domains.review.client import ACTOR_ID, check_status, get_dataset, start_review_actor
from domains.review.etl import transform_raw_reviews
from domains.review.repository import (
    fetch_place_ids_for_review,
    fetch_stores_for_review,
    filter_existing_place_ids,
    save_review_batch,
    write_execution_log,
)

PipelineMode = Literal["initial", "daily", "manual"]


def resolve_place_ids(
    place_ids: list[str] | None = None,
    *,
    store_limit: int = 20,
) -> tuple[list[str], str]:
    """Resolve placeIds from CLI args or PostgreSQL store (Taipei only)."""

    if place_ids:
        cleaned = [pid.strip() for pid in place_ids if pid and pid.strip()]
        if cleaned:
            return cleaned, "argument"

    from_store = fetch_place_ids_for_review(limit=store_limit)
    if from_store:
        return from_store, "store"

    raise RuntimeError(
        "store 表沒有台北市店家可抓評論。"
        "請先寫入 store（address 含「台北市」），"
        "或執行: uv run python -m domains.review.run_dev_setup"
    )


def initial_max_reviews(one_star: int, two_star: int, *, buffer: int = 50) -> int:
    """R002: first fetch = 1★ + 2★ count + 50."""

    return max(1, int(one_star) + int(two_star) + buffer)


def build_actor_input(
    place_ids: list[str],
    *,
    max_reviews: int = 5,
    reviews_sort: str = "newest",
    reviews_start_date: str | None = None,
    language: str = "zh-TW",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "language": language,
        "maxReviews": max(1, int(max_reviews)),
        "personalData": True,
        "placeIds": place_ids,
        "reviewsSort": reviews_sort,
        "reviewsFilterString": "",
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
        state = getattr(status, "status", None) or status.get("status")

        if state == "SUCCEEDED":
            return status

        if state in {"FAILED", "ABORTED", "TIMED-OUT"}:
            raise RuntimeError(f"Apify actor failed with status: {state}")

        if time.time() >= deadline:
            raise TimeoutError(
                f"Apify actor timed out after {timeout_seconds}s (run_id={run_id})"
            )

        time.sleep(poll_seconds)


def fetch_reviews_from_apify(
    place_ids: list[str],
    *,
    max_reviews: int = 5,
    reviews_sort: str = "newest",
    reviews_start_date: str | None = None,
    use_mock: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if use_mock:
        from domains.review.mock_client import fetch_mock_reviews

        return fetch_mock_reviews(
            place_ids,
            max_reviews=max_reviews,
            reviews_sort=reviews_sort,
            reviews_start_date=reviews_start_date,
        )

    params = build_actor_input(
        place_ids,
        max_reviews=max_reviews,
        reviews_sort=reviews_sort,
        reviews_start_date=reviews_start_date,
    )
    run = start_review_actor(params)
    run_id = run.id
    finished = wait_for_actor(run_id)

    dataset_id = getattr(finished, "default_dataset_id", None)
    if dataset_id is None and isinstance(finished, dict):
        dataset_id = finished.get("defaultDatasetId") or finished.get(
            "default_dataset_id"
        )

    if not dataset_id:
        raise RuntimeError(f"Apify run {run_id} has no dataset id")

    items = get_dataset(dataset_id)
    meta = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "request": params,
        "item_count": len(items),
    }
    return items, meta


def ingest_raw_reviews(
    raw_items: list[dict[str, Any]],
    *,
    scraped_at: datetime | None = None,
) -> dict[str, int]:
    source_rows, review_rows, stats = transform_raw_reviews(
        raw_items,
        scraped_at=scraped_at or datetime.now(timezone.utc),
    )
    source_count, review_count = save_review_batch(source_rows, review_rows)
    return {
        **stats,
        "source_upserted": source_count,
        "review_upserted": review_count,
    }


def _filter_raw_by_place_ids(
    raw_items: list[dict[str, Any]],
    allowed: set[str],
) -> list[dict[str, Any]]:
    return [
        item
        for item in raw_items
        if isinstance(item, dict) and str(item.get("placeId")) in allowed
    ]


def run_review_pipeline(
    place_ids: list[str] | None = None,
    *,
    mode: PipelineMode = "manual",
    store_limit: int = 20,
    max_reviews: int = 5,
    reviews_sort: str = "newest",
    reviews_start_date: str | None = None,
    dry_run: bool = False,
    require_store_fk: bool = True,
    use_mock: bool = False,
) -> dict[str, Any]:
    """Full Review pipeline for manual runs."""

    started_at = datetime.now(timezone.utc)
    resolved_ids, source = resolve_place_ids(place_ids, store_limit=store_limit)
    missing_in_store: list[str] = []

    if require_store_fk and not dry_run:
        existing_ids = filter_existing_place_ids(resolved_ids)
        missing_in_store = [pid for pid in resolved_ids if pid not in set(existing_ids)]
        resolved_ids = existing_ids
        if not resolved_ids:
            raise RuntimeError(
                "沒有可用的 placeId 可寫入 review。"
                "請先讓 Store domain 寫入 store 表。"
                f"（缺少: {missing_in_store or '未知'}）"
            )

    result: dict[str, Any] = {
        "mode": mode,
        "place_id_source": source,
        "place_ids": resolved_ids,
        "place_ids_missing_in_store": missing_in_store,
        "dry_run": dry_run,
    }

    try:
        raw_items, meta = fetch_reviews_from_apify(
            resolved_ids,
            max_reviews=max_reviews,
            reviews_sort=reviews_sort,
            reviews_start_date=reviews_start_date,
            use_mock=use_mock,
        )
        result["apify"] = meta
        result["use_mock"] = use_mock

        if dry_run:
            _, _, stats = transform_raw_reviews(raw_items)
            result["etl"] = {**stats, "source_upserted": 0, "review_upserted": 0}
        else:
            if require_store_fk:
                raw_items = _filter_raw_by_place_ids(raw_items, set(resolved_ids))
            result["etl"] = ingest_raw_reviews(raw_items)

        if not dry_run:
            write_execution_log(
                pipeline=f"review_{mode}",
                status="success",
                items_count=result.get("etl", {}).get("review_upserted", 0),
                apify_scheduler_id=meta.get("run_id"),
                actor_name=ACTOR_ID,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                request_json=meta.get("request"),
                response_json={"dataset_id": meta.get("dataset_id"), "etl": result.get("etl")},
            )
        return result
    except Exception as exc:
        if not dry_run:
            write_execution_log(
                pipeline=f"review_{mode}",
                status="failed",
                apify_scheduler_id=None,
                actor_name=ACTOR_ID,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                error_msg=str(exc),
            )
        raise


def run_initial_fetch(
    *,
    store_limit: int = 20,
    dry_run: bool = False,
    use_mock: bool = False,
) -> dict[str, Any]:
    """Step 2-A: first-time fetch per store (1★+2★+50, sort=newest)."""

    started_at = datetime.now(timezone.utc)
    stores = fetch_stores_for_review(limit=store_limit)
    if not stores:
        raise RuntimeError(
            "store 表沒有台北市店家可抓評論。"
            "請先寫入 store（address 含「台北市」）。"
        )

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

    try:
        for store in stores:
            place_id = str(store["placeId"])
            max_reviews = initial_max_reviews(store.get("oneStar", 0), store.get("twoStar", 0))
            run_result: dict[str, Any] = {
                "placeId": place_id,
                "maxReviews": max_reviews,
            }

            if dry_run:
                run_result["dry_run"] = True
                aggregate["runs"].append(run_result)
                continue

            raw_items, meta = fetch_reviews_from_apify(
                [place_id],
                max_reviews=max_reviews,
                reviews_sort="newest",
                use_mock=use_mock,
            )
            raw_items = _filter_raw_by_place_ids(raw_items, {place_id})
            etl = ingest_raw_reviews(raw_items)
            run_result["apify"] = meta
            run_result["etl"] = etl
            aggregate["runs"].append(run_result)

            for key in ("raw_count", "source_upserted", "review_upserted", "skipped"):
                aggregate["etl"][key] = aggregate["etl"].get(key, 0) + etl.get(key, 0)

        if not dry_run:
            write_execution_log(
                pipeline="review_initial",
                status="success",
                items_count=aggregate["etl"]["review_upserted"],
                actor_name=ACTOR_ID,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                response_json={"stores": aggregate["stores"], "runs": len(aggregate["runs"])},
            )
        return aggregate
    except Exception as exc:
        if not dry_run:
            write_execution_log(
                pipeline="review_initial",
                status="failed",
                actor_name=ACTOR_ID,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                error_msg=str(exc),
            )
        raise


def run_daily_fetch(
    *,
    store_limit: int = 50,
    dry_run: bool = False,
    use_mock: bool = False,
) -> dict[str, Any]:
    """Step 2-B: daily fetch (lowestRating + yesterday)."""

    started_at = datetime.now(timezone.utc)
    place_ids = fetch_place_ids_for_review(limit=store_limit)
    if not place_ids:
        raise RuntimeError(
            "store 表沒有台北市店家可抓評論。"
            "請先寫入 store（address 含「台北市」）。"
        )

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    result: dict[str, Any] = {
        "mode": "daily",
        "place_ids": place_ids,
        "reviews_start_date": yesterday,
        "reviews_sort": "lowestRating",
        "dry_run": dry_run,
    }

    try:
        if dry_run:
            result["etl"] = {"source_upserted": 0, "review_upserted": 0}
            return result

        raw_items, meta = fetch_reviews_from_apify(
            place_ids,
            max_reviews=100,
            reviews_sort="lowestRating",
            reviews_start_date=yesterday,
            use_mock=use_mock,
        )
        raw_items = _filter_raw_by_place_ids(raw_items, set(place_ids))
        result["apify"] = meta
        result["etl"] = ingest_raw_reviews(raw_items)

        write_execution_log(
            pipeline="review_daily",
            status="success",
            items_count=result["etl"]["review_upserted"],
            apify_scheduler_id=meta.get("run_id"),
            actor_name=ACTOR_ID,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            request_json=meta.get("request"),
            response_json={"dataset_id": meta.get("dataset_id"), "etl": result["etl"]},
        )
        return result
    except Exception as exc:
        write_execution_log(
            pipeline="review_daily",
            status="failed",
            actor_name=ACTOR_ID,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            error_msg=str(exc),
        )
        raise
