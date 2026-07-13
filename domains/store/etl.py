"""
* 處理從client端取得資料
* 整理後資料傳入SQL
"""
def start_job_etl(params,obj):
    return {
        "run_id":obj.id,
        "dataset_id":obj.default_dataset_id,
        "started_at":obj.started_at,
        "status":obj.status,
        "request_json":params,
        "response_json":obj,
    }

def check_status_etl(obj,sql_id): #sql_id從 tosql裡面取回
    rt = {
    "sql_id":sql_id,
    "run_id":run_id, # type: ignore
    "status":obj.status, # type: ignore #SUCCEEDED,READY
    "finished_at":obj.finished_at, # type: ignore
    "exit_code":obj.exit_code,  # type: ignore
    "charged_event_counts":obj.charged_event_counts.get("place-scraped", 0), #怕沒欄位先補0
    "status_message":obj.status_message, # type: ignore
    "response_json":obj
    }
    return rt

def dataset_etl():
    pass;


# TEST BLOCK
if __name__ == "__main__":
   pass;