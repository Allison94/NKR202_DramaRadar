"""
* 定義schema格式
"""
from typing import Literal
from unittest import result

from sqlalchemy import Table,Column,String,TEXT,INTEGER
from sqlalchemy.dialects.postgresql import JSONB
from db.database import metadata
from pydantic import BaseModel,Field

Ai_analysis = Table(
    "ai_analysis",
    metadata,
    Column("reviewId",String(100),primary_key=True),
    Column("placeId",String(100),nullable=False),
    Column("review_text",TEXT,nullable=False),#實際回覆內容
    Column("review_summary",TEXT,nullable=False),#總結顧客回覆
    Column("review_sentiment",String(20),nullable=False),#留言情緒判斷
    Column("review_score",INTEGER,server_default="0",nullable=False), # 評論ＡＩ給分
    Column("owner_text",TEXT,nullable=False),#實際回覆內容
    Column("owner_summary",TEXT,nullable=False),#總結老闆回覆
    Column("owner_sentiment",String(20),nullable=False),#留言情緒判斷
    Column("owner_score",INTEGER,server_default="0",nullable=False),# 評論ＡＩ給分
    Column("pr_reply",TEXT,nullable=False),#ＡＩ公關回覆
    Column("request_json",JSONB,nullable=False),
    Column("response_json",JSONB,nullable=True),
)

EmotionTag = Literal[
    "高級反串 (表面客氣暗藏嘲諷)",
    "暴躁老哥 (直接開嗆、情緒勒索)",
    "無聊公關 (制式道歉)",
    "高情商幽默"
]

class ReviewsAnalysisFormat(BaseModel):
    reviewId:str = Field(description="原始資料的reviewId，絕對不能改變")
    placeId:str = Field(description="原始資料的placeId，絕對不能改變")
    review_text:str = Field(description="""
        顧客實際回覆內容。請注意：
        1. 如果原文是外文（英文、日文、韓文、簡體等），請將其完整翻譯成繁體中文（台灣用語）並，依照【原文\n\n翻譯格式】填入此欄位。
        2. 如果原本就是繁體中文，請進行空格清洗後直接保留。
        """)
    review_summary:str = Field(description="顧客回覆的核心內容摘要，繁體中文 (30字內)")
    review_sentiment:EmotionTag = Field(description="精準判斷顧客的負面情緒或表現型態")
    review_score:int = Field(description="顧客情緒激烈程度給分，範圍 1~10 分 (1 為完全平靜，10 為極度憤怒/激烈)")
    owner_text:str = Field(description="""
        商家實際回覆內容。請注意：
        1. 如果原文是外文（英文、日文、韓文、簡體等），請將其完整翻譯成繁體中文（台灣用語）並，依照【原文\n\n翻譯格式】填入此欄位。
        2. 如果原本就是繁體中文，請進行空格清洗後直接保留。
        """)
    owner_summary:str = Field(description="商家回覆的核心內容摘要，繁體中文 (30字內)")
    owner_sentiment:EmotionTag = Field(description="精準判斷商家的回覆情緒或表現型態")
    owner_score:int = Field(description="商家情緒激烈程度給分，範圍 1~10 分 (1 為完全平靜，10 為極度憤怒/激烈)")
    pr_reply:str = Field(description="根據雙方衝突點，產出一則『建議的最優公關回覆』語氣需高情商、能平息怒火、化解尷尬")
    is_foreign_language: bool = Field(description="輸入的顧客回覆或商家回覆中，是否包含任何非繁體中文的外文")

class GeminiBatchRs(BaseModel):
    results: list[ReviewsAnalysisFormat]