"""LOCAL TEST SEED ONLY — 給 seed_demo_data 寫進 PostgreSQL。

Dashboard / production 只讀 DB，不會 import 這份當畫面 fallback。

注意：每店評論則數可以不同（真實情況）。
「只留一個原始評論網址」是 UI 規則，不是每店只能 1 則評論。
"""

from __future__ import annotations

from typing import Any

# 台北市 + 有吵架成分；reviews 長度刻意不同
DEMO_ROWS: list[dict[str, Any]] = [
    {
        "store_id": "demo-002",
        "name": "西門嘴硬雞排",
        "city": "台北市",
        "district": "萬華區",
        "category": "炸物",
        "lat": 25.0436,
        "lng": 121.5077,
        "intensity": 9.1,
        "reason": "品質",
        "pr_reply": "感謝您的指教，我們會立刻檢查炸油與出餐流程，歡迎再給我們一次機會。",
        "reviews": [
            {
                "stars": 1,
                "text": "雞排偏乾，跟以前吃到的品質不太一樣。",
                "owner_reply": "謝謝您精準找出本店唯一一塊不合口味的雞排。",
            },
            {
                "stars": 1,
                "text": "外皮油耗味很重，店員還說是特色。",
                "owner_reply": "油是每天換的，不喜歡味道可以換別攤。",
            },
            {
                "stars": 2,
                "text": "排隊四十分鐘，結果雞肉還粉粉的。",
                "owner_reply": "尖峰時段難免，我們有盡力加速。",
            },
        ],
    },
    {
        "store_id": "demo-003",
        "name": "信義排隊拉麵",
        "city": "台北市",
        "district": "信義區",
        "category": "拉麵",
        "lat": 25.0334,
        "lng": 121.5645,
        "intensity": 8.7,
        "reason": "排隊",
        "pr_reply": "抱歉造成不便，現場人潮較多才會較嚴格管理隊伍，我們會再把規則標示得更清楚。",
        "reviews": [
            {
                "stars": 1,
                "text": "排到一半離開五分鐘，回來就被取消資格。",
                "owner_reply": "規則已張貼於門口，無法接受規則請勿排隊。",
            },
            {
                "stars": 2,
                "text": "湯頭過鹹，店員卻說是本店靈魂。",
                "owner_reply": "口味偏重是設定，可跟店員說少鹽。",
            },
        ],
    },
    {
        "store_id": "demo-005",
        "name": "中山價格自由咖啡",
        "city": "台北市",
        "district": "中山區",
        "category": "咖啡廳",
        "lat": 25.0521,
        "lng": 121.5226,
        "intensity": 7.8,
        "reason": "價格",
        "pr_reply": "謝謝提醒，我們會再檢視定價說明，讓客人更清楚費用包含哪些服務。",
        "reviews": [
            {
                "stars": 1,
                "text": "一杯飲料接近三百元，覺得性價比不高。",
                "owner_reply": "價格包含空間、原料與服務，並非只計算液體成本。",
            },
        ],
    },
    {
        "store_id": "demo-008",
        "name": "士林夜市嘴砲大腸",
        "city": "台北市",
        "district": "士林區",
        "category": "夜市小吃",
        "lat": 25.0878,
        "lng": 121.5242,
        "intensity": 8.2,
        "reason": "品質",
        "pr_reply": "抱歉讓您失望，我們會加強出餐檢查，也請現場同仁用更有禮貌的方式溝通。",
        "reviews": [
            {
                "stars": 1,
                "text": "說好的爆汁結果又乾又柴，店員還說我不會吃。",
                "owner_reply": "每串火候不同，覺得不好吃可以不要買。",
            },
            {
                "stars": 2,
                "text": "份量比以前小很多，價格卻沒變。",
                "owner_reply": "原料成本上漲，只能調整份量。",
            },
            {
                "stars": 1,
                "text": "問可不可以不要辣就被兇。",
                "owner_reply": "尖峰很忙，語氣重一點請見諒。",
            },
            {
                "stars": 2,
                "text": "衛生手套破了還繼續抓食材。",
                "owner_reply": "當下已更換，歡迎現場監督。",
            },
        ],
    },
    {
        "store_id": "demo-010",
        "name": "大安加料不說鍋",
        "city": "台北市",
        "district": "大安區",
        "category": "火鍋",
        "lat": 25.0268,
        "lng": 121.5434,
        "intensity": 7.2,
        "reason": "價格",
        "pr_reply": "很抱歉造成誤會，我們會把加料標示放大，也請櫃檯主動提醒。",
        "reviews": [
            {
                "stars": 1,
                "text": "結帳才說加料另計，菜單根本看不清楚。",
                "owner_reply": "菜單有註記加點費用，結帳前請自行確認。",
            },
            {
                "stars": 2,
                "text": "肉片解凍水很多，吃起來像泡過。",
                "owner_reply": "冷藏運送難免，不滿意可跟現場反應。",
            },
        ],
    },
    {
        "store_id": "demo-012",
        "name": "北投態度溫泉蛋",
        "city": "台北市",
        "district": "北投區",
        "category": "甜品",
        "lat": 25.1323,
        "lng": 121.4982,
        "intensity": 6.8,
        "reason": "態度",
        "pr_reply": "謝謝指正，我們會加強服務禮貌與出餐溫度檢查。",
        "reviews": [
            {
                "stars": 2,
                "text": "問一下要不要糖就被白眼，溫泉蛋還是冷的。",
                "owner_reply": "忙的時候沒辦法一一微笑，不喜歡可以換別家。",
            },
            {
                "stars": 1,
                "text": "甜度跟點單完全不一樣，還嫌客人囉嗦。",
                "owner_reply": "現場人多聽錯有可能，下次請再說清楚一次。",
            },
            {
                "stars": 2,
                "text": "座位很擠還一直催人離開。",
                "owner_reply": "用餐高峰需輪轉，請見諒。",
            },
        ],
    },
]
