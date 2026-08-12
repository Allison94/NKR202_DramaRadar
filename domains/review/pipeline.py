"""Review domain pipeline.

負責串接：
client -> etl -> db_handler

目前沿用已驗證成功的 service.py 邏輯，
提供給 Airflow / CLI 呼叫。
"""

from typing import Any

from domains.review.service import (
    run_initial_fetch,
    run_daily_fetch,
    run_owner_reply_recheck,
    run_review_pipeline,
)


def review_initial_pipeline(
    store_limit: int = 50,
    dry_run: bool = False,
) -> dict[str, Any]:
    return run_initial_fetch(
        store_limit=store_limit,
        dry_run=dry_run,
    )


def review_daily_pipeline(
    store_limit: int = 100,
    dry_run: bool = False,
) -> dict[str, Any]:
    return run_daily_fetch(
        store_limit=store_limit,
        dry_run=dry_run,
    )


def review_recheck_pipeline(
    limit: int = 100,
    dry_run: bool = False,
) -> dict[str, Any]:
    return run_owner_reply_recheck(
        limit=limit,
        dry_run=dry_run,
    )


def review_manual_pipeline(**kwargs) -> dict[str, Any]:
    return run_review_pipeline(**kwargs)
