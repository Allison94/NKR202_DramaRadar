from sqlalchemy import INTEGER, TEXT, TIMESTAMP, Column, Table,MetaData,String, func
from sqlalchemy.dialects.postgresql import JSONB
from db.database import metadata

execution_log = Table(
    "execution_log",
    metadata,
    Column("id",INTEGER,primary_key=True,autoincrement=True),
    Column("pipeline",String(200),nullable=False),
    Column("status",String(20),nullable=False),
    Column("items_count",INTEGER,server_default="0",nullable=False),
    Column("apify_scheduler_id",String(20)),#apify run_id
    Column("apify_dataset_id",String(20)),#apify dataset_id
    Column("actor_name",String(100)),
    Column("started_at",TIMESTAMP,server_default=func.now()),
    Column("finished_at",TIMESTAMP),
    Column("request_json",JSONB),
    Column("response_json",JSONB),
    Column("error_msg",TEXT),#通用錯誤訊息欄位 = apify status_message
    Column("retry_count",INTEGER,server_default="0",nullable=False)
)