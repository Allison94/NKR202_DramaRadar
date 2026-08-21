"""Review Airflow DAGs.

Three DAGs live in this file:

1. review_initial_dag_v2
   - manual trigger only
   - no schedule
   - stores split into batches of at most 50
   - at most 5 Apify Actor runs at a time

2. review_daily_dag_v2
   - daily schedule
   - newest + reviewsStartDate
   - stores split into batches of at most 50
   - after Daily finishes, run due Owner Reply Recheck batches
   - at most 5 Apify Actor runs at a time

3. review_salvage_dag_v1
   - manual trigger only
   - 把已付費但沒入庫的 Apify run 撈回來
   - 只讀既有的 run 與 dataset，不啟動任何 Actor，不產生費用

Each batch is a mapped task group: start+wait → process.
That way one run SUCCEEDED writes review immediately; it does not
wait for every Apify run to finish.

Actor start + status polling is handled by @task.sensor:
- start the Actor on the first poke
- check once every 120 seconds
- keep retrying until Apify status is SUCCEEDED
- process that batch as soon as this sensor is done
- mode="poke" so extra mapped batches wait until a slot is free
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pendulum
from airflow.sdk import (
    Param,
    PokeReturnValue,
    dag,
    get_current_context,
    task,
    task_group,
)

from domains.review.config import (
    BATCH_SIZE,
    MAX_ACTIVE_APIFY_RUNS,
    STATUS_POKE_INTERVAL_SECONDS,
    STATUS_SENSOR_TIMEOUT_SECONDS,
)
from domains.review.salvage import (
    find_salvageable_runs,
    run_cost_usd,
    run_dataset_id,
)
from domains.review.service import (
    check_apify_run,
    prepare_daily_batches,
    prepare_initial_batches,
    prepare_recheck_batches,
    process_daily_batch,
    process_initial_batch,
    process_recheck_batch,
    salvage_finished_run,
    start_daily_batch,
    start_initial_batch,
    start_recheck_batch,
)


logger = logging.getLogger(__name__)


# Prevent a stuck Apify run from leaving the Airflow sensor waiting forever.
SENSOR_TIMEOUT_SECONDS = STATUS_SENSOR_TIMEOUT_SECONDS
RUN_INFO_XCOM_KEY = "apify_run_info"


def _is_apify_memory_limit_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "memory limit" in text


def _start_and_wait_apify(
    batch: dict[str, Any],
    *,
    start_fn: Callable[[dict[str, Any]], dict[str, Any]],
    log_prefix: str,
) -> PokeReturnValue:
    """Start one Actor run if needed, then poll until SUCCEEDED.

    Mapped sensors share MAX_ACTIVE_APIFY_RUNS, so extra batches wait
    for a free slot instead of launching more Actor runs.
    """

    context = get_current_context()
    ti = context["ti"]

    # map_indexes 必須明確指定成自己這一個。省略的話 Airflow 會撈出這個 task
    # 「所有」map index 的 XCom，並且只在剛好一筆時才回傳單一值 —— 一旦有第二個
    # batch 也推了 run_info 就會變成 list，導致下面的 run_info["run_id"] 爆掉。
    run_info = ti.xcom_pull(
        key=RUN_INFO_XCOM_KEY,
        task_ids=ti.task_id,
        map_indexes=ti.map_index,
    )

    if not run_info:
        logger.info(
            "%s start batch=%s stores=%s maxReviews=%s",
            log_prefix,
            batch.get("batch_index"),
            len(batch.get("place_ids", [])),
            batch.get("max_reviews"),
        )

        try:
            run_info = start_fn(batch)
        except Exception as exc:
            if _is_apify_memory_limit_error(exc):
                logger.warning(
                    "%s Apify memory full, retry start later batch=%s",
                    log_prefix,
                    batch.get("batch_index"),
                )
                return PokeReturnValue(is_done=False)
            raise

        ti.xcom_push(key=RUN_INFO_XCOM_KEY, value=run_info)
        logger.info(
            "%s actor started batch=%s run_id=%s",
            log_prefix,
            batch.get("batch_index"),
            run_info.get("run_id"),
        )

    checked = check_apify_run(run_info)

    logger.info(
        "%s check run_id=%s state=%s",
        log_prefix,
        checked.get("run_id"),
        checked.get("run_status"),
    )

    if checked.get("done"):
        return PokeReturnValue(
            is_done=True,
            xcom_value=checked,
        )

    logger.info(
        "%s run_id=%s not finished, retry later",
        log_prefix,
        checked.get("run_id"),
    )
    return PokeReturnValue(is_done=False)



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

    @task.sensor(
        poke_interval=STATUS_POKE_INTERVAL_SECONDS,
        timeout=SENSOR_TIMEOUT_SECONDS,
        mode="poke",
        max_active_tis_per_dag=MAX_ACTIVE_APIFY_RUNS,
        max_active_tis_per_dagrun=MAX_ACTIVE_APIFY_RUNS,
    )
    def start_and_wait_batch(batch: dict) -> PokeReturnValue:
        return _start_and_wait_apify(
            batch,
            start_fn=start_initial_batch,
            log_prefix="[review_initial]",
        )

    @task
    def process_batch(run_info: dict):
        result = process_initial_batch(run_info)

        logger.info(
            "[review_initial] processed batch=%s result=%s",
            result.get("batch_index"),
            result,
        )

        return result

    @task_group(group_id="initial_batch")
    def run_initial_batch(batch: dict):
        completed = start_and_wait_batch(batch)
        process_batch(completed)

    run_initial_batch.expand(
        batch=prepare_batches(),
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

    @task.sensor(
        poke_interval=STATUS_POKE_INTERVAL_SECONDS,
        timeout=SENSOR_TIMEOUT_SECONDS,
        mode="poke",
        max_active_tis_per_dag=MAX_ACTIVE_APIFY_RUNS,
        max_active_tis_per_dagrun=MAX_ACTIVE_APIFY_RUNS,
    )
    def start_and_wait_daily(batch: dict) -> PokeReturnValue:
        return _start_and_wait_apify(
            batch,
            start_fn=start_daily_batch,
            log_prefix="[review_daily]",
        )

    @task
    def process_daily(run_info: dict):
        result = process_daily_batch(run_info)

        logger.info(
            "[review_daily] processed batch=%s result=%s",
            result.get("batch_index"),
            result,
        )

        return result

    @task_group(group_id="daily_batch")
    def run_daily_batch(batch: dict):
        completed = start_and_wait_daily(batch)
        return process_daily(completed)

    daily_processed = run_daily_batch.expand(
        batch=prepare_daily(),
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

    @task.sensor(
        poke_interval=STATUS_POKE_INTERVAL_SECONDS,
        timeout=SENSOR_TIMEOUT_SECONDS,
        mode="poke",
        max_active_tis_per_dag=MAX_ACTIVE_APIFY_RUNS,
        max_active_tis_per_dagrun=MAX_ACTIVE_APIFY_RUNS,
    )
    def start_and_wait_recheck(batch: dict) -> PokeReturnValue:
        return _start_and_wait_apify(
            batch,
            start_fn=start_recheck_batch,
            log_prefix="[review_recheck]",
        )

    @task
    def process_recheck(run_info: dict):
        result = process_recheck_batch(run_info)

        logger.info(
            "[review_recheck] processed batch=%s result=%s",
            result.get("batch_index"),
            result,
        )

        return result

    @task_group(group_id="recheck_batch")
    def run_recheck_batch(batch: dict):
        completed = start_and_wait_recheck(batch)
        process_recheck(completed)

    recheck_batches = prepare_recheck()

    # Recheck starts only after all mapped Daily groups have finished.
    daily_processed >> recheck_batches

    run_recheck_batch.expand(
        batch=recheck_batches,
    )


review_daily_dag()


# ============================================================
# Salvage DAG — manual only
# ============================================================

@dag(
    dag_id="review_salvage_dag_v1",
    description="Review 救援：把已付費但沒入庫的 Apify run 撈回來（不啟動新 Actor）",
    schedule=None,
    start_date=pendulum.datetime(
        2026,
        8,
        1,
        tz="Asia/Taipei",
    ),
    catchup=False,
    tags=["review", "salvage", "manual"],
    params={
        "hours": Param(
            24,
            type="integer",
            minimum=1,
            maximum=168,
            title="往回追溯幾小時",
            description=(
                "掃描這段時間內的 Apify run。Apify dataset 只保留 7 天"
                "（168 小時），超過就救不回來了。"
            ),
        ),
        "run_ids": Param(
            [],
            type="array",
            items={"type": "string"},
            title="指定 run id（留空＝自動掃描）",
            description="填了就只處理這幾個，會忽略上面的時數設定。",
        ),
        "pipeline": Param(
            "review_initial",
            type="string",
            enum=[
                "review_initial",
                "review_daily",
                "review_owner_recheck",
            ],
            title="寫進 execution_log 的 pipeline 名稱",
        ),
        "include_ingested": Param(
            False,
            type="boolean",
            title="連已入庫的 run 也重撈",
            description="ETL 是 upsert，重撈安全但多餘。平常不用勾。",
        ),
        "dry_run": Param(
            False,
            type="boolean",
            title="只盤點不寫入",
            description="勾起來只會列出找到哪些 run，不會碰資料庫。",
        ),
    },
)
def review_salvage_dag():
    """把 Actor 已經跑完、費用已經產生，但沒寫進資料庫的資料收回來。

    查 run 狀態與讀 dataset 在 Apify 都不計費，所以這個 DAG 重跑幾次都不會花錢。
    """

    @task
    def find_runs() -> list[str]:
        params = get_current_context()["params"]

        explicit = [
            str(run_id).strip()
            for run_id in (params.get("run_ids") or [])
            if str(run_id).strip()
        ]

        if explicit:
            logger.info(
                "[review_salvage] 使用指定的 %s 個 run id",
                len(explicit),
            )
            return explicit

        candidates = find_salvageable_runs(
            hours=float(params.get("hours") or 24),
            include_ingested=bool(params.get("include_ingested")),
        )

        for run in candidates:
            logger.info(
                "[review_salvage] 可救 run_id=%s dataset=%s cost=US$%.3f",
                run.get("id"),
                run_dataset_id(run),
                run_cost_usd(run),
            )

        logger.info(
            "[review_salvage] 共找到 %s 個可救的 run，已花費 US$%.3f",
            len(candidates),
            sum(run_cost_usd(run) for run in candidates),
        )

        if params.get("dry_run"):
            logger.info("[review_salvage] dry_run＝只盤點，不寫入資料庫")
            return []

        return [str(run["id"]) for run in candidates]

    # 參數不能叫 run_id：那是 Airflow 保留的 task context 變數，expand 會被擋下來。
    @task(max_active_tis_per_dag=3)
    def salvage_run(apify_run_id: str) -> dict:
        params = get_current_context()["params"]

        result = salvage_finished_run(
            apify_run_id,
            pipeline=str(params.get("pipeline") or "review_initial"),
        )

        logger.info(
            "[review_salvage] run_id=%s result=%s",
            apify_run_id,
            result,
        )

        return result

    @task(trigger_rule="all_done")
    def summarize(results: list[dict] | None) -> dict:
        rows = results or []
        ingested = [row for row in rows if row and row.get("ingested")]

        summary = {
            "runs_attempted": len(rows),
            "runs_ingested": len(ingested),
            "raw_reviews": sum(
                row.get("raw_count") or 0
                for row in ingested
            ),
        }

        logger.info("[review_salvage] %s", summary)

        return summary

    summarize(salvage_run.expand(apify_run_id=find_runs()))


review_salvage_dag()
