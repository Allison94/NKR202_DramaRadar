import datetime

import requests
from shared.config import settings
# 抓ＰＯＳＴ
# curl -i -X GET \
#  "https://graph.threads.net/v1.0/18063333437725637?fields=id%2Cmedia_product_type%2Cmedia_type%2Cmedia_url%2Cpermalink%2Cowner%2Cusername%2Ctext%2Ctopic_tag%2Ctimestamp%2Cshortcode%2Cthumbnail_url%2Cchildren%2Cis_quote_post&access_token=<放ＴＯＫＥＮ>"


user_id = "DELETED_KEY"
# post 
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
        "fields": "id,username,text,media_type,media_url,permalink,timestamp"
    }   
    if publish_id:
        rs = requests.get(url=f"{url}/{publish_id}",headers=header,params=params)
        print(rs.json())