---
title: R001-Apify API (Google Maps Extractor)

---

# R001-Apify API (Google Maps Extractor)

## 1. Document Information

| Item         | Content                           |
| ------------ | --------------------------------- |
| Document ID  | R001                              |
| Title        | Apify API (Google Maps Extractor) |
| Author       | Allison                           |
| Version      | v1.0                              |
| Last Updated | 2026/7/4                          |

# 2. API Overview

| Item                   | Description                                                     |
| ---------------------- | --------------------------------------------------------------- |
| Provider               | [Compass](https://apify.com/compass)                            |
| API Name               | Apify API (Google Maps Extractor)                               |
| Official Documentation | [Link](https://apify.com/compass/google-maps-extractor)         |
| Authentication         |API Token、python 安裝 apify_client                                        |
| Pricing                | [Link](https://apify.com/compass/google-maps-extractor/pricing) |
| Usage Limits           | 使用`location`欄位，一次只能抓120筆，請勿使用!!                 |

---

# 3. Request Analysis

## Required Parameters

| Parameter | 資料型別 | 範例  | Required| Description |
| --- | --- | --- | --- | --- |
| `searchStringsArray` | `string[]` | `["restaurant"]` | ✔   | 搜尋關鍵字，可放多個，例如 `restaurant`、`hotel`、`coffee`。 |
| `maxCrawledPlacesPerSearch` | `number` | `50` | ✖   | 每個搜尋關鍵字最多抓取的 Google Maps 地點數量。 |
| `language` | `string` | `"en"` | ✖   | Google Maps 搜尋語言，例如 `en`、`zh-TW`。 |
| `categoryFilterWords` | `string[]` | `["pizza","italian"]` | ✖   | 類別過濾，只保留符合這些分類的店家。 |
| `searchMatching` | `string` | `"all"` | ✖   | 關鍵字匹配方式，通常為 `all` 或 `any`。`all` 表示需符合所有條件。 |
| `placeMinimumStars` | `number \| string` | `4.5` | ✖   | 最低 Google 評分，例如 `4.5`。空字串代表不限制。 |
| `scrapePlaceDetailPage` | `boolean` | `false` | ✖   | 是否進一步抓取店家詳細頁資訊（較慢）。 |
| `countryCode` | `string` | `"US"` | ✖   | 國家代碼（ISO 3166-1 Alpha-2）。 |
| `city` | `string` | `"New York"` | ✖   | 城市名稱。 |

## Optional Parameters
| Parameter | 資料型別 | 範例  | Required| Description |
| --- | --- | --- | --- | --- |
| `state` | `string` | `"New York"` | ✖   | 州、省或行政區。 |
| `skipClosedPlaces` | `boolean` | `false` | ✖   | 是否略過已永久停業或暫停營業店家。 |
| `postalCode` | `string` | `"10001"` | ✖   | 郵遞區號。 |
| `startUrls` | `object[]` | `[{"url":"https://www.google.com/maps/..."}]` | ✖   | 從指定 Google Maps URL 開始爬取，而不是使用搜尋關鍵字。 |
| `startUrls[].url` | `string` | `"https://www.google.com/maps/place/..."` | ✖   | Google Maps 地點、搜尋或列表 URL。 |
| `customGeolocation.coordinates` | `number[]` | `[-73.9857,40.7484]` | ✖   | 經緯度座標，格式為 `[longitude, latitude]`。 |

## Request Example

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
  "language": "zh-TW",
  "placeMinimumStars":4.5
}
```

# 4. Response Analysis

## Response Structure
[OutPut Schema](https://apify.com/compass/google-maps-extractor/output-schema)
## Important Fields

僅列出 DramaRadar 會使用的欄位。

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| title | string | ✔ | Name of the place |
| placeId | string | ✔ | Google Place ID |
| categoryName | string | ✖ | Primary category |
| categories | string[] | ✔ | All categories |
| description | string | ✖ | Description of the place |
| address | string | ✖ | Full address |
| url | string | ✔ | Google Maps URL |
| imageUrl | string | ✖ | Main image URL |
| totalScore | number | ✖ | Average Google rating |
| reviewsCount | number | ✖ | Total number of reviews |
| reviewsDistribution | ReviewDistribution | ✖ | 評論星等分布 |
| permanentlyClosed | boolean | ✔ | 是否歇業 |
| temporarilyClosed | boolean | ✔ | 是否暫停營業 |
| scrapedAt | string (ISO-8601) | ✔ | 資料抓取時間 |

## Response Example
```json=
{
  "title": "Din Tai Fung Taipei 101",
  "placeId": "ChIJN1t_tDeuEmsRUsoyG83frY4",
  "categoryName": "Taiwanese restaurant",
  "categories": [
    "Taiwanese restaurant",
    "Dim sum restaurant",
    "Restaurant"
  ],
  "description": "A popular Taiwanese restaurant famous for its xiaolongbao and traditional dishes.",
  "address": "B1, Taipei 101, No. 7, Section 5, Xinyi Rd, Xinyi District, Taipei City 110, Taiwan",
  "url": "https://maps.google.com/?cid=1234567890123456789",
  "imageUrl": "https://lh3.googleusercontent.com/p/AF1QipMockImage123=w800-h600",
  "totalScore": 4.7,
  "reviewsCount": 18432,
  "reviewsDistribution": {
    "oneStar": 143,
    "twoStar": 218,
    "threeStar": 694,
    "fourStar": 3951,
    "fiveStar": 13426
  },
  "permanentlyClosed": false,
  "temporarilyClosed": false,
  "scrapedAt": "2026-07-04T15:42:31.128Z"
}
```
# 5. Data Mapping

```
    API Response

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
