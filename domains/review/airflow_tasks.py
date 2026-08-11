from domains.review.service import run_daily_fetch


def run_review_daily_task():
    return run_daily_fetch(
        store_limit=100,
        dry_run=False,
    )