import json,requests,logging
from time import sleep
from datetime import datetime, timezone
from shared.config import settings
from db.database import engine,metadata
from db.shared_tables import execution_log
from domains.threads.models import threads_log
from sqlalchemy import insert
from sqlalchemy.exc import SQLAlchemyError
from domains.threads.post import threads_post

logger = logging.getLogger(__name__)

URL = f"https://graph.threads.net/v1.0"
def get_header() -> dict:
    return {
        "Authorization": f"Bearer {settings.threads_long_key}",
        "Content-Type": "application/json"
    }

def to_log(status,items_count,func_name,timestamp,request_json,response_json,error_msg):
    data = {
        "pipeline":"threads",
        "status":status,
        "items_count":items_count,
        "apify_scheduler_id":func_name,
        "actor_name":settings.threads_user_id,
        "started_at":timestamp,
        "finished_at":timestamp,
        "request_json":request_json,
        "response_json":response_json,
        "error_msg":error_msg
    }
    with engine.begin() as conn:
        stmt = insert(execution_log)
        rs = conn.execute(stmt,data)
        print(rs.rowcount)

def create_container():
    create_container_endpoint = f"/{settings.threads_user_id}/threads"
    params = {
        "media_type":"TEXT",
        "text":threads_post()
    }
    try:
        rs = requests.post(url=URL+create_container_endpoint,headers=get_header(),json=params, allow_redirects=False)
        rs_data = rs.json()
        print(rs_data)
        creation_id = rs_data.get("id",None)
        status = "Success" if creation_id else "Error" 
        error_msg = json.dumps(rs_data.get("error",None))
        to_log(status,1,"create_container",datetime.now(timezone.utc) ,params,rs_data,error_msg)

        logger.info(f"[Info:create_container]creation_id:{creation_id}\nmsg:{error_msg}")

        return creation_id
    except Exception as e:
        logger.exception(f"[Error:create_container]發生錯誤")
        raise e

def publish_container(creation_id=None):
    if not creation_id:
        return None
    
    publish_endpoint = f"/{settings.threads_user_id}/threads_publish"
    try:
        request = {"creation_id":creation_id}
        rs = requests.post(url=URL+publish_endpoint,headers=get_header(),json=request,timeout=30)
        publish_data = rs.json()
        publish_id = publish_data.get("id",None)
        print(publish_id)

        status = "Success" if publish_id else "Error" 
        error_msg = json.dumps(publish_data.get("error",None))

        to_log(status,1,"publish_container",datetime.now(timezone.utc) ,request,publish_data,error_msg)
        logger.info(f"[Info:publish_container]publish_id:{publish_id}\nmsg:{error_msg}")

        return publish_id
    except Exception as e:
        logger.exception(f"[Error:publish_container]發生錯誤")
        raise e

def published(publish_id=None):
    params = {
        "fields": "id,text,media_type,media_url,permalink,timestamp"
    }   
    try:
        if publish_id:
            rs = requests.get(url=f"{URL}/{publish_id}",headers=get_header(),params=params)
            publish_data = rs.json()
            published_id = publish_data.get("id",None)
            print(publish_data)
            # {'id': '17888281206670059', 'text': 'This post is test By API. 2026-07-30 15:19:56.300646', 'media_type': 'TEXT_POST', 'permalink': 'https://www.threads.com/@dramarada202/post/Dba_yM7gUrYQrf9EVPlzGupf2FWDzxx9FZTyKc0', 'timestamp': '2026-07-30T15:19:59+0000'}
            status = "Success" if published_id else "Error" 
            time = publish_data.get("timestamp",None)
            error_msg = json.dumps(publish_data.get("error",None))
            to_log(status,1,"get_post",time,{"publish_id":publish_id},publish_data,error_msg)
            logger.info(f"[Info:publish]published_id:{published_id}\nmsg:{error_msg}")

            return publish_data
        else:
            return None
        
    except Exception as e:
        logger.exception(f"[Error:publish]發生錯誤")
        raise e

def save_to_sql(publish_data=None):
    try:
        if publish_data:
            metadata.create_all(engine)
            with engine.begin() as conn:
                stmt = insert(threads_log)
                rs = conn.execute(stmt,publish_data)
                if rs.rowcount > 0:
                    print("儲存成功")
                logger.info(f"[Info:save_to_sql]rowcount:{rs.rowcount}")
        else:
            logger.exception(f"[Error:save_to_sql]publish_data is None:{publish_data}")


    except SQLAlchemyError as e:
        logger.exception(f"[Error:save_to_sql]發生錯誤")
        raise e

def threads_run():
    creation_id = create_container()
    publish_id = publish_container(creation_id)
    publish_data = published(publish_id)
    save_to_sql(publish_data)
