"""
* airflow
"""
import logging
from datetime import datetime, timedelta
from domains.store.pipeline import StoreInterface
from domains.store.config import taipei_postcodes
from airflow.sdk import task,dag

logger = logging.getLogger(__name__)

@dag(
    dag_id="store_dag_v1",
    description="抓store清單",
    catchup=False, # 不要抓舊的
    start_date=datetime(2026,1,1),
    schedule=None # 先不要定時跑
)
def store_pipeline_dag(): #ti是紀錄try幾次

    # task1
    @task(retries=2,retry_delay=timedelta(minutes=5))
    def start_job(postcode_str:str):
        sinterface = StoreInterface(postcode=postcode_str)
        job_info = sinterface.task1_start_job()
        logger.info(f"job_info：{job_info}")
        return {
            "postcode_str":postcode_str,
            "job_info":job_info
        }

    #task2
    @task(retries=30,retry_delay=timedelta(minutes=1))
    def check_status(task1_output:dict,ti=None):
        current_try = ti.try_number #紀錄跑幾次 #type:ignore
        sinterface = StoreInterface(task1_output["postcode_str"])
        status_info = sinterface.task2_check_status(task1_output["job_info"],current_try)
        logger.info(f"status_info：{status_info}\nretry_times:{current_try}")
        return {
            "postcode_str":task1_output["postcode_str"],
            "status_info":status_info
        }

    #task3
    @task(retries=5,retry_delay=timedelta(minutes=5))
    def get_dataset(task2_output:dict):
        sinterface = StoreInterface(task2_output["postcode_str"])
        dataset_info = sinterface.task3_get_dataset(task2_output["status_info"])
        logger.info(f"dataset_info：{dataset_info}")
        return dataset_info


    # taipei_postcodes = taipei_postcodes # 正式用
    test_taipei_postcodes = ["100", "103"] # 測試用
    task1_rs = start_job.expand(postcode_str=test_taipei_postcodes)
    task2_rs = check_status.expand(task1_output=task1_rs)
    final_rs = get_dataset.expand(task2_output=task2_rs)

store_pipeline_dag()