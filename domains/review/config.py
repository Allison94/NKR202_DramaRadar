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

# Initial / Daily / Recheck：每個 Apify run 一次丟 50 家
BATCH_SIZE = 50

# Apify Actor 狀態由 Airflow Sensor 每 2 分鐘重新確認；未完成就繼續等
STATUS_POKE_INTERVAL_SECONDS = 120

# 卡住才等到這個上限就失敗。SUCCEEDED 會立刻下一步，不會空等滿這段時間。
# 對齊 store DAG：retries=30、每分鐘查一次 ≈ 30 分鐘
STATUS_SENSOR_TIMEOUT_SECONDS = 30 * 60

# Apify 帳號同時跑中的 Actor 記憶體上限 16GB，每個 run 約 1024MB（最多約 16 個）。
# start + wait 綁在同一個 sensor，所以這個數字才是真正同時在跑的 Review Actor 數。
MAX_ACTIVE_APIFY_RUNS = 5


# ============================================================
# Owner Reply Recheck
# ============================================================

# 沒有老闆回覆 → 今天 + 2 天再查
RECHECK_AFTER_DAYS = 2

# 從最初 publishedAtDate 起超過 10 天 → 停止 Recheck
RECHECK_MAX_AGE_DAYS = 10