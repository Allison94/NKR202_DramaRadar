---
title: R003-Gemini API

---

# R003-Gemini API

## 1. Document Information

| Item         | Content    |
| ------------ | ---------- |
| Document ID  | R003       |
| Title        | Gemini API |
| Author       | Allison    |
| Version      | v1.0       |
| Last Updated | 2026/7/6   |

# 2. API Overview

| Item                   | Description                                                      |
| ---------------------- | ---------------------------------------------------------------- |
| Provider               | google                                                           |
| API Name               | Gemini API                                                       |
| Official Documentation | [Link](https://ai.google.dev/gemini-api/docs/libraries?hl=zh-tw) |
| Authentication         | API Token、python 安裝 google-genai                              |
| Pricing                | [Link](https://ai.google.dev/gemini-api/docs/pricing?hl=zh-tw)   |

---

# 3. Request Analysis

## Required Parameters


| Parameter | Type | Sample | Required | Description |
| --- | --- | --- | --- | --- |
| `model` | String | `"gemini-2.5-flash"` | 是 | **指定要使用的 Gemini 模型名稱**。|
| `contents` | String \| Array | `"請分析以下評論...\n[{\"id\": 1, \"text\": \"...\"}]"` | 是 | **主要的 Prompt 提示詞與待分析數據**。<br>在此欄位直接放入您的指令以及用 `json.dumps()` 打包好的評論陣列。 |
| `config.response_mime_type` | String | `"application/json"` | 否 | **強制約束 AI 回傳的純文字格式**。<br>填入 `"application/json"` 可以確保 AI 絕對不會吐出「好的，以下是分析：」等廢話，而是直接回傳乾淨的 JSON。 |
| `config.response_schema` | Type (Pydantic / Class) | `list[ReviewAnalysis]` | 否 | **指定 AI 的輸出資料結構規格**。<br>傳入您的 Pydantic 類別規格（例如強迫回傳符合結構的陣列），能 100% 保證回傳的欄位能被 Python 和資料庫解析。 |
| `config.system_instruction` | String | `"你是一位擁有 10 年經驗的頂級危機處理公關..."` | 否 | **設定 AI 的背景人設與全域行為準則**。<br>用來固定 AI 的說話語氣（如：專業誠懇）、處理負評的邏輯，不需每次都寫在 contents 裡面。 |
| `config.temperature` | Float | `0.2` | 否 | **控制 AI 回答的隨機性與創造力**。<br>範圍為 `0.0` 到 `2.0`。做資料庫分析與公關稿建議設低（如 `0.1` 或 `0.2`），讓格式極度穩定且不胡言亂語。 |
| `config.thinking_config` | Object | `{"thinking_budget": 1024}` | 否 | **開啟 Gemini 2.5 獨有的「深度思考模式」**。<br>可配置 `thinking_budget`（Token 數）。在遇到棘手的極端負評公關回覆時，能讓 AI 先進行邏輯推理再輸出，大幅提升高情商回覆品質。 |
| `config.max_output_tokens` | Integer | `8192` | 否 | **限制 AI 單次回答的最大 Token 數量**。<br>Gemini 2.5 Flash 最大可設為 `8192`。確保 50 則評論的分析與公關稿不會因為長度超標而被切斷。 |

## Request Example

```json=
{
  "model": "gemini-2.5-flash",
  "contents": "請分析以下 Google Maps 評論陣列，並為每則評論產出情緒分析與公關回覆。必須嚴格遵守輸出的 JSON Schema 格式。\n\n[\n  {\n    \"id\": \"ChZDSUhNMG9uS0VJQ0FnSUN6X3BiNlVREAE\",\n    \"text\": \"上菜速度慢得誇張，等了快 40 分鐘！服務生態度還很不耐煩。不過牛排本身是好吃的，但整體體驗很糟糕，不會再光顧了。\"\n  },\n  {\n    \"id\": \"ChZDSUhNMG9uS0VJQ0FnSUN6X3BiN2ZFRFF\",\n    \"text\": \"環境乾淨衛生，機車很好停。椒麻雞便當超級好吃，配菜也很豐富，百吃不厭，強烈推薦！\"\n  },\n  {\n    \"id\": \"ChZDSUhNMG9uS0VJQ0FnSUN6X3BiOGdFR0E\",\n    \"text\": \"食物還可以，但價格偏高。店內冷氣不夠強，夏天吃飯吃到滿頭大汗，體驗普通。\"\n  }\n]",
  "config": {
    "system_instruction": "你是一位擁有 10 年經驗的頂級危機處理公關。你的任務是精準分析顧客不滿的痛點，並撰寫出語氣誠懇、專業、不卑不亢、且能展現改善誠意的公關回覆。如果是好評，則要熱情並感謝支持。",
    "response_mime_type": "application/json",
    "response_schema": {
      "type": "ARRAY",
      "description": "包含每則評論分析結果的陣列",
      "items": {
        "type": "OBJECT",
        "properties": {
          "review_id": { "type": "STRING", "description": "對應輸入的評論唯一 ID" },
          "sentiment": { "type": "STRING", "description": "情緒分類，例如正面、負面、混合" },
          "score": { "type": "INTEGER", "description": "情緒分數 -5 到 5" },
          "summary": { "type": "STRING", "description": "評論重點一句話摘要" },
          "pr_reply": { "type": "STRING", "description": "得體的官方公關回覆文字" }
        },
        "required": ["review_id", "sentiment", "score", "summary", "pr_reply"]
      }
    },
    "temperature": 0.2,
    "max_output_tokens": 8192,
    "thinking_config": {
      "thinking_budget": 1024
    }
  }
}

```

# 4. Response Analysis

## Response Structure
    輸出結構由使用者規範
```python=
#規範範例
from pydantic import BaseModel, Field

class ReviewAnalysis(BaseModel):
    # 透過 description 精準導引 AI 的大腦
    review_id: str = Field(description="必須一字不漏複製顧客評論原始的唯一 ID")
    
    sentiment: str = Field(description="情感分析結果，只能從這三個標籤挑選：'正面'、'負面'、'混合'")
    
    score: int = Field(description="情緒不滿或滿意分數，範圍嚴格限制在整數 -5 (極度憤怒) 到 5 (極度滿意)")
    
    summary: str = Field(description="用一句話精簡總結顧客這則評論的核心痛點或稱讚點")
    
    pr_reply: str = Field(description="針對該評論撰寫的高情商官方公關回覆，語氣要誠懇專業")

```
## Response Example
```json=
[
  {
    "review_id": "ChZDSUhNMG9uS0VJQ0FnSUN6X3BiNlVREAE",
    "sentiment": "混合（有褒有貶）",
    "score": -2,
    "summary": "顧客肯定牛排美味，但對極慢的上菜速度與不耐煩的服務態度感到強烈不滿，表示不會再光顧。",
    "pr_reply": "您好，非常感謝您蒞臨本店並回饋您的用餐體驗。首先，對於讓您和同行夥伴苦等了將近 40 分鐘，以及服務人員在態度上的不耐煩，我們感到非常抱歉，這確實違反了我們應有的服務標準。我們非常高興得知您肯定我們的牛排品質，但出餐流程與服務態度的缺失確實嚴重影響了您的體驗。團隊已於今日針對出餐效率及第一線同仁的服務禮儀進行檢討與加強培訓，避免類似情況再次發生。我們誠摯地希望能有機會再次邀請您蒞臨，讓我們為您提供符合預期的滿意服務。再次為本次的不愉快體驗向您致上最深的歉意。 ── 店家管理團隊敬上"
  },
  {
    "id": "ChZDSUhNMG9uS0VJQ0FnSUN6X3BiN2ZFRFF",
    "sentiment": "正面",
    "score": 5,
    "summary": "顧客對店內環境、停車便利性以及椒麻雞便當大加讚賞，給予百吃不厭的強烈推薦。",
    "pr_reply": "您好！非常高興能得到您如此崇高的評價！我們一直致力於提供乾淨舒適的用餐環境與便利的周邊機能，得知我們的椒麻雞便當能成為讓您「百吃不厭」的美味，這對我們全體廚藝與服務團隊是最大的鼓舞。我們會持續維持高品質的餐點與配菜，期待您下次停好車後，再次進來享用您最愛的美味便當！再次感謝您的熱情推薦！ ── 店家管理團隊敬上"
  },
  {
    "id": "ChZDSUhNMG9uS0VJQ0FnSUN6X3BiOGdFR0E",
    "sentiment": "負面",
    "score": -1,
    "summary": "顧客認為食物普通且價格偏高，並抱怨夏季店內冷氣不夠強，導致滿頭大汗、體驗普通。",
    "pr_reply": "您好，非常感謝您抽出時間留下反饋。對於餐點性價比未能完全符合您的預期，我們深表遺憾。另外，關於您提到夏天店內冷氣不夠強，導致您在用餐時感到悶熱不適，我們致上誠摯的歉意。管理團隊今日已聯絡冷氣廠商前來全面檢修並調低運轉溫度，並會同步評估加裝循環扇以改善空調死角。感謝您的提點，這能讓我們發現服務細節的不足，期待未來能有機會為您提供更舒適、滿意的用餐體驗。 ── 店家管理團隊敬上"
  }
]

```
# 5. Data Mapping

```
    API Response

    ↓

    產出資料存入SQL
```

# 6. Constraints


# 7. Design Impact

此 API 對專案設計造成哪些影響。

- Architecture
- Database
- ETL
- Scheduler
- Business Rule
- Data Contract

# 8. Conclusion

## Suitable

✅

## Risks
使用2.5flash版本有效防ai幻覺，並降低成本