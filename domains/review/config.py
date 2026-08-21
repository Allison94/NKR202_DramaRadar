"""Review domain configuration."""

ACTOR_ID = "compass/google-maps-reviews-scraper"

LANGUAGE = "zh-TW"
REVIEWS_ORIGIN = "all"


# ============================================================
# Initial：第一次抓取
# ============================================================

# 每家：
# maxReviews = store.oneStar + store.twoStar + INITIAL_BUFFER
INITIAL_BUFFER = 50
INITIAL_SORT = "lowestRanking"


# ============================================================
# Daily：每天更新
# ============================================================

# newest + reviewsStartDate=昨天，只抓新增評論
DAILY_SORT = "newest"


# ============================================================
# Batch / Airflow
# ============================================================

# Initial / Daily / Recheck：每個 Batch 最多 200 家
BATCH_SIZE = 200

# Apify Actor 狀態由 Airflow Sensor 每 2 分鐘重新確認
STATUS_POKE_INTERVAL_SECONDS = 120


# ============================================================
# Owner Reply Recheck
# ============================================================

# 沒有老闆回覆 → 今天 + 2 天再查
RECHECK_AFTER_DAYS = 2

# 從最初 publishedAtDate 起超過 10 天 → 停止 Recheck
RECHECK_MAX_AGE_DAYS = 10