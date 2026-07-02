# 🗺️ NKR202_DRAMARADAR - 重要檔案地圖

* 採用 **Dev Containers** 架構
* 安裝 Docker Desktop 並一鍵啟動，即可獲得完全一致的開發環境

```text
nkr202_dramaradar/
├── .devcontainer/
│   ├── devcontainer.json   <-- 設定連接埠轉發、指定 app 服務路徑、自動安裝vscode extension、python環境
│   └── docker-compose.yml  <-- 啟動Python執行環境(app)與PostgreSQL 15資料庫(db)
├── .env                    <-- 密碼本：存放本機資料庫帳密與 Gemini 等 API Key（!! 絕對禁止推上 Git !!）
├── .env.example            <-- 密碼本範例，可推上git，目的是告知需要的key或欄位清單
├── Dockerfile              <-- 以Python 3.12+uv為基底，加裝Git憑證與Postgres驅動
├── pyproject.toml          <-- 定義專案所需的套件
├── .gitignore              <-- 設定git排除上傳內容
└── docs                    <-- 專案所有架構文件

```

### 快速起手式
* 確認安裝
    - [ ] 確認電腦已安裝 [Docker Desktop](https://docker.com) 或是其他docker gui 工具都可以，並且已經啟動（左下角顯示綠色 Engine Running）。
    - [ ] 確認git已安裝，cmd 輸入`git -v`可確認是否有安裝
    - [ ] 確認vscode已安裝
    - [ ] 確認ssh通道已開啟 (git push & git pull用)
    > **連不上git再做**
    > Mac: Terminal 輸入`ssh-add ~/.ssh/id_rsa`
    > Win: 到service 找到`OpenSSH Authentication Agent`啟用，powershell 輸入 `ssh-add $env:USERPROFILE\.ssh\id_rsa`
* 確認帳號
    - [ ] 確認是否已有github帳號
    - [ ] 確認是否已被加入github專案協作者
* 啟用專案 & 安裝環境
    - [ ] 電腦先建立一個放置專案的資料夾，都用小寫英文，命名`nkr202_dramaradar`
    - [ ] 用 VS Code 開啟剛剛建的專案資料夾。
    - [ ] 點選vscode 左側`原始檔控制`功能，登入github帳號
    - [ ] 打開`終端機`，輸入`git clone 專案網址`
    - [ ] 將專案最外層 `.env.example`檔案改為`.env`，填入API金鑰。
    > (所有不能讓別人看的機密資料都要存在這邊，然後引入到程式內)
    - [ ] 點選選單或快捷鍵，執行 `開發容器: 在容器中開啟資料夾...`，即可進入共同開發環境！
