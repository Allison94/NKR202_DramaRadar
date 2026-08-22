# DramaRadar 完整架構圖集

- **版本**：v1.0
- **日期**：2026-08-22
- **依據**：目前程式碼、DAG、SQLAlchemy models 與 `docker-compose.prod.yml`

本文件集中放置簡報、開發與維運所需的完整圖表。圖中的資料關聯是**邏輯關聯**；目前 SQLAlchemy models 沒有宣告 `ForeignKey`，實體資料庫只有 Primary Key 約束。

## 圖表索引

1. 系統情境圖
2. 容器／服務架構圖
3. Domain 元件圖
4. 端到端資料流
5. Airflow DAG 拓撲
6. Store Domain 流程
7. Review Domain 流程
8. Owner Reply Recheck 狀態圖
9. Apify 付費資料救援流程
10. AI Analysis 流程與斷點續跑
11. Threads 發文序列圖
12. GCP 正式環境部署圖
13. Domain Model
14. 實體資料庫 ERD

---

## 1. 系統情境圖

```mermaid
flowchart LR
    OP["維運者／開發者"]
    USER["Dashboard 使用者"]
    SYS["DramaRadar<br/>商圈輿情分析平台"]
    GM["Google Maps 資料<br/>via Apify"]
    GEM["Google Gemini"]
    TH["Threads Graph API"]

    OP -->|"Airflow UI／CLI／部署"| SYS
    USER -->|"瀏覽地圖、排行榜、分析"| SYS
    GM -->|"店家與評論"| SYS
    SYS -->|"評論＋老闆回覆"| GEM
    GEM -->|"結構化情緒分析"| SYS
    SYS -->|"每日貼文"| TH
```

## 2. 容器／服務架構圖

```mermaid
flowchart TB
    subgraph AF["Airflow 3.3 / LocalExecutor"]
        API["api-server<br/>UI + REST API"]
        SCH["scheduler<br/>排程與 task 執行"]
        DP["dag-processor<br/>解析 DAG"]
        INIT["airflow-init<br/>DB migration + 管理者"]
    end

    subgraph APP["DramaRadar Application"]
        DOM["Store / Review / AI Analysis / Threads"]
        DASH["Streamlit Dashboard<br/>唯讀"]
    end

    DB[("PostgreSQL 15<br/>業務資料 + Airflow metadata")]
    EXT["Apify / Gemini / Threads API"]

    INIT --> DB
    API <--> DB
    SCH <--> DB
    DP <--> DB
    SCH --> DOM
    DOM <--> DB
    DOM <--> EXT
    DASH --> DB
```

> 專案沒有 FastAPI 或獨立 backend API。Airflow 直接執行 Python Domain 模組；Dashboard 直接讀 PostgreSQL。

## 3. Domain 元件圖

```mermaid
flowchart LR
    subgraph STORE["Store Domain"]
        SC["client"] --> SP["pipeline"]
        SP --> SE["etl"]
        SP --> SR["repository / db_handler"]
    end

    subgraph REVIEW["Review Domain"]
        RC["client"] --> RS["service"]
        RS --> RE["etl + filters"]
        RS --> RR["repository"]
        RDA["dag"] --> RS
        RSV["salvage"] --> RS
    end

    subgraph AI["AI Analysis Domain"]
        AC["client"] --> AP["pipeline"]
        AP --> AE["etl / Gemini schema"]
        AP --> AR["db_handler"]
    end

    subgraph THREADS["Threads Domain"]
        TP["post"] --> TA["api"]
        TT["token_access"] --> TA
        TA --> TR["threads_log"]
    end

    DB[("PostgreSQL")]
    STORE <--> DB
    REVIEW <--> DB
    AI <--> DB
    THREADS <--> DB
```

## 4. 端到端資料流

```mermaid
flowchart LR
    A1["Apify<br/>Google Places"] --> SS[("store_source<br/>Raw JSONB")]
    SS -->|"ETL + 業務篩選"| ST[("store")]
    ST -->|"合格店家"| A2["Apify<br/>Reviews Scraper"]
    A2 --> RS[("review_source<br/>Raw JSONB")]
    RS -->|"只保留 1–2 星"| RV[("review")]
    RV -->|"有老闆回覆"| GEM["Gemini<br/>Structured Output"]
    GEM --> AI[("ai_analysis")]
    AI --> DASH["Streamlit<br/>地圖／排行／分析"]
    AI --> POST["貼文組裝"]
    POST --> API["Threads Graph API"]
    API --> TL[("threads_log")]

    EL[("execution_log")]
    A1 -.-> EL
    A2 -.-> EL
    GEM -.-> EL
    API -.-> EL
```

## 5. Airflow DAG 拓撲

```mermaid
flowchart TB
    DAILY["dags_trigger_daily_3am<br/>0 3 * * * Asia/Taipei"]
    ALL["dags_trigger_all<br/>手動"]

    RD["review_daily_dag_v2"]
    AD["ai_analysis_daily_dag_v1"]
    TH["threads_dags_v1"]

    ST["store_dag_v1"]
    RI["review_initial_dag_v2"]
    AA["ai_analysis_all_dag_v1<br/>預設略過已分析"]

    SAL["review_salvage_dag_v1<br/>手動、只讀既有 Apify run"]

    DAILY --> RD --> AD --> TH
    ALL --> ST --> RI --> AA --> TH
    SAL
```

> 所有子 DAG 的 `schedule=None`。總控 DAG 使用 `TriggerDagRunOperator(wait_for_completion=True)` 保證階段順序。

## 6. Store Domain 流程

```mermaid
flowchart TD
    START["手動觸發 store_dag_v1"]
    MAP["12 個台北郵遞區號<br/>Dynamic Task Mapping"]
    RUN["start_job<br/>啟動 Apify Actor"]
    CHECK{"check_status<br/>是否 SUCCEEDED？"}
    WAIT["Airflow retry<br/>每 1 分鐘，最多 30 次"]
    DATA["get_dataset"]
    RAW[("store_source<br/>Raw JSONB")]
    FILTER{"Store ETL"}
    STORE[("store")]
    DROP["不納入追蹤"]

    START --> MAP --> RUN --> CHECK
    CHECK -- 否 --> WAIT --> CHECK
    CHECK -- 是 --> DATA --> RAW --> FILTER
    FILTER -- "評論≥30 且<br/>總分≤4.3 或一星≥10%<br/>且仍營業" --> STORE
    FILTER -- 不符合 --> DROP
```

## 7. Review Domain 流程

```mermaid
flowchart TD
    MODE{"執行模式"}
    INIT["Initial<br/>全量、lowestRanking"]
    DAILY["Daily<br/>newest + 昨天起"]
    RECHECK["Recheck<br/>到期店家"]
    BATCH["每批最多 50 家"]
    MAP["Mapped Sensor<br/>最多 5 個 Apify run"]
    START["第一次 poke：啟動 Actor<br/>保存 current map index 的 XCom"]
    STATUS{"每 120 秒查狀態<br/>30 分鐘 timeout"}
    DATA["讀取 Dataset"]
    RAW[("review_source<br/>全部原始評論")]
    ETL["ETL：只保留 1–2 星<br/>排除制式公關回覆"]
    REVIEW[("review")]

    MODE --> INIT --> BATCH
    MODE --> DAILY --> BATCH
    MODE --> RECHECK --> BATCH
    BATCH --> MAP --> START --> STATUS
    STATUS -- 未完成 --> STATUS
    STATUS -- SUCCEEDED --> DATA --> RAW --> ETL --> REVIEW
```

## 8. Owner Reply Recheck 狀態圖

```mermaid
stateDiagram-v2
    [*] --> Waiting: 低星評論尚無老闆回覆
    Waiting: owner_reply_recheck = TRUE；next_check_at = 今日 + 2 天
    Waiting --> Checking: next_check_at 到期
    Checking --> Completed: 找到有效老闆回覆
    Checking --> Skipped: 命中制式公關話術
    Checking --> Waiting: 無回覆且未滿 10 天
    Checking --> Expired: 距發布日超過 10 天
    Completed --> [*]
    Skipped --> [*]
    Expired --> [*]
```

## 9. Apify 付費資料救援流程

```mermaid
flowchart TD
    FAIL["Actor 已啟動<br/>Airflow task 後續失敗"]
    PAID["Apify 繼續完成 run<br/>費用已產生"]
    SAL["手動觸發 review_salvage_dag_v1"]
    FIND["find_runs<br/>列出時限內 SUCCEEDED run"]
    DEDUPE["扣除 execution_log<br/>已有 success 的 run_id"]
    READ["只讀既有 dataset<br/>不啟動新 Actor"]
    UPSERT["共用 Review ETL<br/>Upsert 入庫"]
    LOG["寫入 run_id、dataset_id、成本與結果"]

    FAIL --> PAID --> SAL --> FIND --> DEDUPE --> READ --> UPSERT --> LOG
```

> Apify dataset 約保留 7 天。救援流程查狀態與讀 dataset，不會再啟動付費爬取。

## 10. AI Analysis 流程與斷點續跑

```mermaid
flowchart TD
    SELECT["讀取有老闆回覆的 review"]
    MODE{"模式"}
    DAILY["Daily：scrapedAt > 昨天"]
    ALL["All：預設排除<br/>已存在 ai_analysis 的 reviewId"]
    FORCE["force=true：允許重算全部"]
    BATCH["每批 50 則"]
    GEM["Gemini structured output"]
    OK{"API 成功？"}
    SAVE["每批立即 upsert ai_analysis<br/>並寫 execution_log"]
    RETRY["Airflow 最多重試 2 次<br/>間隔 10 分鐘"]
    RESUME["重試時只讀尚未分析<br/>避免重複 token 費用"]

    SELECT --> MODE
    MODE --> DAILY --> BATCH
    MODE --> ALL --> BATCH
    MODE --> FORCE --> BATCH
    BATCH --> GEM --> OK
    OK -- 是 --> SAVE
    OK -- "503 / 暫時錯誤" --> RETRY --> RESUME --> BATCH
```

## 11. Threads 發文序列圖

```mermaid
sequenceDiagram
    participant AF as Airflow
    participant DB as PostgreSQL
    participant TK as Token Refresh
    participant API as Threads Graph API

    AF->>TK: refresh_threads_token()
    alt 刷新成功
        AF->>DB: 讀取當日最高 review_score + owner_score
        DB-->>AF: 事件內容或無候選
        AF->>API: POST /{user_id}/threads
        API-->>AF: creation_id
        AF->>API: POST /{user_id}/threads_publish
        API-->>AF: publish_id
        AF->>API: GET /{publish_id}
        API-->>AF: permalink / timestamp / text
        AF->>DB: 寫 threads_log + execution_log
    else 刷新失敗
        AF-->>AF: 結束，不發文
    end
```

## 12. GCP 正式環境部署圖

```mermaid
flowchart TB
    OP["維運者"]
    TUN["SSH Tunnel"]

    subgraph VM["GCP VM / Ubuntu / Docker Compose"]
        APIS["airflow-api-server<br/>0.0.0.0:8080（現況）"]
        SCH["airflow-scheduler"]
        DP["airflow-dag-processor"]
        INIT["airflow-init<br/>一次性"]
        DASH["dashboard<br/>0.0.0.0:8501（現況）"]
        DB[("db / PostgreSQL 15<br/>127.0.0.1:5432")]
        PV[("postgres_data")]
        LV[("airflow_logs")]
    end

    EXT["Apify / Gemini / Threads"]

    OP --> TUN
    TUN --> APIS
    TUN --> DASH
    INIT --> DB
    APIS <--> DB
    SCH <--> DB
    DP <--> DB
    DASH --> DB
    DB --- PV
    SCH --- LV
    SCH <--> EXT
```

> 正式環境的程式碼在 build 階段 COPY 進 image，不使用專案 bind mount；更新程式後必須重新 build。現行 compose 只有 PostgreSQL 綁 `127.0.0.1`，Airflow UI 與 Dashboard 綁所有網卡；GCP 防火牆不可開放 8080／8501 公網 ingress，維運應走 SSH tunnel。若要在容器層硬化，port mapping 應改成 `127.0.0.1:8080:8080` 與 `127.0.0.1:8501:8501`。

## 13. Domain Model

```mermaid
classDiagram
    direction LR
    class Store {
        具爭議性的餐飲店家
        blocked
        skip_review_fetch
    }
    class Review {
        1–2 星低星評論
        老闆回覆
        Recheck 狀態
    }
    class AIAnalysis {
        雙方摘要與情緒
        雙方激烈度
        建議公關回覆
    }
    class ThreadsPost {
        貼文內容
        永久連結
    }
    class ExecutionLog {
        Pipeline 狀態
        Request / Response
        Run / Dataset ID
    }

    Store "1" --> "0..*" Review : 擁有
    Review "1" --> "0..1" AIAnalysis : 有回覆才分析
    AIAnalysis "1" --> "0..1" ThreadsPost : 每日最高分可發布
```

`ExecutionLog` 是獨立的跨 Pipeline 紀錄，不直接參照業務實體。

## 14. 實體資料庫 ERD

```mermaid
erDiagram
    store_source ||--o| store : "ETL 後可能保留"
    store ||--o{ review : "placeId 邏輯關聯"
    review_source ||--o| review : "ETL 後可能保留"
    review ||--o| ai_analysis : "reviewId 邏輯關聯"

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

### ERD 注意事項

- `store_source → store`、`review_source → review` 是「Raw 經 ETL 後可能產生 Business row」，不是必然一對一。
- `threads_log` 沒有 `reviewId` 或 `analysisId`；它只保存 Threads API 回傳的貼文資料，所以與 `ai_analysis` 無法在資料庫層直接 join。
- `execution_log` 不與業務表建立關係。
- models 未宣告 Foreign Key、Secondary Index 或 migration；目前參照完整性依賴 ETL 順序與 Upsert。
