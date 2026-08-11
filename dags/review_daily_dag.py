from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum

from domains.review.airflow_tasks import run_review_daily_task


with DAG(
    dag_id="review_daily",
    description="每天抓取 Google Maps 新評論",
    schedule="0 3 * * *",
    start_date=pendulum.datetime(
        2026,
        8,
        1,
        tz="Asia/Taipei",
    ),
    catchup=False,
    tags=["review"],
) as dag:

    fetch_reviews = PythonOperator(
        task_id="fetch_reviews",
        python_callable=run_review_daily_task,
    )