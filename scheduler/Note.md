# Scheduler

本資料夾**不放程式碼**，只放 Airflow 的執行期產物，透過 `docker-compose.yml` 掛載進 Airflow 容器。

| 路徑 | 掛載至容器 | 內容 |
|---|---|---|
| `scheduler/logs/` | `/opt/airflow/logs` | 各 DAG run 的執行日誌 |
| `scheduler/plugins/` | `/opt/airflow/plugins` | 自訂 plugin（目前未使用） |
| `scheduler/config/` | `/opt/airflow/config` | Airflow 設定覆寫（目前未使用） |

## DAG 定義在哪裡

**不在這裡。** `domains/` 整個資料夾掛載為 `/opt/airflow/dags/domains`，所以 DAG 檔案與各自的 Domain 程式碼放在一起：

| 檔案 | DAG |
|---|---|
| `domains/dags.py` | `dags_trigger_daily_3am`、`dags_trigger_all` |
| `domains/store/dag.py` | `store_dag_v1` |
| `domains/review/dag.py` | `review_initial_dag_v2`、`review_daily_dag_v2` |
| `domains/ai_analysis/dag.py` | `ai_analysis_daily_dag_v1`、`ai_analysis_all_dag_v1` |
| `domains/threads/dag.py` | `threads_dags_v1` |

這樣做的原因是每個 Domain 的排程邏輯與業務程式碼一起改、一起 review，不用在兩個資料夾之間跳。

## 排程設計

所有子 DAG 的 `schedule` 都是 `None`，由 `domains/dags.py` 的兩支總控 DAG 以 `TriggerDagRunOperator`（`wait_for_completion=True`）串接。

```
dags_trigger_daily_3am（0 3 * * *，Asia/Taipei）
  └─ review_daily_dag_v2 → ai_analysis_daily_dag_v1 → threads_dags_v1

dags_trigger_all（手動）
  └─ store_dag_v1 → review_initial_dag_v2 → ai_analysis_all_dag_v1 → threads_dags_v1
```

子 DAG 一律不自帶排程，是為了避免同一支 DAG 同時被自身 schedule 與上游 Trigger 啟動而重複執行。

Store 不在每日流程中：店家清單變動不頻繁，而 Apify 店家爬蟲按筆計費，需要時再手動觸發 `store_dag_v1`。

## 相關設定

Airflow 服務定義在專案根目錄的 `docker-compose.yml`（`x-airflow-common`）：

- Executor：`LocalExecutor`
- Metadata DB：與業務資料共用同一個 PostgreSQL 實例
- DAG 預設暫停（`DAGS_ARE_PAUSED_AT_CREATION=true`），首次使用需在 UI 手動開啟
- UI：http://localhost:8080，帳密為 `.env` 的 `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD`

初始化（只需執行一次）：

```bash
docker compose up airflow-init
```

## 注意

`scheduler/logs/` 會持續累積 DAG run 日誌，已列入 `.gitignore` 的管理範圍，不需要 commit。
