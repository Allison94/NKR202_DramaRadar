"""
* 資料處理
"""
import json
from domains.ai_analysis.client import genai_client
from domains.ai_analysis.config import system_instruction_v1,ai_model,ai_temperature
from domains.ai_analysis.models import GeminiBatchRs

def get_ai_analysis(reviews:list[dict]):
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

    return {
        "ai_output":response_list,
        "usage":response.usage_metadata,     #存log
        # prompt_token_count 輸入tk、candidates_token_count 輸出tk、total_token_count 總tk
        "json_safety":response.candidates[0].finish_reason # STOP、SAFETY、MAX_TOKENS #存log
    }