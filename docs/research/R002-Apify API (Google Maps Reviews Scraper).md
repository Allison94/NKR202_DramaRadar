---
title: R002-Apify API (Google Maps Reviews Scraper)

---

# R002-Apify API (Google Maps Reviews Scraper)

## 1. Document Information

| Item         | Content                           |
| ------------ | --------------------------------- |
| Document ID  | R002                              |
| Title        | Apify API (Google Maps Reviews Scraper) |
| Author       | Allison                           |
| Version      | v1.0                              |
| Last Updated | 2026/7/6                          |

# 2. API Overview

| Item                   | Description                                                     |
| ---------------------- | --------------------------------------------------------------- |
| Provider               | [Compass](https://apify.com/compass)                            |
| API Name               | Apify API (Google Maps Reviews Scraper)                               |
| Official Documentation | [Link](https://apify.com/compass/google-maps-reviews-scraper)|
| Authentication         |API Token、python 安裝 apify_client                                        |
| Pricing                |[Link](https://apify.com/compass/google-maps-reviews-scraper/pricing)|

---

# 3. Request Analysis

## Required Parameters


| Parameter | Type | Sample | Required | Description |
| --- | --- | --- | --- | --- |
| `placeIds` | Array (String) | `["ChIJabcdEFGHijklMNOPqrstUVWX"]` | 否 (與 startUrls 二選一) | **Google 地點的唯一識別碼 (Place ID) 清單**。<br>精準抓取指定 ID 的評論。若未提供此欄位，則必須填寫 `startUrls`。 |
| `maxReviews` | Integer | `100` | 否 | **每個地點抓取的評論數量上限**。<br>控制爬取的資料量，設定為 `0` 代表抓取所有可用評論。 |
| `reviewsSort` | String | `"newest"` | 否 | **評論的排序方式**。<br>可選項目：<br>• `"newest"` (最新)<br>• `"highestRating"` (評分最高)<br>• `"lowestRating"` (評分最低)<br>• `"mostRelevant"` (最相關) |
| `reviewsStartDate` | String | `"2024-01-01"` | 否 | **評論日期的起算點 (YYYY-MM-DD)**。<br>只抓取該日期之後（含當天）發布的新評論。 |
| `personalData` | Boolean | `true` | 否 | **是否包含評論者的個人資料**。<br>設定為 `true` 會爬取評論者的名稱、個人頭像網址、歷史評論數等公開資訊。 |



## Optional Parameters
| Parameter | Type | Sample | Required | Description |
| --- | --- | --- | --- | --- |
| `startUrls` | Array (Object) | `[{"url": "https://google.com..."}]` | 否 (與 placeIds 二選一) | **目標地點的 Google Maps 網址清單**。<br>可放入特定商家、景點或座標的 URL。若未提供此欄位，則必須填寫 `placeIds`。 |
| `reviewsFilterString` | String | `""` | 否 | **評論關鍵字過濾篩選**。<br>填入特定字串，爬蟲會優先篩選出包含該字詞的評論內容。 |
| `language` | String | `"en"` | 否 | **評論顯示的語言代碼**。<br>例如 `"en"` (英文)、`"zh-TW"` (繁體中文)，決定爬取下來的文字語系。 |

## Request Example

```json=
#第一次 用placeids抓review，限制數量依照抓到地點的1,2星評價數量+50抓取

#之後每次，用placeids抓review，用reviewsSort抓最低評價+reviewsStartDate抓前一天

{
  "startUrls": [
    {
      "url": "https://www.google.com/maps/place/Yellowstone+National+Park/@44.5857951,-110.5140571,9z/data=!3m1!4b1!4m5!3m4!1s0x5351e55555555555:0xaca8f930348fe1bb!8m2!3d44.427963!4d-110.588455?hl=en-GB"
    }
  ],
  "placeIds": [
    "ChIJabcdEFGHijklMNOPqrstUVWX"
  ],
  "maxReviews": 100,
  "reviewsSort": "newest",
  "reviewsStartDate": "2024-01-01",
  "reviewsFilterString": "",
  "language": "en",
  "reviewsOrigin": "all",
  "personalData": true
}
```

# 4. Response Analysis

## Response Structure
[OutPut Schema](https://apify.com/compass/google-maps-reviews-scraper/output-schema)
## Important Fields

僅列出 DramaRadar 會使用的欄位。


| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `text` | String \| Null | 是 | **評論原始文字**。<br>評論者撰寫時所使用的原始語言內容。 |
| `publishedAtDate` | String | 是 | **絕對發布日期 (ISO 8601)**。<br>精準的時間戳記，例如：`2024-01-15T08:30:00.000Z`。 |
| `likesCount` | Number | 否 | **獲得按讚數**。<br>該則評論被其他用戶點擊「實用」或「按讚」的總次數。 |
| `reviewId` | String \| Null | 是 | **評論唯一識別碼**。<br>Google Maps 系統給予該則評論的專屬 ID。 |
| `reviewUrl` | String \| Null | 是 | **評論直達網址**。<br>可直接連結到該條特定評論的 URL。 |
| `stars` | Number \| Null | 是 | **評論星等 (1-5)**。<br>用戶給予的評分數值。 |
| `responseFromOwnerDate` | String \| Null | 是 | **商家回覆時間**。<br>店家老闆回覆此評論的日期時間。 |
| `responseFromOwnerText` | String \| Null | 是 | **商家回覆內容**。<br>店家老闆對該評論撰寫的回應文字。 |
| `reviewImageUrls` | Array (String) | 否 | **評論附圖網址清單**。<br>用戶隨評論上傳的照片 URL 陣列。 |
| `visitedIn` | String \| Null | 是 | **造訪月份**。<br>用戶實際造訪該地點的月份與年份。 |
| `originalLanguage` | String \| Null | 是 | **原始語言代碼**。<br>評論原本所使用的語言縮寫（如 `zh-Hant`, `en`）。 |
| `name` | String \| Null | 是 | **評論者姓名**。<br>撰寫評論的用戶公開顯示名稱。 |
| `reviewerId` | String \| Null | 是 | **評論者唯一識別碼**。<br>該用戶的 Google 帳號識別碼。 |
| `isLocalGuide` | Boolean | 否 | **是否為在地嚮導**。<br>若為 `true` 代表該用戶擁有 Google 在地嚮導身分。 |
| `title` | String | 是 | **地點名稱**。<br>被爬取商家的店名或景點名稱。 |
| `placeId` | String | 是 | **Google 地點 ID**。<br>該地點在 Google Maps 上的唯一識別碼。 |
| `location` | Object | 是 | **地理座標**。<br>包含經度 (Longitude) 與緯度 (Latitude) 的物件。 |
| `categories` | Array (String) | 是 | **分類標籤清單**。<br>該地點所屬的所有類別（如 `["餐廳", "咖啡廳"]`）。 |
| `categoryName` | String \| Null | 是 | **主分類名稱**。<br>該地點最核心的第一分類類別。 |
| `totalScore` | Number \| Null | 是 | **平均總評分 (0-5)**。<br>該店家在 Google 上的綜合平均星等。 |
| `permanentlyClosed` | Boolean | 是 | **是否永久停業**。<br>標記該地點目前是否已永久關閉。 |
| `temporarilyClosed` | Boolean | 是 | **是否暫時停業**。<br>標記該地點目前是否處於暫時休業狀態。 |
| `reviewsCount` | Number \| Null | 是 | **總評論數量**。<br>該商家在 Google Maps 上獲得的總評論則數。 |
| `url` | String | 是 | **商家主頁網址**。<br>該地點在 Google 地圖上的官方詳細資訊頁面連結。 |
| `imageUrl` | String \| Null | 是 | **商家主圖網址**。<br>該地點在 Google Maps 封面上顯示的主照片連結。 |
| `scrapedAt` | String | 是 | **爬取時間戳記 (ISO 8601)**。<br>此筆資料被爬蟲抓取下來的當下時間。 |
| `city` | String \| Null | 是 | **城市**。<br>該地點所屬的城市名稱（如：台北市）。 |
| `countryCode` | String \| Null | 是 | **國家代碼**。<br>兩碼國際國家代碼（如 `TW`, `US`）。 |
| `postalCode` | String \| Null | 是 | **郵遞區號**。<br>該地址的郵遞區號。 |


## Response Example
```json=
{
  "text": "這家餐廳的服務很好，餐點也很好吃！",
  "publishedAtDate": "2024-01-15T08:30:00.000Z",
  "likesCount": 5,
  "reviewId": "ChZDSUhNMG9uS0VJQ0FnSUN6X3BiNlVREAE",
  "reviewUrl": "https://google.com...",
  "stars": 5,
  "responseFromOwnerDate": "2024-01-16T10:00:00.000Z",
  "responseFromOwnerText": "謝謝您的好評！歡迎再次光臨！",
  "reviewImageUrls": [
    "https://googleusercontent.com..."
  ],
  "visitedIn": "2024-01",
  "originalLanguage": "zh-Hant",
  "name": "王小明",
  "reviewerId": "11223344556677889900",
  "isLocalGuide": true,
  "title": "美味餐廳台北店",
  "placeId": "ChIJabcdEFGHijklMNOPqrstUVWX",
  "location": {
    "lat": 25.033964,
    "lng": 121.564468
  },
  "categories": [
    "餐廳",
    "咖啡廳"
  ],
  "categoryName": "餐廳",
  "totalScore": 4.5,
  "permanentlyClosed": false,
  "temporarilyClosed": false,
  "reviewsCount": 1250,
  "url": "https://google.com...",
  "imageUrl": "https://googleusercontent.com...",
  "scrapedAt": "2026-07-06T01:50:00.000Z",
  "city": "台北市",
  "countryCode": "TW",
  "postalCode": "110"
}

```
# 5. Data Mapping

```
    API Response
    (需分一次全抓跟每日抓條件不同)

    ↓

    原始資料存入SQL

    ↓

    ETL
    
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
費用問題，請注意不要一次CALL所有資料
