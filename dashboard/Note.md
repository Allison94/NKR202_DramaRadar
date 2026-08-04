# Dashboard — 組長驗收對照

格式來源：**只讀** `db/schema.sql`（不改 schema、不改 docker-compose / .env）。

## 正式資料路徑（給組長看程式）

| 步驟 | 檔案 | 做什麼 |
|------|------|--------|
| 1 | `domains/store/repository.py` | SQL 讀 `store` / `review` / `ai_analysis` |
| 2 | `domains/store/service.py` | 轉 DataFrame，**禁止**假資料 fallback |
| 3 | `dashboard/app.py` | 畫面顯示 |

測試 seed（可選）：`domains/store/seed_rows.py` + `seed_demo_data` 寫進 DB — **不會**被網頁靜默呼叫；假資料只存在資料庫。

畫面：搜不到在篩選下方醒目提示；排行榜同頁多榜＋直條圖；點店名讀 `review`。

## 組長要求 → 欄位

| 要求 | schema 欄位 | 畫面對應 |
|------|-------------|----------|
| 連資料庫 | PostgreSQL | 側邊欄「資料來源：PostgreSQL」 |
| 店家資料 | `store.title/address/url/lat/lng` | 地圖彈窗 |
| 一店多則評論 | `review` 多列 | 精選對決列表 |
| 評論原網址 | `review.reviewUrl` | 彈窗 / 列表連結 |
| 客人評分人設 | `ai_analysis.review_score` + `review_sentiment` | 彈窗「客人」 |
| 老闆評分人設 | `ai_analysis.owner_score` + `owner_sentiment` | 彈窗「老闆」 |
| AI 公關範例 | `ai_analysis.pr_reply` | 老闆回覆**下方**；公關教室頁 |
| 沒吵架不要放 | `review.stars <= 2` + 烈度門檻 | SQL + service 過濾 |
| 範圍 | `store.address` 含台北市 | SQL filter |
| 兩個燈光 | Streamlit 主題選單 | `.streamlit/config.toml` + CSS 隱藏 |

## DB 空時

顯示「已連線但沒有資料」，**不會**出現假店家。

## 啟動（不改環境）

Dev Container 終端機：

```bash
uv run streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501
```

用 IDE Ports 轉發開 8501。
