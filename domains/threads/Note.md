# Threads Domain

負責把當日最激烈的一則吵架事件發布到 Threads。

## 資料流

```
ai_analysis JOIN review（READ，scrapedAt >= 昨日午夜）
  → 依 review_score + owner_score 排序取第 1 筆
  → 組成貼文文字
  → Threads Graph API：建立容器 → 發布 → 取回貼文資訊
  → threads_log（WRITE）
  → execution_log（每個步驟各記一筆）
```

## 檔案職責

| 檔案 | 說明 |
|---|---|
| `post.py` | `threads_post()`：查詢當日最高分事件並組成貼文字串 |
| `api.py` | `threads_run()`：串接三個 API 步驟並寫入紀錄 |
| `token_access.py` | 長期權杖刷新（`refresh_threads_token`）與短期換長期（`change_long_key`） |
| `models.py` | `threads_log` 資料表定義 |
| `dag.py` | `threads_dags_v1` |

## Threads Graph API

Base URL：`https://graph.threads.net/v1.0`，認證方式為 `Authorization: Bearer {THREADS_LONG_KEY}`。

發文為三步驟，缺一不可：

| 步驟 | Endpoint | 說明 |
|---|---|---|
| 1. 建立容器 | `POST /{THREADS_USER_ID}/threads` | 傳入 `media_type=TEXT` 與 `text`，取得 `creation_id` |
| 2. 發布 | `POST /{THREADS_USER_ID}/threads_publish` | 傳入 `creation_id`，取得貼文 `id` |
| 3. 取回資訊 | `GET /{publish_id}` | 取 `id,text,media_type,media_url,permalink,timestamp` 寫入 `threads_log` |

三個步驟各自寫一筆 `execution_log`，`apify_scheduler_id` 欄位借用來記錄步驟名稱（`create_container` / `publish_container` / `get_post`）。

## Token 管理

| 環境變數 | 用途 |
|---|---|
| `THREADS_API_KEY` | App Secret，短期權杖換長期權杖時使用 |
| `THREADS_LONG_KEY` | 長期存取權杖，實際發文用的 Bearer token |
| `THREADS_USER_ID` | Threads 使用者 ID，組在 endpoint 路徑中 |

長期權杖有效期 60 天。DAG 每次執行會先呼叫 `refresh_threads_token()` 刷新並**寫回 `.env`**，刷新失敗就不發文。

權杖完全失效時，需到 Meta 開發者後台取得新的短期權杖，再手動執行：

```bash
uv run python -m domains.threads.token_access
```

這是互動式指令（會 `input()` 等待輸入），不能在排程中執行。

## 貼文格式

有事件時輸出「今日最Drama」：雙方發言各截斷 100 字、AI 戰力指數（`review_score` / `owner_score`）、AI 建議公關回覆、評論原始連結。

當日沒有合格事件時輸出「今日不Drama」替代貼文，維持每日更新節奏。

## Airflow DAG

`dag_id = threads_dags_v1`，`schedule = None`，由 `dags_trigger_daily_3am`（Asia/Taipei 03:00）或 `dags_trigger_all` 觸發。單一 task `threads_daily_post`：先刷新權杖，成功才執行 `threads_run()`。重試 2 次，間隔 10 分鐘。
