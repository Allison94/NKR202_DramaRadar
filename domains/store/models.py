from sqlalchemy import BOOLEAN,String, Table,FLOAT,INTEGER,TEXT,Column
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
    Column("categories",JSONB,nullable=False),
    Column("address",TEXT,nullable=True),
    Column("url",TEXT,nullable=False),
    Column("imageUrl",TEXT,nullable=True),
    Column("business_status",String(200),nullable=False),
    Column("scrapedAt",TIMESTAMP,nullable=False),
    Column("totalScore",FLOAT,nullable=False),
    Column("reviewsCount",INTEGER,nullable=False),
    Column("oneStar",INTEGER,nullable=False),
    Column("twoStar",INTEGER,nullable=False),
    Column("threeStar",INTEGER,nullable=False),
    Column("fourStar",INTEGER,nullable=False),
    Column("fiveStar",INTEGER,nullable=False),
    Column("blocked",BOOLEAN,server_default="Fasle",nullable=False),
    Column("skip_review_fetch",BOOLEAN,server_default="Fasle",nullable=False)
)
    