"""Review Airflow DAG.

每天台灣時間 03:00 抓取新評論。
"""

import logging
from datetime import timedelta

import pendulum
from airflow.sdk import dag, task

from domains.review.pipeline import review_daily_pipeline

logger = logging.getLogger(__name__)


default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}


@dag(
    dag_id="review_daily_dag_v1",
    description="每日抓取 Google Maps 新評論",
    schedule="0 3 * * *",
    start_date=pendulum.datetime(2026, 8, 1, tz="Asia/Taipei"),
    catchup=False,
    default_args=default_args,
    tags=["review", "daily"],
)
def review_daily_dag():

    @task
    def daily_task():
        logger.info("[INFO: review_daily] Start")

        result = review_daily_pipeline(
            store_limit=100,
            dry_run=False,
        )

        logger.info("[INFO: review_daily] End result=%s", result)

        return result

    daily_task()


review_daily_dag()
