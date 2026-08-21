"""Review Airflow DAGs.

Two DAGs live in this file:

1. review_initial_dag_v2
   - manual trigger only
   - no schedule
   - stores split into batches of at most 200
   - mapped batches can run in parallel

2. review_daily_dag_v2
   - daily schedule
   - newest + reviewsStartDate
   - stores split into batches of at most 200
   - after Daily finishes, run due Owner Reply Recheck batches

Actor status polling is handled by @task.sensor:
- check once every 120 seconds
- mode="reschedule" so the worker slot is released between checks
"""

from __future__ import annotations

import logging

import pendulum
from airflow.sdk import PokeReturnValue, dag, task

from domains.review.config import (
    BATCH_SIZE,
    STATUS_POKE_INTERVAL_SECONDS,
)
from domains.review.service import (
    check_apify_run,
    prepare_daily_batches,
    prepare_initial_batches,
    prepare_recheck_batches,
    process_daily_batch,
    process_initial_batch,
    process_recheck_batch,
    start_daily_batch,
    start_initial_batch,
    start_recheck_batch,
)


logger = logging.getLogger(__name__)


# Prevent a stuck Apify run from leaving the Airflow sensor waiting forever.
# 900 seconds matches the previous Review polling timeout.
SENSOR_TIMEOUT_SECONDS = 900



# ============================================================
# Initial DAG — manual only
# ============================================================

@dag(
    dag_id="review_initial_dag_v2",
    description="Review Initial：手動第一次全量抓取",
    schedule=None,
    start_date=pendulum.datetime(
        2026,
        8,
        1,
        tz="Asia/Taipei",
    ),
    catchup=False,
    tags=["review", "initial"],
)
def review_initial_dag():

    @task
    def prepare_batches():
        batches = prepare_initial_batches(
            batch_size=BATCH_SIZE,
        )

        logger.info(
            "[review_initial] prepared %s batches",
            len(batches),
        )

        return batches

    @task
    def start_batch(batch: dict):
        logger.info(
            "[review_initial] start batch=%s stores=%s maxReviews=%s",
            batch.get("batch_index"),
            len(batch.get("place_ids", [])),
            batch.get("max_reviews"),
        )

        run_info = start_initial_batch(batch)

        logger.info(
            "[review_initial] actor started batch=%s run_id=%s",
            batch.get("batch_index"),
            run_info.get("run_id"),
        )

        return run_info

    @task.sensor(
        poke_interval=STATUS_POKE_INTERVAL_SECONDS,
        timeout=SENSOR_TIMEOUT_SECONDS,
        mode="reschedule",
    )
    def wait_batch(run_info: dict) -> PokeReturnValue:
        checked = check_apify_run(run_info)

        logger.info(
            "[review_initial] check run_id=%s state=%s",
            checked.get("run_id"),
            checked.get("run_status"),
        )

        if checked.get("done"):
            return PokeReturnValue(
                is_done=True,
                xcom_value=checked,
            )

        return PokeReturnValue(is_done=False)

    @task
    def process_batch(run_info: dict):
        result = process_initial_batch(run_info)

        logger.info(
            "[review_initial] processed batch=%s result=%s",
            result.get("batch_index"),
            result,
        )

        return result

    batches = prepare_batches()

    started = start_batch.expand(
        batch=batches,
    )

    completed = wait_batch.expand(
        run_info=started,
    )

    process_batch.expand(
        run_info=completed,
    )


review_initial_dag()


# ============================================================
# Daily DAG — scheduled
# ============================================================

@dag(
    dag_id="review_daily_dag_v2",
    description="Review Daily：每日新增評論 + Owner Reply Recheck",
    schedule=None,
    start_date=pendulum.datetime(
        2026,
        8,
        1,
        tz="Asia/Taipei",
    ),
    catchup=False,
    tags=["review", "daily"],
)
def review_daily_dag():

    # --------------------------------------------------------
    # Daily new reviews
    # --------------------------------------------------------

    @task
    def prepare_daily():
        batches = prepare_daily_batches(
            batch_size=BATCH_SIZE,
        )

        logger.info(
            "[review_daily] prepared %s daily batches",
            len(batches),
        )

        return batches

    @task
    def start_daily(batch: dict):
        logger.info(
            "[review_daily] start batch=%s stores=%s date=%s",
            batch.get("batch_index"),
            len(batch.get("place_ids", [])),
            batch.get("reviews_start_date"),
        )

        run_info = start_daily_batch(batch)

        logger.info(
            "[review_daily] actor started batch=%s run_id=%s",
            batch.get("batch_index"),
            run_info.get("run_id"),
        )

        return run_info

    @task.sensor(
        poke_interval=STATUS_POKE_INTERVAL_SECONDS,
        timeout=SENSOR_TIMEOUT_SECONDS,
        mode="reschedule",
    )
    def wait_daily(run_info: dict) -> PokeReturnValue:
        checked = check_apify_run(run_info)

        logger.info(
            "[review_daily] check run_id=%s state=%s",
            checked.get("run_id"),
            checked.get("run_status"),
        )

        if checked.get("done"):
            return PokeReturnValue(
                is_done=True,
                xcom_value=checked,
            )

        return PokeReturnValue(is_done=False)

    @task
    def process_daily(run_info: dict):
        result = process_daily_batch(run_info)

        logger.info(
            "[review_daily] processed batch=%s result=%s",
            result.get("batch_index"),
            result,
        )

        return result

    daily_batches = prepare_daily()

    daily_started = start_daily.expand(
        batch=daily_batches,
    )

    daily_completed = wait_daily.expand(
        run_info=daily_started,
    )

    daily_processed = process_daily.expand(
        run_info=daily_completed,
    )

    # --------------------------------------------------------
    # Owner Reply Recheck
    # --------------------------------------------------------

    @task
    def prepare_recheck():
        batches = prepare_recheck_batches(
            batch_size=BATCH_SIZE,
        )

        logger.info(
            "[review_recheck] prepared %s batches",
            len(batches),
        )

        return batches

    @task
    def start_recheck(batch: dict):
        logger.info(
            "[review_recheck] start batch=%s stores=%s due_reviews=%s",
            batch.get("batch_index"),
            len(batch.get("place_ids", [])),
            len(batch.get("due_reviews", [])),
        )

        run_info = start_recheck_batch(batch)

        logger.info(
            "[review_recheck] actor started batch=%s run_id=%s",
            batch.get("batch_index"),
            run_info.get("run_id"),
        )

        return run_info

    @task.sensor(
        poke_interval=STATUS_POKE_INTERVAL_SECONDS,
        timeout=SENSOR_TIMEOUT_SECONDS,
        mode="reschedule",
    )
    def wait_recheck(run_info: dict) -> PokeReturnValue:
        checked = check_apify_run(run_info)

        logger.info(
            "[review_recheck] check run_id=%s state=%s",
            checked.get("run_id"),
            checked.get("run_status"),
        )

        if checked.get("done"):
            return PokeReturnValue(
                is_done=True,
                xcom_value=checked,
            )

        return PokeReturnValue(is_done=False)

    @task
    def process_recheck(run_info: dict):
        result = process_recheck_batch(run_info)

        logger.info(
            "[review_recheck] processed batch=%s result=%s",
            result.get("batch_index"),
            result,
        )

        return result

    recheck_batches = prepare_recheck()

    # Recheck starts only after all mapped Daily processing is finished.
    daily_processed >> recheck_batches

    recheck_started = start_recheck.expand(
        batch=recheck_batches,
    )

    recheck_completed = wait_recheck.expand(
        run_info=recheck_started,
    )

    process_recheck.expand(
        run_info=recheck_completed,
    )


review_daily_dag()