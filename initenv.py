#初始化本機env檔案，自動產生資料
import os
import secrets

def init_env():
    env_file = ".env"
    example_file = ".env.example"

    # 如果已經有 .env 了，就什麼都不做
    if os.path.exists(env_file):
        print(".env 檔案已存在，跳過自動生成。")
        return

    # 檢查有沒有範本檔
    if not os.path.exists(example_file):
        print(f"找不到 {example_file}，請確認專案結構！")
        return

    # 隨機產生一組 16 字元的安全密碼
    random_password = secrets.token_urlsafe(12)

    print("自動生成本地開發專屬的.env檔案...")
    
    with open(example_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 自動填入本地開發用的預設帳密
    content = content.replace("POSTGRES_USER=", "POSTGRES_USER=dev_user")
    content = content.replace("POSTGRES_PASSWORD=", f"POSTGRES_PASSWORD={random_password}")
    content = content.replace("POSTGRES_DB=", "POSTGRES_DB=dramaradar_dev")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"已自動建立 .env 並隨機生成安全密碼。")

if __name__ == "__main__":
    init_env()
