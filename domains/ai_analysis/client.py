"""
* 只負責連線
"""
import logging
from contextlib import contextmanager

from google import genai
from shared.config import settings

logger = logging.getLogger(__name__)

@contextmanager # 上下文管理
def genai_client():
    try:
        yield genai.Client(api_key=settings.gemini_api_key) # 在外面用完才關閉
    except Exception as e:
        logger.exception("[Error: genai_client]gemini連線發生錯誤")
        raise e
