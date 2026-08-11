# Review Domain

只動 `domains/review/`（DAG 例外：`dags/review_daily_dag.py`）。

## 組長驗收重點

1. **真實 Apify 資料**寫進 PostgreSQL（不是 demo JSON / demo-* 假 placeId）
2. **API**：`compass/google-maps-reviews-scraper`（R002）
3. **Airflow DAG** 每天 **03:00（Asia/Taipei）** 增量抓昨天新評論

## 資料流

```
store（READ，真實 placeId，skip_review_fetch=FALSE）
  → Apify Google Maps Reviews Scraper
  → ETL（本地篩選；不用貴的 reviewsFilterString）
  → review_source / review（WRITE）
  → execution_log（每次 API request + response/error）
```

## 模式

| mode | 用途 | Apify |
|------|------|--------|
| `initial` | 第一次 | `maxReviews=1★+2★+50`, `reviewsSort=newest` |
| `daily` | DAG 每日 03:00 | `lowestRating` + `reviewsStartDate=昨天` |
| `recheck` | 補老闆回覆 | `owner_reply_recheck` + `next_check_at` |
| `manual` | 手動指定 placeId | 自訂 |
| `clear-store` | 清空假資料 | 刪相關表 |

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
```

## Airflow DAG

檔案：`dags/review_daily_dag.py`

- `dag_id=review_daily_fetch`
- `schedule="0 3 * * *"`（Asia/Taipei 每天 03:00）
- `PythonOperator` → `domains.review.airflow_tasks.run_review_daily_task`
- 規則：`skip_review_fetch`、昨天增量、`owner_reply_recheck`

把專案 `dags/` 掛到 Airflow 的 `DAGS_FOLDER` 即可被排程（不必改本專案 docker-compose）。
