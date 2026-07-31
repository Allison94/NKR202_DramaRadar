# Dashboard 工作清單對照

## 進度

| # | 工作項 | 狀態 | 說明 |
|---|--------|------|------|
| 0 | 前置準備 | 人工 | — |
| 1 | 文件理解、確認工具 | 完成 | Streamlit + Folium |
| 2 | 測試 Streamlit & Folium | 完成 | `dashboard/app.py` |
| 3 | 規劃介面流程 RWD | 完成 | 側邊欄 + 寬版 layout |
| 4 | 架設首頁 | 完成 | 開場動畫 + 主頁 |
| 5 | **地圖 & 資料庫讀取** | 完成 | Folium 地圖 + 火焰標記 |
| 6 | **排行榜 & 資料庫讀取** | 完成 | Altair 長條圖為主；卡片式排行收在 expander |
| 6+ | **數據分析圖表** | 完成 | 分頁（概況 / 地區 / 評論）+ `dashboard/theme.py` 深色主題 |
| 6++ | **地圖頁優化** | 完成 | KPI 指標、熱力圖 toggle、深色底圖 toggle |
| 7 | 上線測試 & DEBUG | 完成 | Docker 8501 可存取 |
| 8 | 最後調整 | 進行中 | 公關回覆 / 爆料仍為展示版 |

## 資料流

```
store + review + ai_analysis
        ↓
domains/store/repository.py  (SQL)
        ↓
domains/store/service.py     (轉 DataFrame、算烈度/人設)
        ↓
dashboard/app.py             (Streamlit 地圖 / 排行榜 / 圖表)
dashboard/charts.py          (圖表資料整理)
dashboard/theme.py           (Altair 深色主題 + render_bar/pie/scatter)
```

## 烈度規則

1. 有 `ai_analysis` → 用 AI 分數
2. 沒有 AI → 用低星評論 + 店家回覆關鍵字估算（暫時）

## 啟動

```bash
streamlit run dashboard/app.py
# http://localhost:8501
```

側邊欄會顯示資料來源：`PostgreSQL（真實資料）` 或 `Demo 假資料`。
