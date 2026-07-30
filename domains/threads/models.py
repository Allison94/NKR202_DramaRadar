from db.database import metadata
from sqlalchemy import Table,Column,String,TIMESTAMP,TEXT


threads_log = Table(
    "threads_log",
    metadata,
    Column("id",String(100),primary_key=True),
    Column("text",TEXT,nullable=False),
    Column("media_type",String(20),nullable=False),
    Column("media_url",TEXT,nullable=True),
    Column("timestamp",TIMESTAMP,nullable=False),
    Column("permalink",TEXT,nullable=False),
)

