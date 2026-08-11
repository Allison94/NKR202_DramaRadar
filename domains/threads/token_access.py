import requests,logging
from shared.config import settings
from dotenv import set_key
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
        return data.get("access_token",None)
    except Exception as e:
        logger.exception("[Error: change_long_key 短期token換長期token失敗]")
        print(e)
        return None

def refresh_threads_token():
    endpoint = f"{url}refresh_access_token"
    params = {
        "grant_type":"th_refresh_token",
        "access_token":"DELETED_KEY"
    }
    try:
        rs = requests.get(url=endpoint,params=params)
        data = rs.json()
        access_token = data.get("access_token",None)
        if access_token:
            set_key(".env","THREADS_LONG_KEY",access_token)
            logger.info("[Info:refresh_threads_token] access_token已寫入")
            return True
        else:
            logger.error("[Error:refresh_threads_token] access_token延長失敗")
            return False
    except Exception as e:
        logger.exception(f"[Error: refresh_threads_token token效期更新失敗]")
        raise e
