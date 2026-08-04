from datetime import datetime,timedelta
from sqlalchemy import select
from db.database import engine
from domains.ai_analysis.models import Ai_analysis
from domains.review.models import Review

time_utc = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0) 
catch_time = time_utc-timedelta(days=1)
#每天
stmt = (
    select(Ai_analysis,Review)
    .join(Review, Review.c.reviewId == Ai_analysis.c.reviewId)
    .where(Review.c.scrapedAt >= catch_time)
    .order_by((Review.c.review_score+Review.c.review_score).desc())
    .limit(1)
)

with engine.connect() as conn:
    rs = conn.execute(stmt)
    data = rs.first()

if data:
    daily_post_str = f"""
        🔥 【DramaRada】今日最Drama

        💬 吵架事件現場：
        • 客人：「{data.review_text[:100]if len(data.review_text) > 100 else data.review_text}...」 
        • 老闆：「{data.owner_text[:100]if len(data.owner_text) > 100 else data.owner_text}...」 

        🤖 AI 戰力指數分析：
        • 客人火藥味：{data.customer_ai_score}
        • 老闆戰力數：{data.owner_ai_score}

        🤫 AI公關一下：
        「{data.ai_pr_response[:100]if len(data.ai_pr_response) > 100 else data.ai_pr_response}...」 

        🔗 前往案發現場觀賞：
        {data.review_url}

        「🍿今天沒有平安地度過🍿，感謝兩位Drama大師的努力~」
    """
else:
    daily_post_str = f"""
    【DramaRada】今日不Drama

    🕊️ 一天又平安地度過了，感謝大家今天也沒有『動手』打架~~
    """