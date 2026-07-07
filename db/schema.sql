CREATE TABLE "store" (
    "placeId" varchar(100)   NOT NULL,
    "title" varchar(100)   NOT NULL,
    "categoryName" varchar(100)   NOT NULL,
    "categories" jsonb   NOT NULL,
    "address" varchar(200)   NULL,
    "url" TEXT   NOT NULL,
    "imageUrl" TEXT   NULL,
    "business_status" varchar(200)   NOT NULL,
    "scrapedAt" TIMESTAMPTZ   NOT NULL,
    "totalScore" float   NOT NULL,
    "reviewsCount" int   NOT NULL,
    "oneStar" int   NOT NULL,
    "twoStar" int   NOT NULL,
    "threeStar" int   NOT NULL,
    "fourStar" int   NOT NULL,
    "fiveStar" int   NOT NULL,
    "blocked" bool   NOT NULL,
    "review_skip" bool   NOT NULL,
    CONSTRAINT "pk_store" PRIMARY KEY (
        "placeId"
     )
);

CREATE TABLE "store_source" (
    "placeId" varchar(100)   NOT NULL,
    "raw_json" JSONB   NOT NULL,
    "scrapedAt" TIMESTAMPTZ   NOT NULL,
    CONSTRAINT "pk_store_source" PRIMARY KEY (
        "placeId"
     )
);

CREATE TABLE "review_source" (
    "reviewId" varchar(100)   NOT NULL,
    "placeId" varchar(100)   NOT NULL,
    "raw_json" JSONB   NOT NULL,
    "scrapedAt" TIMESTAMPTZ   NOT NULL,
    CONSTRAINT "pk_review_source" PRIMARY KEY (
        "reviewId"
     )
);

CREATE TABLE "review" (
    "reviewId" varchar(100)   NOT NULL,
    "placeId" varchar(100)   NOT NULL,
    "originalLanguage" varchar(50)   NOT NULL,
    "text" TEXT   NOT NULL,
    "publishedAtDate" TIMESTAMPTZ   NOT NULL,
    "reviewUrl" TEXT   NOT NULL,
    "reviewImageUrls" JSONB   NULL,
    "likesCount" int   NOT NULL,
    "totalScore" float   NOT NULL,
    "stars" int   NOT NULL,
    "responseFromOwnerDate" TIMESTAMPTZ   NOT NULL,
    "responseFromOwnerText" TEXT   NOT NULL,
    "scrapedAt" TIMESTAMPTZ   NOT NULL,
    "owner_reply_recheck" bool   NOT NULL,
    "owner_reply_recheck_at" TIMESTAMPTZ   NOT NULL,
    "next_check_at" TIMESTAMPTZ   NOT NULL,
    CONSTRAINT "pk_review" PRIMARY KEY (
        "reviewId"
     )
);

CREATE TABLE "ai_analysis" (
    "reviewId" varchar(100)   NOT NULL,
    "placeId" varchar(100)   NOT NULL,
    "review_text" TEXT   NOT NULL,
    "review_summary" TEXT   NOT NULL,
    "review_sentiment" varchar(20)   NOT NULL,
    "review_score" int   NOT NULL,
    "owner_text" TEXT   NOT NULL,
    "owner_summary" TEXT   NOT NULL,
    "owner_sentiment" varchar(20)   NOT NULL,
    "owner_score" int   NOT NULL,
    "pr_reply" TEXT   NULL,
    "request_json" JSONB   NOT NULL,
    CONSTRAINT "pk_ai_analysis" PRIMARY KEY (
        "reviewId"
     )
);

CREATE TABLE "threads_log" (
    "id" varchar(100)   NOT NULL,
    "text" TEXT   NULL,
    "media_type" varchar(20)   NOT NULL,
    "media_url" TEXT   NULL,
    "timestamp" TIMESTAMPTZ   NOT NULL,
    "permalink" TEXT   NOT NULL,
    CONSTRAINT "pk_threads_log" PRIMARY KEY (
        "id"
     )
);

ALTER TABLE "store_source" ADD CONSTRAINT "fk_store_source_placeId" FOREIGN KEY("placeId")
REFERENCES "store" ("placeId");

ALTER TABLE "review_source" ADD CONSTRAINT "fk_review_source_reviewId" FOREIGN KEY("reviewId")
REFERENCES "review" ("reviewId");

ALTER TABLE "review_source" ADD CONSTRAINT "fk_review_source_placeId" FOREIGN KEY("placeId")
REFERENCES "store" ("placeId");

ALTER TABLE "review" ADD CONSTRAINT "fk_review_placeId" FOREIGN KEY("placeId")
REFERENCES "store" ("placeId");

ALTER TABLE "ai_analysis" ADD CONSTRAINT "fk_ai_analysis_reviewId" FOREIGN KEY("reviewId")
REFERENCES "review" ("reviewId");

ALTER TABLE "ai_analysis" ADD CONSTRAINT "fk_ai_analysis_placeId" FOREIGN KEY("placeId")
REFERENCES "store" ("placeId");

