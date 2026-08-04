"""CLI: Review pipeline — 只讀 store、寫 review_source / review / execution_log。"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path

from domains.review.logging_setup import get_logger
from domains.review.service import (
    ingest_raw_reviews,
    run_daily_fetch,
    run_initial_fetch,
    run_owner_reply_recheck,
    run_review_pipeline,
)

log = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review Domain: DB store → Apify → review_source / review",
    )
    parser.add_argument(
        "--mode",
        choices=["manual", "initial", "daily", "recheck", "clear-store"],
        default="manual",
        help=(
            "manual=單次; initial=1★+2★+50; daily=昨天增量;"
            " recheck=補老闆回覆; clear-store=清空 store/review 假資料"
        ),
    )
    parser.add_argument(
        "--place-id",
        action="append",
        dest="place_ids",
        default=None,
        help="Google placeId（manual，可重複）",
    )
    parser.add_argument(
        "--store-limit",
        type=int,
        default=20,
        help="從 store 讀取上限（skip_review_fetch=TRUE 的店不會出現）",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=5,
        help="manual：Apify maxReviews",
    )
    parser.add_argument(
        "--reviews-sort",
        default="newest",
        choices=["newest", "highestRating", "lowestRating", "mostRelevant"],
    )
    parser.add_argument(
        "--reviews-start-date",
        default=None,
        help="manual：reviewsStartDate YYYY-MM-DD（daily 模式自動用昨天）",
    )
    parser.add_argument(
        "--from-json",
        type=Path,
        default=None,
        help="跳過 Apify，用本地 JSON 測 ETL（placeId 必須已在 store）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只組參數 / 轉換，不呼叫 Apify、不寫 DB",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="DEBUG logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verbose:
        logging.getLogger("domains.review").setLevel(logging.DEBUG)

    try:
        if args.mode == "clear-store":
            from domains.review.repository import clear_all_store_and_review_data

            counts = clear_all_store_and_review_data()
            result = {"mode": "clear-store", "deleted": counts}

        elif args.from_json is not None:
            raw_items = json.loads(args.from_json.read_text(encoding="utf-8"))
            if not isinstance(raw_items, list):
                raise ValueError("--from-json must contain a JSON array")

            if args.dry_run:
                from domains.review.etl import transform_raw_reviews

                _, _, stats = transform_raw_reviews(raw_items)
                result = {"mode": "from_json", "dry_run": True, "etl": stats}
            else:
                from domains.review.repository import filter_existing_place_ids

                needed = sorted(
                    {
                        str(item.get("placeId"))
                        for item in raw_items
                        if isinstance(item, dict) and item.get("placeId")
                    }
                )
                existing = set(filter_existing_place_ids(needed))
                missing = [pid for pid in needed if pid not in existing]
                if missing:
                    raise RuntimeError(
                        "JSON placeId 不在 store（或 skip_review_fetch=TRUE），"
                        f"無法寫 review（FK）。缺少: {missing}"
                    )
                result = {"mode": "from_json", "etl": ingest_raw_reviews(raw_items)}

        elif args.mode == "initial":
            result = run_initial_fetch(
                store_limit=args.store_limit,
                dry_run=args.dry_run,
            )
        elif args.mode == "daily":
            result = run_daily_fetch(
                store_limit=args.store_limit,
                dry_run=args.dry_run,
            )
        elif args.mode == "recheck":
            result = run_owner_reply_recheck(
                limit=args.store_limit,
                dry_run=args.dry_run,
            )
        else:
            result = run_review_pipeline(
                place_ids=args.place_ids,
                mode="manual",
                store_limit=args.store_limit,
                max_reviews=args.max_reviews,
                reviews_sort=args.reviews_sort,
                reviews_start_date=args.reviews_start_date,
                dry_run=args.dry_run,
            )
    except Exception as exc:
        log.error("pipeline failed: %s\n%s", exc, traceback.format_exc())
        print(f"[review] pipeline failed: {exc}", file=sys.stderr)
        return 1

    print("[review] pipeline finished")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
