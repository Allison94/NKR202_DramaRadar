# Shared

跨 Domain 共用的設定，目前只有 `config.py`。

## config.py

以 pydantic-settings 讀取專案根目錄的 `.env`，匯出單例 `settings`。所有 Domain 一律從這裡取值，**不要在程式中直接讀 `os.environ`**，這樣型別檢查與缺漏偵測才有一個統一入口。

```python
from shared.config import settings

client = ApifyClient(settings.apify_store)
```

## 欄位對照

Pydantic 會自動把欄位名轉成大寫環境變數：

| 欄位 | 環境變數 | 使用者 |
|---|---|---|
| `database_url` | `DATABASE_URL` | 全部（透過 `db/database.py` 的 engine） |
| `apify_store` | `APIFY_STORE` | store |
| `apify_review` | `APIFY_REVIEW` | review |
| `gemini_api_key` | `GEMINI_API_KEY` | ai_analysis |
| `threads_api_key` | `THREADS_API_KEY` | threads（換發長期權杖） |
| `threads_long_key` | `THREADS_LONG_KEY` | threads（Bearer token） |
| `threads_user_id` | `THREADS_USER_ID` | threads |

所有欄位**皆為必填、沒有預設值**。缺任何一個，`Settings()` 在 import 階段就會拋出 `ValidationError`，不會等到實際呼叫 API 才失敗。

`extra="ignore"`，所以 `.env` 中的 `POSTGRES_*`、`AIRFLOW_*` 等只給 docker-compose 用的變數不會造成錯誤。

## DATABASE_URL 的來源

`DATABASE_URL` **不在 `.env.example` 裡**，是由 `docker-compose.yml` 依 `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` 組出後注入容器：

```
postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
```

在容器外執行程式時需自行設定，並把 host `db` 換成 `localhost`。
