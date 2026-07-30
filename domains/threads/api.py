import datetime

import requests
from shared.config import settings
from db.database import engine,metadata
from db.shared_tables import execution_log
from domains.threads.models import threads_log
from sqlalchemy import insert,select

user_id = "DELETED_KEY" #!組長說這個要改到env

url = f"https://graph.threads.com/v1.0"
create_container_endpoint = f"/{user_id}/threads"
header = {
    "Authorization":f"Bearer {settings.threads_api_key}",
    "Content-Type": "application/json"
}
params = {
    "media_type":"TEXT",
    "text":f"This post is test By API. {datetime.datetime.now()}"
}
rs = requests.post(url=url+create_container_endpoint,headers=header,json=params, allow_redirects=False)
rs_data = rs.json()
print(rs_data)

publish_endpoint = f"/{user_id}/threads_publish"
if rs_data:
    creation_id = rs_data["id"]
    rs = requests.post(url=url+publish_endpoint,headers=header,json={"creation_id":creation_id})
    publish_data = rs.json()
    publish_id = publish_data["id"]
    print(publish_id)


    params = {
        "fields": "id,text,media_type,media_url,permalink,timestamp"
    }   
    if publish_id:
        rs = requests.get(url=f"{url}/{publish_id}",headers=header,params=params)
        publish_data = rs.json()
        published_id = publish_data["id"]
        print(publish_data)
        # {'id': '17888281206670059', 'username': 'dramarada202', 'text': 'This post is test By API. 2026-07-30 15:19:56.300646', 'media_type': 'TEXT_POST', 'permalink': 'https://www.threads.com/@dramarada202/post/Dba_yM7gUrYQrf9EVPlzGupf2FWDzxx9FZTyKc0', 'timestamp': '2026-07-30T15:19:59+0000'}

        if published_id:
            metadata.create_all(engine)
            with engine.begin() as conn:
                stmt = insert(threads_log)
                rs = conn.execute(stmt,publish_data)
                if rs.rowcount > 0:
                    print("儲存成功")