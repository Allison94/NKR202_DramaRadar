# DramaRadar 吵架雷達

> 商圈輿情分析平台 — 自動蒐集 Google Maps 店家與低星評論，用 AI 分析「顧客 vs 老闆」的對戰現場，並以地圖 / 排行榜視覺化，每日自動發布至 Threads。

專案代號：`NKR202_DramaRadar`

---

## 目錄

- [這是什麼](#這是什麼)
- [系統架構](#系統架構)
- [資料流](#資料流)
- [技術棧](#技術棧)
- [專案結構](#專案結構)
- [快速開始](#快速開始)
- [環境變數](#環境變數)
- [啟動各項服務](#啟動各項服務)
- [Airflow DAG 一覽](#airflow-dag-一覽)
- [手動執行 / CLI](#手動執行--cli)
- [資料庫](#資料庫)
- [業務規則](#業務規則)
- [部署到正式環境](#部署到正式環境)
- [未來事項](#未來事項)
- [文件索引](#文件索引)

---

## 這是什麼

Google Maps 有店家資訊與評論，但沒有「大量分析」「爭議整理」「AI 摘要」「每日自動追蹤」的能力。想看一整個商圈的輿情，只能一間一間點開來看。

DramaRadar 把這件事自動化成一條完整的 Pipeline：

1. **蒐集店家** — 用 Apify 掃台北市 12 個郵遞區號的餐飲店家。
2. **蒐集評論** — 只針對「有戲」的店家抓取 1~2 星低星評論。
3. **AI 分析** — 用 Gemini 判斷顧客與老闆各自的情緒型態、激烈程度（1~10 分），並生成建議公關回覆。
4. **視覺化** — Streamlit + Folium 呈現吵架地圖、吵架名人堂、全站分析。
5. **自動發文** — 每天挑出當日「最 Drama」的一則，自動發布到 Threads。

目前資料範圍鎖定 **台北市餐飲類店家**。

---

## 系統架構

```mermaid
flowchart TB
    subgraph EXT["外部服務"]
        AP1["Apify Actor<br/>compass/crawler-google-places"]
        AP2["Apify Actor<br/>compass/google-maps-reviews-scraper"]
        GEM["Google Gemini<br/>gemini-3.6-flash"]
        THA["Threads Graph API v1.0"]
    end

    SCH["Scheduler / Apache Airflow 3.3<br/>只負責排程，不含業務邏輯"]

    subgraph DOM["業務 Domain"]
        ST["Store"]
        RV["Review"]
        AI["AI Analysis"]
        TH["Threads"]
    end

    DB[("PostgreSQL 15<br/>Raw 表 + 業務表 + execution_log")]
    DASH["Dashboard / Streamlit<br/>唯讀"]

    SCH -. 觸發 .-> ST
    SCH -. 觸發 .-> RV
    SCH -. 觸發 .-> AI
    SCH -. 觸發 .-> TH

    AP1 --> ST
    AP2 --> RV
    GEM --> AI
    TH --> THA

    ST <--> DB
    RV <--> DB
    AI <--> DB
    TH <--> DB
    DB --> DASH
```

系統依 Domain 切分，每個 Domain 只負責單一職責，彼此透過 PostgreSQL 交換資料，不直接互相呼叫：

| Domain / 元件 | 職責 |
|---|---|
| **Store** | 串接 Apify（`compass/crawler-google-places`），蒐集店家基本資料、Raw JSON 保存、ETL、篩選出值得追蹤的店家 |
| **Review** | 串接 Apify（`compass/google-maps-reviews-scraper`），抓取低星評論、Raw JSON 保存、ETL、老闆回覆補抓（recheck） |
| **AI Analysis** | 呼叫 Gemini API，分析評論與老闆回覆的情緒、摘要、激烈度評分、生成公關回覆 |
| **Threads** | 依 AI 分析結果組成貼文、發布至 Threads Graph API、保存發文紀錄 |
| **Dashboard** | Streamlit 前端：吵架地圖、排行榜、全站統計 |
| **Scheduler** | Airflow 依排程協調各 Domain，本身不含任何業務邏輯 |

---

## 資料流

遵循 **Raw First** 原則：外部 API 回傳的原始 JSON 一律完整保存於 `*_source` 表，所有業務資料表都必須由 ETL 產生，且 ETL 可重跑。

```mermaid
flowchart TD
    AP1["Apify<br/>compass/crawler-google-places"]
    SS[("store_source<br/>原始 JSON")]
    ST[("store")]
    AP2["Apify<br/>compass/google-maps-reviews-scraper"]
    RS[("review_source<br/>原始 JSON")]
    RV[("review")]
    GEM["Google Gemini"]
    AI[("ai_analysis")]
    DASH["Dashboard"]
    THA["Threads Graph API"]
    TL[("threads_log")]

    AP1 --> SS
    SS -->|"Store ETL：評論數≥30<br/>且（總分≤4.3 或 1★佔比≥10%）<br/>且仍在營業"| ST
    ST -->|"blocked=FALSE 且<br/>skip_review_fetch=FALSE"| AP2
    AP2 --> RS
    RS -->|"Review ETL：只留 1~2 星"| RV
    RV -->|"只送有老闆回覆的"| GEM
    GEM --> AI
    AI --> DASH
    AI -->|"當日 review_score + owner_score<br/>最高的一筆"| THA
    THA --> TL
```

每個階段的 API request / response、處理筆數與錯誤訊息都會另外寫入 `execution_log`。

每日流程（`dags_trigger_daily_3am`，台北時間凌晨 3 點）：

```mermaid
flowchart TD
    CRON["dags_trigger_daily_3am<br/>0 3 * * *（Asia/Taipei）"]
    RV["review_daily_dag_v2<br/>抓昨日新增低星評論<br/>+ 老闆回覆 recheck"]
    AI["ai_analysis_daily_dag_v1<br/>分析昨日新增且已有老闆回覆的評論"]
    TH["threads_dags_v1<br/>發布當日最高分事件"]
    ST["store_dag_v1<br/>不在每日流程內<br/>需要時手動觸發"]
    DASH["Dashboard<br/>隨時直接讀資料庫"]

    CRON --> RV --> AI --> TH

    style ST stroke-dasharray: 5 5
    style DASH stroke-dasharray: 5 5
```

虛線的兩個方塊不屬於每日排程：Store 的店家清單變動不頻繁且 Apify 成本較高，需要時才手動跑；Dashboard 是唯讀前端，不由排程驅動。

---

## 技術棧

| 分類 | 使用 |
|---|---|
| 語言 | Python 3.12+ |
| 套件管理 | [uv](https://github.com/astral-sh/uv) |
| 開發環境 | Docker Compose + VS Code Dev Containers |
| 排程 | Apache Airflow 3.3+（LocalExecutor） |
| 資料庫 | PostgreSQL 15 |
| DB 存取 | SQLAlchemy 2.0 Core（不使用 ORM Session）+ psycopg2 |
| 爬蟲 | Apify SDK（`compass/crawler-google-places`、`compass/google-maps-reviews-scraper`） |
| LLM | Google Gemini（`google-genai` SDK，model `gemini-3.6-flash`，structured output） |
| 前端 | Streamlit + Folium + Altair |
| 社群發文 | Threads Graph API v1.0 |
| 設定管理 | pydantic-settings |

---

## 專案結構

```text
NKR202_DramaRadar/
├── .devcontainer/
│   └── devcontainer.json       # Dev Container 設定：port 轉發、VS Code 擴充、自動產生 .env
├── docker-compose.yml          # app / db / airflow-webserver / scheduler / dag-processor / init
├── Dockerfile                  # app 開發容器（uv + Python 3.12）
├── Dockerfile.airflow          # Airflow 容器
├── init_env.py                 # 由 .env.example 產生 .env，自動填入隨機 DB / Airflow 密碼
├── pyproject.toml              # 套件定義
│
├── shared/
│   └── config.py               # pydantic-settings，統一讀取 .env（settings 單例）
│
├── db/
│   ├── database.py             # SQLAlchemy engine + 共用 metadata
│   ├── shared_tables.py        # execution_log 表定義
│   └── schema.sql              # 資料庫 DDL 參考（非自動執行）
│
├── domains/                    # 掛載為 Airflow 的 dags 目錄
│   ├── dags.py                 # 兩支總控 DAG：每日 3 點排程 / 一次性全量重跑
│   ├── store/                  # client / etl / pipeline / db_handler / repository / models / dag
│   ├── review/                 # client / service / etl / filters / repository / run_pipeline / dag
│   ├── ai_analysis/            # client / etl / pipeline / db_handler / interface / models / dag
│   └── threads/                # api / post / token_access / models / dag
│
├── dashboard/
│   ├── app.py                  # Streamlit 主程式（單檔式，含全部頁面與 CSS）
│   ├── charts.py               # 圖表資料組裝
│   ├── theme.py                # Altair 主題
│   └── assets/splash.png
│
├── scheduler/                  # Airflow 執行期產物（logs / plugins / config），掛載進容器
│
└── docs/                       # PRD、架構、資料庫設計、API 研究、圖表
```

每個 Domain 內的檔案職責固定：

| 檔案 | 職責 |
|---|---|
| `client.py` | 只負責外部 API 連線取資料，不做任何轉換 |
| `etl.py` | Raw JSON → 可寫入資料庫的 dict/list |
| `db_handler.py` / `repository.py` | 所有 SQL 讀寫 |
| `pipeline.py` / `service.py` | 串接 client → etl → db 的流程編排 |
| `models.py` | SQLAlchemy Table 定義（部分含 Pydantic schema） |
| `config.py` | 該 Domain 所有可調參數 |
| `dag.py` | Airflow DAG 定義 |

---

## 快速開始

### 前置需求

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)（已啟動，Engine 顯示綠色）
- VS Code + [Dev Containers 擴充套件](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- Git

### 步驟

```bash
git clone https://github.com/Allison94/NKR202_DramaRadar.git
cd NKR202_DramaRadar
```

1. 用 VS Code 開啟專案資料夾。
2. 執行命令 **Dev Containers: Reopen in Container**。
   - 開啟時會自動執行 `init_env.py`，由 `.env.example` 產生 `.env`，並填入隨機產生的 PostgreSQL 與 Airflow 帳密。
   - 進入容器後自動執行 `uv sync` 安裝套件。
3. 打開 `.env`，補上第三方 API 金鑰（`GEMINI_API_KEY`、`APIFY_STORE`、`APIFY_REVIEW`、`THREADS_*`）。
4. 完成。

> `.env` 已列入 `.gitignore`，**絕對不要 commit**。

若不使用 Dev Container，也可直接用 Docker Compose：

```bash
python init_env.py          # 產生 .env，接著手動補上 API 金鑰
docker compose up -d db app
docker compose up airflow-init          # 初始化 Airflow metadata DB 與管理者帳號（只需一次）
docker compose up -d airflow-webserver airflow-scheduler airflow-dag-processor
```

---

## 環境變數

`.env` 由 `init_env.py` 產生，分成三組：

### 自動產生（不需手動填）

| 變數 | 說明 |
|---|---|
| `POSTGRES_USER` | 預設 `dev_user` |
| `POSTGRES_PASSWORD` | 隨機產生 |
| `POSTGRES_DB` | 預設 `dramaradar_dev` |
| `AIRFLOW_ADMIN_USER` | 預設 `dev_user`，Airflow UI 登入帳號 |
| `AIRFLOW_ADMIN_PASSWORD` | 隨機產生，Airflow UI 登入密碼 |
| `AIRFLOW_JWT_SECRET` | 隨機產生 |
| `AIRFLOW_API_SECRET_KEY` | 隨機產生 |

### 需自行申請填入

| 變數 | 用途 |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API 金鑰 |
| `APIFY_STORE` | Apify Token（店家爬蟲用） |
| `APIFY_REVIEW` | Apify Token（評論爬蟲用） |
| `THREADS_API_KEY` | Threads App Secret，用於短期 token 換發長期 token |
| `THREADS_LONG_KEY` | Threads 長期存取權杖，程式會自動刷新並寫回 `.env` |
| `THREADS_USER_ID` | Threads 使用者 ID |

### 由 docker-compose 注入

| 變數 | 值 |
|---|---|
| `DATABASE_URL` | `postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}` |

> `DATABASE_URL` **不在** `.env.example` 中，是由 `docker-compose.yml` 依 `POSTGRES_*` 組出並注入容器。若要在容器外執行程式，需自行設定此變數（主機端連線請把 `db` 換成 `localhost`）。

---

## 啟動各項服務

| 服務 | Port | 進入方式 |
|---|---|---|
| Airflow UI | 8080 | http://localhost:8080（帳密為 `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD`） |
| Streamlit Dashboard | 8501 | 手動啟動，見下方 |
| PostgreSQL | 5432 | `postgresql://${POSTGRES_USER}:***@localhost:5432/${POSTGRES_DB}` |

### Dashboard

在 Dev Container 終端機執行：

```bash
uv run streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501
```

頁面：

- **吵架地圖** — Folium 地圖，火焰標記大小代表烈度，可依關鍵字 / 行政區 / 最低烈度篩選，右側顯示店家詳情與 AI 分析。
- **吵架名人堂** — 最火店家、最嗆店家、最怒顧客、戰役最多、Google 最低分等多榜排行。
- **全站分析** — 店家數 / 案件數 / 行政區數 KPI，各行政區長條圖與明細表。

Dashboard 為**唯讀**，直接查 PostgreSQL，資料範圍限台北市、`stars <= 2` 且有老闆回覆的評論。資料庫為空時會顯示「已連線但沒有資料」，不會出現假資料。

---

## Airflow DAG 一覽

**所有子 DAG 的 `schedule` 都是 `None`**，排程統一由 `domains/dags.py` 的兩支總控 DAG 以 `TriggerDagRunOperator` 串接（`wait_for_completion=True`，前一支跑完才跑下一支）。

### 總控 DAG

| dag_id | 排程 | 觸發順序 |
|---|---|---|
| `dags_trigger_daily_3am` | `0 3 * * *`（Asia/Taipei） | `review_daily_dag_v2` → `ai_analysis_daily_dag_v1` → `threads_dags_v1` |
| `dags_trigger_all` | 手動 | `store_dag_v1` → `review_initial_dag_v2` → `ai_analysis_all_dag_v1` → `threads_dags_v1` |

> **Store 不在每日流程中。** 店家清單變動不頻繁且 Apify 成本較高，需要更新時再手動觸發 `store_dag_v1` 或 `dags_trigger_all`。

### 子 DAG

| dag_id | Domain | 任務流程 |
|---|---|---|
| `store_dag_v1` | Store | 以 12 個台北郵遞區號做 dynamic task mapping：`start_job` → `check_status` → `get_dataset` |
| `review_initial_dag_v2` | Review | `prepare_batches` → mapped `initial_batch`（sensor 等 Apify 完成 → `process_batch`）。首次全量抓取，每批 50 家、最多 5 個 Apify run 併行 |
| `review_daily_dag_v2` | Review | `prepare_daily` → mapped `daily_batch` → `prepare_recheck` → mapped `recheck_batch` |
| `review_salvage_dag_v1` | Review | `find_runs` → mapped `salvage_run` → `summarize`。把已付費但沒入庫的 Apify run 撈回來，不啟動新 Actor、不產生費用 |
| `ai_analysis_daily_dag_v1` | AI Analysis | `daily_task`：分析昨日新增且有老闆回覆的評論 |
| `ai_analysis_all_dag_v1` | AI Analysis | `all_task`：重跑全部有老闆回覆的評論 |
| `threads_dags_v1` | Threads | `threads_daily_post`：刷新 token → 挑出今日最高分事件 → 建立容器 → 發布 → 取回 permalink |

DAG 預設為暫停狀態（`DAGS_ARE_PAUSED_AT_CREATION=true`），需在 Airflow UI 手動開啟。

---

## 手動執行 / CLI

```bash
# Store：ETL 測試（使用寫死的 Apify dataset URL）
uv run python -m domains.store.etl

# Store：完整實跑測試（會實際呼叫 Apify、產生費用）
uv run python -m domains.store.tests.test_pipeline

# Review：主要 CLI
uv run python -m domains.review.run_pipeline --mode manual --place-id <placeId> --max-reviews 100
uv run python -m domains.review.run_pipeline --mode daily --dry-run
uv run python -m domains.review.run_pipeline --mode clear-store   # 清空所有業務資料表

# Review：塞一筆真實 placeId 進 store 表，方便驗收
uv run python -m domains.review.bootstrap_real_store

# Review：救援已付費但沒入庫的 Apify run（不會啟動新 Actor，不產生費用）
# 也可以在 Airflow UI 手動觸發 review_salvage_dag_v1
uv run python -m domains.review.salvage --list
uv run python -m domains.review.salvage --auto --hours 6

# AI Analysis：對全部有老闆回覆的評論重跑分析
uv run python -m domains.ai_analysis.pipeline

# Threads：互動式將短期 token 換成長期 token
uv run python -m domains.threads.token_access
```

Review CLI 的 `initial` / `daily` / `recheck` 模式若不加 `--dry-run` 會直接拋出 `RuntimeError`，因為批次與輪詢邏輯由 Airflow sensor 負責，設計上不允許在 CLI 直接跑。

> **成本提醒**：Apify 與 Gemini 皆為按量計費。`domains/store/tests/test_pipeline.py` 與 Review 的 `manual` 模式都會實際發動爬蟲，執行前請確認額度，手動測試建議先加 `--max-reviews 5`。Review 的 `MAX_ACTIVE_APIFY_RUNS = 5` 是為了不超過 Apify 帳號 16GB 的併行記憶體上限，調高前請先確認方案。

---

## 資料庫

DDL 參考 `db/schema.sql`。實際建表是由各 `db_handler.py` 匯入時呼叫 `metadata.create_all()` 完成。

> **沒有 migration 機制。** 專案未導入 Alembic，`metadata.create_all()` 只會建立不存在的資料表，**不會**變更既有資料表結構。修改 `models.py` 欄位後必須手動 `ALTER TABLE`（並同步更新 `db/schema.sql`），或在開發環境用 `--mode clear-store` 清空後重建。
>
> 另外，`models.py` 未宣告任何 `Index` 或 `ForeignKey`，因此實際資料庫中**只有主鍵索引**，`schema.sql` 內的外鍵約束不會被建立。細節見 [`004-Database Design.md`](docs/03_Database/004-Database%20Design.md) 第 6、7 節。

| 資料表 | 類型 | 擁有者 | 說明 |
|---|---|---|---|
| `store_source` | Raw | Store | Apify 店家 API 原始 JSON |
| `store` | Business | Store | 店家正式資料，含星等分布與 `blocked` / `skip_review_fetch` 旗標 |
| `review_source` | Raw | Review | Apify 評論 API 原始 JSON |
| `review` | Business | Review | 低星評論正式資料，含老闆回覆與 recheck 排程欄位 |
| `ai_analysis` | Business | AI Analysis | 雙方摘要、情緒標籤、1~10 分激烈度、建議公關回覆 |
| `threads_log` | Business | Threads | Threads 發文紀錄（含 permalink） |
| `execution_log` | Metadata | 全部 | 各 Pipeline 執行紀錄、Apify run id、items_count、錯誤訊息 |

```mermaid
erDiagram
    store_source ||--o| store : "ETL 後可能保留"
    store ||--o{ review : "placeId"
    review_source ||--o| review : "ETL 後可能保留"
    review ||--o| ai_analysis : "有老闆回覆才分析"

    store_source {
        varchar placeId PK
        jsonb raw_json
        timestamp scrapedAt
    }
    store {
        varchar placeId PK
        text title
        varchar categoryName
        text categories
        text address
        float lat
        float lng
        text url
        text imageUrl
        varchar business_status
        timestamp scrapedAt
        float totalScore
        int reviewsCount
        int oneStar
        int twoStar
        int threeStar
        int fourStar
        int fiveStar
        bool blocked
        bool skip_review_fetch
    }
    review_source {
        varchar reviewId PK
        varchar placeId
        jsonb raw_json
        timestamp scrapedAt
    }
    review {
        varchar reviewId PK
        varchar placeId
        varchar originalLanguage
        text text
        timestamp publishedAtDate
        text reviewUrl
        text reviewImageUrls
        int likesCount
        float totalScore
        int stars
        timestamp responseFromOwnerDate
        text responseFromOwnerText
        timestamp scrapedAt
        bool owner_reply_recheck
        timestamp owner_reply_recheck_at
        timestamp next_check_at
    }
    ai_analysis {
        varchar reviewId PK
        varchar placeId
        text review_text
        text review_summary
        varchar review_sentiment
        int review_score
        text owner_text
        text owner_summary
        varchar owner_sentiment
        int owner_score
        text pr_reply
        jsonb request_json
        jsonb response_json
    }
    threads_log {
        varchar id PK
        text text
        varchar media_type
        text media_url
        timestamp timestamp
        text permalink
    }
    execution_log {
        int id PK
        varchar pipeline
        varchar status
        int items_count
        varchar apify_scheduler_id
        varchar apify_dataset_id
        varchar actor_name
        timestamp started_at
        timestamp finished_at
        jsonb request_json
        jsonb response_json
        text error_msg
        int retry_count
    }
```

`execution_log` 沒有畫關聯線 — 它是所有 Pipeline 共用的執行紀錄表，不參照任何業務資料表。`threads_log` 也沒有畫到 `ai_analysis`：貼文雖由當日最高分分析產生，但表內沒有 `reviewId` / `analysisId`，無法直接追溯。圖上的其餘關聯線代表**邏輯上**的參照關係，資料庫中並未建立實際的外鍵約束（原因見下方 [`004-Database Design.md`](docs/03_Database/004-Database%20Design.md)）。

命名規範：

- Raw 表 `*_source`、Log 表 `*_log`。
- 來自外部 API 的欄位**保留原始命名**（`placeId`、`reviewId`、`totalScore`、`scrapedAt`…，camelCase）。
- 自行新增的欄位用 snake_case（`business_status`、`skip_review_fetch`、`owner_reply_recheck`…）。
- 不重新產生自己的 business identifier，一律沿用 `placeId` / `reviewId`。
- 時間一律 UTC，JSON 一律 JSONB。

每個 Domain 只能寫自己的表，其他 Domain 可讀不可改。唯一例外是 Review 會回寫 `store.skip_review_fetch`。

---

## 業務規則

實際跑在程式裡的篩選與判斷邏輯（參數集中在各 Domain 的 `config.py`）：

### Store 篩選（`domains/store/etl.py`）

店家要同時滿足以下條件才會寫進 `store`：

- `reviewsCount >= 30`
- `totalScore <= 4.3` **或** 一星佔比 `>= 10%`
- 未永久或暫時歇業

搜尋範圍為台北市 12 個郵遞區號 × 6 個關鍵字（餐廳、小吃、麵店、便當、餐酒館、料理），每組最多 20 筆。命中連鎖店黑名單（`config.chains`，約 200 個品牌）的店家會被標記 `skip_review_fetch = True`，不進行評論抓取。

### Review 抓取（`domains/review/`）

- 只保留 **1~2 星**評論寫入 `review`（原始 JSON 仍完整存進 `review_source`）。
- **Initial 模式**：每家 `maxReviews = oneStar + twoStar + 50`，排序 `lowestRanking`。
- **Daily 模式**：排序 `newest`，`reviewsStartDate` 設為昨天，只抓新增。
- **Owner Reply Recheck**：老闆回覆常常晚幾天才出現。沒有回覆的評論會排入 recheck，每 2 天回頭查一次，超過發文日 10 天就放棄。
- 老闆回覆若與制式公關罐頭文相似度 `>= 80%`（Python `difflib.SequenceMatcher`），視為無效戲劇性，該店會被標記 `skip_review_fetch`。
- 批次設定：每個 Apify run 50 家、最多 5 個 run 併行、sensor 每 120 秒 poke 一次、逾時 30 分鐘。

### AI 分析（`domains/ai_analysis/`）

- **只分析有老闆回覆的評論**（`responseFromOwnerText` 非空）— 沒有對戰就沒有戲。
- 每批 50 則送進 Gemini，使用 structured output（Pydantic schema `GeminiBatchRs`），temperature `0.2`。
- 對顧客與老闆**各自**產出：摘要（30 字內）、情緒標籤、1~10 分激烈度。
- 情緒標籤為固定五選一：理性客觀、高級反串、暴躁老哥、無聊公關、高情商幽默。
- 外文評論會翻成繁體中文（保留原文 + 譯文）。
- 額外產生一則「建議的最優公關回覆」（`pr_reply`）。

### Threads 發文（`domains/threads/`）

- 挑選昨日午夜（UTC）之後抓到、`review_score + owner_score` 總和最高的一筆事件。
- 若當日沒有夠格的事件，發布「今日不 Drama」的替代貼文。
- 發文前會自動刷新長期 token 並寫回 `.env`。

---

## 部署到正式環境

根目錄的 `docker-compose.yml` 是**給 Dev Container 用的**，直接搬到伺服器會出問題：它把整個專案目錄 bind mount 進容器（會蓋掉 image 內建好的 `.venv`）、`app` 服務只是 `sleep infinity` 的佔位、`.env` 依賴 Dev Container 的 hook 產生、而且資料庫與 Airflow UI 都直接綁在所有網卡上。

正式環境請改用另一組檔案，開發設定完全不受影響：

| 檔案 | 用途 |
|---|---|
| `docker-compose.prod.yml` | 正式環境服務定義 |
| `Dockerfile.prod` | Dashboard 映像檔，venv 建在 `/opt/venv`（專案目錄外） |
| `Dockerfile.airflow.prod` | Airflow 映像檔，base image 釘死 `3.3.0-python3.12` |
| `.env.prod.example` | 正式環境設定範本 |

### 與開發環境的差異

| 項目 | 開發 | 正式 |
|---|---|---|
| 程式碼 | bind mount 整個專案目錄 | build 階段烘進 image，不掛載 |
| 套件環境 | `.venv` 在專案目錄內（會被 mount 蓋掉，靠 `uv sync` 補回） | `/opt/venv`，不受掛載影響 |
| Dashboard | 手動下指令啟動 | compose 直接啟動 |
| `app` 服務 | `sleep infinity` 供 VS Code 附著 | 無 |
| Airflow logs | bind mount `./scheduler/logs`（Linux 上會有 UID 權限問題） | 具名 volume |
| 對外埠 | `0.0.0.0` | DB 綁 `127.0.0.1`；UI／Dashboard 現況仍綁 `0.0.0.0` |
| Fernet key | 空字串 | 必填 |
| DAG 初始狀態 | 暫停 | 直接啟用 |

### 快速啟動

```bash
cp .env.prod.example .env.prod
chmod 600 .env.prod
# 填齊所有欄位，密鑰產生指令見檔案內註解

docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

`init_env.py` 是 Dev Container 的 hook，在伺服器上不會執行，`.env.prod` 必須手動建立並填完整 — `shared/config.py` 的欄位全部必填，缺一個就在 import 階段拋 `ValidationError`。

現行 compose 只有 PostgreSQL 綁 `127.0.0.1`；Airflow UI 與 Dashboard 的 `8080:8080`、`8501:8501` 會監聽所有網卡。**不要在 GCP 防火牆開放這兩個 port 的公網 ingress**，維運仍透過 SSH tunnel 存取：

```bash
gcloud compute ssh <vm-name> -- -N -L 8080:localhost:8080 -L 8501:localhost:8501
```

**完整的 GCP VM 部署步驟**（建立 VM、機型與記憶體試算、Deploy Key、首次灌資料、備份、疑難排解）見 [`docs/05_Deployment/010-GCP VM Deployment.md`](<docs/05_Deployment/010-GCP VM Deployment.md>)。

### 需要留意的地方

**記憶體是主要限制。** `store_dag_v1` 對 12 個郵遞區號做 dynamic mapping，照 Airflow 預設會一次開 12 個 task process（每個約 300MB）。prod compose 已把 `AIRFLOW_PARALLELISM` 收斂到 6，4GB 機型請再往下調到 3。

**Threads token 無法自動續期。** 詳見下方「未來事項」。目前必須在 60 天內手動更新 `.env.prod` 的 `THREADS_LONG_KEY` 並重啟服務。

**Airflow 與業務資料共用同一個 PostgreSQL。** 沿用開發環境的做法。清資料庫時不要整個 drop，會把 Airflow metadata 一起清掉。

**資料庫備份沒有自動化。** `postgres_data` 是具名 volume，VM 砍掉就沒了。正式使用請自行加上 `pg_dump` 排程並送到 Cloud Storage。

---

## 未來事項

### 1. Threads 權杖改存資料庫

**現況問題。** `domains/threads/token_access.py` 的 `refresh_threads_token()` 取得新權杖後，用 `set_key(".env", ...)` 寫回專案根目錄的 `.env`：

```38:41:domains/threads/token_access.py
        if access_token:
            set_key(".env","THREADS_LONG_KEY",access_token)
            logger.info("[Info:refresh_threads_token] access_token已寫入")
            return True
```

這個做法在本機開發可行，但在容器環境完全失效，原因有三個：

1. **寫入位置是容器內的暫存檔。** `.env` 是相對路徑，在 Airflow 容器裡會解析成 `/opt/airflow/.env`，屬於容器可寫層，重建容器就消失。
2. **就算寫進去也不會被讀到。** pydantic-settings 的優先序是「環境變數 > `.env` 檔」，而 compose 是用 `env_file` 把 `THREADS_LONG_KEY` 當環境變數注入的，永遠蓋過檔案內容。
3. **無法用掛載繞過。** python-dotenv 的 `set_key` 是寫暫存檔再 `os.replace` 原子改名，如果把 `.env` 以單一檔案 bind mount 進容器，rename 會因為掛載點無法被取代而失敗。

實務影響：排程**不會報錯**（`refresh_threads_token()` 仍回傳 `True`），但權杖從未真正延長，原始權杖 60 天到期後發文就靜默停止。

**建議做法。** 把權杖從設定檔搬到資料庫，讓開發與正式環境走同一條路徑：

- 新增 `threads_token` 資料表，欄位約為 `id`、`access_token`、`expires_at`、`refreshed_at`，永遠只保留一列。
- `refresh_threads_token()` 改成 upsert 進這張表，不再碰 `.env`。
- `api.py` 的 `get_header()` 改成呼叫時才從資料庫讀取，不要在 import 階段固定成 `settings.threads_long_key`。
- `.env` 的 `THREADS_LONG_KEY` 降級為「首次啟動的種子值」：資料表是空的就用它初始化，之後一律以資料庫為準。
- `token_access.py` 的 `change_long_key()` 目前用 `input()` 互動輸入，一併改成吃 CLI 參數，才能在伺服器上非互動執行。

這樣改完之後，權杖續期就會跟其他業務資料一樣被容器化環境正確保存，也不再需要人工每 60 天進去改 `.env.prod`。

### 2. 其他已知待辦

| 項目 | 說明 |
|---|---|
| 補次要索引 | 目前只有主鍵索引。擴大到台北市以外時，`review.placeId` 與 `ai_analysis.placeId` 應優先補上 |
| 外鍵約束 | `db/schema.sql` 有定義但不會被執行，參照完整性目前靠 ETL 順序保證 |
| 資料庫備份自動化 | 目前需手動 `pg_dump`，應排進 crontab 並送到 Cloud Storage |
| `test_connection.py` 修復 | 匯入了 `client.py` 中不存在的 `client` 單例，目前無法執行 |
| 時區統一 | `models.py` 建出的是 `TIMESTAMP WITHOUT TIME ZONE`，與 `schema.sql` 宣告的 `TIMESTAMPTZ` 不一致 |

---

## 文件索引

| 文件 | 內容 |
|---|---|
| [`docs/01_Project/001-PRD.md`](docs/01_Project/001-PRD.md) | 產品需求、目標、TA、開發原則與限制 |
| [`docs/02_Architecture/002-Product Architecture.md`](docs/02_Architecture/002-Product%20Architecture.md) | 整體架構、Domain 職責、資料流、正式環境架構 |
| [`docs/02_Architecture/003-Domain Model.md`](docs/02_Architecture/003-Domain%20Model.md) | UML Domain Model 與實體關聯規則 |
| [`docs/02_Architecture/011-Complete Architecture Diagrams.md`](docs/02_Architecture/011-Complete%20Architecture%20Diagrams.md) | 完整架構圖集：系統情境、Domain 流程、DAG、部署、ERD |
| [`docs/03_Database/004-Database Design.md`](docs/03_Database/004-Database%20Design.md) | 資料庫設計原則、資料表欄位、索引與約束現況 |
| [`docs/research/R001-Apify API (Google Maps Extractor).md`](<docs/research/R001-Apify API (Google Maps Extractor).md>) | Apify 店家爬蟲 API 研究 |
| [`docs/research/R002-Apify API (Google Maps Reviews Scraper).md`](<docs/research/R002-Apify API (Google Maps Reviews Scraper).md>) | Apify 評論爬蟲 API 研究 |
| [`docs/research/R003-Gemini API.md`](<docs/research/R003-Gemini API.md>) | Gemini API 研究 |
| [`docs/05_Deployment/010-GCP VM Deployment.md`](<docs/05_Deployment/010-GCP VM Deployment.md>) | GCP VM 部署步驟、機型試算、維運與疑難排解 |
| [`docs/map.md`](docs/map.md) | 文件地圖，含尚未撰寫的文件清單 |
| [`FILEMAP.md`](FILEMAP.md) | 新成員環境建置逐步檢查清單與注意事項 |
| [`db/schema.sql`](db/schema.sql) | 資料庫 DDL 參考 |

各 Domain 資料夾內另有 `Note.md`，記錄該 Domain 的檔案職責、參數選擇與實作細節：

| 筆記 | 重點 |
|---|---|
| [`domains/store/Note.md`](domains/store/Note.md) | Apify 成本實測、run 與 dataset 的回應結構範例 |
| [`domains/review/Note.md`](domains/review/Note.md) | 五種執行模式、批次參數、老闆回覆 recheck 機制 |
| [`domains/ai_analysis/Note.md`](domains/ai_analysis/Note.md) | Gemini 設定、輸出欄位、分析對象條件 |
| [`domains/threads/Note.md`](domains/threads/Note.md) | 三步驟發文流程、Token 管理與換發 |
| [`scheduler/Note.md`](scheduler/Note.md) | DAG 檔案位置、排程設計理由 |
| [`shared/Note.md`](shared/Note.md) | 環境變數對照、`DATABASE_URL` 的來源 |
| [`dashboard/Note.md`](dashboard/Note.md) | Dashboard 驗收對照表 |

---

## 團隊

| 角色 | 成員 |
|---|---|
| Owner / 架構 / Store / AI Analysis / Threads | Allison |
| Review / Dashboard | hys |
| 協作 | Sam、Min |

開發規範：所有變更透過 **Pull Request** 審核後合併；主要分支 `main`，開發分支以 `<name>_dev` 命名。
