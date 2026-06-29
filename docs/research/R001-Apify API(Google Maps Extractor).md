# R001-Appify_API

* **Project Name**：DramaRadar
* **Version**：v1.0
* **Date**：2026/6/30
* **Researcher**：Allison

---

# 1. Purpose

說明研究此 API 的目的，以及它在 DramaRadar 中的用途。

# 2. API Overview

| Item                   | Value |
| ---------------------- | ----- |
| API Name               |  Apify API(Google Maps Extractor)     |
| Provider               |Compass|
| Official Documentation |  [Link](https://apify.com/compass/google-maps-extractor)   |
| Base URL               | compass/google-maps-extractor     |
| Pricing                | [Link](https://apify.com/compass/google-maps-extractor/pricing)|

---

# 3. API Flow

說明此 API 的完整呼叫流程。

```text
DramaRadar
      │
      ▼
Install SDK (apify-client)
      │
      ▼
Request
      │
      ▼
Receive Response
      │
      ▼
Processing
```

---

# 4. Request

## Query Parameters / Request Body

| Parameter | 資料型別 | 範例  | Required| Description |
| --- | --- | --- | --- | --- |
| `searchStringsArray` | `string[]` | `["restaurant"]` | ✔   | 搜尋關鍵字，可放多個，例如 `restaurant`、`hotel`、`coffee`。 |
| `locationQuery` | `string` | `"New York, USA"` | ✖   | 搜尋地區，可輸入城市、國家或完整地址。 |
| `maxCrawledPlacesPerSearch` | `number` | `50` | ✖   | 每個搜尋關鍵字最多抓取的 Google Maps 地點數量。 |
| `language` | `string` | `"en"` | ✖   | Google Maps 搜尋語言，例如 `en`、`zh-TW`。 |
| `categoryFilterWords` | `string[]` | `["pizza","italian"]` | ✖   | 類別過濾，只保留符合這些分類的店家。 |
| `searchMatching` | `string` | `"all"` | ✖   | 關鍵字匹配方式，通常為 `all` 或 `any`。`all` 表示需符合所有條件。 |
| `placeMinimumStars` | `number \| string` | `4.5` | ✖   | 最低 Google 評分，例如 `4.5`。空字串代表不限制。 |
| `skipClosedPlaces` | `boolean` | `false` | ✖   | 是否略過已永久停業或暫停營業店家。 |
| `scrapePlaceDetailPage` | `boolean` | `false` | ✖   | 是否進一步抓取店家詳細頁資訊（較慢）。 |
| `maximumLeadsEnrichmentRecords` | `number` | `0` | ✖   | 最多進行 Lead Enrichment 的筆數。 |
| `countryCode` | `string` | `"US"` | ✖   | 國家代碼（ISO 3166-1 Alpha-2）。 |
| `city` | `string` | `"New York"` | ✖   | 城市名稱。 |
| `state` | `string` | `"New York"` | ✖   | 州、省或行政區。 |
| `postalCode` | `string` | `"10001"` | ✖   | 郵遞區號。 |
| `customGeolocation.coordinates` | `number[]` | `[-73.9857,40.7484]` | ✖   | 經緯度座標，格式為 `[longitude, latitude]`。 |
| `startUrls` | `object[]` | `[{"url":"https://www.google.com/maps/..."}]` | ✖   | 從指定 Google Maps URL 開始爬取，而不是使用搜尋關鍵字。 |
| `startUrls[].url` | `string` | `"https://www.google.com/maps/place/..."` | ✖   | Google Maps 地點、搜尋或列表 URL。 |

## Sample Request

```json=
//    ✖不要用locationQuery 篩選資料，這個一次只能抓120筆
{
  "searchStrings": [
    "餐廳",
    "小吃店",
    "餐車"
  ],
  "countryCode": "TW",
  "city": "Taipei",
  "maxCrawledPlacesPerSearch": 99999,
  "scrapePlaceDetailPage": true, //如果使用city抓法這欄必填
  "language": "zh-TW"
}
```

# 5. Response

## Sample Response
資料量過大，自行參考官方output-schema
https://apify.com/compass/google-maps-extractor/output-schema

## Important Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| title | string | ✔ | Name of the place |
| placeId | string | ✔ | Google Place ID |
| categoryName | string | ✖ | Primary category |
| categories | string[] | ✔ | All categories |
| description | string | ✖ | Description of the place |
| address | string | ✖ | Full address |
| street | string | ✖ | Street address |
| city | string | ✖ | City |
| state | string | ✖ | State / Province |
| postalCode | string | ✖ | Postal code |
| countryCode | string | ✖ | Country code (ISO-3166-1 Alpha-2) |
| location.lat | number | ✖ | Latitude |
| location.lng | number | ✖ | Longitude |
| phone | string | ✖ | Formatted phone number |
| phoneUnformatted | string | ✖ | Phone number with country code |
| website | string | ✖ | Official website |
| url | string | ✔ | Google Maps URL |
| imageUrl | string | ✖ | Main image URL |
| imagesCount | number | ✔ | Total number of images |
| price | string | ✖ | Price level ($ ~ $$$$) |
| openingHours | OpeningHour[] | ✖ | Business opening hours |
| additionalInfo | object | ✖ | Amenities and business information |
| totalScore | number | ✖ | Average Google rating |
| reviewsCount | number | ✖ | Total number of reviews |
| reviewsDistribution | ReviewDistribution | ✖ | Distribution of review ratings |
| reviewsTags | Tag[] | ✖ | Frequently mentioned review keywords |
| placesTags | Tag[] | ✖ | Place characteristic tags |
| menu | string | ✖ | Restaurant menu URL |
| reserveTableUrl | string | ✖ | Table reservation URL |
| orderOnline | OrderOnline | ✖ | Online ordering information |
| popularTimesLiveText | string | ✖ | Current popularity description |
| popularTimesLivePercent | number | ✖ | Current popularity percentage |
| popularTimesHistogram | object | ✖ | Popular times histogram |
| permanentlyClosed | boolean | ✔ | Whether the place is permanently closed |
| temporarilyClosed | boolean | ✔ | Whether the place is temporarily closed |
| scrapedAt | string (ISO-8601) | ✔ | Timestamp when the data was scraped |

# 7. Error Handling

| HTTP Code | Meaning | Handling |
| --------- | ------- | -------- |
|           |         |          |

# 8. Design Decisions

根據研究結果所做出的設計決策。

* 使用 `placeId` 作為 Store 的 External Identifier。
* Source Data 保留完整 JSON。
* Application Data 僅保存系統實際使用欄位。

# 9. Open Questions

目前尚未確認，需要後續研究的問題。

# 11. Design Impact

## 11.1 DramaRadar 將使用哪些欄位？

列出實際會進入 Database 或 Processing 的欄位。

| Field | Used For |
| ----- | -------- |
|       |          |

## 11.3 對 Database Design 有哪些影響？

記錄此 API 對 DOC-004 Database Design 的影響。

* 是否需要保存 External Identifier。NO
* 是否需要建立 Source Table。YES
* 是否需要建立 Index。NO
* 是否需要保存完整 Raw JSON。YES

# 12. Conclusion

本次研究結論。
* Source Data 保留完整 JSON。
* 可作為 DramaRadar 的資料來源。
* Response 結構穩定。
* 滿足 MVP 需求。
* 可開始進行 DOC-004 Database Design。
