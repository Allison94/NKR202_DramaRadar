"""
* 資料處理
"""
import json
from domains.ai_analysis.client import genai_client
from domains.ai_analysis.config import system_instruction_v1,ai_model,ai_temperature
from domains.ai_analysis.models import GeminiBatchRs

def get_ai_analysis(reviews:list[dict]):
    #TODO:把reviewid轉json存進request => safety不是STOP 存資料（可能存一半中斷），從log抓失敗ID重跑
    response = genai_client.models.generate_content(
        model=ai_model,
        contents=f"請分析以下批次資料：\n{json.dumps(reviews, ensure_ascii=False)}",
        config=dict(
            system_instruction=system_instruction_v1,
            response_mime_type="application/json",
            response_schema=GeminiBatchRs,
            temperature=ai_temperature,
            ),
    )

    safety = response.candidates.finish_reason

    if safety == "STOP":
        response_list = json.loads(response.text)["results"]
        
        response_map = {item["reviewId"]:item for item in response_list}
        reviews_map = {review["reviewId"]:review for review in reviews}
    
        for i in response_list:
            ref_id = i["reviewId"]
            request_json = json.dumps(reviews_map.get(ref_id),ensure_ascii=False)
            i["request_json"] = request_json
            response_json = json.dumps(response_map.get(ref_id),ensure_ascii=False)
            i["response_json"] = response_json
            i.pop("is_foreign_language",None) # 剔除不需要欄位

    
    if safety == "STOP": #完成沒問題
        safety_msg = "SUCCESS"
    elif safety == "MAX_TOKENS":
        safety_msg = f"{safety}：輸入過多資料或AI回覆過多，導致超過模型單次輸出的最大Token上限。"
    elif safety == "SAFETY":
        safety_msg = f"{safety}：評論或 AI 生成的回覆中，觸發了 Google 官方的安全過濾器（例如包含極度嚴重的仇恨言論、色情、暴力或騷擾文字）。"
    elif safety == "RECITATION":
        safety_msg = f"{safety}：為了避免侵犯版權，觸發保護機制而停止。"
    else:
        safety_msg = f"{safety}：Google 伺服器端發生突發性的內部錯誤或網路波動。"

    response_msg = {
        "status":safety_msg,
        "input_token":response.usage_metadata.prompt_token_count,
        "output_token":response.usage_metadata.candidates_token_count,
        "total_token":response.usage_metadata.total_token_count
    }
    return {
        "ai_output":response_list,
        "status":safety,
        "response_msg":json.dumps(response_msg) #存log
    }