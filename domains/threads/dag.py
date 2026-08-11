from datetime import datetime,timedelta
from airflow.sdk import task,dag
from domains.threads.api import threads_run
import logging
from airflow.exceptions import AirflowException

logger = logging.getLogger(__name__)

args = {
    "reties":2,
    "retry_delay":timedelta(minutes=10)
}

@dag(
    dag_id="threads_dags_v1",
    description="每日晚上七點post案例到threads",
    start_date=datetime(2026,1,1),
    schedule="0 19 * * *",
    catchup=False,
    default_args=args,
    tags=["threads","daily"]
)

def threads_dags():

    @task
    def threads_daily_post():
        logger.info(f"[INFO: threads_daily_post] Start")
        threads_run()
        logger.info(f"[INFO: threads_daily_post] End")

    threads_daily_post()

threads_dags()