from datetime import datetime,timedelta
from airflow.sdk import task,dag
from domains.threads.api import threads_run
import logging,sys,os
from domains.threads.token_access import refresh_threads_token

current_dir = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
logger = logging.getLogger(__name__)

args = {
    "retries":2,
    "retry_delay":timedelta(minutes=10)
}

@dag(
    dag_id="threads_dags_v1",
    description="每日晚上七點post案例到threads",
    start_date=datetime(2026,1,1),
    schedule="0 19 * * *",
    catchup=False,
    max_active_runs=1,
    default_args=args,
    tags=["threads","daily"]
)

def threads_dags():

    @task
    def threads_daily_post():
        
        logger.info(f"[INFO: threads_daily_post] Start")
        refresh_key = refresh_threads_token()
        if refresh_key:
            threads_run()
        logger.info(f"[INFO: threads_daily_post] End")

    threads_daily_post()

threads_dags()