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

# 原本 Initial 就是 newest；
# 組長這次沒有要求修改 Initial 排序，所以維持原設定。
INITIAL_SORT = "newest"


# ============================================================
# Daily：每天更新
# ============================================================

# 組長要求：
# 每天用 newest + reviewsStartDate 判斷新增評論。
DAILY_SORT = "newest"


# ============================================================
# Owner Reply Recheck
# ============================================================

# 沒有老闆回覆時，3 天後再檢查。
RECHECK_AFTER_DAYS = 3

# 每次最多處理 100 筆需要重新檢查的資料。
RECHECK_LIMIT = 100

# 每個 place 補查時抓最新 20 則評論。
RECHECK_MAX_REVIEWS = 20

RECHECK_SORT = "newest"


# ============================================================
# Apify 執行控制
# ============================================================

# 每 5 秒檢查一次 Actor 狀態。
POLL_SECONDS = 5

# 最多等待 900 秒 = 15 分鐘。
TIMEOUT_SECONDS = 900