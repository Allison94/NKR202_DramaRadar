"""Backward-compatible smoke test for Review scraping.

Prefer the full pipeline:

    uv run python -m domains.review.run_pipeline --place-id <PLACE_ID>
"""

from __future__ import annotations

from domains.review.service import run_review_pipeline


def main() -> None:
    result = run_review_pipeline(
        place_ids=["ChIJi67FDQCrQjQRNnqJst4-2C8"],
        max_reviews=5,
        dry_run=False,
    )

    print("place_id_source:", result["place_id_source"])
    print("place_ids:", result["place_ids"])
    print("apify:", result.get("apify"))
    print("etl:", result.get("etl"))


if __name__ == "__main__":
    main()
