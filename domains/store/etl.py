"""
* 處理從client端取得資料
* 整理後資料傳入SQL
"""
import pandas as pd
import numpy as np
import requests 

def start_job_etl(params:dict,obj:dict)->dict:
    return {
        "run_id":obj.get("id"),
        "dataset_id":obj.get("default_dataset_id"),
        "started_at":obj.get("started_at"),
        "status":obj.get("status"),
        "request_json":params,
        "response_json":obj,
    }

def check_status_etl(obj:dict,job_log_id:str)->dict: #job_log_id從 db_handler裡面取回
    status_msg = obj.get("status_message")
    exit_code = obj.get("exit_code")
    if exit_code != 0 or status_msg != None:
        status_message = f"{exit_code}-{status_msg}"
    
    charged = obj.get("charged_event_counts",{})
    rt = {
        "job_log_id":job_log_id,
        "run_id":obj.get("id"),
        "status":obj.get("status"), #SUCCEEDED,READY
        "start_at":obj.get("start_at"),
        "finished_at":obj.get("finished_at"),
        "exit_code":obj.get("exit_code"),
        "charged_event_counts":charged.get("place-scraped", 0), #怕沒欄位先補0
        "status_message":status_message,
        "response_json":obj
    }
    return rt

def dataset_origin(obj:list[dict])->list[dict]:
    rt = [
        {
        "placeId":item.get("placeId"),
        "raw_json":item,
        "scrapedAt":item.get("scrapedAt"),
        }
        for item in obj
    ]
    # [i for i in range(5)]

    return rt

def dataset_etl(obj:list[dict])->list[dict]:
    # c1. reviewsCount >= 30 (評論數大於30)
    # c2. totalScore <= 4.4 or oneStar/reviewsCount >= (0.1 總分低於4.4或1星佔10%)
    # business_status ? permanentlyClosed & temporarilyClosed => False
    # blocked ? (預設false後續人工調整預留位)
    # skip_review_fetch ? (排除連鎖店跟制式回覆店家，這裡只能排除連鎖)

    sql_columns=["placeId","title","categoryName","categories","address","url","imageUrl","business_status","scrapedAt","totalScore","reviewsCount","oneStar","twoStar","threeStar","fourStar","fiveStar","blocked","skip_review_fetch"]

    c1 = "reviewsCount >= 30"
    c2 = "(totalScore <= 4.4 or oneStarPercent >= 0.1)"

    df = pd.json_normalize(obj)
    df_set = df.assign(
        oneStarPercent = lambda x : x["reviewsDistribution.oneStar"]/x["reviewsCount"],
        categories = lambda x : x["categories"].str.join(",")
    ).query(
        f"{c1} and {c2}"
    ).assign(
        business_status=lambda x: np.where(x["permanentlyClosed"] | x["temporarilyClosed"],"CLOSED","OPEN"),
        skip_review_fetch = lambda x : x["title"].str.contains(str(excluded_restaurants("|")),na=False,regex=True), #排除連鎖店和已知指定店家
        blocked=False,#預設FALSE,
    ).rename(columns={
        "reviewsDistribution.oneStar": "oneStar",
        "reviewsDistribution.twoStar": "twoStar",
        "reviewsDistribution.threeStar": "threeStar",
        "reviewsDistribution.fourStar": "fourStar",
        "reviewsDistribution.fiveStar": "fiveStar"
    })[sql_columns]

    return df_set.to_dict(orient="records")

def excluded_restaurants(joinstr=None)->str|list: #連鎖店清單，用ai抓的
    chains = [ # === 🤖 1. 鋼鐵罐頭訊息大軍 (不管給幾星，小編或系統永遠回一模一樣的固定話術) ===
        "星巴克",              # 永遠回覆定型化官方感謝詞（常出現在星級較高的分店）
        "摩斯漢堡",            # 「感謝您的支持，您的建議是我們進步的動力...」
        "漢堡王",              # 也是極高度使用制式罐頭回覆的跨國品牌
        "路易莎",          # 台北部分分店有開自動回覆系統，內容百分之百固定
        "怡客", "丹堤", # 傳統連鎖咖啡，多使用固定罐頭訊息
        "築間幸福鍋物",        # 部分分店小編會留固定的公關罐頭文「感謝您蒞臨築間...」
        "馬辣",  # 馬辣系列（含新馬辣）常使用固定的行銷語句複製貼上
        "肉多多火鍋",          # 「謝謝您的讚美！肉多多火鍋歡迎您再度光臨...」
        "黑沃", "先喝道",   # 中大型手搖/咖啡連鎖，回覆內容相似度極高
        "金色三麥",            # 遇到客訴或好評，多由系統或公關回覆定型化文字
        "王品牛排", "西堤牛排", "陶板屋", "夏慕尼", "石二鍋", "12MINI", "聚日式鍋物", "肉次方",
        "嚮辣", "和牛涮", "青花驕", " oroshi (喔咾)", "初瓦", "乍牛", "品田牧場", "瓦城泰國料理", 
        "非常泰", "1010湘", "大心新泰式麵食", "時時香", "樂子", "BOBO", "涓豆腐", "北村豆腐家", 
        "姜滿堂", "韓姜熙的小廚房", "飛機河粉", "阿達師五星麵舖", "壽司郎", "藏壽司", "爭鮮旋轉壽司", 
        "吉野家", "すき家", "薩莉亞", "丸龜製麵", "大戶屋", "麥當勞", "肯德基", "必勝客", 
        "達美樂", "SUBWAY", "鼎泰豐", "八方雲集", "梁社漢排骨", "悟饕池上飯包", "三商巧福", 
        "福勝亭", "鮮五丼", "鬍鬚張", "錢都日式涮涮鍋", "85度C", "多那之", "50嵐", 
        "清心福全", "可不可熟成紅茶", "麻古茶坊", "迷客夏", "珍煮丹", "五桐號", "一芳", 
        "城市盒子", "拿坡里", "品川蘭", "BANCO", "古拉爵", "涮乃葉", "藍屋", "SKYLARK", 
        "橫濱牛排", "海底撈", "一蘭拉麵", "美登利", "金子半之助", "添好運", "點點心", 
        "Bake Code", "星期五美式餐廳", "TGI FRIDAYS", "新馬辣經典麻辣鍋", "問鼎", "狗一下", 
        "乾杯燒肉", "老乾杯", "黑毛屋", "橘色涮涮屋", " extension 1by 橘色", "春水堂", 
        "雙月食品社", "朱記餡餅粥", "大心", "欣葉", "開飯川食堂", "饗食天堂", "旭集", 
        "饗饗", "果然匯", "小蒙牛", "天香回味", "太和殿", "滿堂紅", "正忠排骨飯", "金仙魯肉飯", 
        "大埔鐵板燒", "麥味登", "早安美芝城", "弘爺漢堡", "阿寶早餐", "得正", "茶湯會", 
        "天仁茗茶", "喫茶趣", "萬波", "龜記", "再睡5分鐘", "鶴茶樓", "烏弄", "勝博殿", 
        "邁泉豬排", "伊勢路勝勢", "靜岡勝政", "魔法咖哩", "CoCo壹番屋", "晴木千層豬排", 
        "天丼天吉屋", "開丼", "燒肉LIKE", "IKIGAI燒肉", "星胡同", "大河屋", "米塔炙燒牛排", 
        "莫凡彼", "Miopane", "薄多義", "義式屋古拉爵", "Bellini Pasta Pasta", "貝里尼", 
        "卡布里喬莎", "五鮮級", "六扇門", "師大第一腿","燈籠滷味","好大大雞排", "派克雞排", "惡魔雞排", 
        "艋舺雞排", "檀島香港茶餐廳", "翠華餐廳", "太興茶餐廳", "茗香園", "大Heart", "瓦城", 
        "PABLO", "閃電咖啡", "Flash Coffee", "彼得好咖啡", "西雅圖極品咖啡", "覺旅咖啡", 
        "Journey Kaffe", "Second Floor Cafe", "貳樓", "Miacucina","大苑子", 
        "五桐號", "布萊恩紅茶", "叮哥茶飲", "七盞茶", "進發家","紫艷中餐廳","潮品集","Cin Cin Osteria"]
    if joinstr == False or joinstr == None:
        return chains
    return joinstr.join(chains)

# TEST BLOCK
if __name__ == "__main__":
    url = "https://api.apify.com/v2/datasets/bQussivqr43V3XDdF/items?signature=MC4xNzg1NDM2MzYzNjg3LlVtemlUNHVRamVOTEVLTUZ3ZEl0&format=json&clean=true"

    da = requests.get(url).json()
    
    print(dataset_etl(da))