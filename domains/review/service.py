"""Review service layer.

Responsibilities:
- Build Apify request payloads.
- Prepare Initial / Daily / Recheck batches.
- Start Apify Actor runs.
- Check one Actor status per call (no polling loop here).
- Read finished datasets and run Review ETL.
- Update store.skip_review_fetch when generic PR replies are detected.

Airflow DAG owns:
- parallel execution
- status polling
- 120-second recheck interval
"""

from __future__ import annotations

import traceback
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from domains.review.config import (
    BATCH_SIZE,
    INITIAL_BUFFER,
    INITIAL_SORT,
    DAILY_SORT,
    RECHECK_AFTER_DAYS,
    RECHECK_MAX_AGE_DAYS,
)
from domains.review.client import (
    ACTOR_ID,
    check_status,
    get_dataset,
    start_review_actor,
)
from domains.review.etl import transform_raw_reviews
from domains.review.logging_setup import get_logger
from domains.review.repository import (
    fetch_place_ids_for_review,
    fetch_reviews_needing_recheck,
    fetch_stores_for_review,
    filter_existing_place_ids,
    mark_stores_skip_review_fetch,
    save_review_batch,
    update_review_recheck_states,
    write_execution_log,
)


log = get_logger(__name__)

PipelineMode = Literal["initial", "daily", "recheck", "manual"]



def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _chunked(values: list[Any], size: int = BATCH_SIZE) -> list[list[Any]]:
    if size <= 0:
        raise ValueError("batch size must be > 0")

    return [
        values[index:index + size]
        for index in range(0, len(values), size)
    ]


def initial_max_reviews(
    one_star: int,
    two_star: int,
    *,
    buffer: int = INITIAL_BUFFER,
) -> int:
    """Initial rule: maxReviews = oneStar + twoStar + 50."""
    return int(one_star or 0) + int(two_star or 0) + int(buffer)


def build_actor_input(
    place_ids: list[str],
    *,
    max_reviews: int | None,
    reviews_sort: str | None,
    reviews_start_date: str | None = None,
    language: str = "zh-TW",
) -> dict[str, Any]:
    """Build Compass Google Maps Reviews Scraper input."""

    payload: dict[str, Any] = {
        "language": language,
        "personalData": True,
        "placeIds": place_ids,
        "reviewsFilterString": "",
        "reviewsOrigin": "all",
    }

    if reviews_sort:
        payload["reviewsSort"] = reviews_sort

    if max_reviews is not None:
        payload["maxReviews"] = int(max_reviews)

    if reviews_start_date:
        payload["reviewsStartDate"] = reviews_start_date

    return payload


def _status_state(status: Any) -> str | None:
    state = getattr(status, "status", None)

    if state:
        return str(state)

    if isinstance(status, dict):
        value = status.get("status")
        return str(value) if value is not None else None

    return None


def _dataset_id_from_status(status: Any) -> str | None:
    dataset_id = getattr(status, "default_dataset_id", None)

    if dataset_id:
        return str(dataset_id)

    if isinstance(status, dict):
        value = (
            status.get("defaultDatasetId")
            or status.get("default_dataset_id")
        )
        return str(value) if value else None

    return None


def start_apify_run(
    place_ids: list[str],
    *,
    pipeline: str,
    max_reviews: int | None,
    reviews_sort: str | None,
    reviews_start_date: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Start Actor only.

    This function does NOT wait and does NOT poll.
    Airflow DAG is responsible for status polling.
    """

    params = build_actor_input(
        place_ids,
        max_reviews=max_reviews,
        reviews_sort=reviews_sort,
        reviews_start_date=reviews_start_date,
    )

    started = _utcnow()

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
        run_id = str(
            getattr(run, "id", None)
            or (run.get("id") if isinstance(run, dict) else "")
        )

        if not run_id:
            raise RuntimeError("Apify start_review_actor returned no run id")

        return {
            "pipeline": pipeline,
            "run_id": run_id,
            "place_ids": list(place_ids),
            "request": params,
            "started_at": started.isoformat(),
            "context": context or {},
        }

    except Exception as exc:
        write_execution_log(
            pipeline=pipeline,
            status="failed",
            items_count=0,
            actor_name=ACTOR_ID,
            started_at=started,
            finished_at=_utcnow(),
            request_json=params,
            response_json={},
            error_msg=f"{exc}\n{traceback.format_exc()}",
        )
        raise


def check_apify_run(run_info: dict[str, Any]) -> dict[str, Any]:
    """
    Check Actor exactly once.

    Airflow sensor calls this function every 120 seconds.
    There is intentionally no while-loop / sleep here.
    """

    run_id = str(run_info["run_id"])
    status = check_status(run_id)
    state = _status_state(status)

    if state == "SUCCEEDED":
        dataset_id = _dataset_id_from_status(status)

        if not dataset_id:
            raise RuntimeError(
                f"Apify run {run_id} SUCCEEDED but has no dataset id"
            )

        return {
            **run_info,
            "done": True,
            "run_status": state,
            "dataset_id": dataset_id,
        }

    if state in {"FAILED", "ABORTED", "TIMED-OUT"}:
        started_at = _parse_datetime(run_info.get("started_at"))

        write_execution_log(
            pipeline=str(run_info["pipeline"]),
            status="failed",
            items_count=0,
            apify_scheduler_id=run_id,
            actor_name=ACTOR_ID,
            started_at=started_at,
            finished_at=_utcnow(),
            request_json=dict(run_info.get("request") or {}),
            response_json={"run_status": state},
            error_msg=f"Apify actor terminal state: {state}",
        )

        raise RuntimeError(
            f"Apify actor failed: {state} (run_id={run_id})"
        )

    return {
        **run_info,
        "done": False,
        "run_status": state or "UNKNOWN",
    }


def ingest_raw_reviews(
    raw_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    ETL + DB write.

    transform_raw_reviews already enforces:
    - DB only keeps 1★ / 2★
    - generic PR reviews do not enter review
    """

    source_rows, review_rows, stats = transform_raw_reviews(raw_items)

    source_count, review_count = save_review_batch(
        source_rows,
        review_rows,
    )

    generic_pr_place_ids = [
        str(place_id)
        for place_id in stats.get("generic_pr_place_ids", [])
        if place_id
    ]

    skipped_store_count = mark_stores_skip_review_fetch(
        generic_pr_place_ids
    )

    return {
        **stats,
        "source_upserted": source_count,
        "review_upserted": review_count,
        "stores_marked_skip_review_fetch": skipped_store_count,
    }


def _load_and_ingest_finished_run(
    run_info: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dataset_id = str(run_info["dataset_id"])
    allowed = {
        str(place_id)
        for place_id in run_info.get("place_ids", [])
    }

    raw_items = [
        item
        for item in get_dataset(dataset_id)
        if isinstance(item, dict)
        and str(item.get("placeId")) in allowed
    ]

    etl = ingest_raw_reviews(raw_items)

    write_execution_log(
        pipeline=str(run_info["pipeline"]),
        status="success",
        items_count=len(raw_items),
        apify_scheduler_id=str(run_info["run_id"]),
        actor_name=ACTOR_ID,
        started_at=_parse_datetime(run_info.get("started_at")),
        finished_at=_utcnow(),
        request_json=dict(run_info.get("request") or {}),
        response_json={
            "dataset_id": dataset_id,
            "item_count": len(raw_items),
            "run_status": "SUCCEEDED",
        },
    )

    return raw_items, etl


# ============================================================
# Initial
# ============================================================

def prepare_initial_batches(
    *,
    batch_size: int = BATCH_SIZE,
) -> list[dict[str, Any]]:
    """
    Prepare Initial batches.

    maxReviews is a per-place Actor setting, while our Initial maxReviews
    can differ by store. Therefore stores are first grouped by identical
    maxReviews, then each group is split into batches of at most 200 stores.
    """

    stores = fetch_stores_for_review(limit=None)

    grouped: dict[int, list[str]] = defaultdict(list)

    for store in stores:
        place_id = str(store["placeId"])

        max_reviews = initial_max_reviews(
            store.get("oneStar", 0),
            store.get("twoStar", 0),
        )

        grouped[max_reviews].append(place_id)

    batches: list[dict[str, Any]] = []

    for max_reviews in sorted(grouped):
        place_ids = grouped[max_reviews]

        for chunk in _chunked(place_ids, batch_size):
            batches.append(
                {
                    "batch_index": len(batches),
                    "place_ids": chunk,
                    "max_reviews": max_reviews,
                    "reviewsSort": INITIAL_SORT
                }
            )

    log.info(
        "prepare_initial_batches stores=%s batches=%s batch_size=%s",
        len(stores),
        len(batches),
        batch_size,
    )

    return batches


def start_initial_batch(batch: dict[str, Any]) -> dict[str, Any]:
    return start_apify_run(
        list(batch["place_ids"]),
        pipeline="review_initial",
        max_reviews=int(batch["max_reviews"]),
        reviews_sort=None,
        context={
            "mode": "initial",
            "batch_index": int(batch["batch_index"]),
            "max_reviews": int(batch["max_reviews"]),
        },
    )


def process_initial_batch(
    run_info: dict[str, Any],
) -> dict[str, Any]:
    raw_items, etl = _load_and_ingest_finished_run(run_info)

    return {
        "mode": "initial",
        "batch_index": run_info.get("context", {}).get("batch_index"),
        "stores": len(run_info.get("place_ids", [])),
        "raw_count": len(raw_items),
        "etl": etl,
    }


# ============================================================
# Daily
# ============================================================

def prepare_daily_batches(
    *,
    batch_size: int = BATCH_SIZE,
    reviews_start_date: str | None = None,
) -> list[dict[str, Any]]:
    place_ids = fetch_place_ids_for_review(limit=None)

    # Airflow container may run in UTC. Daily business date must use Taiwan time.
    taipei_today = datetime.now(
        timezone(timedelta(hours=8))
    ).date()

    start_date = reviews_start_date or (
        taipei_today - timedelta(days=1)
    ).isoformat()

    batches = [
        {
            "batch_index": index,
            "place_ids": chunk,
            "reviews_sort": DAILY_SORT,
            "reviews_start_date": start_date,
        }
        for index, chunk in enumerate(
            _chunked(place_ids, batch_size)
        )
    ]

    log.info(
        "prepare_daily_batches stores=%s batches=%s "
        "batch_size=%s reviewsStartDate=%s",
        len(place_ids),
        len(batches),
        batch_size,
        start_date,
    )

    return batches


def start_daily_batch(batch: dict[str, Any]) -> dict[str, Any]:
    return start_apify_run(
        list(batch["place_ids"]),
        pipeline="review_daily",
        max_reviews=None,
        reviews_sort="newest",
        reviews_start_date=str(batch["reviews_start_date"]),
        context={
            "mode": "daily",
            "batch_index": int(batch["batch_index"]),
            "reviews_start_date": str(batch["reviews_start_date"]),
        },
    )


def process_daily_batch(
    run_info: dict[str, Any],
) -> dict[str, Any]:
    raw_items, etl = _load_and_ingest_finished_run(run_info)

    return {
        "mode": "daily",
        "batch_index": run_info.get("context", {}).get("batch_index"),
        "stores": len(run_info.get("place_ids", [])),
        "raw_count": len(raw_items),
        "etl": etl,
    }


# ============================================================
# Owner Reply Recheck
# ============================================================

def prepare_recheck_batches(
    *,
    batch_size: int = BATCH_SIZE,
) -> list[dict[str, Any]]:
    """
    Read all due Recheck rows.

    No former 100-row limit.
    Stores are deduplicated and split into batches of at most 200 places.
    """

    due = fetch_reviews_needing_recheck()

    eligible_place_ids = filter_existing_place_ids(
        sorted(
            {
                str(row["placeId"])
                for row in due
                if row.get("placeId")
            }
        )
    )

    eligible = set(eligible_place_ids)

    due_by_place: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in due:
        place_id = str(row.get("placeId") or "")

        if not place_id or place_id not in eligible:
            continue

        published_at = _parse_datetime(
            row.get("publishedAtDate")
        )

        due_by_place[place_id].append(
            {
                "reviewId": str(row["reviewId"]),
                "placeId": place_id,
                "publishedAtDate": (
                    published_at.isoformat()
                    if published_at
                    else None
                ),
            }
        )

    batches: list[dict[str, Any]] = []

    for chunk in _chunked(eligible_place_ids, batch_size):
        due_reviews: list[dict[str, Any]] = []

        for place_id in chunk:
            due_reviews.extend(due_by_place.get(place_id, []))

        batches.append(
            {
                "batch_index": len(batches),
                "place_ids": chunk,
                "due_reviews": due_reviews,
                "reviews_sort": "newest",
            }
        )

    log.info(
        "prepare_recheck_batches due_reviews=%s stores=%s "
        "batches=%s batch_size=%s",
        len(due),
        len(eligible_place_ids),
        len(batches),
        batch_size,
    )

    return batches


def start_recheck_batch(batch: dict[str, Any]) -> dict[str, Any]:
    """
    Recheck has no former per-store maxReviews=20 limit.
    """

    return start_apify_run(
        list(batch["place_ids"]),
        pipeline="review_owner_recheck",
        max_reviews=None,
        reviews_sort="newest",
        context={
            "mode": "recheck",
            "batch_index": int(batch["batch_index"]),
            "due_reviews": list(batch.get("due_reviews") or []),
        },
    )


def _build_recheck_state_updates(
    due_reviews: list[dict[str, Any]],
    raw_items: list[dict[str, Any]],
    *,
    now: datetime,
    generic_pr_place_ids: set[str],
) -> list[dict[str, Any]]:
    raw_by_review_id = {
        str(item.get("reviewId")): item
        for item in raw_items
        if item.get("reviewId")
    }

    updates: list[dict[str, Any]] = []

    for due in due_reviews:
        review_id = str(due["reviewId"])
        place_id = str(due["placeId"])
        published_at = _parse_datetime(
            due.get("publishedAtDate")
        ) or now

        # Store 已因制式公關回覆被 skip，Review 本身也停止 Recheck。
        if place_id in generic_pr_place_ids:
            updates.append(
                {
                    "review_id": review_id,
                    "owner_reply_recheck": False,
                    "owner_reply_recheck_at": now,
                    "next_check_at": None,
                }
            )
            continue

        raw = raw_by_review_id.get(review_id)

        owner_reply = ""
        if raw is not None:
            owner_reply = str(
                raw.get("responseFromOwnerText") or ""
            ).strip()

        # 這次已補抓到老闆回覆。
        if owner_reply:
            updates.append(
                {
                    "review_id": review_id,
                    "owner_reply_recheck": False,
                    "owner_reply_recheck_at": now,
                    "next_check_at": None,
                }
            )
            continue

        # 超過最初留言時間 10 天，不再更新。
        if now > (
            published_at
            + timedelta(days=RECHECK_MAX_AGE_DAYS)
        ):
            updates.append(
                {
                    "review_id": review_id,
                    "owner_reply_recheck": False,
                    "owner_reply_recheck_at": now,
                    "next_check_at": None,
                }
            )
            continue

        # 這次仍沒有回覆 → 今天 + 2 天再查。
        updates.append(
            {
                "review_id": review_id,
                "owner_reply_recheck": True,
                "owner_reply_recheck_at": now,
                "next_check_at": (
                    now + timedelta(days=RECHECK_AFTER_DAYS)
                ),
            }
        )

    return updates


def process_recheck_batch(
    run_info: dict[str, Any],
) -> dict[str, Any]:
    dataset_id = str(run_info["dataset_id"])
    allowed = {
        str(place_id)
        for place_id in run_info.get("place_ids", [])
    }

    raw_items = [
        item
        for item in get_dataset(dataset_id)
        if isinstance(item, dict)
        and str(item.get("placeId")) in allowed
    ]

    etl = ingest_raw_reviews(raw_items)

    generic_pr_place_ids = {
        str(place_id)
        for place_id in etl.get(
            "generic_pr_place_ids",
            [],
        )
    }

    due_reviews = list(
        run_info.get("context", {}).get(
            "due_reviews",
            [],
        )
    )

    now = _utcnow()

    state_updates = _build_recheck_state_updates(
        due_reviews,
        raw_items,
        now=now,
        generic_pr_place_ids=generic_pr_place_ids,
    )

    recheck_updated = update_review_recheck_states(
        state_updates
    )

    write_execution_log(
        pipeline=str(run_info["pipeline"]),
        status="success",
        items_count=len(raw_items),
        apify_scheduler_id=str(run_info["run_id"]),
        actor_name=ACTOR_ID,
        started_at=_parse_datetime(run_info.get("started_at")),
        finished_at=now,
        request_json=dict(run_info.get("request") or {}),
        response_json={
            "dataset_id": dataset_id,
            "item_count": len(raw_items),
            "run_status": "SUCCEEDED",
            "recheck_rows_updated": recheck_updated,
        },
    )

    return {
        "mode": "recheck",
        "batch_index": run_info.get("context", {}).get("batch_index"),
        "stores": len(run_info.get("place_ids", [])),
        "due_reviews": len(due_reviews),
        "raw_count": len(raw_items),
        "recheck_rows_updated": recheck_updated,
        "etl": etl,
    }


# ============================================================
# Compatibility / manual dry-run helpers
# ============================================================

def run_initial_fetch(*, dry_run: bool = False) -> dict[str, Any]:
    """
    Compatibility helper.

    Formal Initial execution belongs to Airflow DAG.
    """

    batches = prepare_initial_batches()

    if dry_run:
        return {
            "mode": "initial",
            "dry_run": True,
            "batches": batches,
        }

    raise RuntimeError(
        "Formal Initial must be triggered through review_initial_dag_v2"
    )


def run_daily_fetch(*, dry_run: bool = False) -> dict[str, Any]:
    """
    Compatibility helper.

    Formal Daily execution belongs to Airflow DAG.
    """

    batches = prepare_daily_batches()

    if dry_run:
        return {
            "mode": "daily",
            "dry_run": True,
            "batches": batches,
        }

    raise RuntimeError(
        "Formal Daily must be triggered through review_daily_dag_v2"
    )


def run_owner_reply_recheck(
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Compatibility helper.

    Formal Recheck execution belongs to Daily Airflow DAG.
    """

    batches = prepare_recheck_batches()

    if dry_run:
        return {
            "mode": "recheck",
            "dry_run": True,
            "batches": batches,
        }

    raise RuntimeError(
        "Formal Recheck runs inside review_daily_dag_v2"
    )


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
    """Manual / test helper. Formal Initial/Daily/Recheck belong to Airflow."""

    if mode == "initial":
        return run_initial_fetch(dry_run=dry_run)

    if mode == "daily":
        return run_daily_fetch(dry_run=dry_run)

    if mode == "recheck":
        return run_owner_reply_recheck(dry_run=dry_run)

    if place_ids:
        resolved = filter_existing_place_ids(place_ids)
    else:
        resolved = fetch_place_ids_for_review(limit=store_limit)

    if not resolved:
        raise RuntimeError(
            "沒有可用 placeId（請確認 store 且 skip_review_fetch=FALSE）"
        )

    request = build_actor_input(
        resolved,
        max_reviews=max_reviews,
        reviews_sort=reviews_sort,
        reviews_start_date=reviews_start_date,
    )

    if dry_run:
        return {
            "mode": "manual",
            "dry_run": True,
            "place_ids": resolved,
            "request": request,
        }

    # Manual mode only starts the Actor; it does not poll.
    run_info = start_apify_run(
        resolved,
        pipeline="review_manual",
        max_reviews=max_reviews,
        reviews_sort=reviews_sort,
        reviews_start_date=reviews_start_date,
        context={"mode": "manual"},
    )

    return {
        "mode": "manual",
        "dry_run": False,
        "run": run_info,
        "message": "Actor started. Formal status polling is handled by Airflow DAG.",
    }