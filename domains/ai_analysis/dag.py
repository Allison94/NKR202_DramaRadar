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
    start_date=datetime(2027,1,1),
    default_args=args,
    tags=["ai","daily"]
)

def ai_analysis_daily_dag():

    # daily
    def daily_dag():
        logger.info(f"[INFO: daily_dag] Start")
        return ai_analysis_pipeline()

    daily_dag()
    logger.info(f"[INFO: daily_dag] End")

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
    def all_dag():
        logger.info(f"[INFO: daily_dag] Start")
        return ai_analysis_pipeline("all")

    all_dag()
    logger.info(f"[INFO: daily_dag] End")

ai_analysis_all_dag()