import time

from domains.review.client import (
    check_status,
    get_dataset,
    start_review_actor,
)


params = {
    "language": "zh-TW",
    "maxReviews": 5,
    "personalData": True,
    "placeIds": [
        "ChIJi67FDQCrQjQRNnqJst4-2C8",
    ],
    "reviewsSort": "newest",
    "reviewsFilterString": "",
    "reviewsOrigin": "all",
}

# 啟動 Actor
run = start_review_actor(params)
run_id = run.id

print("Run ID：", run_id)

# 持續確認狀態
while True:
    status = check_status(run_id)

    print("目前狀態：", status.status)

    if status.status == "SUCCEEDED":
        break

    if status.status in {"FAILED", "ABORTED", "TIMED-OUT"}:
        raise RuntimeError(f"Actor 執行失敗：{status.status}")

    time.sleep(5)

# 取得 Dataset ID
dataset_id = status.default_dataset_id

if dataset_id is None:
    raise RuntimeError("找不到 Dataset ID")

print("Dataset ID：", dataset_id)

# 抓資料
reviews = get_dataset(dataset_id)

print("評論數：", len(reviews))

for review in reviews[:5]:
    print("店家：", review.get("title"))
    print("星數：", review.get("stars"))
    print("評論：", review.get("text"))
    print("店家回覆：", review.get("responseFromOwnerText"))
    print("-" * 40)