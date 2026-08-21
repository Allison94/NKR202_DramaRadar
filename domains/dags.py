from pydoc import describe
from sched import scheduler

import pendulum
import logging
from airflow.sdk import dag
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
logger = logging.getLogger(__name__)

@dag(
    dag_id="dags_trigger_daily_3am",
    description="整合所有 domains 的 DAG",
    start_date=pendulum.datetime(2026, 8, 22,tz="Asia/Taipei"),
    schedule="0 3 * * *",
    catchup=False,
    tags=["daily","dags_all"]
)
def trigger_workflow():
    review = TriggerDagRunOperator(
        task_id="trigger_review",
        trigger_dag_id="review_daily_dag_v2",
        wait_for_completion=True,
    )

    ai = TriggerDagRunOperator(
        task_id="trigger_ai_analysis",
        trigger_dag_id="ai_analysis_daily_dag_v1",
        wait_for_completion=True,
    )

    threads = TriggerDagRunOperator(
        task_id="trigger_threads",
        trigger_dag_id="threads_dags_v1",
        wait_for_completion=True,
    )
    logger.info("[Info:trigger_workflow] Start")
    review >> ai >> threads
    logger.info("[Info:trigger_workflow] End")
trigger_workflow()

@dag(
    dag_id="dags_trigger_all",
    describe="一次性抓取，沒限制數量",
    start_date=pendulum.datetime(2026, 8, 22,tz="Asia/Taipei"),
    schedule=None,
    catchup=False,
    tag=["all","dags_all"]  
)
def trigger_workflow_once():
    store = TriggerDagRunOperator(
        task_id="trigger_store",
        trigger_dag_id="store_dag_v1",
        wait_for_completion=True,
    )
    review = TriggerDagRunOperator(
        task_id="trigger_review",
        trigger_dag_id="review_initial_dag_v2",
        wait_for_completion=True,
    )

    ai = TriggerDagRunOperator(
        task_id="trigger_ai_analysis",
        trigger_dag_id="ai_analysis_all_dag_v1",
        wait_for_completion=True,
    )

    threads = TriggerDagRunOperator(
        task_id="trigger_threads",
        trigger_dag_id="threads_dags_v1",
        wait_for_completion=True,
    )
    logger.info("[Info:trigger_workflow_once] Start")
    store >> review >> ai >> threads
    logger.info("[Info:trigger_workflow_once] End")

trigger_workflow_once()