import os

import requests
from dotenv import load_dotenv

# 讀取 .env
load_dotenv()

# 取得 Token
token = os.getenv("APIFY_REVIEW")

if not token:
    print("找不到 APIFY_REVIEW")
    exit()

print("APIFY_REVIEW 讀取成功")
print("Token 前 10 碼：", token[:10], "...")

# API Header
headers = {
    "Authorization": f"Bearer {token}"
}

# 呼叫 Apify API
response = requests.get(
    "https://api.apify.com/v2/acts/compass~google-maps-reviews-scraper",
    headers=headers,
    timeout=30,
)

# 顯示結果
print("狀態碼：", response.status_code)

data = response.json()["data"]

print("Actor 名稱：", data["title"])
print("Actor 建立者：", data["username"])
print("Actor ID：", data["id"])
print("是否公開：", data["isPublic"])