"""
* 整合client etl tosql
* 傳入airflows
"""
from domains.store.client import start_job_actor,check_status,get_dataset
from domains.store.etl import start_job_etl,check_status_etl,dataset_origin,dataset_etl
from domains.store.db_handler import save_apify_log,update_apify_log,save_to_store_source,save_to_store

def start_job():
    # TAIPEI_POSTCODES = ["100", "103", "104", "105", "106", "108", "110", "111", "112", "114", "115", "116"]
    params = {
    "county": "TW",
    "language": "zh-TW",
    "maxCrawledPlacesPerSearch": 3,
    "postalCode": "100",
    "searchStringsArray": ["餐廳","小吃","麵店","便當","餐酒館","料理"],
    }

    start = start_job_actor(params=params)
    job_etl = start_job_etl(params,start)
    job_log_id = save_apify_log(job_etl) #正常為id錯誤為None

    run_id = job_etl.get("run_id")
    dataset_id = job_etl.get("dataset_id")

    return run_id,job_log_id,dataset_id

def status(run_id,job_log_id):
    if run_id:
        status_obj = check_status(run_id)
        status_etl = check_status_etl(status_obj,job_log_id)
        rs_rowcount = update_apify_log(status_etl)
        return rs_rowcount
    
def dataset_line(dataset_id):
    

        return 
def run():
    run_id,job_log_id,dataset_id = start_job()
    rs_rowcount = status(run_id,job_log_id)
    if rs_rowcount != 0 and rs_rowcount != None:
        dataset_line(dataset_id)

        
if __name__ == "__main__":
    run()

    ## TODO: 如何解藕