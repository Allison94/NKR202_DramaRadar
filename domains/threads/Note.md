
    # Column("reviewId",String(100),primary_key=True),
    # Column("placeId",String(100),nullable=False),
    # Column("originalLanguage",String(50),nullable=False),
    # Column("text",TEXT,nullable=False),
    # Column("publishedAtDate",TIMESTAMP,nullable=False),
    # Column("reviewUrl",TEXT,nullable=False),
    # Column("reviewImageUrls",TEXT),
    # Column("likesCount",INTEGER,server_default="0",nullable=False),
    # Column("totalScore",FLOAT,server_default="0.0",nullable=False),
    # Column("stars",INTEGER,server_default="0",nullable=False),
    # Column("responseFromOwnerDate",TIMESTAMP),
    # Column("responseFromOwnerText",TEXT),
    # Column("scrapedAt",TIMESTAMP,nullable=False),
    # Column("owner_reply_recheck",BOOLEAN,server_default="False",nullable=False),
    # Column("owner_reply_recheck_at",TIMESTAMP),
    # Column("next_check_at",TIMESTAMP),



    # Column("reviewId",String(100),primary_key=True),
    # Column("placeId",String(100),nullable=False),
    # Column("review_text",TEXT,nullable=False),#實際回覆內容
    # Column("review_summary",TEXT,nullable=False),#總結顧客回覆
    # Column("review_sentiment",String(20),nullable=False),#留言情緒判斷
    # Column("review_score",INTEGER,server_default="0",nullable=False), # 評論ＡＩ給分
    # Column("owner_text",TEXT,nullable=False),#實際回覆內容
    # Column("owner_summary",TEXT,nullable=False),#總結老闆回覆
    # Column("owner_sentiment",String(20),nullable=False),#留言情緒判斷
    # Column("owner_score",INTEGER,server_default="0",nullable=False),# 評論ＡＩ給分
    # Column("pr_reply",TEXT,nullable=False),#ＡＩ公關回覆
    # Column("request_json",JSONB,nullable=False),
    # Column("response_json",JSONB,nullable=True),