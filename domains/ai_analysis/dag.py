"""
* airflow
"""
import sys,os
current_dir = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
from datetime import datetime,timedelta
import logging
from airflow.sdk import task,dag
from domains.ai_analysis.pipeline import ai_analysis_pipeline

logger = logging.getLogger(__name__)

args = {
    "retries":2,
    "retry_delay":timedelta(minutes=10)
}

# 每日跑三點固定跑ai_analysis
@dag(
    dag_id="ai_analysis_daily_dag_v1",
    description="llm分析reviews，每日三點固定",
    catchup=False,
    schedule=None,
    start_date=datetime(2026,1,1),
    default_args=args,
    tags=["ai","daily"]
)

def ai_analysis_daily_dag():

    # daily
    @task
    def daily_task():
        logger.info(f"[INFO: daily_task] Start")
        return ai_analysis_pipeline()

    daily_task()
    logger.info(f"[INFO: daily_task] End")

ai_analysis_daily_dag()


# 一次跑 手動操作
@dag(
    dag_id="ai_analysis_all_dag_v1",
    description="llm分析，一次全跑",
    catchup=False,
    schedule=None,
    start_date=datetime(2026,1,1),
    default_args=args,
    tags=["ai","all"]
)

def ai_analysis_all_dag():
    @task
    def all_task():
        logger.info(f"[INFO: all_task] Start")
        return ai_analysis_pipeline("all")

    all_task()
    logger.info(f"[INFO: all_task] End")

ai_analysis_all_dag()