from apify_client import ApifyClient
from git import Actor
from shared.config import settings

client = ApifyClient(settings.apify_store)

def call_api(params): #api fetch dataset return 
  actor = client.actor("compass/google-maps-extractor")
  # call_api = actor.call(run_input=params) #用call會馬上回，資料量太大會斷線
  dataset_id = actor.start(run_input=params)
  # print(dataset_id)
  return dataset_id


def get_dataset(dataset_id) -> list[dict]: 
  # dataset_id that expire after 7 days
  # 115："z8QJQaNfB3KsQ9zQQ"  110："bQussivqr43V3XDdF" 
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
  # "maxCrawledPlacesPerSearch": 30,
  # "postalCode": "115",
  # "searchStringsArray": ["餐廳","小吃","麵店","便當","餐酒館","料理"],
  # }
  # end

  get_dataset("bQussivqr43V3XDdF")

