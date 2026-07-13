from sqlalchemy import INTEGER, TEXT, TIMESTAMP, Column, Table,MetaData,String, func
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

execution_log = Table(
    "execution_log",
    metadata,
    Column("id",String(100),primary_key=True),
    Column("pipeline",String(200),nullable=False),
    Column("status",String(20),nullable=False),
    Column("items_count",INTEGER,server_default="0",nullable=False),
    Column("apify_scheduler_id",String(20)),
    Column("actor_name",String(100)),
    Column("start_at",TIMESTAMP,server_default=func.now()),
    Column("finished_at",TIMESTAMP),
    Column("request_json",JSONB),
    Column("response_json",JSONB),
    Column("error_msg",TEXT),
    Column("retry_count",INTEGER,server_default="0",nullable=False)
)