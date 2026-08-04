"""Airflow DAG: Review 每日增量 — 凌晨 03:00。

規則：
- 不是一次抓全部，用 reviewsStartDate=昨天
- store.skip_review_fetch=TRUE 的店不抓（service/repository 處理）
- 同一 run 會順便做 owner_reply_recheck
"""

from __future__ import annotations

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.bash import BashOperator
except ImportError:  # pragma: no cover
    DAG = None  # type: ignore[misc, assignment]
    BashOperator = None  # type: ignore[misc, assignment]


if DAG is not None:
    default_args = {
        "owner": "dramaradar",
        "depends_on_past": False,
        "retries": 1,
        "retry_delay": timedelta(minutes=10),
    }

    with DAG(
        dag_id="review_daily_fetch",
        description="Daily Review: yesterday reviews + owner_reply_recheck @ 03:00",
        default_args=default_args,
        schedule="0 3 * * *",
        start_date=datetime(2026, 8, 1),
        catchup=False,
        tags=["review", "apify"],
    ) as dag:
        BashOperator(
            task_id="run_review_daily",
            bash_command=(
                "cd /nkr202_dramaradar && "
                "uv run python -m domains.review.run_pipeline --mode daily --store-limit 100"
            ),
        )
