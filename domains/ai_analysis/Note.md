# AI Analysis Domain

用 Gemini 分析「顧客 vs 老闆」的交鋒，對雙方各自產出摘要、情緒標籤與激烈程度評分。

## 執行鏈

```
client → db_handler 抓資料 → etl → db_handler 存資料（log & ai result） → pipeline → dag
```

- `config.py` 放模型版本與 system instruction 等變數
- `models.py` 同時放資料庫 schema 與 AI 輸出 schema
- 一律 bulk 處理，不要一筆一筆 for loop，效能太差

## 分析對象

**只分析已有老闆回覆的評論**（`responseFromOwnerText` 非空）— 顧客單方面抱怨不構成可分析的衝突。

| 模式 | 查詢條件 | 觸發 |
|---|---|---|
| `daily` | 有老闆回覆 **且** `scrapedAt > 昨天` | `ai_analysis_daily_dag_v1` |
| `all` | 有老闆回覆、**且尚未分析過**（不限時間） | `ai_analysis_all_dag_v1` |

## 中斷後可以接續

Gemini 會回 `503 UNAVAILABLE`（模型忙碌），這是常態，不是程式的錯。

pipeline 是**每批跑完就寫資料庫**，所以中斷時已完成的批次不會白跑。加上 `all` 模式預設會用 `reviewId NOT IN (SELECT reviewId FROM ai_analysis)` 濾掉分析過的，重試就會自動從斷點接續。

這道過濾很重要：DAG 設定了 `retries=2`，少了它，一次 503 會讓同一批評論被送去 Gemini 三次，token 費用也付三次。

改過 prompt 想整批重新分析時，在 `ai_analysis_all_dag_v1` 的 Trigger 表單勾 **force**，或呼叫 `ai_analysis_pipeline("all", force=True)`。

`daily` 模式刻意**不加**這道過濾。Owner Reply Recheck 會更新既有評論的 `responseFromOwnerText`，那種情況必須重新分析；而每日的量本來就小，重跑的代價遠低於漏分析。

## Gemini 設定

| 項目 | 值 |
|---|---|
| SDK | `google-genai`（`genai.Client`） |
| Model | `gemini-3.6-flash` |
| Temperature | `0.2` |
| 輸出約束 | `response_schema = GeminiBatchRs`（Pydantic） |
| 批次大小 | 50 則 / 次 |

用 structured output 而非自由文字，確保回傳欄位能直接寫進資料庫，不需要再解析。

## 輸出欄位

對顧客與老闆**各自**輸出三項：

| 欄位 | 說明 |
|---|---|
| `*_text` | 清洗後原文；外文會翻成繁體中文，格式為「原文\n\n翻譯」 |
| `*_summary` | 摘要，30 字內 |
| `*_sentiment` | 情緒標籤，固定五選一 |
| `*_score` | 激烈程度 1~10（1 完全平靜，10 極度憤怒） |

情緒標籤五選一：理性客觀、高級反串、暴躁老哥、無聊公關、高情商幽默。

另外產出 `pr_reply`：根據雙方衝突點建議的最優公關回覆，Dashboard 的「公關救援」與 Threads 貼文都會用到。

## 執行紀錄

寫入 `execution_log`，`pipeline = "ai_analysis"`。token 用量以 JSON 形式存在 `error_msg` 欄位。

## 手動執行

```bash
# 重跑全部有老闆回覆的評論
uv run python -m domains.ai_analysis.pipeline
```

或在 Python 中呼叫 `ai_analysis_pipeline("daily")` / `ai_analysis_pipeline("all")`。

## 待改進

`db_handler.py` 的 `yesterday` 使用不帶時區的 `datetime.now()`，且在**模組載入時**就計算完成。以 Airflow 每日觸發的短生命週期 process 來說沒有問題，但若改成常駐 process 會取到過期的時間基準。
