"""Backward-compatible smoke test. Prefer:

    uv run python -m domains.review.run_pipeline --mode manual --place-id <ID>
"""

from __future__ import annotations

import json

from domains.review.service import run_review_pipeline


def main() -> None:
    result = run_review_pipeline(
        place_ids=["ChIJi67FDQCrQjQRNnqJst4-2C8"],
        max_reviews=5,
        dry_run=True,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
