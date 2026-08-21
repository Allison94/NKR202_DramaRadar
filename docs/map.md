# 文件地圖

本頁列出 `docs/` 目前**實際存在**的文件。規劃中但尚未撰寫的文件列於最後一節。

```text
docs
├── map.md                          <-- 本頁
│
├── 01_Project
│   └── 001-PRD.md                  產品需求、目標、開發原則與限制
│
├── 02_Architecture
│   ├── 002-Product Architecture.md 整體架構、Domain 職責、資料流、排程拓撲、業務判斷邏輯
│   └── 003-Domain Model.md         業務實體與關聯規則
│
├── 03_Database
│   └── 004-Database Design.md      資料庫設計原則、資料表、索引與約束現況
│
├── research
│   ├── R001-Apify API (Google Maps Extractor).md
│   ├── R002-Apify API (Google Maps Reviews Scraper).md
│   └── R003-Gemini API.md
│
├── diagrams
│   ├── OverallArchitecture.png     系統元件與依賴
│   ├── DataFlow.png                資料生命週期
│   ├── DailyWorkflow.png           每日業務流程
│   ├── DomainModel.png             UML Domain Model
│   ├── ERD.png                     資料表關聯
│   └── ProductionArchitecture.png  正式環境部署
│
└── diagrams.drawio                 上述圖表的原始檔
```

## 其他位置的文件

| 路徑 | 內容 |
|---|---|
| `README.md` | 專案總覽、快速開始、DAG 一覽、業務規則（**現況的主要入口**） |
| `FILEMAP.md` | 新成員環境建置檢查清單 |
| `db/schema.sql` | 資料庫 DDL 參考 |
| `domains/*/Note.md` | 各 Domain 的開發筆記與 API 回應範例 |
| `dashboard/Note.md` | Dashboard 驗收對照表 |

## 規劃中，尚未撰寫

以下為原始文件規劃，目前**沒有**對應檔案。相關內容暫時散落在 README、`db/schema.sql` 與程式碼中：

| 編號 | 標題 | 目前替代來源 |
|---|---|---|
| 005 | Data Contract | `domains/*/models.py`、`db/schema.sql` |
| 006 | API Contract | `docs/research/R00*`、`domains/*/client.py` |
| 007 | Engineering Standards | README「專案結構」的檔案職責表 |
| 008 | Folder Structure | README「專案結構」 |
| 009 | Team Development Guide | `FILEMAP.md` |
| ADR-001 | 架構決策紀錄 | 尚未建立 |
| R004 | Threads API | `domains/threads/api.py`、`token_access.py` |
