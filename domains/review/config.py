"""Review domain configuration."""

ACTOR_ID = "compass/google-maps-reviews-scraper"

LANGUAGE = "zh-TW"
REVIEWS_ORIGIN = "all"

# 初次抓取：1★ + 2★ + buffer
INITIAL_BUFFER = 50
INITIAL_SORT = "newest"

# 每日增量
DAILY_SORT = "lowestRanking"
DAILY_STORE_LIMIT = 100

# Apify polling
POLL_SECONDS = 5
TIMEOUT_SECONDS = 900

# 避免單次 Actor 意外產生過高費用
MAX_TOTAL_CHARGE_USD = 0.5
