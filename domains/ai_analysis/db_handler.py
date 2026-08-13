"""
* 資料庫處理
"""
import json
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from db.database import engine,metadata
from domains.review.models import Review
from domains.ai_analysis.models import Ai_analysis
from db.shared_tables import execution_log as elog
import logging

logger = logging.getLogger(__name__)

try:
    metadata.create_all(bind=engine)
except SQLAlchemyError as e:
    logger.exception(f"[Error:global > create_all]Create Tables Error")
    raise e

yesterday = datetime.now()-timedelta(days=1) 
#每天凌晨三點同步，scrapedAt會是凌晨三點，所以抓大於昨天
def ai_log(data:dict):
    param ={
        "pipeline":"ai_analysis",
        "status":data["status"],
        "items_count":len(data["ai_output"]),
        "actor_name":"ai_log",
        "error_msg":json.dumps(data["response_msg"]),
        "request_json":data["review_id_list"],#存idlist
        "response_json":data["ai_output"],
    }
    with engine.begin() as conn:
        try:
            stmt = insert(elog)
            result = conn.execute(stmt,param)
            rowcount = result.rowcount
            return rowcount
        except SQLAlchemyError as e:
            logger.exception(f"[Error: ai_log]log insert 發生錯誤")
            raise e
        
def daily_reviews(): # 每日定時更新
    with engine.connect() as conn:
        try:
            stmt = select(Review).where(
                Review.c.responseFromOwnerText != None,
                Review.c.responseFromOwnerText != "",
                Review.c.scrapedAt > yesterday
            )
            rs = conn.execute(stmt)
            data = [
                {
                    "reviewId":row.reviewId,
                    "placeId":row.placeId,
                    "text":row.text,
                    "responseFromOwnerText":row.responseFromOwnerText
                }for row in rs
            ]
            return data
        except SQLAlchemyError as e:
            logger.exception("[Error: daily_reviews] 抓取reviews失敗")
            raise e

def all_reviews(): # 一次性重跑
    with engine.connect() as conn:
        try:
            stmt = select(Review).where(
                Review.c.responseFromOwnerText != None,
                Review.c.responseFromOwnerText != "",
            )

            rs = conn.execute(stmt)
            data = [
                {
                    "reviewId":row.reviewId,
                    "placeId":row.placeId,
                    "text":row.text,
                    "responseFromOwnerText":row.responseFromOwnerText
                }for row in rs
            ]
            return data
        except SQLAlchemyError as e:
            logger.exception("[Error: all_reviews] 抓取reviews失敗")
            raise e

def ai_analysis_save(datalist:list[dict]):
    with engine.begin() as conn:
        try:
            stmt = insert(Ai_analysis)
            update_columns ={
                column.name: getattr(stmt.excluded, column.name)
                for column in Ai_analysis.columns
            }
            stmt = stmt.on_conflict_do_update(
                set_= update_columns,
                index_elements= ["reviewId","placeId"]
            )
            rs = conn.execute(stmt,datalist)
            return rs.rowcount
        except SQLAlchemyError as e:
            logger.exception("[Error: ai_analysis_save] 存ai分析資料失敗")
            raise e