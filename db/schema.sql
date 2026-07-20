CREATE TABLE "store" (
    "placeId" VARCHAR(100)  NOT NULL,
    "title" TEXT  NOT NULL,
    "categoryName" VARCHAR(100)  NOT NULL,
    "categories" JSONB  NOT NULL,
    "address" TEXT,
    "lat" FLOAT DEFAULT 0.0 NOT NULL,
    "lng" FLOAT DEFAULT 0.0 NOT NULL,
    "url" TEXT  NOT NULL,
    "imageUrl" TEXT,
    "business_status" VARCHAR(200)  NOT NULL,
    "scrapedAt" TIMESTAMPTZ  NOT NULL,
    "totalScore" FLOAT  DEFAULT 0.0  NOT NULL,
    "reviewsCount" INT  DEFAULT 0  NOT NULL,
    "oneStar" INT  DEFAULT 0  NOT NULL,
    "twoStar" INT  DEFAULT 0  NOT NULL,
    "threeStar" INT  DEFAULT 0  NOT NULL,
    "fourStar" INT  DEFAULT 0  NOT NULL,
    "fiveStar" INT  DEFAULT 0  NOT NULL,
    "blocked" bool  DEFAULT FALSE  NOT NULL,
    "skip_review_fetch" bool  DEFAULT FALSE  NOT NULL,
    CONSTRAINT "pk_store" PRIMARY KEY (
        "placeId"
    )
);

CREATE TABLE "store_source" (
    "placeId" VARCHAR(100)  NOT NULL,
    "raw_json" JSONB  NOT NULL,
    "scrapedAt" TIMESTAMPTZ  NOT NULL,
    CONSTRAINT "pk_store_source" PRIMARY KEY (
        "placeId"
    )
);

CREATE TABLE "review_source" (
    "reviewId" VARCHAR(100)  NOT NULL,
    "placeId" VARCHAR(100)  NOT NULL,
    "raw_json" JSONB  NOT NULL,
    "scrapedAt" TIMESTAMPTZ  NOT NULL,
    CONSTRAINT "pk_review_source" PRIMARY KEY (
        "reviewId"
    )
);

CREATE TABLE "review" (
    "reviewId" VARCHAR(100)  NOT NULL,
    "placeId" VARCHAR(100)  NOT NULL,
    "originalLanguage" VARCHAR(50)  NOT NULL,
    "text" TEXT  NOT NULL,
    "publishedAtDate" TIMESTAMPTZ  NOT NULL,
    "reviewUrl" TEXT  NOT NULL,
    "reviewImageUrls" JSONB,
    "likesCount" INT DEFAULT 0  NOT NULL,
    "totalScore" FLOAT  DEFAULT 0.0  NOT NULL,
    "stars" INT  DEFAULT 0  NOT NULL,
    "responseFromOwnerDate" TIMESTAMPTZ,
    "responseFromOwnerText" TEXT,
    "scrapedAt" TIMESTAMPTZ  NOT NULL,
    "owner_reply_recheck" bool  NOT NULL,
    "owner_reply_recheck_at" TIMESTAMPTZ,
    "next_check_at" TIMESTAMPTZ,
    CONSTRAINT "pk_review" PRIMARY KEY (
        "reviewId"
    )
);

CREATE TABLE "ai_analysis" (
    "reviewId" VARCHAR(100)  NOT NULL,
    "placeId" VARCHAR(100)  NOT NULL,
    "review_text" TEXT  NOT NULL,
    "review_summary" TEXT  NOT NULL,
    "review_sentiment" VARCHAR(20)  NOT NULL,
    "review_score" INT DEFAULT 0  NOT NULL,
    "owner_text" TEXT  NOT NULL,
    "owner_summary" TEXT  NOT NULL,
    "owner_sentiment" VARCHAR(20)  NOT NULL,
    "owner_score" INT DEFAULT 0  NOT NULL,
    "pr_reply" TEXT,
    "request_json" JSONB  NOT NULL,
    "response_json" JSONB,
    CONSTRAINT "pk_ai_analysis" PRIMARY KEY (
        "reviewId"
    )
);

CREATE TABLE "threads_log" (
    "id" VARCHAR(100)  NOT NULL,
    "text" TEXT,
    "media_type" VARCHAR(20)  NOT NULL,
    "media_url" TEXT,
    "timestamp" TIMESTAMPTZ  NOT NULL,
    "permalink" TEXT  NOT NULL,
    CONSTRAINT "pk_threads_log" PRIMARY KEY (
        "id"
    )
);

CREATE TABLE "execution_log" (
    "id" SERIAL,
    "pipeline" VARCHAR(200)  NOT NULL,
    "status" VARCHAR(20)  NOT NULL,
    "items_count" INT DEFAULT 0  NOT NULL,
    "apify_scheduler_id" VARCHAR(20),
    "actor_name" VARCHAR(100),
    "start_at" TIMESTAMPTZ DEFAULT NOW()  NOT NULL,
    "finished_at" TIMESTAMPTZ,
    "request_json" JSONB,
    "response_json" JSONB,
    "error_msg" TEXT,
    "retry_count" INT DEFAULT 0  NOT NULL,
    CONSTRAINT "pk_execution_log" PRIMARY KEY (
        "id"
    )
);

ALTER TABLE "review" ADD CONSTRAINT "fk_review_placeId" FOREIGN KEY("placeId")
REFERENCES "store" ("placeId");

ALTER TABLE "ai_analysis" ADD CONSTRAINT "fk_ai_analysis_reviewId" FOREIGN KEY("reviewId")
REFERENCES "review" ("reviewId");

ALTER TABLE "ai_analysis" ADD CONSTRAINT "fk_ai_analysis_placeId" FOREIGN KEY("placeId")
REFERENCES "store" ("placeId");