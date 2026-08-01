# Review Domain — 組長驗收對照

格式來源：**`db/schema.sql`**（照欄位讀寫，不改 schema）。  
範圍：台北市（`store.address` LIKE `%台北市%` / `%臺北市%`）。  
環境：不改 `docker-compose.yml` / `.env`。

## 正式資料路徑

```
READ  store          ← domains/review/repository.py
        ↓
Apify 或 --mock / --from-json（測試才用 mock）
        ↓
etl.py（欄位對齊 schema "review"）
        ↓
WRITE review_source  ← raw_json
WRITE review         ← business
WRITE execution_log
```

## schema 對照

| 表 | 動作 | 關鍵欄位 |
|----|------|----------|
| `store` | 讀 | placeId, oneStar, twoStar, address |
| `review_source` | 寫 | reviewId, placeId, raw_json, scrapedAt |
| `review` | 寫 | reviewId, placeId, text, stars, reviewUrl, responseFromOwnerText, owner_reply_recheck… |
| `execution_log` | 寫 | pipeline, status, items_count… |

`owner_reply_recheck` 預設 FALSE；時間欄位預設 NULL。

## CLI

```bash
# 正式（預設不用 mock）
uv run python -m domains.review.run_pipeline --mode initial --store-limit 5

# 本地測試才加 --mock
uv run python -m domains.review.run_pipeline --mode initial --mock

# 一鍵灌測試資料（寫進 DB，給本機看；不是網頁假資料 fallback）
uv run python -m domains.review.run_dev_setup
```
