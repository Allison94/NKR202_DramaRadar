# 010-GCP VM Deployment

- **Version**：v1.0
- **Date**：2026/8/22
- **Author**：Allison

---

# 1. Purpose

說明如何把 DramaRadar 部署到單台 GCP Compute Engine VM。

使用的是 `docker-compose.prod.yml` 那一組正式環境設定，**不是**根目錄給 Dev Container 用的 `docker-compose.yml`。兩者的差異與原因見 README 的「部署到正式環境」章節。

# 2. 事前準備

| 項目 | 說明 |
|---|---|
| GCP 專案 | 已啟用 Compute Engine API 並綁定帳單 |
| `gcloud` CLI | 本機已安裝並 `gcloud auth login` |
| GitHub | 有 repo 的讀取權限（下面用 Deploy Key） |
| 第三方金鑰 | Gemini、Apify（store / review 各一把）、Threads 三項 |

# 3. 機型選擇

記憶體是唯一需要認真算的資源。常駐服務（PostgreSQL、api-server、scheduler、dag-processor、Dashboard）約佔 2.2GB，其餘留給 Airflow 的 task process — 每個約 300MB，數量由 `AIRFLOW_PARALLELISM` 決定。

| 機型 | 記憶體 | 建議 `AIRFLOW_PARALLELISM` | 適用 |
|---|---|---|---|
| `e2-medium` | 4GB | 3 | 最低限度，建議另外開 swap |
| `e2-standard-2` | 8GB | 6（預設） | **建議** |
| `e2-standard-4` | 16GB | 12 | 未來擴大到其他縣市時 |

磁碟至少 30GB：兩個 image 加起來約 4GB，其餘給 PostgreSQL 資料與 Airflow logs。預設的 10GB 會在 build 階段就爆掉。

# 4. 建立 VM

`asia-east1`（彰化）延遲最低，資料範圍也是台北。

```bash
gcloud compute instances create dramaradar \
  --zone=asia-east1-b \
  --machine-type=e2-standard-2 \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-balanced
```

**不需要開任何防火牆規則。** `docker-compose.prod.yml` 裡所有服務都只綁 `127.0.0.1`，公網 IP 上看不到任何東西，一律透過 SSH tunnel 存取（見第 9 節）。這是刻意的設計，不要為了方便去改。

# 5. 安裝 Docker

```bash
gcloud compute ssh dramaradar --zone=asia-east1-b
```

進到 VM 之後：

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

> **一定要重新登入。** 群組成員資格是在登入時寫進 session 的，`usermod` 對已經開著的 shell 不會追溯生效。少了這步，接下來每個 docker 指令都會噴 `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`。

```bash
exit
```

重新 `gcloud compute ssh dramaradar --zone=asia-east1-b` 進來，然後確認：

```bash
docker compose version
docker ps
```

兩個指令都不報錯才算完成。不想斷線的話，`newgrp docker` 也可以在當前 session 直接切換群組。

# 6. 取得程式碼

Repo 是私有的，用唯讀 Deploy Key 最乾淨 — 不需要在 VM 上放任何個人帳號憑證。

在 VM 上產生金鑰：

```bash
ssh-keygen -t ed25519 -C "dramaradar-vm" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

把輸出的公鑰貼到 GitHub：repo → **Settings** → **Deploy keys** → **Add deploy key**，**不要**勾選 Allow write access。

然後 clone：

```bash
git clone git@github.com:Allison94/NKR202_DramaRadar.git
cd NKR202_DramaRadar
```

# 7. 設定 .env.prod

```bash
cp .env.prod.example .env.prod
chmod 600 .env.prod
```

產生需要的密鑰。以下都只用 Debian 內建工具，不依賴 docker，所以這一步可以先做，不必等 docker 權限處理好：

```bash
# POSTGRES_PASSWORD、AIRFLOW_ADMIN_PASSWORD
openssl rand -base64 24

# AIRFLOW_JWT_SECRET、AIRFLOW_API_SECRET_KEY（各跑一次）
openssl rand -hex 32

# AIRFLOW_FERNET_KEY
# Fernet.generate_key() 的實作就是 base64.urlsafe_b64encode(os.urandom(32))，
# 所以用標準函式庫產生即可，不需要安裝 cryptography
python3 -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

嫌一個一個貼太麻煩的話，用這段一次補完所有機器可產生的欄位。它只會填**空值**，已經有值的不動，重複執行安全：

```bash
python3 - <<'PY'
import base64, os, re, secrets, pathlib

p = pathlib.Path(".env.prod")
text = p.read_text()

gen = {
    "POSTGRES_PASSWORD":      lambda: secrets.token_urlsafe(24),
    "AIRFLOW_ADMIN_PASSWORD": lambda: secrets.token_urlsafe(18),
    "AIRFLOW_JWT_SECRET":     lambda: secrets.token_hex(32),
    "AIRFLOW_API_SECRET_KEY": lambda: secrets.token_hex(32),
    "AIRFLOW_FERNET_KEY":     lambda: base64.urlsafe_b64encode(os.urandom(32)).decode(),
}
for key, make in gen.items():
    text, n = re.subn(rf"(?m)^{key}=\s*$", lambda m, k=key, f=make: f"{k}={f()}", text)
    print(f"{key}: {'已產生' if n else '已有值，略過'}")
p.write_text(text)
PY
```

產生的值都限定在 URL-safe 字元集，不會弄壞 compose 組出來的 `postgresql://` 連線字串。

剩下六組第三方 API 金鑰只能手動填：

```bash
nano .env.prod
```

`shared/config.py` 的七個欄位**全部必填**，留空的話容器會在 import 階段拋 `ValidationError` 然後反覆重啟。`DATABASE_URL` 不用填，compose 會依 `POSTGRES_*` 自動組出來。

> **注意 `AIRFLOW_ADMIN_PASSWORD`。** compose 只對 Fernet key 與兩個 secret 做了必填檢查（`:?`），管理者密碼留空**不會**報錯，但會建出一個空密碼的 Admin 帳號。上面的腳本已經涵蓋這個欄位。

填完先驗證，不要直接 build：

```bash
# 列出仍為空值的欄位，沒有輸出就代表填完了
grep -nE '^[A-Z_]+=$' .env.prod

# 只做解析檢查，秒回；比等 10 分鐘 build 完才發現設定錯要快得多
docker compose -f docker-compose.prod.yml --env-file .env.prod config -q
```

# 8. 啟動

指令很長，先設個 alias：

```bash
echo "alias dc='docker compose -f docker-compose.prod.yml --env-file .env.prod'" >> ~/.bashrc
source ~/.bashrc
```

啟動（第一次要 build，約 10 分鐘）：

```bash
dc up -d --build
```

確認狀態：

```bash
dc ps
```

`airflow-init` 應該是 `Exited (0)`（一次性任務，跑完就結束），其餘服務都要是 `Up`。若 `airflow-init` 不是 0，看它的 log：

```bash
dc logs airflow-init
```

# 9. 存取服務

**回到自己的電腦**，開一條 SSH tunnel：

```bash
gcloud compute ssh dramaradar --zone=asia-east1-b -- -N \
  -L 8080:localhost:8080 \
  -L 8501:localhost:8501
```

這個視窗保持開著，然後在瀏覽器打開：

| 服務 | 網址 | 帳密 |
|---|---|---|
| Airflow UI | http://localhost:8080 | `.env.prod` 的 `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` |
| Dashboard | http://localhost:8501 | 無 |

要讓團隊長期存取 Dashboard，請在 VM 上加一層反向代理（Caddy 最省事，自動處理 Let's Encrypt 憑證）並設定認證，**不要**把 compose 裡的 `127.0.0.1` 改成 `0.0.0.0`。

# 10. 首次灌資料

正式環境的 DAG 預設是**啟用**的（`DAGS_ARE_PAUSED_AT_CREATION=false`），所以 `dags_trigger_daily_3am` 隔天凌晨 3 點就會自己跑。但資料庫是空的，第一次要手動觸發全量流程。

在 Airflow UI 找到 `dags_trigger_all` 手動觸發，它會依序跑：

```
store_dag_v1 → review_initial_dag_v2 → ai_analysis_all_dag_v1 → threads_dags_v1
```

> **這一步會實際花錢。** Apify 店家爬蟲按筆計費（約 $0.005 USD / 店），12 個郵遞區號 × 6 個關鍵字 × 每組最多 20 筆；評論爬蟲與 Gemini 另計。建議先在 Apify 後台確認額度上限。

全量流程視資料量可能跑數小時，過程中可以看 log：

```bash
dc logs -f airflow-scheduler
```

# 11. 日常維運

## 更新程式碼

```bash
cd ~/NKR202_DramaRadar
git pull
dc up -d --build
```

因為程式碼是烘進 image 的，**改完一定要重新 build**，不像開發環境改檔就生效。

## 查看 log

```bash
dc logs -f airflow-scheduler
dc logs -f dashboard
dc logs --tail 100 airflow-api-server
```

## 備份資料庫

`postgres_data` 是 Docker 具名 volume，VM 砍掉就沒了。至少要定期匯出：

```bash
dc exec db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backup-$(date +%F).sql.gz
gsutil cp backup-$(date +%F).sql.gz gs://<your-bucket>/dramaradar/
```

建議掛進 VM 的 crontab 每日執行。

## 重啟 / 停止

```bash
dc restart airflow-scheduler   # 單一服務
dc down                        # 全部停止（資料保留）
dc down -v                     # 連 volume 一起刪，資料會消失
```

# 12. 疑難排解

| 症狀 | 原因與處理 |
|---|---|
| `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock` | `usermod -aG docker` 後沒有重新登入。用 `id -nG $USER` 對照 `groups`：前者有 docker、後者沒有，就是還沒生效。`exit` 重新 SSH，或執行 `newgrp docker`。兩邊都沒有 docker 則是 `usermod` 漏跑了 |
| `required variable XXX is missing a value` | `.env.prod` 存在但欄位是空的（多半是複製完範本忘了填）。回到第 7 節跑產生腳本，再用 `grep -nE '^[A-Z_]+=$' .env.prod` 確認沒有漏 |
| `env file ... not found` | `.env.prod` 根本不存在。compose 每個服務都宣告了 `env_file: .env.prod`，這與 `--env-file` 旗標是兩套機制，檔案必須實際存在 |
| Task 被 kill、log 出現 `Killed` 或 OOM | 記憶體不足。調低 `.env.prod` 的 `AIRFLOW_PARALLELISM`（4GB 機型設 3），或升機型 |
| build 到一半失敗，`no space left on device` | 磁碟滿了。`docker system prune -af` 清掉舊 image，或擴充磁碟 |
| 服務起來但立刻退出，log 是 `ValidationError` | `.env.prod` 有欄位沒填。`shared/config.py` 的七個欄位全部必填 |
| Airflow UI 連不上 | 確認 SSH tunnel 還開著，以及 `dc ps` 裡 `airflow-api-server` 是 `Up` |
| Airflow UI 打得開，但帳密登入失敗 | 多半是**改了 `.env.prod` 的密碼但帳號早就建好了**。`airflow users create` 遇到既有帳號會直接跳過、不更新密碼。先用 `dc exec airflow-api-server airflow users list` 確認帳號存在，再依下方指令重設。另外注意手打密碼時 `O`/`0`、`l`/`1`/`I` 很容易混淆 |
| DAG 在 UI 上看不到 | `dc logs airflow-dag-processor` 看有沒有 import error；改過程式碼但沒重新 build 也會這樣 |
| Dashboard 顯示「已連線但沒有資料」 | 資料庫是空的，需先執行第 10 節的首次灌資料 |
| Threads 發文突然停掉 | 長期權杖過期。見第 13 節 |

## 重設 Airflow 管理者密碼

```bash
dc exec airflow-api-server \
  airflow users reset-password --username admin --password '新密碼'
```

密碼務必用單引號包起來，否則 shell 會解讀裡面的符號。

`airflow-init` 在每次啟動時都會重設一次管理者密碼，因此改完 `.env.prod` 後直接 `dc up -d` 也會生效。反過來說，**在 UI 手動改過的管理者密碼會在下次啟動時被 `.env.prod` 蓋掉** —— 要換密碼請改 `.env.prod`，不要在 UI 改。

# 13. 已知限制

## Threads 權杖無法自動續期

`domains/threads/token_access.py` 的 `refresh_threads_token()` 用 `set_key(".env", ...)` 把新權杖寫回檔案。這個做法在容器環境**沒有作用**：

1. 寫入的是容器內的暫存檔，重建容器就消失。
2. pydantic-settings 的環境變數優先序高於 `.env` 檔，就算寫進去也不會被讀到。

實務影響是排程不會報錯，但權杖不會真的延長。**必須在 60 天內手動更新**：

```bash
# 本機取得新的短期權杖後，在 VM 上換成長期權杖
dc run --rm airflow-scheduler python -m domains.threads.token_access
# 把輸出的長期權杖填回 .env.prod 的 THREADS_LONG_KEY
nano .env.prod
dc up -d
```

根治方式是把權杖改存資料庫，見 README 的「未來事項」。

## 其他

- Airflow metadata 與業務資料共用同一個 PostgreSQL。清資料庫時不要整個 drop。
- 資料庫只有主鍵索引，沒有外鍵約束（見 `004-Database Design.md` 第 6、7 節）。目前資料量不構成問題。
- 單台 VM 沒有高可用性。VM 重啟時 compose 的 `restart: unless-stopped` 會自動拉起服務，但 VM 本身故障就會中斷。
