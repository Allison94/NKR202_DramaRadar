"""LOCAL TEST SEED ONLY — never used by Dashboard get_dashboard_dataframe().

Dashboard / production path reads PostgreSQL via repository.py (schema.sql).
These rows exist solely for: seed_stores / mock_client / run_dev_setup.
"""

from __future__ import annotations

from typing import Any

# Taipei City + high drama only (組長：沒吵架成分的不要放)
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
        "persona": "🤡 高級反串",
        "review_text": "雞排偏乾，跟以前吃到的品質不太一樣。",
        "owner_reply": "謝謝您精準找出本店唯一一塊不合口味的雞排。",
        "reviews": 912,
        "owner_replies": 129,
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
        "persona": "📣 規則至上",
        "review_text": "排到一半離開五分鐘，回來就被取消資格。",
        "owner_reply": "規則已張貼於門口，無法接受規則請勿排隊。",
        "reviews": 1450,
        "owner_replies": 203,
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
        "persona": "💎 價值辯護",
        "review_text": "一杯飲料接近三百元，覺得性價比不高。",
        "owner_reply": "價格包含空間、原料與服務，並非只計算液體成本。",
        "reviews": 730,
        "owner_replies": 88,
    },
]
