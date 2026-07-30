import requests
from shared.config import settings
import logging

url = "https://graph.threads.net/"
logger = logging.getLogger(__name__)

def change_long_key():
    endpoint = f"{url}access_token"
    short_token = ""
    params = {
        "grant_type":"th_exchange_token",
        "client_secret":settings.threads_api_key,
        "access_token":short_token,# 帶短期權杖
    }

    try:
        rs = requests.get(url=endpoint,params=params)
        data = rs.json()
        print(data)
        return data["access_token"]
    except Exception as e:
        logger.exception("[Error: change_long_key 短期token換長期token失敗]")
        print(e)
        return ""

def refresh_threads_token():
    endpoint = f"{url}refresh_access_token"
    params = {
        "grant_type":"th_refresh_token",
        "access_token":settings.threads_api_key
    }
    try:
        rs = requests.get(url=endpoint,params=params)
        data = rs.json()
        print(data)
        return data 
    except Exception as e:
        logger.exception(f"[Error: refresh_threads_token token效期更新失敗]")
        print(e)
        return None

if __name__ == "__main__":
    refresh_threads_token()