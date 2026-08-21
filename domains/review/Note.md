# Review Domain

只動 `domains/review/`。DAG 定義也在本資料夾（`domains/review/dag.py`），因為 `domains/` 整個掛載為 Airflow 的 DAG 目錄。

## 驗收重點

1. **真實 Apify 資料**寫進 PostgreSQL（不是 demo JSON / demo-* 假 placeId）
2. **API**：`compass/google-maps-reviews-scraper`（R002）
3. **每天 03:00（Asia/Taipei）** 增量抓昨天新評論，由總控 DAG `dags_trigger_daily_3am` 觸發

## 資料流

```
store（READ，真實 placeId，blocked=FALSE 且 skip_review_fetch=FALSE）
  → Apify Google Maps Reviews Scraper
  → ETL（本地篩選 1~2 星；不用貴的 reviewsFilterString）
  → review_source / review（WRITE）
  → execution_log（每次 API request + response/error）
```

偵測到制式公關回覆（相似度 ≥ 80%）時，會回寫 `store.skip_review_fetch = TRUE`。這是本 Domain 唯一寫入 `store` 的情形。

## 模式

| mode | 用途 | Apify 參數 |
|------|------|--------|
| `initial` | 第一次全量抓取 | `maxReviews = 1★+2★+50`、`reviewsSort=lowestRanking` |
| `daily` | 每日 03:00 增量 | `reviewsSort=newest`、`reviewsStartDate=昨天` |
| `recheck` | 補老闆回覆 | 依 `owner_reply_recheck` + `next_check_at` 挑選 |
| `manual` | 手動指定 placeId | 自訂 |
| `clear-store` | 清空測試資料 | 不呼叫 API，直接刪表 |

`initial` / `daily` / `recheck` 的批次與輪詢由 Airflow 負責，CLI 只能以 `--dry-run` 檢查組出來的參數；不加 `--dry-run` 會直接拋 `RuntimeError`。

## 檔案職責

| 檔案 | 說明 |
|---|---|
| `service.py` | **核心流程**：批次組裝、Apify 啟動／狀態確認／ingest、三種模式的實作 |
| `client.py` | Apify 連線 |
| `etl.py` | Raw JSON → `review_source` / `review` |
| `filters.py` | 去重、驗證、制式公關回覆判定 |
| `repository.py` | **所有 SQL 的唯一來源** |
| `config.py` | 批次大小、sensor 間隔、recheck 天數等參數 |
| `dag.py` | `review_initial_dag_v2`、`review_daily_dag_v2` |
| `run_pipeline.py` | CLI 入口 |
| `bootstrap_real_store.py` | 塞真實 placeId 進 `store`，供 Store 尚未灌資料時測試 |

`pipeline.py`、`db_handler.py`、`airflow_tasks.py`、`review1.py` 為早期版本留下的相容包裝層，新功能請寫在 `service.py` + `repository.py`。

## 驗收指令（Dev Container）

```bash
# 1) 清掉 demo 假資料
uv run python -m domains.review.run_pipeline --mode clear-store

# 2) 寫入真實 Google placeId（Store 還沒灌資料時用）
uv run python -m domains.review.bootstrap_real_store

# 3) 打真的 Apify（會花額度，建議先 max-reviews 5）
uv run python -m domains.review.run_pipeline \
  --mode manual \
  --place-id ChIJi67FDQCrQjQRNnqJst4-2C8 \
  --max-reviews 5

# 4) 模擬 DAG 每日增量（dry-run 不打 API）
uv run python -m domains.review.run_pipeline --mode daily --dry-run

# 5) 不打 Apify，用本地 JSON 測 ETL（placeId 必須已在 store）
uv run python -m domains.review.run_pipeline --from-json sample_review.json
```

`manual` 模式只會啟動 Apify Actor，**不會**輪詢結果或寫入評論 — 輪詢是 Airflow Sensor 的職責。

## Airflow DAG

檔案：`domains/review/dag.py`

| dag_id | schedule | 流程 |
|---|---|---|
| `review_initial_dag_v2` | `None`（由 `dags_trigger_all` 觸發） | `prepare_batches` → mapped `initial_batch`（`start_and_wait_batch` sensor → `process_batch`） |
| `review_daily_dag_v2` | `None`（由 `dags_trigger_daily_3am` 觸發） | `prepare_daily` → mapped `daily_batch` → `prepare_recheck` → mapped `recheck_batch` |

兩支 DAG 的 `schedule` 都是 `None`，實際排程時間由 `domains/dags.py` 的總控 DAG 決定，避免同一支 DAG 被自身排程與上游 Trigger 重複啟動。

批次參數（`config.py`）：每批 50 家、最多 5 個 Apify run 併行、sensor 每 120 秒 poke、逾時 30 分鐘。

## Owner Reply Recheck

老闆回覆通常晚於評論出現：

- 評論寫入時若沒有老闆回覆 → `owner_reply_recheck = TRUE`，`next_check_at = 今天 + 2 天`
- 到期重抓：有回覆就更新並結束 recheck；沒有就 `next_check_at += 2 天`
- 距 `publishedAtDate` 超過 10 天 → 放棄追蹤
