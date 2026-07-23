from db.database import metadata
from sqlalchemy import Table,Column,String,TIMESTAMP,TEXT,INTEGER,FLOAT,BOOLEAN
from sqlalchemy.dialects.postgresql import JSONB

Review_source = Table(
    "review_source",
    metadata,
    Column("reviewId",String(100),primary_key=True),
    Column("placeId",String(100),nullable=False),
    Column("raw_json",JSONB,nullable=False),
    Column("scrapedAt",TIMESTAMP,nullable=False)
)

Review = Table(
    "review",
    metadata,
    Column("reviewId",String(100),primary_key=True),
    Column("placeId",String(100),nullable=False),
    Column("originalLanguage",String(50),nullable=False),
    Column("text",TEXT,nullable=False),
    Column("publishedAtDate",TIMESTAMP,nullable=False),
    Column("reviewUrl",TEXT,nullable=False),
    Column("reviewImageUrls",TEXT),
    Column("likesCount",INTEGER,server_default="0",nullable=False),
    Column("totalScore",FLOAT,server_default="0.0",nullable=False),
    Column("stars",INTEGER,server_default="0",nullable=False),
    Column("responseFromOwnerDate",TIMESTAMP),
    Column("responseFromOwnerText",TEXT),
    Column("scrapedAt",TIMESTAMP,nullable=False),
    Column("owner_reply_recheck",BOOLEAN,nullable=False),
    Column("owner_reply_recheck_at",TIMESTAMP),
    Column("next_check_at",TIMESTAMP),
)