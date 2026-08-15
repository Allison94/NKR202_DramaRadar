"""只負責 Review Apify API 連線，不處理 ETL / DB。"""

import logging

from apify_client import ApifyClient

from shared.config import settings
from domains.review import config


logger = logging.getLogger(__name__)


class ReviewClient:

    def __init__(self):
        token = (settings.apify_review or "").strip()

        if not token:
            raise RuntimeError(
                "缺少 APIFY_REVIEW token，請確認 .env 設定。"
            )

        self.client = ApifyClient(token)

    def start_job_actor(self, run_input: dict) -> dict:
        try:
            safe_input = run_input.copy()

            # API 端不做文字篩選；統一交給本地 ETL。
            safe_input["reviewsFilterString"] = ""

            actor = self.client.actor(config.ACTOR_ID)

            # 不在 Review Domain 人為設定費用上限。
            obj = actor.start(
                run_input=safe_input,
            )

            return obj if isinstance(obj, dict) else dict(obj)

        except Exception as e:
            logger.exception(
                f"[Error:start_job_actor] 啟動 Review Apify 發生錯誤\n"
                f"輸入資料:{run_input}"
            )
            raise

    def check_status(self, run_id: str) -> dict:
        try:
            obj = self.client.run(run_id).get()

            if isinstance(obj, dict):
                return obj

            return dict(obj)

        except Exception:
            logger.exception(
                f"[Error:check_status] Review 狀態確認錯誤 run_id:{run_id}"
            )
            raise

    def get_dataset(self, dataset_id: str) -> list[dict]:
        try:
            items = self.client.dataset(dataset_id).list_items().items
            return list(items)

        except Exception:
            logger.exception(
                f"[Error:get_dataset] Review dataset 讀取錯誤 "
                f"dataset_id:{dataset_id}"
            )
            raise


# service.py 相容介面
ACTOR_ID = config.ACTOR_ID


def start_review_actor(params: dict):
    client = ReviewClient()
    return client.start_job_actor(params)


def check_status(run_id: str):
    client = ReviewClient()
    return client.check_status(run_id)


def get_dataset(dataset_id: str):
    client = ReviewClient()
    return client.get_dataset(dataset_id)