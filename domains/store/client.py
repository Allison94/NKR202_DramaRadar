"""
* 只負責處理api連線取資料，不處理
"""
from apify_client import ApifyClient
from shared.config import settings

class StoreClient:

  def __init__(self):
    self.client = ApifyClient(settings.apify_store) #set api token

  def start_job_actor(self,run_input:dict)->dict:  
    actor = self.client.actor("compass/crawler-google-places")
    obj = actor.start(run_input=run_input)
    return obj if isinstance(obj,dict) else dict(obj)
    # 用actor.call() 會馬上回，資料量太大會斷線

  def check_status(self,run_id:str)->dict:
    obj = self.client.run(run_id).get()
    return obj if isinstance(obj, dict) else getattr(obj, "__dict__", {})

  def get_dataset(self,dataset_id) -> list[dict]: 
    # dataset_id that expire after 7 days
    # 115："z8QJQaNfB3KsQ9zQQ"  110："bQussivqr43V3XDdF" 3條："g3AanSmnAvDdM6Rfv"
    dataset = self.client.dataset(dataset_id).list_items().items
    return dataset
    



# 測試區
if __name__ == "__main__":
  storeclient = StoreClient()
  storeclient.check_status("HS3KlcUb8sIBxUb25")
  # get_dataset("g3AanSmnAvDdM6Rfv")