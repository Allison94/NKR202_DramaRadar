from apify_client import ApifyClient
from shared.config import Setting

client = ApifyClient(Setting.apigy_store)

TAIPEI_POSTCODES = [
    "100", "103", "104", "105", "106", "108", "110", "111", "112", "114", "115", "116"
]
input = {
  "county": "TW",
  "language": "zh-TW",
  "maxCrawledPlacesPerSearch": 30,
  "postalCode": "115",
  "searchStringsArray": ["餐廳","小吃","麵店","便當","餐酒館","料理"],
}

actor = client.actor("compass/google-maps-extractor")

call_api = actor.call(run_input=input)