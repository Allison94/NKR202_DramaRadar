# Review Domain

只動 `domains/review/`（DAG 例外：`dags/review_daily_dag.py`）。

## 資料流

```
store（READ，skip_review_fetch=FALSE）
  → Apify Google Maps Reviews
  → ETL（本地篩選，不用貴的 reviewsFilterString）
  → review_source / review（WRITE）
  → execution_log（每次 API 觸發：request + response/error）
```

## 模式

| mode | 用途 | Apify |
|------|------|--------|
| `initial` | 第一次 | `maxReviews=1★+2★+50`, `reviewsSort=newest` |
| `daily` | 每日凌晨 3 點 | `reviewsSort=lowestRating`, `reviewsStartDate=昨天`，maxReviews 小 |
| `recheck` | 補老闆回覆 | 依 `owner_reply_recheck` + `next_check_at` |
| `manual` | 手動測試 | 自訂 |
| `clear-store` | 清空假資料 | 刪 ai_analysis → review → review_source → store_source → store |

## CLI

```bash
# 清空假資料（store 全刪）
uv run python -m domains.review.run_pipeline --mode clear-store

# 第一次（店要先由 Store domain 寫進 DB）
uv run python -m domains.review.run_pipeline --mode initial --store-limit 20

# 每日增量（等同 DAG）
uv run python -m domains.review.run_pipeline --mode daily

# dry-run（不打 API、不寫 DB）
uv run python -m domains.review.run_pipeline --mode daily --dry-run
```

## 規則摘要

1. **資料來源只有 DB `store`**，格式依 `db/schema.sql`
2. `skip_review_fetch=TRUE` → 不抓
3. 無老闆回覆 → `owner_reply_recheck=TRUE`, `next_check_at=+3天`
4. **不用** Apify `reviewsFilterString`（貴）；本地 `filters.py` 處理
5. 每次 API start/success/fail 都寫 `execution_log`
6. 本 domain **不寫** store / ai_analysis / dashboard

## DAG

`dags/review_daily_dag.py` — cron `0 3 * * *`（每天 03:00）
