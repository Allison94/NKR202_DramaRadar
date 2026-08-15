"""Legacy Review Airflow task compatibility wrapper.

正式 Initial / Daily / Recheck 已由 domains/review/dag.py 的兩個 DAG 負責。
此檔保留舊 import 相容性，不再帶 store_limit=100。
"""

from domains.review.service import run_daily_fetch


def run_review_daily_task():
    return run_daily_fetch(
        dry_run=False,
    )