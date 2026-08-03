"""
* 整合client etl tosql
* 傳入airflows
"""
from domains.store.client import StoreClient
from domains.store import config,etl,db_handler

class StoreInterface:
    def __init__(self,postcode:str,params:dict|None=None,):
        if params:
            self.params = params.copy()
        else:
            self.params = config.params.copy()
        self.postcode = postcode

    def task1_start_job(self)->dict:
        # setting params
        search_condition = config.params
        search_condition["postalCode"] = self.postcode

        # client 
        store_client = StoreClient()
        actor_rs = store_client.start_job_actor(search_condition)

        # etl
        store_etl = etl.start_job_etl(search_condition,actor_rs)

        # db_handler
        db_log_id = db_handler.save_apify_log(store_etl)

        rs = {
            "status":actor_rs["status"],
            "run_id": actor_rs["id"],
            "dataset_id": actor_rs["default_dataset_id"],
            "db_log_id": db_log_id #none or number
        }
        return rs
    
    def task2_check_status(self,job_info:dict,retry_times:int=0)->dict:
        # client 
        store_client = StoreClient()
        status_rs = store_client.check_status(job_info["run_id"])

        # etl
        status_etl = etl.check_status_etl(status_rs,job_info["db_log_id"])
        
        # db_handler
        db_log_update_id = db_handler.update_apify_log(status_etl,retry_times)

        rs = {
            "status":status_rs["status"],
            "dataset_id":job_info["dataset_id"],
            "db_log_update_id":db_log_update_id, #none or number
        }
        return rs
    
    def task3_get_dataset(self,status_info:dict)->dict:
        db_log_update_id = status_info["db_log_update_id"]
        if db_log_update_id == None or db_log_update_id == 0:
            return {
                "dataset_id":status_info["dataset_id"],
                "origin_rowcount":None,
                "etl_rowcount":None,
            }
        # client
        store_client = StoreClient()
        dataset = store_client.get_dataset(status_info["dataset_id"])

        # etl
        origin_list_dict = etl.dataset_origin(dataset)
        # db_handler
        origin_rowcount = db_handler.save_to_store_source(origin_list_dict)

        # etl
        etl_dict = etl.dataset_etl(dataset)
        # db_handler
        etl_rowcount = db_handler.save_to_store(etl_dict)
        
        rs = {
            "dataset_id":status_info["dataset_id"],
            "origin_rowcount":origin_rowcount,
            "etl_rowcount":etl_rowcount,
        }
        return rs