# 🗺️ NKR202_DRAMARADAR - 重要檔案地圖

* 採用 **Dev Containers** 架構
* 安裝 Docker Desktop 並一鍵啟動，即可獲得完全一致的開發環境

> 本頁著重在「環境怎麼建起來」。專案功能、DAG 一覽與業務規則請看 [`README.md`](README.md)。

## 環境相關檔案

```text
nkr202_dramaradar/
├── .devcontainer/
│   └── devcontainer.json   <-- 指定 app 服務、連接埠轉發、自動安裝 vscode extension、進容器後自動 uv sync
├── docker-compose.yml      <-- 【在根目錄，不在 .devcontainer 內】啟動 app、db(PostgreSQL 15)、Airflow 四個服務
├── Dockerfile              <-- app 開發容器：以 Python 3.12 + uv 為基底，加裝 Git 憑證與 Postgres 驅動
├── Dockerfile.airflow      <-- Airflow 容器
├── init_env.py             <-- 開啟 Dev Container 時自動執行，由 .env.example 產生 .env 並填入隨機資料庫／Airflow 密碼
├── .env                    <-- 密碼本：本機資料庫帳密與 Gemini 等 API Key（!! 絕對禁止推上 Git !!）
├── .env.example            <-- 密碼本範例，可推上 git，目的是告知需要的 key 或欄位清單
├── pyproject.toml          <-- 定義專案所需的套件
├── uv.lock                 <-- 套件版本鎖定檔，確保每個人裝到一樣的版本
├── requirements.txt        <-- 由 pyproject.toml 編譯而來，只給 Airflow 映像檔用（Airflow 走 pip 不走 uv）
├── .gitignore              <-- 設定 git 排除上傳內容
├── .dockerignore           <-- 設定 docker 排除內容
└── .streamlit/config.toml  <-- Dashboard 佈景設定（純 UI，不影響 Docker/DB）
```

正式環境另有一組獨立檔案，**本機開發完全用不到**，改動時也不會影響開發環境：

```text
nkr202_dramaradar/
├── docker-compose.prod.yml  <-- 正式環境服務定義：不掛載原始碼、logs 與 DB 走具名 volume；目前只有 DB 明確綁 127.0.0.1
├── Dockerfile.prod          <-- Dashboard 正式映像檔，venv 建在 /opt/venv（專案目錄外）
├── Dockerfile.airflow.prod  <-- Airflow 正式映像檔，base image 釘死 3.3.0-python3.12
└── .env.prod.example        <-- 正式環境設定範本（實際的 .env.prod 同樣禁止 commit）
```

部署步驟見 [`docs/05_Deployment/010-GCP VM Deployment.md`](<docs/05_Deployment/010-GCP VM Deployment.md>)。

## 程式與文件

```text
nkr202_dramaradar/
├── shared/                 <-- 跨 Domain 共用設定，統一讀取 .env
├── db/                     <-- 資料庫連線、共用資料表、schema.sql
├── domains/                <-- 四個業務 Domain 與 DAG 定義（整個資料夾掛載為 Airflow 的 dags 目錄）
│   ├── dags.py             <-- 總控 DAG：每日 3 點排程 / 一次性全量重跑
│   ├── store/              <-- 店家蒐集
│   ├── review/             <-- 評論蒐集
│   ├── ai_analysis/        <-- Gemini 分析
│   └── threads/            <-- Threads 發文
├── dashboard/              <-- Streamlit 前端
├── scheduler/              <-- Airflow 執行期產物（logs / plugins / config），掛載進容器
└── docs/                   <-- 專案所有架構文件，入口見 docs/map.md
```

各資料夾內都有 `Note.md` 記錄該部分的實作細節與參數選擇理由，`docs/` 內的圖表一律以 Mermaid 內嵌，沒有獨立圖片檔。

### 快速起手式
* 確認安裝
    - [ ] 確認電腦已安裝 [Docker Desktop](https://docker.com) 或是其他 docker gui 工具都可以，並且已經啟動（左下角顯示綠色 Engine Running）。
    - [ ] 確認 git 已安裝，cmd 輸入 `git -v` 可確認是否有安裝
    - [ ] 確認 vscode 已安裝，並安裝 **Dev Containers** 擴充套件
    - [ ] 確認 ssh 通道已開啟 (git push & git pull 用)
    > **連不上 git 再做**
    > Mac: Terminal 輸入 `ssh-add ~/.ssh/id_rsa`
    > Win: 到 service 找到 `OpenSSH Authentication Agent` 啟用，powershell 輸入 `ssh-add $env:USERPROFILE\.ssh\id_rsa`
* 確認帳號
    - [ ] 確認是否已有 github 帳號
    - [ ] 確認是否已被加入 github 專案協作者
    - [ ] 準備好第三方 API 金鑰：Gemini、Apify、Threads
* 啟用專案 & 安裝環境
    - [ ] 電腦先建立一個放置專案的資料夾，都用小寫英文，命名 `nkr202_dramaradar`
    - [ ] 用 VS Code 開啟剛剛建的專案資料夾。
    - [ ] 點選 vscode 左側 `原始檔控制` 功能，登入 github 帳號
    - [ ] 打開 `終端機`，輸入 `git clone 專案網址`
    - [ ] 點選選單或快捷鍵，執行 `開發容器: 在容器中開啟資料夾...`
    > 開啟時會自動執行 `init_env.py` 產生 `.env`（含隨機資料庫與 Airflow 密碼），進入容器後自動執行 `uv sync` 安裝套件。**不需要**手動把 `.env.example` 改名。
    - [ ] 打開 `.env`，補上第三方 API 金鑰：`GEMINI_API_KEY`、`APIFY_STORE`、`APIFY_REVIEW`、`THREADS_API_KEY`、`THREADS_LONG_KEY`、`THREADS_USER_ID`
    > (所有不能讓別人看的機密資料都要存在這邊，然後引入到程式內)
    - [ ] 第一次使用 Airflow 需初始化：終端機執行 `docker compose up airflow-init`
    - [ ] 完成！開 http://localhost:8080 進 Airflow，或執行 `uv run streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501` 開 Dashboard

### 注意事項

* **`.env` 絕對不要 commit。** 已列入 `.gitignore`，但改動 git 設定時請再確認一次。
* **`DATABASE_URL` 不在 `.env.example` 裡。** 它由 `docker-compose.yml` 依 `POSTGRES_*` 三個變數組出後注入容器。要在容器外跑程式的話得自己設，並把 host 從 `db` 改成 `localhost`。
* **`shared/config.py` 的環境變數全部必填。** 少填任何一個 API 金鑰，程式在 import 階段就會拋 `ValidationError`，不是等到呼叫 API 才失敗。只想跑 Dashboard 也一樣要把 `.env` 填齊。
* **Airflow DAG 預設是暫停的。** 進 UI 後要手動打開才會執行。
* **改了 `models.py` 的欄位不會自動生效。** 專案沒有導入 migration 工具，`metadata.create_all()` 只建立不存在的資料表，不會 ALTER 既有資料表。需手動下 SQL，或用 `uv run python -m domains.review.run_pipeline --mode clear-store` 清空業務資料表後重建。
* **Apify 與 Gemini 都是按量計費。** `domains/store/tests/test_pipeline.py` 會實際發動爬蟲，執行前先確認額度。手動測 Review 時建議加 `--max-reviews 5`。
* **Airflow 與業務資料共用同一個 PostgreSQL。** 清資料庫時不要整個 drop，會把 Airflow 的 metadata 一起清掉。
* **`scheduler/logs/` 會持續長大。** 已被 `.gitignore` 排除，不用 commit，但本機空間要留意。
* **套件請透過 `uv` 安裝**（`uv add 套件名`），讓 `pyproject.toml` 與 `uv.lock` 同步更新，不要直接 `pip install`。
