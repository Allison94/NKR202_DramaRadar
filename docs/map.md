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
├── 05_Deployment
│   └── 010-GCP VM Deployment.md    GCP VM 部署步驟、機型試算、維運與疑難排解
│
└── research
    ├── R001-Apify API (Google Maps Extractor).md
    ├── R002-Apify API (Google Maps Reviews Scraper).md
    └── R003-Gemini API.md
```

## 圖表

**所有圖表都以 Mermaid 內嵌在文件裡**，沒有獨立的圖片檔。這樣改程式時圖可以跟程式碼一起 diff、一起 review，不會出現圖與實作長期脫節的情況。

| 圖表 | 位置 |
|---|---|
| Overall Architecture | `02_Architecture/002-Product Architecture.md` Figure 2-1 |
| Data Flow | `02_Architecture/002-Product Architecture.md` Figure 4-1 |
| Daily Workflow | `02_Architecture/002-Product Architecture.md` Figure 5-1 |
| Production Architecture | `02_Architecture/002-Product Architecture.md` Figure 6-1 |
| Scheduler Topology | `02_Architecture/002-Product Architecture.md` 第 7 節 |
| Domain Model | `02_Architecture/003-Domain Model.md` Figure 2-1 |
| ERD | `03_Database/004-Database Design.md` 第 4 節 |

README 另有架構圖、資料流圖、每日流程圖與 ERD 的簡化版本。

> 舊版的 `docs/diagrams/*.png` 與 `docs/diagrams.drawio` 已於 2026/8/22 移除。那批圖畫於實作定案之前，內容已與程式不符（最明顯的是 Production Architecture 畫了不存在的 `Fast API` 元件、Daily Workflow 包含已移出每日排程的 Store）。需要時可從 git 歷史取回。

## 其他位置的文件

| 路徑 | 內容 |
|---|---|
| `README.md` | 專案總覽、快速開始、DAG 一覽、業務規則（**現況的主要入口**） |
| `FILEMAP.md` | 新成員環境建置檢查清單 |
| `講稿.md` | 口頭報告講稿，依 Domain 拆解實作過程踩過的坑與解法 |
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
| 011 | Runbook / 監控告警 | 尚未建立，目前僅有 010 的疑難排解表 |
| ADR-001 | 架構決策紀錄 | 尚未建立 |
| R004 | Threads API | `domains/threads/api.py`、`token_access.py` |
