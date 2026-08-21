"""Review domain compatibility pipeline wrappers.

正式排程：
- Initial：domains/review/dag.py，手動 DAG
- Daily + Recheck：domains/review/dag.py，每日 DAG

此檔保留 CLI / 舊 import 相容介面，不再加入正式 Store / Recheck 數量限制。
"""

from typing import Any

from domains.review.service import (
    run_daily_fetch,
    run_initial_fetch,
    run_owner_reply_recheck,
    run_review_pipeline,
)


def review_initial_pipeline(
    dry_run: bool = False,
) -> dict[str, Any]:
    return run_initial_fetch(
        dry_run=dry_run,
    )


def review_daily_pipeline(
    dry_run: bool = False,
) -> dict[str, Any]:
    return run_daily_fetch(
        dry_run=dry_run,
    )


def review_recheck_pipeline(
    dry_run: bool = False,
) -> dict[str, Any]:
    return run_owner_reply_recheck(
        dry_run=dry_run,
    )


def review_manual_pipeline(**kwargs) -> dict[str, Any]:
    return run_review_pipeline(**kwargs)