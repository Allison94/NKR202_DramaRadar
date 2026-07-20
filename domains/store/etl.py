"""
* 處理從client端取得資料
* 整理後資料傳入SQL
"""
import logging
import re
import pandas as pd
import numpy as np
import requests 
import json
from datetime import datetime
from domains.store.config import chains
logger = logging.getLogger(__name__)
def json_obj_format(obj):
    if isinstance(obj,datetime): # 時間格式轉文字時間
        return obj.isoformat()
    
    if hasattr(obj,"__dict__"): # 標準dict格式
        return obj.__dict__
    
    return str(obj)

def start_job_etl(params:dict,obj:dict)->dict:
    return {
        "run_id":obj.get("id"),
        "dataset_id":obj.get("default_dataset_id"),
        "started_at":obj.get("started_at"),
        "status":obj.get("status"),
        "request_json":json.loads(json.dumps(params,default=json_obj_format)),
        "response_json":json.loads(json.dumps(obj,default=json_obj_format)),
    }

def check_status_etl(obj:dict,job_log_id:str)->dict: #job_log_id從 db_handler裡面取回
    # exitcode正常為０ data_counts取得資料列 message不管正常不正常都會有 "you can 刪掉系統廢話"
    
    charged = obj.get("charged_event_counts",{})
    status_message = f"""Exit_code:{obj.get("exit_code")}\nMessage:{(obj.get("status_message") or "").split("You can")[0]}"""

    rt = {
        "job_log_id":job_log_id,
        "run_id":obj.get("id"),
        "status":obj.get("status"), #SUCCEEDED,READY
        "started_at":obj.get("started_at"),
        "finished_at":obj.get("finished_at"),
        "charged_event_counts":charged.get("place-scraped", 0), #怕沒欄位先補0
        "status_message":status_message,
        "response_json":json.loads(json.dumps(obj,default=json_obj_format)),
        "items_count":charged.get("place-scraped", 0)
    }
    return rt

def dataset_origin(obj:list[dict])->list[dict]:
    rt = [
        {
            "placeId":item.get("placeId"),
            "raw_json":json.loads(json.dumps(item,default=json_obj_format)),
            "scrapedAt":item.get("scrapedAt"),
        } for item in obj
    ]
    # [i for i in range(5)]

    return rt

def dataset_etl(obj:list[dict])->list[dict]:
    # c1. reviewsCount >= 30 (評論數大於30)
    # c2. totalScore <= 4.4 or oneStar/reviewsCount >= (0.1 總分低於4.4或1星佔10%)
    # business_status ? permanentlyClosed & temporarilyClosed => False
    # blocked ? (預設false後續人工調整預留位)
    # skip_review_fetch ? (排除連鎖店跟制式回覆店家，這裡只能排除連鎖)

    sql_columns=["placeId","title","categoryName","categories","address","lat","lng","url","imageUrl","business_status","scrapedAt","totalScore","reviewsCount","oneStar","twoStar","threeStar","fourStar","fiveStar","blocked","skip_review_fetch"]

    c1 = "reviewsCount >= 30"
    c2 = "(totalScore <= 4.4 or oneStarPercent >= 0.1)"

    df = pd.json_normalize(obj)

    if df.empty:
        return []
    
    df = df.dropna(subset=["title"]) #先清掉店名空的
    df_set = df.assign(
        reviewsCount = lambda x :x["reviewsCount"].fillna(0),
        oneStar = lambda x : x["reviewsDistribution.oneStar"].fillna(0),
        twoStar = lambda x : x["reviewsDistribution.twoStar"].fillna(0),
        threeStar = lambda x : x["reviewsDistribution.threeStar"].fillna(0),
        fourStar = lambda x : x["reviewsDistribution.fourStar"].fillna(0),
        fiveStar = lambda x : x["reviewsDistribution.fiveStar"].fillna(0),
        oneStarPercent =lambda x : np.where(x["reviewsCount"] > 0,x["oneStar"]/x["reviewsCount"],0.0),
        categories = lambda x : x["categories"].fillna("").str.join(","),
        lat = lambda x: x["location.lat"],
        lng = lambda x: x["location.lng"]
    ).query(
        f"{c1} and {c2}"
    ).assign(
        business_status=lambda x: np.where(x["permanentlyClosed"] | x["temporarilyClosed"],"CLOSED","OPEN"),
        skip_review_fetch = lambda x : x["title"].str.contains(str(excluded_restaurants("|")),na=False,regex=True), #排除連鎖店和已知指定店家
        blocked=False,#預設FALSE,
    ).replace({np.nan: None})

    try:
        return df_set[sql_columns].to_dict(orient="records")
    except Exception as e:
        logger.exception(
            f"[Error:dataset_etl]"
            f"預期欄位:{sql_columns}\n"
            f"產出欄位:{list(df_set.columns)}\n"
        )
        raise e

def excluded_restaurants(joinstr=None)->str|list: #連鎖店清單，用ai抓的
    if joinstr == False or joinstr == None:
        return chains #從config抓
    return joinstr.join(re.escape(r) for r in chains)

# TEST BLOCK
if __name__ == "__main__":
    url = "https://api.apify.com/v2/datasets/bQussivqr43V3XDdF/items?signature=MC4xNzg1NDM2MzYzNjg3LlVtemlUNHVRamVOTEVLTUZ3ZEl0&format=json&clean=true"

    da = requests.get(url).json()
    
    print(dataset_etl(da))