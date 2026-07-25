"""
* 一次性
1. SQL撈all_reviews，計算總數，以batch分割
2. 資料處理後，呼叫llm，得到結果
3. 存入SQL => execution_log、ai_analysis
* 每天更新
1. SQL撈daily_reviews，計算總數，以batch分割
2. 資料處理後，呼叫llm，得到結果
3. 存入SQL => execution_log、ai_analysis
"""
import logging
from domains.ai_analysis.client import genai_client
from domains.ai_analysis.etl import Gemini
from domains.ai_analysis.db_handler import daily_reviews,all_reviews,ai_log,ai_analysis_save
from domains.ai_analysis.config import batch_size
logger = logging.getLogger(__name__)
def ai_analysis_pipeline(during:str="daily"):
    if during == "all":
        reviews = all_reviews()
    else:
        reviews = daily_reviews()

    if reviews:
        records = []
        review_count = len(reviews)
        for i in range(0,review_count,batch_size):
            chunk = reviews[i : i + batch_size]
            with genai_client() as llm_client:
                llm = Gemini(client_obj=llm_client) # client
                llm_result = llm.ai_analysis(chunk) # etl
                log_rs = ai_log(llm_result) # db
                save_rs = ai_analysis_save(llm_result["ai_output"]) # db
                status = llm_result["status"]

            records_line = {
                "log_count":log_rs,
                "save_count":save_rs
            }
            records.append(records_line)

            if status != "STOP":
                logger.error(f"[Danger: ai_analysis_pipeline] during:{during} {llm_result['response_msg']}")
        return records
    else:
        logger.info(f"[Info: ai_analysis_pipeline] during:{during}  無Review可分析")
        return None


if __name__ == "__main__":
    data = ai_analysis_pipeline()
    print(data)