from datetime import datetime, timezone
import json

import requests
from shared.config import settings
from db.database import engine,metadata
from db.shared_tables import execution_log
from domains.threads.models import threads_log
from sqlalchemy import insert,select

def to_log(status,items_count,func_name,timestamp,request_json,response_json,error_msg):
    data = {
        "pipeline":"threads",
        "status":status,
        "items_count":items_count,
        "apify_scheduler_id":func_name,
        "actor_name":user_id,
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

user_id = "DELETED_KEY" #!組長說這個要改到env
url = f"https://graph.threads.com/v1.0"
create_container_endpoint = f"/{user_id}/threads"
header = {
    "Authorization":f"Bearer {settings.threads_api_key}",
    "Content-Type": "application/json"
}
params = {
    "media_type":"TEXT",
    "text":f"This post is test By API. {datetime.now()}"
}
rs = requests.post(url=url+create_container_endpoint,headers=header,json=params, allow_redirects=False)
rs_data = rs.json()
print(rs_data)
creation_id = rs_data.get("id",None)
status = "Success" if creation_id else "Error" 
error_msg = json.dumps(rs_data.get("error",None))
to_log(status,1,"create_container",datetime.now(timezone.utc) ,params,rs_data,error_msg)

publish_endpoint = f"/{user_id}/threads_publish"
if rs_data:
    request = {"creation_id":creation_id}
    rs = requests.post(url=url+publish_endpoint,headers=header,json=request)
    publish_data = rs.json()
    publish_id = publish_data.get("id",None)
    print(publish_id)

    status = "Success" if publish_id else "Error" 
    error_msg = json.dumps(publish_data.get("error",None))
    to_log(status,1,"publish_container",datetime.now(timezone.utc) ,request,publish_data,error_msg)

    params = {
        "fields": "id,text,media_type,media_url,permalink,timestamp"
    }   
    if publish_id:
        rs = requests.get(url=f"{url}/{publish_id}",headers=header,params=params)
        publish_data = rs.json()
        published_id = publish_data.get("id",None)
        print(publish_data)
        # {'id': '17888281206670059', 'text': 'This post is test By API. 2026-07-30 15:19:56.300646', 'media_type': 'TEXT_POST', 'permalink': 'https://www.threads.com/@dramarada202/post/Dba_yM7gUrYQrf9EVPlzGupf2FWDzxx9FZTyKc0', 'timestamp': '2026-07-30T15:19:59+0000'}
        status = "Success" if published_id else "Error" 
        time = publish_data.get("timestamp",None)
        error_msg = json.dumps(publish_data.get("error",None))
        to_log(status,1,"get_post",time,{"publish_id":publish_id},publish_data,error_msg)

        if published_id:
            metadata.create_all(engine)
            with engine.begin() as conn:
                stmt = insert(threads_log)
                rs = conn.execute(stmt,publish_data)
                if rs.rowcount > 0:
                    print("儲存成功")