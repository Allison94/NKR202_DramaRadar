"""
* SQLAlchemy Core 2.0
* 接收ETL進來的data
"""
from domains.store.models import Store, Store_source
from db.shared_tables import execution_log
from sqlalchemy import insert,update
from db.database import engine
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

def save_apify_log(obj:dict):
    if not obj:
        return
    
    stmt = insert(execution_log).values(
        pipeline="store",# TODO:可以用def name之類的，後改
        status=obj["status"],
        apify_scheduler_id=obj["run_id"],
        apify_dataset_id=obj["dataset_id"],
        actor_name="Allison",# TODO:之後可改自動抓server或者抓git user.name
        start_at=obj["start_at"],
        request_json=obj["request_json"],
        response_json=obj["response_json"]
    )
    
    with engine.connect() as conn:
        try:
            result = conn.execute(stmt)
            pk = result.inserted_primary_key
            pk_id = pk[0] if pk else None
            return pk_id
        except SQLAlchemyError as e:
            logger.exception(f"[Error:save_apify_log] log 存入發生錯誤")
            raise e

def update_apify_log(obj:dict):
    if not obj:
        return
    
    stmt = (
        update(execution_log)
        .where(execution_log.c.id == obj["job_log_id"])
        .values(
            apify_scheduler_id=obj["run_id"],
            status=obj["status"],
            finished_at=obj["finished_at"],
            exit_code=obj["exit_code"],
            charged_event_counts=obj["charged_event_counts"],
            error_msg=obj["status_message"],
            response_json=obj["response_json"]
        )
    )

    with engine.connect() as conn:
        try:
            result = conn.execute(stmt)
            return result.rowcount
        except SQLAlchemyError as e:
            logger.exception(f"[Error:update_apify_log] update log 存入發生錯誤")
            raise e
    
def save_to_store_source(obj:list[dict]):
    if not obj:
        return
    
    stmt = insert(Store_source).values(obj)

    with engine.begin() as conn:
        try:
            result = conn.execute(stmt)
            return result.rowcount
        except SQLAlchemyError as e:
            logger.exception(f"[Error:save_to_store_source]Store Origin Source 存入發生錯誤")
            raise e
    
def save_to_store(df:list[dict]):
    if not df:
        return
    
    stmt = insert(Store).values(df)

    with engine.begin() as conn:
        try:
            result = conn.execute(stmt)
            return result.rowcount
        except SQLAlchemyError as e:
            logger.exception(f"[Error:save_to_store] Store 存入發生錯誤")
            raise e