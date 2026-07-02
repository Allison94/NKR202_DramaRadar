# 1. 用uv官方的 Python 3.12 輕量版環境（速度極快、體積極小）
FROM ghcr.io/astral-sh/uv:python3.12-slim

# 2. 設定容器內部的虛擬工作目錄
WORKDIR /nkr202_dramaradar

# 3. 安裝 Linux 與 Git 必備工具，以及編譯 PostgreSQL 驅動所需的底層系統套件
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    openssh-client \
    sudo \
    curl \
    gcc \ 
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. 建立 vscode 安全使用者，避免 Docker 內外檔案發生權限衝突
ARG USERNAME=vscode
RUN useradd -m $USERNAME && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME

# 5. 預先複製套件清單並執行uv同步（利用 Docker 快取機制，只要沒新增套件，之後啟動都只要 1 秒鐘）
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-cache

# 6. 預先開放所有可能用到的連接埠 (8000:FastAPI, 8501:Streamlit, 8080:Airflow, 5432:Postgres)
EXPOSE 8000 8501 8080 5432

# 7. 切換為安全使用者登入
USER $USERNAME
