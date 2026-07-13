from sqlalchemy import MetaData, create_engine
from shared.config import settings

DATABASE_URL = settings.database_url

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20
)

metadata = MetaData() #init 