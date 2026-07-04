# 1. 用 uv 官方的 Python 3.12 輕量版環境
# FROM ghcr.io/astral-sh/uv:python3.12-slim
FROM astral/uv:python3.12-bookworm-slim

# 2. 設定容器內部的虛擬工作目錄
WORKDIR /nkr202_dramaradar

# 3. 安裝Linux與Git必備工具，以及編譯所需的系統套件
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    openssh-client \
    sudo \
    curl \
    gcc \ 
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. 建立vscode安全使用者，避免權限衝突
ARG USERNAME=vscode
RUN useradd -m $USERNAME && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME

# 將工作目錄的擁有者改為vscode使用者
# 因為第2步root建立此資料夾後，若不修改擁有權，第5步切換成vscode會無法在裡面寫入檔案（例如無法建立.venv）
RUN chown -R $USERNAME:$USERNAME /nkr202_dramaradar

# 5. 切換為安全使用者登入
USER $USERNAME

# 讓uv把虛擬環境建立在工作目錄下（.venv），並且將虛擬環境的執行路徑加到系統PATH中
ENV UV_PROJECT_ENVIRONMENT=/nkr202_dramaradar/.venv
ENV PATH="/nkr202_dramaradar/.venv/bin:$PATH"

# 6. 複製套件清單並執行uv同步
COPY --chown=$USERNAME:$USERNAME pyproject.toml uv.lock* ./
RUN uv sync --no-cache

# 7. 預先開放連接埠 (8000:FastAPI, 8501:Streamlit, 8080:Airflow, 5432:Postgres)
EXPOSE 8000 8501 8080 5432
