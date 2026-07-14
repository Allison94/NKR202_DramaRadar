"""
只負責處理 Google Maps Reviews API 連線與取得資料，
不處理資料清洗、轉換或寫入資料庫。
"""

from apify_client import ApifyClient

from shared.config import settings


client = ApifyClient(settings.apify_review)


def start_review_actor(params):
    """啟動 Google Maps Reviews Scraper。"""
    actor = client.actor("compass/google-maps-reviews-scraper")

    return actor.start(
        run_input=params,
        max_total_charge_usd=0.01,
    )

def check_status(run_id):
    """查詢 Actor 執行狀態。"""
    return client.run(run_id).get()


def get_dataset(dataset_id) -> list[dict]:
    """根據 Dataset ID 取得評論資料。"""
    return client.dataset(dataset_id).list_items().items