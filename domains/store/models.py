from sqlalchemy import BOOLEAN, Float,String, Table,FLOAT,INTEGER,TEXT,Column
from sqlalchemy.dialects.postgresql import JSONB,TIMESTAMP
from db.database import metadata

Store_source = Table(
    "store_source",
    metadata,
    Column("placeId",String(100),primary_key=True),
    Column("raw_json",JSONB,nullable=False),
    Column("scrapedAt",TIMESTAMP,nullable=False)
)

Store = Table(
    "store",
    metadata,
    Column("placeId",String(100),primary_key=True),
    Column("title",TEXT,nullable=False),
    Column("categoryName",String(100),nullable=False),
    Column("categories",TEXT,nullable=False),
    Column("address",TEXT,nullable=True),
    Column("lat",Float,server_default="0.0",nullable=False),
    Column("lng",Float,server_default="0.0",nullable=False),
    Column("url",TEXT,nullable=False),
    Column("imageUrl",TEXT,nullable=True),
    Column("business_status",String(200),nullable=False),
    Column("scrapedAt",TIMESTAMP,nullable=False),
    Column("totalScore",FLOAT,server_default="0.0",nullable=False),
    Column("reviewsCount",INTEGER,server_default="0",nullable=False),
    Column("oneStar",INTEGER,server_default="0",nullable=False),
    Column("twoStar",INTEGER,server_default="0",nullable=False),
    Column("threeStar",INTEGER,server_default="0",nullable=False),
    Column("fourStar",INTEGER,server_default="0",nullable=False),
    Column("fiveStar",INTEGER,server_default="0",nullable=False),
    Column("blocked",BOOLEAN,server_default="False",nullable=False),
    Column("skip_review_fetch",BOOLEAN,server_default="False",nullable=False)
)