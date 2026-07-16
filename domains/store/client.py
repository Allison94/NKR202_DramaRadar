"""
* 只負責處理api連線取資料，不處理
"""
from apify_client import ApifyClient
from shared.config import settings

client = ApifyClient(settings.apify_store) #set api token

def start_job_actor(params):  
  actor = client.actor("compass/crawler-google-places")
  return actor.start(run_input=params)
  # 用actor.call() 會馬上回，資料量太大會斷線

def check_status(run_id):
  obj = client.run(run_id).get()
  return obj

def get_dataset(dataset_id) -> list[dict]: 
  # dataset_id that expire after 7 days
  # 115："z8QJQaNfB3KsQ9zQQ"  110："bQussivqr43V3XDdF" 3條："g3AanSmnAvDdM6Rfv"
  dataset = client.dataset(dataset_id).list_items().items
  return dataset
  



# 測試區
if __name__ == "__main__":
  # 之後放到pipeline - start
  # TAIPEI_POSTCODES = [
  #   "100", "103", "104", "105", "106", "108", "110", "111", "112", "114", "115", "116"
  # ]

  # params = {
  # "county": "TW",
  # "language": "zh-TW",
  # "maxCrawledPlacesPerSearch": 3,
  # "postalCode": "100",
  # "searchStringsArray": ["餐廳","小吃","麵店","便當","餐酒館","料理"],
  # }
  # end
  check_status("HS3KlcUb8sIBxUb25")
  # get_dataset("g3AanSmnAvDdM6Rfv")