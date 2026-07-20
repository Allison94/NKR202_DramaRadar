"""
* 單元測試
"""
import json
import time
from domains.store.pipeline import StoreInterface

def test_pipeline():
    try:
        # mockdata
        postcode = "115"
        # params = {
        #     "county": "TW",
        #     "language": "zh-TW",
        #     "maxCrawledPlacesPerSearch": 3,
        #     # "postalCode": postcode,
        #     "searchStringsArray": ["餐廳","小吃","麵店","便當","餐酒館","料理"],
        # }

        si = StoreInterface(postcode=postcode)

        #job
        job = si.task1_start_job()
        job_output = f"domains/store/tests/result/job_output_{job.get("dataset_id")}.json"
        with open(job_output, "w", encoding="utf-8") as f:
            json.dump(job, f, indent=4, ensure_ascii=False)

        #status
        retry_times = 30
        sleep_second = 30
        for i in range(1,retry_times+1):
            print(f"進行第 {i}/{retry_times} 次狀態確認")
            status = si.task2_check_status(job,i)
            if status["status"] == "SUCCEEDED":
                print(status["status"])
                break
            elif status["status"] in ["FAILED", "ABORTED", "TIMED-OUT"]:
                print(status["status"])
                raise RuntimeError(f"[STOP] 狀態: {status["status"]}")
            
            time.sleep(sleep_second) # 等Ｎ秒重試

        status_output = f"domains/store/tests/result/status_output_{status.get("dataset_id")}.json"
        with open(status_output, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=4, ensure_ascii=False)

        #getdata
        dataset = si.task3_get_dataset(status)
        dataset_output = f"domains/store/tests/result/dataset_output_{dataset.get("dataset_id")}.json"
        with open(dataset_output, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    test_pipeline()