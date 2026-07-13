# 給自己用的筆記
## Test Recorde

* 2026/7/10 apify web後台手動抓 postcode 110信義區 限制30筆 
    > response 30筆 cost：$0.15 time：43s
* 2026/7/10 apify web後台手動抓 postcode 115南港區 不限制 
    > response 966筆 cost：$4.83 time：6m15s

## Cmd
> uv run python -m domains.store.client
> -m is module 

## active
> sql => use core 2.0 not ORM 

## pipeline
> get run id  => client
> etl
> save to sql with log => tosql

> get status => client
> etl
> update to sql with log => tosql

> get dataset id  => client
> save to sql with origin data => tosql
> etl 
> save to sql with clean data => tosql

> DAG => 前面三個line

## start_job_actor、check_status return 
``` 
#AI整理 (兩個格式一樣)
{
    # ==========================================
    # 1. 核心識別識別碼 (資料工程最重要的三大 ID)
    # ==========================================
    "id": "HS3KlcUb8sIBxUb25",                         # (Run ID)
    "act_id": "2Mdma1N6Fd0y3QEjR",                     # (Actor) 本身的 ID
    "user_id": "uy8QCikyX4JuvmaGy",                    # Apify 帳號 ID
    "build_id": "wBkPzjWS9D86JQrTf",                   # 爬蟲程式碼的編譯版本 ID
    "actor_task_id": None,                             # 用 Task 啟動才會有值

    # ==========================================
    # 2. 狀態與生命週期週期 (維運追蹤指標)
    # ==========================================
    "status": "READY",                                 # 當前狀態
    "started_at": datetime(2026, 7, 13, 8, 45, 7),     # 👈 你的 7 天過期時鐘
    "finished_at": None,                               # 尚未結束，所以是 None
    "exit_code": 0,                                    # 結束代碼，正常為0
    "status_message": None,                            # 錯誤或狀態提示訊息
    "is_status_message_terminal": None,

    # ==========================================
    # 3. 儲存資源庫 ID (資料採收的核心鑰匙)
    # ==========================================
    "default_dataset_id": "g3AanSmnAvDdM6Rfv",         # 資料ID，7 天內要來收網！
    "default_key_value_store_id": "8mlUbYfYcDxC8GP3p", # 儲存 Log 或截圖的預設 K-V 庫 ID
    "default_request_queue_id": "Zuu86zFxgcQucajNc",   # 遠端控制爬取 URL 隊列的 ID
    "storage_ids": {
        "datasets": {"default": "g3AanSmnAvDdM6Rfv"},
        "key_value_stores": {"default": "8mlUbYfYcDxC8GP3p"},
        "request_queues": {"default": "Zuu86zFxgcQucajNc"}
    },

    # ==========================================
    # 4. 運行規格與設定限制 (效能防線)
    # ==========================================
    "options": {
        "build": "latest",
        "memory_mbytes": 1024,                         # 運行記憶體：1GB
        "disk_mbytes": 2048,                           # 磁碟空間：2GB
        "timeout_secs": 36000,                         # 任務超時上限：10 小時
        "max_items": None,
        "max_total_charge_usd": 0.019005,              # 預估最高可能花費金額 (美金)
        "isMaxTotalChargeUsdSetByUser": False
    },
    "container_url": "https://apify.net", # 遠端容器的即時通訊網址

    # ==========================================
    # 5. 計費與用量統計
    # ==========================================
    "pricing_info": {
        "pricing_model": "PAY_PER_EVENT",              # 按件計費模式 (Scraped per place)
        "created_at": datetime(2026, 4, 29, 12, 8, 27),官方制定計費規則的日期
        "actor_charge_events": {
            "place-scraped": {"title": "Scraped place", "price_usd": 0.005}, # 每成功爬一家店家收 0.005 美金
            "filter-applied": {"title": "Add-on: Filter", "price_usd": 0.001},
            "apify-actor-start": {"title": "Actor Start", "price_usd": 0.00005}
        }
    },
    "stats": {                                         # 當前運行效能統計 (因為才剛 READY，所以全是 0 或 None)
        "input_body_len": 604,
        "duration_millis": None,
        "run_time_secs": None,
        "compute_units": 0.0,
        "reboot_count": 0
    },
    "charged_event_counts": {                          # 計費計數器
        "place-scraped": 3,                            # 爬到幾條資料
        "apify-actor-start": 1
    }
}
```

## respons dataset
```json!=
# 格式list[dict] => 這邊只顯示其中一個dict
{
   "title":"饒咖哩 日式咖哩專賣店",
   "subTitle":"None",
   "description":"None",
   "price":"$1-200",
   "categoryName":"日式咖哩餐廳",
   "address":"115台灣臺北市南港區玉成里玉成街14-14號",
   "neighborhood":"None",
   "street":"玉成街14-14號",
   "city":"玉成里",
   "postalCode":"115",
   "state":"臺北市南港區",
   "countryCode":"TW",
   "website":"https://www.facebook.com/share/1F9epTyFWS/?mibextid=wwXIfr",
   "phone":"+886 2 2783 0108",
   "phoneUnformatted":"+886227830108",
   "claimThisBusiness":false,
   "location":{
      "lat":25.0505127,
      "lng":121.5809709
   },
   "locatedIn":"None",
   "floor":"None",
   "plusCode":"None",
   "menu":"None",
   "servicesLink":"None",
   "totalScore":4.5,
   "permanentlyClosed":false,
   "temporarilyClosed":false,
   "placeId":"ChIJi67FDQCrQjQRNnqJst4-2C8",
   "categories":[
      "日式咖哩餐廳",
      "餐廳"
   ],
   "fid":"0x3442ab000dc5ae8b:0x2fd83edeb2897a36",
   "cid":"3447574640951130678",
   "reviewsCount":133,
   "imagesCount":183,
   "imageCategories":[
      
   ],
   "scrapedAt":"2026-07-10T16:37:25.233Z",
   "reserveTableUrl":"None",
   "googleFoodUrl":"None",
   "hotelStars":"None",
   "hotelDescription":"None",
   "checkInDate":"None",
   "checkOutDate":"None",
   "hotelAds":[
      
   ],
   "popularTimesLiveText":"None",
   "popularTimesLivePercent":"None",
   "popularTimesHistogram":{
      
   },
   "openingHours":[
      {
         "day":"星期六",
         "hours":"休息"
      },
      {
         "day":"星期日",
         "hours":"11:00 to 14:00, 16:30 to 19:30"
      },
      {
         "day":"星期一",
         "hours":"11:00 to 14:00, 16:30 to 19:30"
      },
      {
         "day":"星期二",
         "hours":"11:00 to 14:00, 16:30 to 19:30"
      },
      {
         "day":"星期三",
         "hours":"11:00 to 14:00, 16:30 to 19:30"
      },
      {
         "day":"星期四",
         "hours":"11:00 to 14:00, 16:30 to 19:30"
      },
      {
         "day":"星期五",
         "hours":"11:00 to 14:00, 16:30 to 19:30"
      }
   ],
   "peopleAlsoSearch":[
      
   ],
   "placesTags":[
      
   ],
   "reviewsTags":[
      
   ],
   "additionalInfo":{
      "服務項目":[
         {
            "外送":true
         },
         {
            "外帶":true
         },
         {
            "內用":true
         }
      ],
      "熱門原因":[
         {
            "午餐":true
         },
         {
            "晚餐":true
         },
         {
            "獨自用餐":true
         }
      ],
      "無障礙程度":[
         {
            "無障礙座位":false
         },
         {
            "無障礙停車場":false
         }
      ],
      "產品/服務":[
         {
            "提供簡餐":true
         }
      ],
      "用餐選擇":[
         {
            "午餐":true
         },
         {
            "晚餐":true
         },
         {
            "餐飲服務":true
         },
         {
            "座位":true
         }
      ],
      "氣氛":[
         {
            "環境舒適":true
         }
      ],
      "客層族群":[
         {
            "跨性別友善空間":true
         },
         {
            "適合闔家光臨":true
         },
         {
            "LGBTQ+ 友善空間":true
         }
      ],
      "付款方式":[
         {
            "只收現金":true
         }
      ],
      "兒童":[
         {
            "兒童高腳椅":true
         },
         {
            "適合兒童":true
         }
      ],
      "停車場":[
         {
            "收費室內停車場":true
         },
         {
            "收費停車場":true
         },
         {
            "收費路邊停車格":true
         }
      ],
      "寵物":[
         {
            "允許狗狗入內":true
         },
         {
            "可帶狗入住":true
         }
      ]
   },
   "gasPrices":[
      
   ],
   "url":"https://www.google.com/maps/search/?api=1&query=%E9%A5%92%E5%92%96%E5%93%A9%20%E6%97%A5%E5%BC%8F%E5%92%96%E5%93%A9%E5%B0%88%E8%B3%A3%E5%BA%97&query_place_id=ChIJi67FDQCrQjQRNnqJst4-2C8",
   "searchPageUrl":"https://www.google.com/maps/search/%E5%B0%8F%E5%90%83/@25.0506424,121.5816331,18.860180801432133z?hl=zh-TW",
   "searchString":"小吃",
   "language":"zh-TW",
   "rank":7,
   "isAdvertisement":false,
   "imageUrl":"http://t2.gstatic.com/images?q=tbn:ANd9GcSjPaw4Hc4P31pQcyFax1T6KYPLz9pWhhr5cixpAOUsWj-XkHfm",
   "kgmid":"/g/11vsh419j7"
}
```