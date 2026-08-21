-- 快速盤點資料庫現況。唯讀，不會改到任何東西。
--
-- 開發環境：
--   docker compose exec -T db bash -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/inventory.sql
--
-- 正式環境（已設好 dc alias）：
--   dc exec -T db bash -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/inventory.sql

\echo '===== 各資料表筆數 ====='
SELECT 'store'         AS 資料表, count(*) AS 筆數 FROM store
UNION ALL SELECT 'store_source',  count(*) FROM store_source
UNION ALL SELECT 'review',        count(*) FROM review
UNION ALL SELECT 'review_source', count(*) FROM review_source
UNION ALL SELECT 'ai_analysis',   count(*) FROM ai_analysis
UNION ALL SELECT 'execution_log', count(*) FROM execution_log;

\echo ''
\echo '===== 店家 ====='
SELECT
    count(*)                                      AS 全部,
    count(*) FILTER (WHERE "blocked")             AS 已封鎖,
    count(*) FILTER (WHERE "skip_review_fetch")   AS 跳過抓評論
FROM store;

\echo ''
\echo '===== 評論與 AI 分析進度 ====='
-- 有老闆回覆 = 已分析 + 待分析。
-- ai_analysis 總筆數可能比「已分析」多：老闆回覆事後被移除的評論，
-- 分析結果仍留在表裡，但不再符合分析條件。
SELECT
    count(*)                                                       AS 評論總數,
    count(*) FILTER (WHERE "responseFromOwnerText" IS NOT NULL
                       AND "responseFromOwnerText" <> '')          AS 有老闆回覆,
    count(*) FILTER (WHERE "responseFromOwnerText" IS NOT NULL
                       AND "responseFromOwnerText" <> ''
                       AND "reviewId" IN (SELECT "reviewId" FROM ai_analysis))
                                                                   AS 已分析,
    count(*) FILTER (WHERE "responseFromOwnerText" IS NOT NULL
                       AND "responseFromOwnerText" <> ''
                       AND "reviewId" NOT IN (SELECT "reviewId" FROM ai_analysis))
                                                                   AS 待分析,
    (SELECT count(*) FROM ai_analysis)                             AS ai_analysis表總筆數
FROM review;

\echo ''
\echo '===== 最近 15 筆 pipeline 執行紀錄 ====='
SELECT
    id,
    pipeline,
    status,
    items_count      AS 筆數,
    apify_scheduler_id AS run_id,
    apify_dataset_id AS dataset_id,
    to_char(started_at, 'MM-DD HH24:MI') AS 開始
FROM execution_log
ORDER BY id DESC
LIMIT 15;

\echo ''
\echo '===== 已付費但可能沒入庫的 Apify run ====='
\echo '（started 有紀錄、但同一個 run_id 沒有 success 紀錄）'
SELECT
    e.pipeline,
    e.apify_scheduler_id AS run_id,
    to_char(e.started_at, 'MM-DD HH24:MI') AS 開始
FROM execution_log e
WHERE e.status = 'started'
  AND e.apify_scheduler_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM execution_log s
      WHERE s.status = 'success'
        AND s.apify_scheduler_id = e.apify_scheduler_id
  )
ORDER BY e.started_at DESC;
