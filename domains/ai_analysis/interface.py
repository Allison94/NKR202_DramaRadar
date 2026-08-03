"""
* 定義ＬＬＭ介面
"""
from abc import ABC, abstractmethod
from typing import List, TypedDict

class LLMInterfaceSchema(TypedDict):
    ai_output:List[dict]
    status:str
    response_msg:dict # 存log
    review_id_list:dict # 抓清單 如果沒跑完或有錯可以從指定位置重來

class LLMServiceInterface(ABC):
    @abstractmethod
    def ai_analysis(self, reviews_chunk: List[dict])->LLMInterfaceSchema:
        pass