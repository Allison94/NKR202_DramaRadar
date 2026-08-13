import pendulum
import logging
from airflow.sdk import dag,task
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
logger = logging.getLogger(__name__)

@dag(
    dag_id="dags_trigger_3am",
    description="整合所有 domains 的 DAG",
    start_date=pendulum.datetime(2026, 1, 1,tz="Asia/Taipei"),
    schedule="0 3 * * *",
    catchup=False,
    tags=["daily","dags_all"]
)
def trigger_workflow():

    store = TriggerDagRunOperator(
        task_id="trigger_store",
        trigger_dag_id="store_dag_v1",
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
    logger.info("[Info:trigger_workflow] Start")
    store >> ai >> threads
    logger.info("[Info:trigger_workflow] End")


trigger_workflow()