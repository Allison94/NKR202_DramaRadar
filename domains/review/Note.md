# Review Domain 工作清單對照

負責表：`review_source`（Raw）、`review`（Business）  
可讀：`store.placeId`（不可改 store）

## 進度

| # | 工作項 | 狀態 | 對應檔案 / 指令 |
|---|--------|------|----------------|
| 0 | 前置準備：Apify 帳號、Token 記錄 | 人工 | `.env` → `APIFY_REVIEW` |
| 1 | API 理解、對照 schema 欄位 | 完成 | `docs/research/R002-*.md` |
| 1-1 | 測試 API 連線 | 完成 | `uv run python -m domains.review.test_connection` |
| 2 | 抓取資料（第一次 + 每日兩條線） | 完成 | `--mode initial` / `--mode daily` |
| 3 | 存原始資料入 SQL | 完成 | `review_source` via `repository.py` |
| 4 | ETL（去重、異常、制式公關過濾） | 完成 | `filters.py` + `etl.py` |
| 5 | ETL 後存入 SQL | 完成 | `review` via `repository.py` |
| 6 | DAG 建立 | 初版 | `dags/review_daily_dag.py` |
| 6 | 測試流程通順 | 可測 | 見下方指令 |
| 7 | 移除測試資料 | 待做 | 正式上線前清 `ensure_test_store` 資料 |
| 8 | 測試 API → 正式 API | 待做 | 換 `.env` 的 production token |
| 9 | 最後調整 | 進行中 | 依 PR review |

## Pipeline 規則（組長 R002）

**第一次（initial）**
- 每家店 `maxReviews = oneStar + twoStar + 50`
- `reviewsSort = newest`

**每日（daily）**
- `reviewsSort = lowestRating`
- `reviewsStartDate = 昨天`

**ETL 過濾**
- Raw 全進 `review_source`
- 制式公關回覆（相似度 ≥ 80%）不進 `review`
- 缺 `reviewId` / `placeId`、空評論、無效星等 → 跳過 business 表

## 常用指令（Dev Container 內）

```bash
# 0. 建表（新 DB 只需一次）
uv run python -m db.apply_schema

# 1-1. 測 Apify 連線
uv run python -m domains.review.test_connection

# 2-A. 第一次抓取（需 store 已有店家）
uv run python -m domains.review.run_pipeline --mode initial --store-limit 5

# 2-B. 每日增量
uv run python -m domains.review.run_pipeline --mode daily

# 本地 JSON 測 ETL（不花 Apify）
uv run python -m domains.review.ensure_test_store
uv run python -m domains.review.run_pipeline --from-json domains/review/sample_review.json

# 6. 看 execution_log
# SELECT * FROM "execution_log" ORDER BY "started_at" DESC LIMIT 10;

# Dashboard
streamlit run dashboard/app.py
```

## 檔案結構

| 檔案 | 職責 |
|------|------|
| `client.py` | Apify 連線 |
| `filters.py` | 去重、制式公關、欄位驗證 |
| `etl.py` | Apify JSON → schema row |
| `repository.py` | 讀 store、寫 review_source/review、execution_log |
| `service.py` | initial / daily / manual pipeline |
| `run_pipeline.py` | CLI |
| `test_connection.py` | Step 1-1 |
| `ensure_test_store.py` | 開發用 FK 測試店家 |

## 注意

- 寫 `review` 前，`placeId` 必須已在 `store`（FK）
- `owner_reply_recheck` 預設 `FALSE`，時間欄位 `NULL`
- AI Analysis 由其他組員負責；Review 只準備好 `review` 資料
