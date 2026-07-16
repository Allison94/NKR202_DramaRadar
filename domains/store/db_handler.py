"""
* SQLAlchemy Core 2.0
* 接收ETL進來的data
"""
from domains.store.models import Store_source
from db.shared_tables import execution_log
from sqlalchemy import insert,update
from db.database import engine

def save_apify_log(obj):
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
        result = conn.execute(stmt)
        pk = result.inserted_primary_key
        pk_id = pk[0] if pk else None
        return pk_id

def update_apify_log(obj):
    stmt = (
        update(execution_log)
        .where(execution_log.c.id == obj.pk_id)
        .values(
            apify_scheduler_id=obj.run_id,
            status=obj.status,
            finished_at=obj.finished_at,
            exit_code=obj.exit_code,
            charged_event_counts=obj.charged_event_counts,
            error_msg=obj.status_message,
            response_json=obj.response_json
        )
    )

    with engine.connect() as conn:
        result = conn.execute(stmt)
        return result.rowcount
    
def save_to_store_source(obj):
    pass;

def save_to_store(data):
    pass;