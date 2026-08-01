"""CLI entrypoint for the Review domain pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from domains.review.service import (
    ingest_raw_reviews,
    run_daily_fetch,
    run_initial_fetch,
    run_review_pipeline,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review Domain: Apify → review_source → ETL → review",
    )
    parser.add_argument(
        "--mode",
        choices=["manual", "initial", "daily"],
        default="manual",
        help="manual=單次測試; initial=第一次全量; daily=每日增量",
    )
    parser.add_argument(
        "--place-id",
        action="append",
        dest="place_ids",
        default=None,
        help="Google placeId（manual 模式，可重複）",
    )
    parser.add_argument(
        "--store-limit",
        type=int,
        default=20,
        help="從 store 讀取的上限",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=5,
        help="manual 模式：每家店 Apify 上限",
    )
    parser.add_argument(
        "--reviews-sort",
        default="newest",
        choices=["newest", "highestRating", "lowestRating", "mostRelevant"],
    )
    parser.add_argument(
        "--from-json",
        type=Path,
        default=None,
        help="跳過 Apify，用本地 JSON 測 ETL",
    )
    parser.add_argument(
        "--mock",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="使用假資料模擬 Apify（需明確加 --mock；預設關閉）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只抓/只轉換，不寫 DB",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.from_json is not None:
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
                missing = [pid for pid in needed if pid not in set(filter_existing_place_ids(needed))]
                if missing:
                    raise RuntimeError(
                        "JSON placeId 不在 store，無法寫 review（FK）。"
                        "請先: uv run python -m domains.review.ensure_test_store"
                        f" 缺少: {missing}"
                    )
                result = {"mode": "from_json", "etl": ingest_raw_reviews(raw_items)}

        elif args.mode == "initial":
            result = run_initial_fetch(
                store_limit=args.store_limit,
                dry_run=args.dry_run,
                use_mock=args.mock,
            )
        elif args.mode == "daily":
            result = run_daily_fetch(
                store_limit=args.store_limit,
                dry_run=args.dry_run,
                use_mock=args.mock,
            )
        else:
            result = run_review_pipeline(
                place_ids=args.place_ids,
                mode="manual",
                store_limit=args.store_limit,
                max_reviews=args.max_reviews,
                reviews_sort=args.reviews_sort,
                dry_run=args.dry_run,
                use_mock=args.mock,
            )
    except Exception as exc:
        print(f"[review] pipeline failed: {exc}", file=sys.stderr)
        return 1

    print("[review] pipeline finished")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
