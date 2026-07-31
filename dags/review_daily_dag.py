"""Airflow DAG: daily Review fetch (Step 6).

Mount this folder into Airflow's dags directory when the scheduler is ready.
"""

from __future__ import annotations

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.bash import BashOperator
except ImportError:  # pragma: no cover - local dev without Airflow installed
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
        description="Daily Review pipeline: lowestRating + yesterday",
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
                "uv run python -m domains.review.run_pipeline --mode daily"
            ),
        )
